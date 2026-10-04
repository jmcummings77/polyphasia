"""Export candidate Neo4j import CSVs without connecting to a database.

This prototype preserves the original graph-database exploration: language tags
become node labels, and only root-to-derived relationships are exported. A full
graph proved difficult to explore without useful subgraph annotations. The CSV
format is tested locally, but importing it into a live Neo4j instance is not.

Run from the repository root after installing polyphasia::

    python -m experiments.neo4j_export input.tsv output-directory
"""

import argparse
import csv
from pathlib import Path
from typing import Sequence

import pandas as pd

from polyphasia.loader import clean_data_frame, load_to_pandas


def export_csvs(source_tsv: Path, output_directory: Path) -> tuple[Path, Path]:
    """Write nodes.csv and edges.csv to the requested directory.

    Endpoint parsing and relationship selection follow ``clean_data_frame``.
    Node IDs retain the complete endpoint text, and nodes are sorted by ID for
    reproducible output. Existing CSVs at these two paths are replaced.
    """
    cleaned = clean_data_frame(load_to_pandas(source_tsv))
    source_nodes = cleaned[["source_node", "source_language", "source_word"]].rename(
        columns={
            "source_node": "wordId:ID",
            "source_language": "language:LABEL",
            "source_word": "word",
        }
    )
    target_nodes = cleaned[["target_node", "target_language", "target_word"]].rename(
        columns={
            "target_node": "wordId:ID",
            "target_language": "language:LABEL",
            "target_word": "word",
        }
    )
    nodes = (
        pd.concat([source_nodes, target_nodes], ignore_index=True)
        .drop_duplicates(subset="wordId:ID")
        .sort_values("wordId:ID")
    )
    edges = cleaned[["source_node", "edge_type", "target_node"]].rename(
        columns={
            "source_node": "source:START_ID",
            "edge_type": "relType:TYPE",
            "target_node": "target:END_ID",
        }
    )

    output_directory.mkdir(parents=True, exist_ok=True)
    nodes_path = output_directory / "nodes.csv"
    edges_path = output_directory / "edges.csv"
    nodes.to_csv(nodes_path, index=False, quoting=csv.QUOTE_NONNUMERIC)
    edges.to_csv(edges_path, index=False, quoting=csv.QUOTE_NONNUMERIC)
    return nodes_path, edges_path


def main(argv: Sequence[str] | None = None) -> int:
    """Run the explicit local-file export command."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("source_tsv", type=Path, help="Input etymology TSV file")
    parser.add_argument(
        "output_directory",
        type=Path,
        help="Directory for nodes.csv and edges.csv (existing files are replaced)",
    )
    args = parser.parse_args(argv)
    nodes_path, edges_path = export_csvs(args.source_tsv, args.output_directory)
    print(f"Wrote {nodes_path} and {edges_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
