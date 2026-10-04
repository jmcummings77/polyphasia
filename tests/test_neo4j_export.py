"""Local-file contract tests for the optional Neo4j export experiment."""

import csv
import importlib
import subprocess
import sys
from pathlib import Path

import pandas as pd

from experiments import neo4j_export


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return reader.fieldnames, list(reader)


def test_export_one_edge_preserves_complete_words(tmp_path):
    source = tmp_path / "input.tsv"
    source.write_text(
        'eng: origin\trel:has_derived_form\teng: word: ",comma"\n', encoding="utf-8"
    )

    nodes_path, edges_path = neo4j_export.export_csvs(source, tmp_path / "out")

    node_columns, nodes = read_csv(nodes_path)
    assert node_columns == ["wordId:ID", "language:LABEL", "word"]
    assert nodes == [
        {"wordId:ID": "eng: origin", "language:LABEL": "eng", "word": "origin"},
        {
            "wordId:ID": 'eng: word: ",comma"',
            "language:LABEL": "eng",
            "word": 'word: ",comma"',
        },
    ]
    edge_columns, edges = read_csv(edges_path)
    assert edge_columns == ["source:START_ID", "relType:TYPE", "target:END_ID"]
    assert edges == [
        {
            "source:START_ID": "eng: origin",
            "relType:TYPE": "rel:has_derived_form",
            "target:END_ID": 'eng: word: ",comma"',
        }
    ]


def test_export_filters_relationships_and_deduplicates_nodes(tmp_path):
    source = tmp_path / "input.tsv"
    source.write_text(
        "eng: root\trel:has_derived_form\teng: branch\n"
        "eng: branch\trel:etymological_origin_of\teng: leaf\n"
        "eng: ignored\trel:is_derived_from\teng: root\n",
        encoding="utf-8",
    )

    nodes_path, edges_path = neo4j_export.export_csvs(source, tmp_path / "out")

    assert [node["wordId:ID"] for node in read_csv(nodes_path)[1]] == [
        "eng: branch",
        "eng: leaf",
        "eng: root",
    ]
    assert len(read_csv(edges_path)[1]) == 2


def test_export_filtered_input_writes_headers(tmp_path):
    source = tmp_path / "input.tsv"
    source.write_text("eng: leaf\trel:is_derived_from\teng: root\n", encoding="utf-8")

    nodes_path, edges_path = neo4j_export.export_csvs(source, tmp_path / "out")

    assert read_csv(nodes_path) == (["wordId:ID", "language:LABEL", "word"], [])
    assert read_csv(edges_path) == (
        ["source:START_ID", "relType:TYPE", "target:END_ID"],
        [],
    )


def test_import_does_not_read_or_write_data(monkeypatch, tmp_path):
    def unexpected_io(*args, **kwargs):
        raise AssertionError("Importing an experiment must not read or write data")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(pd, "read_csv", unexpected_io)
    monkeypatch.setattr(pd.DataFrame, "to_csv", unexpected_io)
    monkeypatch.setattr(Path, "mkdir", unexpected_io)

    importlib.reload(neo4j_export)

    assert list(tmp_path.iterdir()) == []


def test_cli_writes_requested_directory(tmp_path):
    source = tmp_path / "input.tsv"
    source.write_text("eng: root\trel:has_derived_form\teng: leaf\n", encoding="utf-8")
    output = tmp_path / "nested" / "output"

    result = subprocess.run(
        [sys.executable, "-m", "experiments.neo4j_export", str(source), str(output)],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert str(output / "nodes.csv") in result.stdout
    assert len(read_csv(output / "nodes.csv")[1]) == 2
    assert len(read_csv(output / "edges.csv")[1]) == 1
