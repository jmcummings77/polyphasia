"""Render portfolio figures from verified, previously computed reports.

Run ``python -m scripts.build_portfolio_figures --analysis reports/20130208
--benchmark reports/benchmarks/query-benchmark.json --output NEW_DIRECTORY``.
No corpus analysis or performance measurements are rerun by this renderer.
"""

import argparse
import hashlib
import json
import math
import platform
import sys
from pathlib import Path
from typing import Any

# These source-only scripts/experiments are intentionally absent from the wheel.
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

BLUE, ORANGE, INK = "#245b78", "#bd622c", "#223642"
FIGURE_NAMES = (
    "transformation-attrition.png",
    "projection-comparison.png",
    "runtime-memory-scaling.png",
)
DISPLAY_QUERIES = ("ancestors", "root_families", "components")


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def validate_benchmark(report: dict[str, Any]) -> None:
    """Check case identities and saved comparisons against their measured code.

    Historical reports require the recorded builder/query sources. Reconstructing
    these bounded inputs and selections validates their labels without timing
    queries, launching workers, or executing the exhaustive baseline.
    """
    from experiments import benchmark_queries as benchmark

    if report.get("schema_version") != 1:
        raise ValueError("Unsupported benchmark schema")
    implementation_hashes = {
        "benchmark_queries.py": _sha256(Path(benchmark.__file__)),
        "queries.py": _sha256(Path(benchmark.queries.__file__)),
    }
    if report.get("implementation_sha256") != implementation_hashes:
        raise ValueError(
            "Benchmark validation requires its recorded implementation sources"
        )
    parameters = report["parameters"]
    if parameters["sizes"] != [128, 256, 512] or parameters["repeats"] != 3:
        raise ValueError("Figures require sizes 128/256/512 and three repetitions")
    if (
        parameters["cycle_sizes"] != [6, 7, 8]
        or parameters.get("warmup_queries_per_worker") != 1
    ):
        raise ValueError("Figures require cycle sizes 6/7/8 and one warmup per worker")
    expected = benchmark.benchmark_cases(
        tuple(parameters["sizes"]), tuple(parameters["cycle_sizes"])
    )
    identities = {(c["topology"], c["size"], c["query"]) for c in expected}
    cases = report["cases"]
    if (
        len(cases) != len(expected)
        or {(c["topology"], c["size"], c["query"]) for c in cases} != identities
    ):
        raise ValueError("Benchmark case coverage is incomplete or duplicated")
    for case in cases:
        runs = case["runs"]
        if len(runs) != 6 or {(r["method"], r["repetition"]) for r in runs} != {
            (method, repetition)
            for method in ("baseline", "optimized")
            for repetition in (1, 2, 3)
        }:
            raise ValueError("Benchmark repetition coverage is invalid")
        if any(not math.isfinite(r["peak_rss_bytes"]) for r in runs):
            raise ValueError("Benchmark RSS must be finite")
        identity = {key: case[key] for key in ("topology", "size", "query")}
        if benchmark.summarize_case(identity, runs) != case:
            raise ValueError("Benchmark summary disagrees with its recorded runs")
        graph, seeds = benchmark.build_case(case["topology"], case["size"])
        expected_input = {
            "directed": graph.is_directed(),
            "nodes": graph.number_of_nodes(),
            "edges": graph.number_of_edges(),
            "seeds": len(seeds),
            "sha256": benchmark._fingerprint(
                {
                    "directed": graph.is_directed(),
                    "nodes": sorted(graph),
                    "edges": sorted(graph.edges()),
                    "seeds": sorted(seeds),
                }
            ),
        }
        if case["input"] != expected_input:
            raise ValueError(
                "Benchmark input disagrees with its declared topology and size"
            )
        selected = benchmark._optimized(graph, seeds, case["query"])
        if case["selected_nodes"] != len(selected) or case[
            "selected_nodes_sha256"
        ] != benchmark._fingerprint(sorted(selected)):
            raise ValueError("Benchmark selection disagrees with its declared query")


def validate_accounting(audit: dict[str, Any], analysis: dict[str, Any]) -> None:
    """Check the record, seed, selection, and overlap denominators used in plots."""
    total = audit["input"]["assertions"]
    if total <= 0 or total != analysis["input"]["assertions"]:
        raise ValueError("Input assertion totals must agree and be positive")
    for policy in ("root_only", "normalized"):
        projection, audited = (
            analysis["projections"][policy],
            audit["projections"][policy],
        )
        retained, excluded = (
            audited["retained_assertions"],
            audited["excluded_assertions"],
        )
        if min(retained, excluded) < 0 or retained + excluded != total:
            raise ValueError(
                "Retained/excluded assertions do not conserve input records"
            )
        if (
            projection["seeds"] + projection["raw_language_nodes_excluded"]
            != analysis["input"]["raw_language_nodes"]
        ):
            raise ValueError(
                "Projected seeds do not reconcile with raw language labels"
            )
        queries = projection["queries"]
        for metrics in queries.values():
            if not (
                0
                <= metrics["seeds_included"]
                <= projection["seeds"]
                <= projection["nodes"]
            ):
                raise ValueError("Invalid seed denominator")
            if (
                not (0 <= metrics["nodes"] <= projection["nodes"])
                or sum(metrics["node_languages"].values()) != metrics["nodes"]
            ):
                raise ValueError("Query node/language counts do not reconcile")
        seen = set()
        for row in projection["overlaps"]:
            left, right = queries[row["left"]]["nodes"], queries[row["right"]]["nodes"]
            intersection = row["intersection_nodes"]
            union = left + right - intersection
            if not (0 <= intersection <= min(left, right)) or (
                row["union_nodes"],
                row["left_only_nodes"],
                row["right_only_nodes"],
                row["jaccard"],
            ) != (
                union,
                left - intersection,
                right - intersection,
                intersection / union if union else None,
            ):
                raise ValueError("Overlap accounting is inconsistent")
            seen.add(frozenset((row["left"], row["right"])))
        if len(seen) != 6 or len(projection["overlaps"]) != 6:
            raise ValueError("Six distinct pairwise overlaps are required")


def _figure(title: str, subtitle: str, height: float) -> Any:
    from matplotlib.figure import Figure

    figure = Figure(figsize=(10.8, height), facecolor="white")
    figure.text(0.045, 0.965, title, fontsize=18, fontweight="bold", va="top")
    figure.text(0.045, 0.91, subtitle, fontsize=10.5, va="top", color="#52656e")
    return figure


def _attrition(audit: dict[str, Any]) -> Any:
    from matplotlib.ticker import FuncFormatter

    total = audit["input"]["assertions"]
    figure = _figure(
        "Direction policy changes retained records",
        f"{total:,} original assertions · each input record is retained or excluded",
        4.6,
    )
    axis = figure.add_subplot()
    figure.subplots_adjust(left=0.20, right=0.96, top=0.77, bottom=0.25)
    for position, policy in enumerate(("root_only", "normalized")):
        data = audit["projections"][policy]
        retained, excluded = data["retained_assertions"], data["excluded_assertions"]
        axis.barh(
            position,
            retained,
            color=BLUE,
            height=0.52,
            label="Retained" if position == 0 else None,
        )
        axis.barh(
            position,
            excluded,
            left=retained,
            color=ORANGE,
            height=0.52,
            label="Excluded" if position == 0 else None,
        )
        for value, start in ((retained, 0), (excluded, retained)):
            if value:
                axis.text(
                    start + value / 2,
                    position,
                    f"{value:,}\n{value / total:.1%}",
                    ha="center",
                    va="center",
                    color="white",
                    fontsize=11,
                )
    axis.set_yticks(
        [0, 1], ["Forward only\nroot_only", "Direction normalized\nnormalized"]
    )
    axis.invert_yaxis()
    axis.set(xlim=(0, total), xlabel="Recorded assertions")
    axis.xaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:,.0f}"))
    figure.legend(
        *axis.get_legend_handles_labels(),
        loc="upper right",
        bbox_to_anchor=(0.965, 0.845),
        ncols=2,
        frameon=False,
    )
    figure.text(
        0.045,
        0.035,
        "Duplicates and reciprocal assertions remain separate records. Graph edges are not plotted.",
        fontsize=10,
        color="#52656e",
    )
    return figure


def _projection(analysis: dict[str, Any]) -> Any:
    from matplotlib.ticker import FuncFormatter

    normalized = analysis["projections"]["normalized"]
    queries, ancestors = (
        normalized["queries"],
        normalized["queries"]["ancestors"]["nodes"],
    )
    language = (
        "English"
        if analysis["parameters"]["language"] == "eng"
        else analysis["parameters"]["language"]
    )
    figure = _figure(
        "Query meaning changes the analytical population",
        f"Normalized policy · {normalized['seeds']:,} projected {language} seeds; {normalized['raw_language_nodes_excluded']:,} raw labels excluded",
        6.0,
    )
    axis = figure.add_subplot()
    figure.subplots_adjust(left=0.19, right=0.95, top=0.79, bottom=0.25)
    labels = ("Ancestors", "Root families", "Weak components")
    overlaps = {
        row["right"]: row
        for row in normalized["overlaps"]
        if row["left"] == "ancestors"
    }
    for position, query in enumerate(DISPLAY_QUERIES):
        common = (
            ancestors if query == "ancestors" else overlaps[query]["intersection_nodes"]
        )
        added = 0 if query == "ancestors" else overlaps[query]["right_only_nodes"]
        omitted = 0 if query == "ancestors" else overlaps[query]["left_only_nodes"]
        axis.barh(
            position,
            common,
            color=BLUE,
            height=0.43,
            label="Also in ancestry selection" if position == 0 else None,
        )
        axis.barh(
            position,
            added,
            left=common,
            color=ORANGE,
            height=0.43,
            label="Additional context" if position == 0 else None,
        )
        axis.text(
            queries[query]["nodes"] + queries["components"]["nodes"] * 0.018,
            position,
            f"{queries[query]['nodes']:,}",
            va="center",
            fontsize=12,
            fontweight="bold",
        )
        note = "Reference: seeds and all their recorded ancestors"
        if query != "ancestors":
            missing_seeds = normalized["seeds"] - queries[query]["seeds_included"]
            note = f"Adds {added:,} labels; omits {omitted:,} ancestors ({missing_seeds:,} {language} seeds)"
        axis.text(
            0,
            position + 0.34,
            note,
            fontsize=9.8,
            color=ORANGE if omitted else "#52656e",
            va="center",
        )
    axis.set_yticks(range(3), labels)
    axis.set(
        xlim=(0, queries["components"]["nodes"] * 1.19),
        ylim=(2.65, -0.45),
        xlabel="Distinct recorded node labels",
    )
    axis.xaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:,.0f}"))
    figure.legend(
        *axis.get_legend_handles_labels(),
        loc="upper right",
        bbox_to_anchor=(0.95, 0.865),
        ncols=2,
        frameon=False,
    )
    differences = [
        queries[q]["nodes"]
        - analysis["projections"]["root_only"]["queries"][q]["nodes"]
        for q in DISPLAY_QUERIES
    ]
    policy_note = (
        "Normalized minus root_only: "
        + ", ".join(
            f"{label.lower()} {delta:+,}" for label, delta in zip(labels, differences)
        )
        + " nodes."
    )
    if (
        differences == [1, 1, 1]
        and normalized["seeds"] == analysis["projections"]["root_only"]["seeds"]
    ):
        policy_note = "Normalized adds 1 node versus root_only in each shown selection; the seed count is unchanged."
    figure.text(0.045, 0.065, policy_note, fontsize=10, color="#52656e")
    figure.text(
        0.045,
        0.025,
        "Root-family selection can omit rootless cycles and their downstream nodes; broader context is not ancestry.",
        fontsize=10,
        color="#52656e",
    )
    return figure


def _scaling(benchmark: dict[str, Any]) -> Any:
    from matplotlib.ticker import FuncFormatter

    figure = _figure(
        "Shared traversal scales better on overlapping selections",
        "Synthetic graphs · 128 / 256 / 512 nodes · three independent workers per method and size",
        7.5,
    )
    axes = figure.subplots(2, 2, sharex="col", sharey="row")
    figure.subplots_adjust(
        left=0.085, right=0.97, top=0.79, bottom=0.22, hspace=0.30, wspace=0.22
    )
    memory_max = max(
        case["summary"][method]["peak_rss_bytes"]["maximum"] / 2**20
        for case in benchmark["cases"]
        if case["query"] in {"root_family", "component"}
        for method in ("baseline", "optimized")
    )
    for column, (query, title) in enumerate(
        (
            ("root_family", "Root families · overlapping-root DAG"),
            ("component", "Components · four disjoint paths"),
        )
    ):
        cases = sorted(
            (c for c in benchmark["cases"] if c["query"] == query),
            key=lambda c: c["size"],
        )
        sizes = [case["size"] for case in cases]
        axes[0, column].set_title(title, fontsize=11.5, pad=10)
        for method, color, marker, label in (
            ("baseline", ORANGE, "o", "Repeated traversal"),
            ("optimized", BLUE, "s", "Shared traversal"),
        ):
            for row, (metric, scale) in enumerate(
                (("wall_seconds", 1000), ("peak_rss_bytes", 1 / 2**20))
            ):
                statistics = [c["summary"][method][metric] for c in cases]
                medians = [s["median"] * scale for s in statistics]
                axis = axes[row, column]
                axis.plot(
                    sizes,
                    medians,
                    color=color,
                    marker=marker,
                    linewidth=2,
                    markersize=5,
                    label=label,
                )
                axis.fill_between(
                    sizes,
                    [s["minimum"] * scale for s in statistics],
                    [s["maximum"] * scale for s in statistics],
                    color=color,
                    alpha=0.16,
                )
                axis.set_xscale("log", base=2)
                axis.set_xticks(sizes)
                axis.xaxis.set_major_formatter(
                    FuncFormatter(lambda value, _: f"{value:,.0f}")
                )
                if row == 0:
                    axis.set_yscale("log")
                    axis.yaxis.set_major_formatter(
                        FuncFormatter(lambda value, _: f"{value:g}")
                    )
                    axis.annotate(
                        f"{medians[-1]:.3g} ms",
                        (sizes[-1], medians[-1]),
                        xytext=(-8, 9 if method == "baseline" else -17),
                        textcoords="offset points",
                        ha="right",
                        color=color,
                        fontsize=10,
                    )
        axes[1, column].set(
            ylim=(0, math.ceil(memory_max * 1.15 / 5) * 5),
            xlabel="Graph nodes (doubling scale)",
        )
        memory = cases[-1]["summary"]
        axes[1, column].text(
            0.03,
            0.94,
            f"512 nodes: repeated {memory['baseline']['peak_rss_bytes']['median'] / 2**20:.2f} · shared {memory['optimized']['peak_rss_bytes']['median'] / 2**20:.2f} MiB",
            transform=axes[1, column].transAxes,
            fontsize=9.5,
        )
    axes[0, 0].set_ylabel("Query time · ms (log scale)")
    axes[1, 0].set_ylabel("Whole-process peak RSS · MiB")
    axes[0, 0].legend(loc="upper left", frameon=False, fontsize=9)
    figure.text(
        0.045,
        0.12,
        "Lines: median; bands: min–max. One untimed warmup per worker; timing excludes construction and fingerprints.",
        fontsize=9.7,
        color="#52656e",
    )
    figure.text(
        0.045,
        0.085,
        "RSS includes interpreter, imports, graph, warmup and query; it is not incremental query memory.",
        fontsize=9.7,
        color="#52656e",
    )
    figure.text(
        0.045,
        0.05,
        "These bounded synthetic measurements are not full-corpus timings. All 15 benchmark cases remain in the source report.",
        fontsize=9.7,
        color="#52656e",
    )
    return figure


def build_figures(analysis: Path, benchmark: Path, output: Path) -> dict[str, Any]:
    """Validate persisted evidence, render PNGs, and write a deterministic manifest."""
    import matplotlib
    import matplotlib.ft2font
    import numpy
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    from polyphasia.analysis import validate_run

    analysis, benchmark, output = Path(analysis), Path(benchmark), Path(output)
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"Output directory already exists: {output}")
    validate_run(analysis)
    inputs = {
        name: analysis / name
        for name in ("manifest.json", "audit.json", "analysis.json")
    }
    inputs["query-benchmark.json"] = benchmark
    hashes = {name: _sha256(path) for name, path in inputs.items()}
    audit = json.loads(inputs["audit.json"].read_text(encoding="utf-8"))
    report = json.loads(inputs["analysis.json"].read_text(encoding="utf-8"))
    measurements = json.loads(benchmark.read_text(encoding="utf-8"))
    validate_accounting(audit, report)
    validate_benchmark(measurements)
    renderer_hash = _sha256(Path(__file__))
    output.mkdir(parents=True, exist_ok=False)
    with matplotlib.rc_context(matplotlib.rcParamsDefault):
        matplotlib.rcParams.update(
            {
                "font.family": "DejaVu Sans",
                "font.size": 10.5,
                "text.parse_math": False,
                "text.usetex": False,
                "text.color": INK,
                "axes.labelcolor": INK,
                "xtick.color": "#52656e",
                "ytick.color": INK,
                "axes.spines.top": False,
                "axes.spines.right": False,
                "axes.spines.left": False,
                "axes.axisbelow": True,
                "axes.grid": True,
                "grid.alpha": 0.18,
            }
        )
        for name, figure in zip(
            FIGURE_NAMES,
            (_attrition(audit), _projection(report), _scaling(measurements)),
            strict=True,
        ):
            FigureCanvasAgg(figure)
            figure.savefig(
                output / name,
                dpi=120,
                metadata={"Software": "polyphasia portfolio renderer"},
            )
            # Reset shared log scales before Matplotlib clears their limits.
            for axis in figure.axes:
                axis.set_xscale("linear")
                axis.set_yscale("linear")
            figure.clear()
    if hashes != {
        name: _sha256(path) for name, path in inputs.items()
    } or renderer_hash != _sha256(Path(__file__)):
        raise ValueError("Inputs or renderer changed during figure generation")
    manifest = {
        "schema_version": 1,
        "input_sha256": hashes,
        "renderer_sha256": renderer_hash,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "matplotlib": matplotlib.__version__,
            "numpy": numpy.__version__,
            "freetype": matplotlib.ft2font.__freetype_version__,
        },
        "artifacts": {
            name: {
                "sha256": _sha256(output / name),
                "bytes": (output / name).stat().st_size,
            }
            for name in FIGURE_NAMES
        },
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--benchmark", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        build_figures(args.analysis, args.benchmark, args.output)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f"Figure generation failed: {exc}\n")
    print(f"Saved three verified figures to {args.output}")


if __name__ == "__main__":
    main()
