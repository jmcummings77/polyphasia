"""Audit source assertions and compare explicit, non-destructive projections.

Run ``python -m polyphasia.audit INPUT.tsv --output NEW_DIRECTORY`` to save the
assertion table, deterministic audit report, and a provenance manifest.
"""

import argparse
import hashlib
import json
import logging
import platform
from collections import Counter
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from typing import Any, Iterable

import networkx as nx
import pandas as pd

from polyphasia.assertions import (
    INVERSE_RELATIONSHIPS,
    prepare_assertions,
    project_assertions,
)
from polyphasia.constants import EDGE_LIST_COLUMN_NAMES, VALID_RELATIONSHIP_TYPES_LIST
from polyphasia.loader import load_to_pandas

logger = logging.getLogger(__name__)


def _counts(values: Iterable[str]) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))


def _language_counts(nodes: Iterable[str]) -> dict[str, int]:
    return _counts(node.partition(": ")[0] for node in nodes)


def _inverse_coverage(assertions: pd.DataFrame) -> dict[str, Any]:
    """Compare unique facts, so repeated assertions cannot inflate coverage."""
    results = {}
    for inverse, forward in INVERSE_RELATIONSHIPS.items():
        forward_rows = assertions.loc[
            assertions.normalized_edge_type == forward, ["source_node", "target_node"]
        ]
        inverse_rows = assertions.loc[
            assertions.normalized_edge_type == inverse, ["source_node", "target_node"]
        ]
        forward_pairs = set(zip(forward_rows.source_node, forward_rows.target_node))
        inverse_pairs = set(zip(inverse_rows.target_node, inverse_rows.source_node))
        matched = sum(pair in inverse_pairs for pair in forward_pairs)
        results[forward] = {
            "inverse_relationship": inverse,
            "forward_assertions": len(forward_rows),
            "inverse_assertions": len(inverse_rows),
            "unique_forward_pairs": len(forward_pairs),
            "unique_inverse_pairs": len(inverse_pairs),
            "matched_pairs": matched,
            "forward_only_pairs": len(forward_pairs) - matched,
            "inverse_only_pairs": len(inverse_pairs) - matched,
            "forward_pair_coverage": (
                matched / len(forward_pairs) if forward_pairs else None
            ),
            "inverse_pair_coverage": (
                matched / len(inverse_pairs) if inverse_pairs else None
            ),
        }
    return results


def _projection_summary(
    assertions: pd.DataFrame, all_nodes: set[str], policy: str
) -> dict[str, Any]:
    graph = project_assertions(assertions, policy=policy)
    retained = sum(data["assertion_count"] for _, _, data in graph.edges(data=True))
    retained_types: Counter[str] = Counter()
    for _, _, data in graph.edges(data=True):
        retained_types.update(data["raw_relationship_counts"])
    excluded_types = Counter(assertions.edge_type) - retained_types
    scc_sizes: Counter[int] = Counter()
    cyclic_sizes: Counter[int] = Counter()
    cyclic_nodes: set[str] = set()
    for component in nx.strongly_connected_components(graph):
        size = len(component)
        scc_sizes[size] += 1
        if size > 1 or graph.has_edge(next(iter(component)), next(iter(component))):
            cyclic_sizes[size] += 1
            cyclic_nodes.update(component)
    weak_sizes = Counter(len(c) for c in nx.weakly_connected_components(graph))
    summary = {
        "policy_version": graph.graph["policy_version"],
        "retained_assertions": retained,
        "excluded_assertions": len(assertions) - retained,
        "retained_raw_relationship_counts": dict(sorted(retained_types.items())),
        "excluded_raw_relationship_counts": dict(sorted(excluded_types.items())),
        "nodes": len(graph),
        "excluded_nodes": len(all_nodes) - len(graph),
        "node_languages": _language_counts(graph),
        "excluded_node_languages": _language_counts(all_nodes.difference(graph)),
        "edges": graph.number_of_edges(),
        "canonical_relationship_facts": sum(
            len(data["relationship_types"]) for _, _, data in graph.edges(data=True)
        ),
        "assertions_beyond_first_per_edge": retained - graph.number_of_edges(),
        "pairs_with_multiple_relationship_types": sum(
            len(data["relationship_types"]) > 1 for _, _, data in graph.edges(data=True)
        ),
        "self_loop_edges": nx.number_of_selfloops(graph),
        "weak_components": sum(weak_sizes.values()),
        "largest_weak_component": max(weak_sizes, default=0),
        "strongly_connected_components": {
            "count": sum(scc_sizes.values()),
            "size_histogram": {str(k): v for k, v in sorted(scc_sizes.items())},
            "cyclic_count": sum(cyclic_sizes.values()),
            "cyclic_size_histogram": {
                str(k): v for k, v in sorted(cyclic_sizes.items())
            },
            "cyclic_nodes": len(cyclic_nodes),
            "largest_cyclic_component": max(cyclic_sizes, default=0),
            "cyclic_node_languages": _language_counts(cyclic_nodes),
            "edges_incident_to_cyclic_nodes": sum(
                source in cyclic_nodes or target in cyclic_nodes
                for source, target in graph.edges
            ),
        },
    }
    # NetworkX caches views with references back to the graph. Clear its large
    # data structures now instead of waiting for cyclic garbage collection.
    graph.clear()
    return summary


def audit_assertions(assertions: pd.DataFrame) -> dict[str, Any]:
    """Summarize a table from ``prepare_assertions`` without deleting evidence.

    Counts describe records in this input, not linguistic confidence or source
    completeness. Node counts are distinct exact labels across both endpoints.
    """
    nodes = set(assertions.source_node)
    nodes.update(assertions.target_node)
    raw_counts = _counts(assertions.edge_type)
    normalized_counts = _counts(assertions.normalized_edge_type)
    pair_types = assertions.groupby(["source_node", "target_node"], sort=False)[
        "normalized_edge_type"
    ].nunique()
    multiple_type_pairs = int((pair_types > 1).sum())
    del pair_types
    report: dict[str, Any] = {
        "schema_version": 1,
        "input": {
            "assertions": len(assertions),
            "nodes": len(nodes),
            "node_languages": _language_counts(nodes),
            "raw_relationship_counts": raw_counts,
            "normalized_relationship_counts": normalized_counts,
            "unknown_relationship_counts": {
                key: count
                for key, count in normalized_counts.items()
                if key not in VALID_RELATIONSHIP_TYPES_LIST
            },
            "alias_normalizations": int(
                (assertions.edge_type != assertions.normalized_edge_type).sum()
            ),
            "exact_duplicate_assertions": int(
                assertions.duplicated(EDGE_LIST_COLUMN_NAMES).sum()
            ),
            "normalized_duplicate_assertions": int(
                assertions.duplicated(
                    ["source_node", "normalized_edge_type", "target_node"]
                ).sum()
            ),
            "ordered_pairs_with_multiple_normalized_types": multiple_type_pairs,
            "self_loop_assertions": int(
                (assertions.source_node == assertions.target_node).sum()
            ),
        },
        "inverse_coverage": _inverse_coverage(assertions),
        "projections": {},
    }
    # Build and release one projection at a time; do not retain two full graphs.
    for policy in ("root_only", "normalized"):
        logger.info("Summarizing %s projection", policy)
        report["projections"][policy] = _projection_summary(assertions, nodes, policy)
    return report


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_audit(
    source: Path,
    output: Path,
    *,
    source_url: str | None = None,
    dataset_version: str | None = None,
) -> dict[str, Any]:
    """Write a new local audit directory, refusing to replace existing outputs.

    Original fields are saved verbatim as TSV cell values; assertion IDs count
    parsed nonblank records, not physical lines. The original file is untouched.
    Invalid input fails before creating the output directory.
    """
    source, output = Path(source), Path(output)
    if output.exists():
        raise FileExistsError(f"Output directory already exists: {output}")
    input_bytes = source.stat().st_size
    input_hash = _sha256(source)
    implementation_hashes = {
        name: _sha256(Path(__file__).with_name(name))
        for name in ("audit.py", "assertions.py", "loader.py", "constants.py")
    }
    logger.info("Loading and validating %s", source)
    assertions = prepare_assertions(load_to_pandas(source))
    if _sha256(source) != input_hash:
        raise ValueError("Input changed while loading; rerun with a stable file")
    logger.info("Auditing %s assertions", len(assertions))
    report = audit_assertions(assertions)
    if any(
        _sha256(Path(__file__).with_name(name)) != digest
        for name, digest in implementation_hashes.items()
    ):
        raise ValueError(
            "Implementation changed during the audit; rerun with stable code"
        )
    logger.info("Writing artifacts to %s", output)
    output.mkdir(parents=True, exist_ok=False)
    assertion_path = output / "assertions.tsv"
    assertions.to_csv(assertion_path, sep="\t", index=False, lineterminator="\n")
    report_path = output / "audit.json"
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input": {
            "path": str(source.resolve()),
            "sha256": input_hash,
            "bytes": input_bytes,
            "source_url": source_url,
            "dataset_version": dataset_version,
        },
        "environment": {
            "python": platform.python_version(),
            **{name: version(name) for name in ("polyphasia", "pandas", "networkx")},
        },
        "implementation_sha256": implementation_hashes,
        "policies": {
            name: summary["policy_version"]
            for name, summary in report["projections"].items()
        },
        "assertion_id_definition": "1-based nonblank parsed record ordinal",
        "artifacts": {
            path.name: {"sha256": _sha256(path), "bytes": path.stat().st_size}
            for path in (assertion_path, report_path)
        },
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Headerless source TSV")
    parser.add_argument(
        "--output", required=True, type=Path, help="New output directory"
    )
    parser.add_argument("--source-url", help="Provenance URL; no download is performed")
    parser.add_argument("--dataset-version", help="Source version, e.g. 2013-02-08")
    args = parser.parse_args()
    try:
        report = write_audit(
            args.source,
            args.output,
            source_url=args.source_url,
            dataset_version=args.dataset_version,
        )
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Audit failed: {exc}\n")
    print(f"Audited {report['input']['assertions']} assertions into {args.output}")


if __name__ == "__main__":
    main()
