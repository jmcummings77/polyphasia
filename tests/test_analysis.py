"""Workflow provenance, reproducibility, and failure-boundary checks."""

import csv
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from polyphasia import analysis

FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "analysis-fixture.tsv"


@pytest.fixture(scope="module")
def completed_runs(tmp_path_factory):
    root = tmp_path_factory.mktemp("analysis-runs")
    for name in ("first", "second"):
        analysis.write_analysis(
            FIXTURE,
            root / name,
            input_kind="synthetic",
            dataset_version="synthetic-v1",
            trace_words=("eng: examples", "eng: loop-leaf"),
        )
    return root / "first", root / "second"


def test_repeated_runs_have_identical_analytical_artifacts(completed_runs):
    first, second = completed_runs
    first_manifest, second_manifest = (analysis.validate_run(p) for p in completed_runs)
    assert first_manifest["artifacts"] == second_manifest["artifacts"]
    for name in analysis.ARTIFACTS:
        assert (first / name).read_bytes() == (second / name).read_bytes()
    assert first_manifest["created_at"] != second_manifest["created_at"]
    assert (
        first_manifest["input"]["sha256"]
        == hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    )
    assert first_manifest["input"]["bytes"] == 1743
    assert first_manifest["input"]["kind"] == "synthetic"
    assert first_manifest["execution"]["wall_seconds"] > 0
    assert first_manifest["environment"]["networkx"]
    assert first_manifest["git"]["revision"]


def test_tables_and_traces_reconcile_with_independent_fixture(completed_runs):
    root, _ = completed_runs
    with (root / "queries.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    normalized = {r["query"]: r for r in rows if r["policy"] == "normalized"}
    assert len(rows) == 8
    assert normalized["ancestors"]["nodes"] == "24"
    assert normalized["ancestors"]["edges"] == "18"
    assert normalized["root_families"]["seeds_included"] == "16"
    assert normalized["root_families"]["seeds"] == "19"
    assert normalized["root_families"]["raw_language_nodes"] == "22"
    assert normalized["root_families"]["raw_language_nodes_excluded"] == "3"
    report = json.loads((root / "analysis.json").read_text())
    traces = {t["word"]: t for t in report["projections"]["normalized"]["traces"]}
    assert traces["eng: loop-leaf"]["status"] == "rootless"
    ids = [
        row["assertion_id"]
        for row in traces["eng: examples"]["edges"][-1]["evidence_sample"]
    ]
    assert ids == [4, 5, 6, 7, 8]
    for name in ("retention", "query-comparison", "rankings"):
        assert (
            (root / "figures" / f"{name}.png")
            .read_bytes()
            .startswith(b"\x89PNG\r\n\x1a\n")
        )


def test_existing_output_is_never_replaced(completed_runs):
    root, _ = completed_runs
    original = (root / "manifest.json").read_bytes()
    with pytest.raises(FileExistsError):
        analysis.write_analysis(FIXTURE, root)
    assert (root / "manifest.json").read_bytes() == original


def test_manifest_detects_corruption(completed_runs, tmp_path):
    source, _ = completed_runs
    shutil.copytree(source, tmp_path / "run")
    path = tmp_path / "run" / "queries.csv"
    path.write_bytes(path.read_bytes().replace(b"24", b"99"))
    with pytest.raises(ValueError, match="mismatch"):
        analysis.validate_run(tmp_path / "run")


@pytest.mark.parametrize("change", ["schema", "workflow", "missing", "traversal"])
def test_manifest_rejects_incomplete_or_unsupported_runs(
    completed_runs, tmp_path, change
):
    source, _ = completed_runs
    shutil.copytree(source, tmp_path / "run")
    path = tmp_path / "run" / "manifest.json"
    manifest = json.loads(path.read_text())
    if change == "schema":
        manifest["schema_version"] = 99
    elif change == "workflow":
        manifest["workflow"] = "other"
    elif change == "missing":
        del manifest["artifacts"]["queries.csv"]
    else:
        manifest["artifacts"]["../outside"] = manifest["artifacts"].pop("queries.csv")
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        analysis.validate_run(path.parent)


def test_artifact_symlink_cannot_leave_the_run(completed_runs, tmp_path):
    source, _ = completed_runs
    shutil.copytree(source, tmp_path / "run")
    artifact = tmp_path / "run" / "queries.csv"
    artifact.unlink()
    artifact.symlink_to(source / "queries.csv")
    with pytest.raises(ValueError, match="leaves"):
        analysis.validate_run(tmp_path / "run")


def test_pinned_input_failure_happens_before_analysis(tmp_path, monkeypatch):
    def no_load(*args):
        pytest.fail("Mismatched input should not be loaded")

    monkeypatch.setattr(analysis, "load_to_pandas", no_load)
    with pytest.raises(ValueError, match="SHA-256"):
        analysis.write_analysis(FIXTURE, tmp_path / "run", expected_sha256="0" * 64)
    assert not (tmp_path / "run").exists()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"input_kind": "invalid"},
        {"language": ""},
        {"policies": ()},
        {"top_n": -1},
        {"trace_max_depth": -1},
        {"trace_max_nodes": 0},
    ],
)
def test_invalid_parameters_create_no_run(tmp_path, kwargs):
    with pytest.raises(ValueError):
        analysis.write_analysis(FIXTURE, tmp_path / "run", **kwargs)
    assert not (tmp_path / "run").exists()


def test_input_change_during_loading_is_rejected(tmp_path, monkeypatch):
    source = tmp_path / "input.tsv"
    source.write_bytes(FIXTURE.read_bytes())
    load = analysis.load_to_pandas

    def changed(path):
        frame = load(path)
        path.write_bytes(path.read_bytes() + b"\n")
        return frame

    monkeypatch.setattr(analysis, "load_to_pandas", changed)
    with pytest.raises(ValueError, match="changed while loading"):
        analysis.write_analysis(source, tmp_path / "run")
    assert not (tmp_path / "run").exists()


@pytest.mark.parametrize("failure", ["render", "source", "implementation"])
def test_late_failure_never_publishes_a_completed_run(tmp_path, monkeypatch, failure):
    source = tmp_path / "input.tsv"
    source.write_bytes(FIXTURE.read_bytes())

    def fail_or_change(*args):
        if failure == "render":
            raise ValueError("Rendering failed")
        if failure == "source":
            source.write_bytes(source.read_bytes() + b"\n")
        else:
            monkeypatch.setattr(analysis, "_implementation_hashes", lambda: {})

    monkeypatch.setattr(analysis, "write_figures", fail_or_change)
    with pytest.raises(ValueError, match="failed|changed"):
        analysis.write_analysis(source, tmp_path / "run")
    assert not (tmp_path / "run").exists()
    assert not list(tmp_path.glob(".run-*"))


def test_empty_single_policy_analysis_and_absent_git(tmp_path, monkeypatch):
    source = tmp_path / "empty.tsv"
    source.write_text("")

    def unavailable(*args, **kwargs):
        raise OSError("Git is unavailable in an installed wheel")

    monkeypatch.setattr(analysis.subprocess, "run", unavailable)
    report = analysis.write_analysis(source, tmp_path / "run", policies=("root_only",))
    assert report["input"]["assertions"] == 0
    assert report["projections"]["root_only"]["seeds"] == 0
    assert analysis.validate_run(tmp_path / "run")["git"] == {
        "revision": None,
        "dirty": None,
    }


def test_cli_generates_and_refuses_to_overwrite_run(tmp_path):
    command = [
        sys.executable,
        "-m",
        "polyphasia.analysis",
        str(FIXTURE),
        "--output",
        str(tmp_path / "run"),
        "--word",
        "eng: examples",
        "--input-kind",
        "synthetic",
    ]
    first = subprocess.run(command, capture_output=True, text=True)
    assert first.returncode == 0, first.stderr
    assert "Analyzed 37 assertions" in first.stdout
    analysis.validate_run(tmp_path / "run")
    second = subprocess.run(command, capture_output=True, text=True)
    assert second.returncode == 1
    assert "already exists" in second.stderr
