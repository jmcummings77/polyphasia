"""Deterministic tables and static figures for an analysis report."""

import csv
from pathlib import Path
from typing import Any

QUERY_NAMES = {
    "ancestors": "Ancestors",
    "descendants": "Descendants",
    "root_families": "Root families",
    "components": "Weak components",
}


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_tables(report: dict[str, Any], output: Path) -> None:
    """Write scalar tables with explicit denominators and stable row ordering."""
    query_rows = []
    overlap_rows = []
    ranking_rows = []
    for policy, projection in report["projections"].items():
        for query, metrics in projection["queries"].items():
            query_rows.append(
                {
                    "policy": policy,
                    "query": query,
                    "nodes": metrics["nodes"],
                    "edges": metrics["edges"],
                    "seeds": projection["seeds"],
                    "seeds_included": metrics["seeds_included"],
                    "raw_language_nodes": report["input"]["raw_language_nodes"],
                    "raw_language_nodes_excluded": projection[
                        "raw_language_nodes_excluded"
                    ],
                }
            )
        for overlap in projection["overlaps"]:
            overlap_rows.append({"policy": policy, **overlap})
        for relation in ("word_origin", "derivation"):
            for direction in ("out_degree", "in_degree"):
                for rank, row in enumerate(
                    projection["rankings"][relation][direction], 1
                ):
                    ranking_rows.append(
                        {
                            "policy": policy,
                            "relation": relation,
                            "direction": direction,
                            "rank": rank,
                            **row,
                        }
                    )
    _write_csv(
        output / "queries.csv",
        [
            "policy",
            "query",
            "nodes",
            "edges",
            "seeds",
            "seeds_included",
            "raw_language_nodes",
            "raw_language_nodes_excluded",
        ],
        query_rows,
    )
    _write_csv(
        output / "overlaps.csv",
        [
            "policy",
            "left",
            "right",
            "intersection_nodes",
            "union_nodes",
            "left_only_nodes",
            "right_only_nodes",
            "jaccard",
        ],
        overlap_rows,
    )
    _write_csv(
        output / "rankings.csv",
        [
            "policy",
            "relation",
            "direction",
            "rank",
            "node",
            "language",
            "word",
            "neighbors",
            "affix_like",
        ],
        ranking_rows,
    )


def write_figures(audit: dict[str, Any], report: dict[str, Any], output: Path) -> None:
    """Render PNGs with fixed styles and no timestamp metadata.

    Matplotlib is an optional analysis dependency. Figures are deterministic
    within the recorded rendering environment, not guaranteed byte-identical
    across Matplotlib, FreeType, or platform versions.
    """
    import matplotlib
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from matplotlib.ticker import MaxNLocator

    directory = output / "figures"
    directory.mkdir()
    policies = list(report["projections"])
    colors = ["#245b78", "#c66a36"]

    def save(figure: Figure, name: str) -> None:
        FigureCanvasAgg(figure)
        figure.savefig(directory / name, dpi=150, metadata={"Software": "polyphasia"})
        figure.clear()

    with matplotlib.rc_context(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    ):
        figure = Figure(figsize=(8, 4), layout="constrained")
        ax = figure.subplots()
        retained = [audit["projections"][p]["retained_assertions"] for p in policies]
        excluded = [audit["projections"][p]["excluded_assertions"] for p in policies]
        ax.barh(policies, retained, label="Retained", color=colors[0])
        ax.barh(policies, excluded, left=retained, label="Excluded", color="#c5ced3")
        ax.set(
            xlabel="Recorded assertions (not independent evidence)",
            title="Relationship policies account for every input record",
        )
        ax.legend(loc="lower right")
        ax.xaxis.set_major_locator(MaxNLocator(nbins=5, integer=True))
        save(figure, "retention.png")

        figure = Figure(figsize=(9, 4), layout="constrained")
        ax = figure.subplots()
        width = 0.8 / len(policies)
        for index, policy in enumerate(policies):
            values = report["projections"][policy]["queries"]
            positions = [i - 0.4 + width / 2 + index * width for i in range(4)]
            ax.bar(
                positions,
                [values[q]["nodes"] for q in QUERY_NAMES],
                width,
                label=policy,
                color=colors[index % len(colors)],
            )
        ax.set_xticks(range(4), QUERY_NAMES.values())
        ax.set(
            ylabel="Distinct recorded node labels",
            title=f"{report['parameters']['language']} seeds: query semantics change context",
        )
        ax.legend()
        ax.yaxis.set_major_locator(MaxNLocator(nbins=5, integer=True))
        save(figure, "query-comparison.png")

        policy = "normalized" if "normalized" in policies else policies[0]
        figure = Figure(figsize=(10, 5), layout="constrained")
        axes = figure.subplots(1, 2)
        for axis, relation, title in zip(
            axes,
            ("word_origin", "derivation"),
            ("Word origin", "Derivation"),
            strict=True,
        ):
            rows = report["projections"][policy]["rankings"][relation]["out_degree"][:5]
            axis.barh(
                [r["node"] for r in rows],
                [r["neighbors"] for r in rows],
                color=colors[0],
            )
            axis.invert_yaxis()
            axis.set(title=title, xlabel="Distinct outgoing neighbors")
            axis.xaxis.set_major_locator(MaxNLocator(nbins=4, integer=True))
            if not rows:
                axis.text(
                    0.5,
                    0.5,
                    "No ranked nodes shown",
                    ha="center",
                    transform=axis.transAxes,
                )
        figure.suptitle(
            f"{policy}: direct neighbors within the combined ancestor selection"
        )
        save(figure, "rankings.png")
