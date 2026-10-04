"""Correctness and reporting contracts for the bounded query benchmarks."""

import hashlib
import json
import subprocess
import sys

import pytest

from experiments import benchmark_queries as benchmark


@pytest.mark.parametrize(
    "topology, size, operation, expected_nodes",
    [
        ("chain", 8, "ancestors", list(range(7))),
        ("overlapping_roots", 8, "ancestors", list(range(7))),
        ("overlapping_roots", 8, "root_family", list(range(8))),
        ("disjoint_components", 8, "component", list(range(8))),
        ("dense_scc", 3, "cyclic_nodes", [0, 1, 2]),
    ],
)
def test_workers_match_hand_calculated_selections(
    topology, size, operation, expected_nodes
):
    case = {"topology": topology, "size": size, "query": operation}
    expected_hash = hashlib.sha256(
        json.dumps(expected_nodes, separators=(",", ":")).encode()
    ).hexdigest()
    baseline = benchmark.run_worker(case, "baseline")
    optimized = benchmark.run_worker(case, "optimized")

    for run in (baseline, optimized):
        assert run["selected_nodes"] == len(expected_nodes)
        assert run["selected_nodes_sha256"] == expected_hash
        assert run["input"]["nodes"] == size
        assert run["peak_rss_bytes"] > 0
    assert baseline["input"] == optimized["input"]


def test_suite_has_deterministic_topologies_and_bounded_dense_cycles():
    cases = benchmark.benchmark_cases((8, 16), (3, 4))

    assert len(cases) == 10
    assert len({(c["topology"], c["size"], c["query"]) for c in cases}) == 10
    assert {c["query"] for c in cases} == {
        "ancestors",
        "root_family",
        "component",
        "cyclic_nodes",
    }
    for case in cases:
        graph, seeds = benchmark.build_case(case["topology"], case["size"])
        repeated, repeated_seeds = benchmark.build_case(case["topology"], case["size"])
        assert list(graph.edges) == list(repeated.edges)
        assert seeds == repeated_seeds
    with pytest.raises(ValueError, match="between 2 and 8"):
        benchmark.benchmark_cases((8,), (9,))
    with pytest.raises(ValueError, match="between 4 and 2048"):
        benchmark.benchmark_cases((2049,), (3,))
    with pytest.raises(ValueError, match="unique"):
        benchmark.benchmark_cases((8, 8), (3,))


def test_one_warmup_and_collection_are_outside_the_timed_query(monkeypatch):
    events = []
    times = iter([10.0, 12.0])

    def query(graph, seeds, operation):
        events.append("query")
        return {0, 1}

    def clock():
        events.append("clock")
        return next(times)

    monkeypatch.setattr(benchmark, "_optimized", query)
    monkeypatch.setattr(benchmark.gc, "collect", lambda: events.append("collect"))
    monkeypatch.setattr(benchmark, "perf_counter", clock)

    run = benchmark.run_worker(
        {"topology": "chain", "size": 8, "query": "ancestors"}, "optimized"
    )

    assert events == ["query", "collect", "clock", "query", "clock"]
    assert run["wall_seconds"] == 2.0


def fake_run(method, seconds):
    return {
        "method": method,
        "input": {"sha256": "same-input", "nodes": 2, "edges": 1},
        "selected_nodes": 2,
        "selected_nodes_sha256": "same-selection",
        "wall_seconds": seconds,
        "peak_rss_bytes": 1024,
    }


def test_summary_uses_medians_and_retains_individual_runs():
    case = {"topology": "chain", "size": 8, "query": "ancestors"}
    runs = [
        fake_run("baseline", 9.0),
        fake_run("baseline", 3.0),
        fake_run("baseline", 6.0),
        fake_run("optimized", 4.0),
        fake_run("optimized", 1.0),
        fake_run("optimized", 2.0),
    ]
    summary = benchmark.summarize_case(case, runs)

    assert summary["summary"]["baseline"]["wall_seconds"] == {
        "median": 6.0,
        "minimum": 3.0,
        "maximum": 9.0,
    }
    assert summary["speedup_baseline_over_optimized"] == 3.0
    assert summary["runs"] == runs
    assert summary["parity_verified"] is True


@pytest.mark.parametrize(
    "field, different",
    [
        ("input", {"sha256": "different-input", "nodes": 2, "edges": 1}),
        ("selected_nodes", 1),
        ("selected_nodes_sha256", "different-selection"),
    ],
)
def test_parity_failure_cannot_produce_a_speedup(field, different):
    runs = [fake_run("baseline", 2.0), fake_run("optimized", 1.0)]
    runs[1][field] = different

    with pytest.raises(ValueError, match="parity failed"):
        benchmark.summarize_case({}, runs)


def test_peak_rss_units_are_explicit(monkeypatch):
    import resource
    from types import SimpleNamespace

    monkeypatch.setattr(resource, "getrusage", lambda _: SimpleNamespace(ru_maxrss=123))
    monkeypatch.setattr(benchmark.sys, "platform", "linux")
    assert benchmark.peak_rss_bytes() == 123 * 1024
    monkeypatch.setattr(benchmark.sys, "platform", "darwin")
    assert benchmark.peak_rss_bytes() == 123
    monkeypatch.setattr(benchmark.sys, "platform", "win32")
    with pytest.raises(RuntimeError, match="Linux and macOS only"):
        benchmark.peak_rss_bytes()


def test_worker_timeout_is_a_clear_failure(monkeypatch):
    def time_out(command, **kwargs):
        assert kwargs["timeout"] == benchmark.WORKER_TIMEOUT_SECONDS
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(benchmark.subprocess, "run", time_out)
    with pytest.raises(RuntimeError, match="worker timeout"):
        benchmark._launch_worker(
            {"topology": "chain", "size": 8, "query": "ancestors"}, "baseline"
        )


def test_suite_alternates_method_order_and_records_measurement_scope(monkeypatch):
    invocations = []

    def worker(case, method):
        invocations.append((case.copy(), method))
        return fake_run(method, 2.0 if method == "baseline" else 1.0)

    monkeypatch.setattr(benchmark, "_launch_worker", worker)
    report = benchmark.run_suite(sizes=(8,), cycle_sizes=(3,), repeats=2)

    assert len(invocations) == 20
    assert [method for _, method in invocations[:4]] == [
        "baseline",
        "optimized",
        "optimized",
        "baseline",
    ]
    assert len(report["cases"]) == 5
    assert report["parameters"]["repeats"] == 2
    assert report["parameters"]["warmup_queries_per_worker"] == 1
    assert set(report["implementation_sha256"]) == {
        "benchmark_queries.py",
        "queries.py",
    }
    assert (
        "not incremental query memory" in report["measurement_scope"]["peak_rss_bytes"]
    )
    assert "warmup" in report["measurement_scope"]["peak_rss_bytes"]
    assert "materialization" in report["measurement_scope"]["wall_seconds"]
    assert {run["repetition"] for run in report["cases"][0]["runs"]} == {1, 2}


def test_cli_runs_small_suite_and_never_replaces_existing_output(tmp_path):
    output = tmp_path / "nested" / "benchmark.json"
    command = [
        sys.executable,
        "-m",
        "experiments.benchmark_queries",
        "--output",
        str(output),
        "--sizes",
        "8",
        "--cycle-sizes",
        "3",
        "--repeats",
        "1",
    ]

    completed = subprocess.run(
        command, capture_output=True, text=True, check=False, timeout=60
    )

    assert completed.returncode == 0, completed.stderr
    original = output.read_bytes()
    report = json.loads(original)
    assert len(report["cases"]) == 5
    assert all(case["parity_verified"] for case in report["cases"])
    assert all(len(case["runs"]) == 2 for case in report["cases"])
    assert "5 verified comparisons" in completed.stdout
    assert "Verified" in completed.stderr

    failed = subprocess.run(command, capture_output=True, text=True, check=False)

    assert failed.returncode == 1
    assert "Output already exists" in failed.stderr
    assert "Traceback" not in failed.stderr
    assert output.read_bytes() == original
