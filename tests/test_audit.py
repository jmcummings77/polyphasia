"""Independent accounting and reproducibility checks for the assertion audit."""

import csv
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pandas as pd
import pytest

from polyphasia import audit
from polyphasia.assertions import prepare_assertions
from polyphasia.audit import audit_assertions, write_audit
from polyphasia.constants import EDGE_LIST_COLUMN_NAMES


@pytest.fixture
def evidence():
    # Six forward endpoint pairs form four disconnected components. Normalizing
    # inverse-only facts adds two more components, without deleting either cycle.
    return pd.DataFrame(
        [
            ["lat: root", "rel:etymological_origin_of", "eng: branch"],
            ["lat: root", "rel:etymological_origin_of", "eng: branch"],
            ["eng: branch", "rel:etymology", "lat: root"],
            ["eng: sole", "rel:etymology", "grc: μόνος"],
            ["lat: root", "rel:has_derived_form", "eng: branch"],
            ["eng: branch", "rel:derived", "lat: root"],
            ["eng: branch", "rel:is_derived_from", "lat: root"],
            ["eng: leaf", "rel:is_derived_from", "eng: stem"],
            ["eng: loop", "rel:has_derived_form", "eng: loop"],
            ["eng: cycle-a", "rel:has_derived_form", "fra: cycle-b"],
            ["fra: cycle-b", "rel:has_derived_form", "eng: cycle-a"],
            ["fra: cycle-b", "rel:has_derived_form", "deu: tail"],
            ["ita: excluded", "rel:unknown", "spa: excluded"],
            ["lat: root", "rel:etymologically_related", "eng: branch"],
            ["por: detached", "rel:variant:orthography", "por: variant"],
            ["eng: island", "rel:has_derived_form", "eng: out"],
            ["eng: branch", "rel:etymology", "lat: root"],
        ],
        columns=EDGE_LIST_COLUMN_NAMES,
    )


def test_audit_distinguishes_raw_duplicates_aliases_and_canonical_facts(evidence):
    report = audit_assertions(prepare_assertions(evidence))
    source = report["input"]

    assert source["assertions"] == 17
    assert source["exact_duplicate_assertions"] == 2
    assert source["normalized_duplicate_assertions"] == 3
    assert source["alias_normalizations"] == 1
    assert source["raw_relationship_counts"]["rel:derived"] == 1
    assert source["raw_relationship_counts"]["rel:is_derived_from"] == 2
    assert source["normalized_relationship_counts"]["rel:is_derived_from"] == 3
    assert source["unknown_relationship_counts"] == {"rel:unknown": 1}
    assert source["ordered_pairs_with_multiple_normalized_types"] == 2
    assert source["self_loop_assertions"] == 1
    assert source["nodes"] == 16
    assert source["node_languages"] == {
        "deu": 1,
        "eng": 8,
        "fra": 1,
        "grc": 1,
        "ita": 1,
        "lat": 1,
        "por": 2,
        "spa": 1,
    }

    for policy, retained, excluded, nodes, edges, facts, extra in [
        ("root_only", 8, 9, 8, 6, 7, 2),
        ("normalized", 14, 3, 12, 8, 9, 6),
    ]:
        projection = report["projections"][policy]
        assert projection["retained_assertions"] == retained
        assert projection["excluded_assertions"] == excluded
        assert projection["nodes"] == nodes
        assert projection["edges"] == edges
        assert projection["canonical_relationship_facts"] == facts
        assert projection["assertions_beyond_first_per_edge"] == extra
        assert projection["pairs_with_multiple_relationship_types"] == 1


def test_inverse_coverage_counts_distinct_pairs_instead_of_evidence_rows(evidence):
    report = audit_assertions(prepare_assertions(evidence))

    assert report["inverse_coverage"]["rel:etymological_origin_of"] == {
        "inverse_relationship": "rel:etymology",
        "forward_assertions": 2,
        "inverse_assertions": 3,
        "unique_forward_pairs": 1,
        "unique_inverse_pairs": 2,
        "matched_pairs": 1,
        "forward_only_pairs": 0,
        "inverse_only_pairs": 1,
        "forward_pair_coverage": 1.0,
        "inverse_pair_coverage": 0.5,
    }
    assert report["inverse_coverage"]["rel:has_derived_form"] == {
        "inverse_relationship": "rel:is_derived_from",
        "forward_assertions": 6,
        "inverse_assertions": 3,
        "unique_forward_pairs": 6,
        "unique_inverse_pairs": 2,
        "matched_pairs": 1,
        "forward_only_pairs": 5,
        "inverse_only_pairs": 1,
        "forward_pair_coverage": 1 / 6,
        "inverse_pair_coverage": 0.5,
    }


def test_projections_account_for_every_assertion_and_endpoint(evidence):
    report = audit_assertions(prepare_assertions(evidence))
    source = report["input"]

    for projection in report["projections"].values():
        assert (
            projection["retained_assertions"] + projection["excluded_assertions"]
            == source["assertions"]
        )
        assert projection["nodes"] + projection["excluded_nodes"] == source["nodes"]
        assert Counter(projection["retained_raw_relationship_counts"]) + Counter(
            projection["excluded_raw_relationship_counts"]
        ) == Counter(source["raw_relationship_counts"])
        assert Counter(projection["node_languages"]) + Counter(
            projection["excluded_node_languages"]
        ) == Counter(source["node_languages"])
        assert sum(projection["node_languages"].values()) == projection["nodes"]

    normalized = report["projections"]["normalized"]
    assert normalized["excluded_raw_relationship_counts"] == {
        "rel:etymologically_related": 1,
        "rel:unknown": 1,
        "rel:variant:orthography": 1,
    }
    assert normalized["excluded_node_languages"] == {"ita": 1, "por": 2, "spa": 1}


@pytest.mark.parametrize(
    "policy, weak_count, scc_count, singletons",
    [("root_only", 4, 7, 6), ("normalized", 6, 11, 10)],
)
def test_cycles_are_diagnosed_without_deleting_them(
    evidence, policy, weak_count, scc_count, singletons
):
    projection = audit_assertions(prepare_assertions(evidence))["projections"][policy]

    assert projection["self_loop_edges"] == 1
    assert projection["weak_components"] == weak_count
    assert projection["largest_weak_component"] == 3
    assert projection["strongly_connected_components"] == {
        "count": scc_count,
        "size_histogram": {"1": singletons, "2": 1},
        "cyclic_count": 2,
        "cyclic_size_histogram": {"1": 1, "2": 1},
        "largest_cyclic_component": 2,
        "cyclic_nodes": 3,
        "cyclic_node_languages": {"eng": 2, "fra": 1},
        # The outgoing cycle-b -> tail edge is incident to the cycle, but tail
        # does not belong to it. The self-loop is counted once, not twice.
        "edges_incident_to_cyclic_nodes": 4,
    }


@pytest.mark.parametrize("seed", [3, 17, 99])
def test_complete_report_is_independent_of_input_order(evidence, seed):
    expected = audit_assertions(prepare_assertions(evidence))
    reordered = evidence.sample(frac=1, random_state=seed)

    assert audit_assertions(prepare_assertions(reordered)) == expected


def test_empty_audit_has_zero_totals_and_undefined_coverage():
    report = audit_assertions(
        prepare_assertions(pd.DataFrame(columns=EDGE_LIST_COLUMN_NAMES))
    )

    assert report["input"]["assertions"] == 0
    assert report["input"]["nodes"] == 0
    assert report["input"]["node_languages"] == {}
    for coverage in report["inverse_coverage"].values():
        assert coverage["forward_pair_coverage"] is None
        assert coverage["inverse_pair_coverage"] is None
        assert coverage["matched_pairs"] == 0
    for projection in report["projections"].values():
        for count in (
            "retained_assertions",
            "excluded_assertions",
            "nodes",
            "edges",
            "weak_components",
            "largest_weak_component",
        ):
            assert projection[count] == 0
        assert projection["strongly_connected_components"]["size_histogram"] == {}
        assert (
            projection["strongly_connected_components"]["largest_cyclic_component"] == 0
        )


@pytest.mark.parametrize(
    "relationship, forward_coverage, inverse_coverage",
    [("rel:etymology", None, 0.0), ("rel:etymological_origin_of", 0.0, None)],
)
def test_one_sided_evidence_distinguishes_missing_denominator_from_zero_coverage(
    relationship, forward_coverage, inverse_coverage
):
    assertions = prepare_assertions(
        pd.DataFrame(
            [["eng: a", relationship, "eng: b"]], columns=EDGE_LIST_COLUMN_NAMES
        )
    )
    coverage = audit_assertions(assertions)["inverse_coverage"][
        "rel:etymological_origin_of"
    ]

    assert coverage["forward_pair_coverage"] == forward_coverage
    assert coverage["inverse_pair_coverage"] == inverse_coverage
    assert coverage["matched_pairs"] == 0


def test_write_audit_preserves_literals_and_records_verifiable_provenance(tmp_path):
    source = tmp_path / "source.tsv"
    original = (
        '\neng: "quoted"\tNA\tp_gem: café: "two"\r\n\n'
        "lat: rādīx\trel:has_derived_form\teng: NA\n"
        "eng: NA\trel:derived\tlat: rādīx\n"
    ).encode("utf-8")
    source.write_bytes(original)
    output = tmp_path / "nested" / "audit"

    report = write_audit(
        source,
        output,
        source_url="https://example.invalid/source.tsv",
        dataset_version="test-snapshot",
    )

    with (output / "assertions.tsv").open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream, delimiter="\t"))
    assert [[row[column] for column in EDGE_LIST_COLUMN_NAMES] for row in rows] == [
        ['eng: "quoted"', "NA", 'p_gem: café: "two"'],
        ["lat: rādīx", "rel:has_derived_form", "eng: NA"],
        ["eng: NA", "rel:derived", "lat: rādīx"],
    ]
    assert [row["assertion_id"] for row in rows] == ["1", "2", "3"]
    assert rows[2]["normalized_edge_type"] == "rel:is_derived_from"
    assert source.read_bytes() == original
    assert report == json.loads((output / "audit.json").read_text(encoding="utf-8"))

    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["input"] == {
        "path": str(source.resolve()),
        "sha256": hashlib.sha256(original).hexdigest(),
        "bytes": len(original),
        "source_url": "https://example.invalid/source.tsv",
        "dataset_version": "test-snapshot",
    }
    assert manifest["created_at"].endswith("+00:00")
    assert set(manifest["environment"]) == {
        "python",
        "polyphasia",
        "pandas",
        "networkx",
    }
    for name, artifact in manifest["artifacts"].items():
        contents = (output / name).read_bytes()
        assert artifact == {
            "sha256": hashlib.sha256(contents).hexdigest(),
            "bytes": len(contents),
        }
    assert set(manifest["artifacts"]) == {"assertions.tsv", "audit.json"}
    package = Path(__file__).resolve().parents[1] / "polyphasia"
    for name, digest in manifest["implementation_sha256"].items():
        assert digest == hashlib.sha256((package / name).read_bytes()).hexdigest()

    repeated = tmp_path / "second-audit"
    assert write_audit(source, repeated) == report
    assert (repeated / "audit.json").read_bytes() == (
        output / "audit.json"
    ).read_bytes()
    assert (repeated / "assertions.tsv").read_bytes() == (
        output / "assertions.tsv"
    ).read_bytes()


@pytest.mark.parametrize("existing_type", ["directory", "file"])
def test_write_audit_refuses_existing_outputs_without_touching_them(
    tmp_path, existing_type
):
    source = tmp_path / "source.tsv"
    source.write_text("eng: a\trel:has_derived_form\teng: b\n", encoding="utf-8")
    output = tmp_path / "existing"
    if existing_type == "directory":
        output.mkdir()
        sentinel = output / "keep.txt"
    else:
        sentinel = output
    sentinel.write_text("keep this", encoding="utf-8")

    with pytest.raises(FileExistsError, match="already exists"):
        write_audit(source, output)

    assert sentinel.read_text(encoding="utf-8") == "keep this"
    if existing_type == "directory":
        assert list(output.iterdir()) == [sentinel]


@pytest.mark.parametrize(
    "contents, error",
    [
        ("eng: a\trel:has_derived_form\n", "three tab-separated fields"),
        ("invalid-node\trel:unknown\teng: b\n", "source_node"),
    ],
)
def test_invalid_input_does_not_create_output_directories(tmp_path, contents, error):
    source = tmp_path / "invalid.tsv"
    source.write_text(contents, encoding="utf-8")
    output = tmp_path / "absent-parent" / "audit"

    with pytest.raises(ValueError, match=error):
        write_audit(source, output)

    assert not output.parent.exists()


def test_input_change_during_loading_cannot_receive_a_valid_manifest(
    tmp_path, monkeypatch
):
    source = tmp_path / "source.tsv"
    source.write_text("eng: a\trel:has_derived_form\teng: b\n", encoding="utf-8")
    output = tmp_path / "audit"
    original_loader = audit.load_to_pandas

    def change_file_after_read(path):
        frame = original_loader(path)
        path.write_text("eng: x\trel:has_derived_form\teng: y\n", encoding="utf-8")
        return frame

    monkeypatch.setattr(audit, "load_to_pandas", change_file_after_read)

    with pytest.raises(ValueError, match="Input changed while loading"):
        write_audit(source, output)

    assert not output.exists()


def test_cli_writes_audit_and_reports_failure_without_a_traceback(tmp_path):
    source = tmp_path / "source.tsv"
    source.write_text("eng: a\trel:has_derived_form\teng: b\n", encoding="utf-8")
    output = tmp_path / "audit"
    command = [
        sys.executable,
        "-m",
        "polyphasia.audit",
        str(source),
        "--output",
        str(output),
        "--dataset-version",
        "fixture-v1",
    ]

    completed = subprocess.run(command, capture_output=True, text=True, check=False)

    assert completed.returncode == 0, completed.stderr
    assert "Audited 1 assertions" in completed.stdout
    assert {path.name for path in output.iterdir()} == {
        "assertions.tsv",
        "audit.json",
        "manifest.json",
    }
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["input"]["dataset_version"] == "fixture-v1"

    failed = subprocess.run(command, capture_output=True, text=True, check=False)

    assert failed.returncode == 1
    assert "Audit failed: Output directory already exists:" in failed.stderr
    assert "Traceback" not in failed.stderr
