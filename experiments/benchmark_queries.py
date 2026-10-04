"""Reproducible, bounded comparisons for Polyphasia graph queries.

Run from the checkout with ``python -m experiments.benchmark_queries --output
data/processed/query-benchmark.json``. Each method/repetition runs in a fresh
process with one untimed warmup followed by garbage collection. Query timing
excludes graph construction, warmup, collection, and fingerprinting; process
peak RSS includes the interpreter, imports, graph, warmup, query, and validation.
"""

import argparse
import gc
import hashlib
import json
import math
import platform
import statistics
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

import networkx as nx

from polyphasia import queries

CASE_QUERIES = {
    "chain": ("ancestors",),
    "overlapping_roots": ("ancestors", "root_family"),
    "disjoint_components": ("component",),
    "dense_scc": ("cyclic_nodes",),
}
DEFAULT_SIZES = (128, 256, 512)
DEFAULT_CYCLE_SIZES = (6, 7, 8)
WORKER_TIMEOUT_SECONDS = 20


def _fingerprint(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def build_case(topology: str, size: int) -> tuple[nx.Graph, set[int]]:
    """Construct deterministic inputs with integer labels and no random sampling.

    ``size`` is always the total node count. The overlapping-root DAG contains
    size//4 roots pointing at a common chain; disjoint components are four paths.
    Dense SCC inputs are complete directed graphs, including a self-loop at 0.
    """
    if topology not in CASE_QUERIES:
        raise ValueError(f"Unknown topology: {topology}")
    minimum, maximum = (2, 8) if topology == "dense_scc" else (4, 2048)
    if not minimum <= size <= maximum:
        raise ValueError(f"{topology} size must be between {minimum} and {maximum}")
    if topology == "chain":
        graph = nx.path_graph(size, create_using=nx.DiGraph)
        seeds = set(range(size // 2, size, 2))
    elif topology == "overlapping_roots":
        graph = nx.DiGraph()
        graph.add_nodes_from(range(size))
        root_count = max(2, size // 4)
        graph.add_edges_from((node, root_count) for node in range(root_count))
        graph.add_edges_from((node, node + 1) for node in range(root_count, size - 1))
        seeds = set(range(max(root_count, size // 2), size, 2))
    elif topology == "disjoint_components":
        graph = nx.Graph()
        graph.add_nodes_from(range(size))
        seeds = set()
        for component in range(4):
            start, stop = component * size // 4, (component + 1) * size // 4
            graph.add_edges_from((node, node + 1) for node in range(start, stop - 1))
            seeds.update(range(start, stop, 2))
    else:
        graph = nx.complete_graph(size, create_using=nx.DiGraph)
        graph.add_edge(0, 0)
        seeds = set()
    return graph, seeds


def benchmark_cases(
    sizes: tuple[int, ...], cycle_sizes: tuple[int, ...]
) -> list[dict[str, Any]]:
    """Expand the fixed suite, validating bounds before launching any workers."""
    if not sizes or not cycle_sizes:
        raise ValueError("At least one main size and one cycle size are required")
    if len(set(sizes)) != len(sizes) or len(set(cycle_sizes)) != len(cycle_sizes):
        raise ValueError("Benchmark sizes must be unique")
    cases = []
    for topology, operations in CASE_QUERIES.items():
        for size in cycle_sizes if topology == "dense_scc" else sizes:
            build_case(topology, size)
            for operation in operations:
                cases.append({"topology": topology, "size": size, "query": operation})
    return cases


def _baseline(graph: nx.Graph, seeds: set[int], operation: str) -> set[int]:
    if operation == "ancestors":
        selected = set(seeds)
        for seed in sorted(seeds):
            selected.update(nx.ancestors(graph, seed))
        return selected
    if operation == "root_family":
        selected = set()
        for root, degree in graph.in_degree():
            if degree == 0:
                family = {root} | nx.descendants(graph, root)
                if family & seeds:
                    selected.update(family)
        return selected
    if operation == "component":
        # Preserve the original repeated-BFS/list accumulation workload; a set
        # is constructed only after all matching seed traversals are complete.
        repeated_nodes = []
        for seed in sorted(seeds):
            repeated_nodes.extend(nx.bfs_tree(graph, seed))
        return set(repeated_nodes)
    if operation == "cyclic_nodes":
        return {node for cycle in nx.simple_cycles(graph) for node in cycle}
    raise ValueError(f"Unknown query: {operation}")


def _optimized(graph: nx.Graph, seeds: set[int], operation: str) -> set[int]:
    if operation == "ancestors":
        return set(queries.ancestor_subgraph(graph, seeds))
    if operation == "root_family":
        return set(queries.root_family_subgraph(graph, seeds))
    if operation == "component":
        return set(queries.component_subgraph(graph, seeds))
    if operation == "cyclic_nodes":
        return set(queries.cyclic_nodes(graph))
    raise ValueError(f"Unknown query: {operation}")


def peak_rss_bytes() -> int:
    """Normalize getrusage's process high-water RSS on Linux and macOS only."""
    if sys.platform not in {"linux", "darwin"}:
        raise RuntimeError("Peak RSS measurement supports Linux and macOS only")
    import resource

    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(rss if sys.platform == "darwin" else rss * 1024)


def run_worker(case: dict[str, Any], method: str) -> dict[str, Any]:
    """Measure one operation; use the CLI worker for isolated RSS measurements."""
    if method not in {"baseline", "optimized"}:
        raise ValueError("method must be 'baseline' or 'optimized'")
    topology, size, operation = case["topology"], case["size"], case["query"]
    graph, seeds = build_case(topology, size)
    if operation not in CASE_QUERIES[topology]:
        raise ValueError(f"Query {operation} is not part of topology {topology}")
    input_summary = {
        "directed": graph.is_directed(),
        "nodes": graph.number_of_nodes(),
        "edges": graph.number_of_edges(),
        "seeds": len(seeds),
        "sha256": _fingerprint(
            {
                "directed": graph.is_directed(),
                "nodes": sorted(graph),
                "edges": sorted(graph.edges()),
                "seeds": sorted(seeds),
            }
        ),
    }
    query = _baseline if method == "baseline" else _optimized
    query(graph, seeds, operation)
    gc.collect()
    started = perf_counter()
    selected = query(graph, seeds, operation)
    elapsed = perf_counter() - started
    # Keep fingerprinting outside the timer. It remains part of process peak RSS.
    result = {
        "method": method,
        "input": input_summary,
        "selected_nodes": len(selected),
        "selected_nodes_sha256": _fingerprint(sorted(selected)),
        "wall_seconds": elapsed,
    }
    result["peak_rss_bytes"] = peak_rss_bytes()
    return result


def _launch_worker(case: dict[str, Any], method: str) -> dict[str, Any]:
    payload = json.dumps({"case": case, "method": method})
    try:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "experiments.benchmark_queries",
                "--worker",
                payload,
            ],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
            check=False,
            timeout=WORKER_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"{case} {method} exceeded the {WORKER_TIMEOUT_SECONDS}s worker timeout"
        ) from exc
    if completed.returncode:
        raise RuntimeError(f"{case} {method} failed: {completed.stderr.strip()}")
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{case} {method} returned invalid worker output") from exc


def _statistics(values: list[float | int]) -> dict[str, float | int]:
    return {
        "median": statistics.median(values),
        "minimum": min(values),
        "maximum": max(values),
    }


def summarize_case(case: dict[str, Any], runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Reject parity failures before computing any performance comparisons."""
    if not runs or {run["method"] for run in runs} != {"baseline", "optimized"}:
        raise ValueError("Both baseline and optimized runs are required")
    reference = runs[0]
    for run in runs:
        if any(
            run[field] != reference[field]
            for field in ("input", "selected_nodes", "selected_nodes_sha256")
        ):
            raise ValueError(f"Input/result parity failed for {case}")
        if not math.isfinite(run["wall_seconds"]) or run["wall_seconds"] <= 0:
            raise ValueError(f"Invalid wall time for {case}")
        if run["peak_rss_bytes"] <= 0:
            raise ValueError(f"Invalid peak RSS for {case}")
    summaries = {}
    for method in ("baseline", "optimized"):
        method_runs = [run for run in runs if run["method"] == method]
        summaries[method] = {
            field: _statistics([run[field] for run in method_runs])
            for field in ("wall_seconds", "peak_rss_bytes")
        }
    return {
        **case,
        "input": reference["input"],
        "selected_nodes": reference["selected_nodes"],
        "selected_nodes_sha256": reference["selected_nodes_sha256"],
        "parity_verified": True,
        "summary": summaries,
        "speedup_baseline_over_optimized": (
            summaries["baseline"]["wall_seconds"]["median"]
            / summaries["optimized"]["wall_seconds"]["median"]
        ),
        "runs": runs,
    }


def run_suite(
    *,
    sizes: tuple[int, ...] = DEFAULT_SIZES,
    cycle_sizes: tuple[int, ...] = DEFAULT_CYCLE_SIZES,
    repeats: int = 3,
) -> dict[str, Any]:
    if not 1 <= repeats <= 10:
        raise ValueError("repeats must be between 1 and 10")
    peak_rss_bytes()  # Reject unsupported hosts before launching any workers.
    cases = benchmark_cases(sizes, cycle_sizes)
    source_paths = {
        "benchmark_queries.py": Path(__file__),
        "queries.py": Path(queries.__file__),
    }
    implementation_hashes = {
        name: hashlib.sha256(path.read_bytes()).hexdigest()
        for name, path in source_paths.items()
    }
    results = []
    for case in cases:
        runs = []
        for repetition in range(1, repeats + 1):
            methods = (
                ("baseline", "optimized")
                if repetition % 2
                else ("optimized", "baseline")
            )
            for method in methods:
                run = _launch_worker(case, method)
                runs.append({"repetition": repetition, **run})
        results.append(summarize_case(case, runs))
        print(
            f"Verified {case['topology']} n={case['size']} {case['query']}",
            file=sys.stderr,
            flush=True,
        )
    if any(
        hashlib.sha256(source_paths[name].read_bytes()).hexdigest() != digest
        for name, digest in implementation_hashes.items()
    ):
        raise RuntimeError("Benchmark implementation changed during the run")
    return {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "python": platform.python_version(),
            "networkx": nx.__version__,
            "platform": platform.platform(),
            "machine": platform.machine(),
        },
        "implementation_sha256": implementation_hashes,
        "parameters": {
            "sizes": list(sizes),
            "cycle_sizes": list(cycle_sizes),
            "repeats": repeats,
            "warmup_queries_per_worker": 1,
            "worker_timeout_seconds": WORKER_TIMEOUT_SECONDS,
        },
        "measurement_scope": {
            "wall_seconds": (
                "perf_counter around one query including materialization of its "
                "selected-node set; excludes graph construction, input/result "
                "fingerprints, subprocess startup, one untimed query warmup "
                "and the garbage collection immediately following that warmup"
            ),
            "peak_rss_bytes": (
                "fresh worker process high-water RSS including interpreter, "
                "imports, input construction, warmup, query and fingerprint validation; "
                "not incremental query memory; macOS bytes, Linux KiB converted "
                "to bytes; no tracemalloc"
            ),
            "aggregation": (
                "median/minimum/maximum of independent processes; methods "
                "alternate order per repetition; all individual runs retained"
            ),
            "parity": (
                "every run must match graph+seed SHA-256, selected-node count "
                "and selected-set SHA-256 before speedup is emitted"
            ),
            "interpretation": (
                "bounded synthetic workloads, not full-dataset performance; "
                "times are sensitive to host load; one warmup reduces lazy "
                "initialization effects but does not eliminate measurement noise"
            ),
        },
        "cases": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="New JSON output file")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--sizes", type=int, nargs="+", default=DEFAULT_SIZES)
    parser.add_argument(
        "--cycle-sizes", type=int, nargs="+", default=DEFAULT_CYCLE_SIZES
    )
    parser.add_argument("--worker", help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        if args.worker is not None:
            payload = json.loads(args.worker)
            print(json.dumps(run_worker(payload["case"], payload["method"])))
            return
        if args.output is None:
            parser.error("--output is required")
        if args.output.exists():
            raise FileExistsError(f"Output already exists: {args.output}")
        report = run_suite(
            sizes=tuple(args.sizes),
            cycle_sizes=tuple(args.cycle_sizes),
            repeats=args.repeats,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
        print(f"Saved {len(report['cases'])} verified comparisons to {args.output}")
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(1, f"Benchmark failed: {exc}\n")


if __name__ == "__main__":
    main()
