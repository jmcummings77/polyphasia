"""Published evidence remains complete and independently checksum-verifiable."""

from pathlib import Path

from polyphasia.analysis import validate_run


def test_published_full_run_preserves_pinned_input_and_clean_provenance():
    root = Path(__file__).resolve().parents[1] / "reports" / "20130208"
    manifest = validate_run(root)
    assert manifest["input"]["kind"] == "full"
    assert manifest["input"]["dataset_version"] == "2013-02-08"
    assert manifest["input"]["sha256"] == (
        "361b946fa306732357b3ee375ea01ccdcbe3db1676898c47c39a92fb9861f7da"
    )
    assert manifest["git"]["dirty"] is False
    assert len(manifest["git"]["revision"]) == 40
    assert manifest["parameters"]["policies"] == ["root_only", "normalized"]
