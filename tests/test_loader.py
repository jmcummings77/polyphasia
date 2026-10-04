"""Small, synthetic regressions for the reusable TSV pipeline."""

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from polyphasia.constants import EDGE_ATTRIBUTES, EDGE_LIST_COLUMN_NAMES
from polyphasia.loader import clean_data_frame, load_to_pandas


def frame(*rows):
    return pd.DataFrame(rows, columns=EDGE_LIST_COLUMN_NAMES)


def test_one_edge_tsv_round_trip(tmp_path):
    source = tmp_path / "one.tsv"
    source.write_text(
        "lat: exemplum\trel:etymological_origin_of\teng: example\n", encoding="utf-8"
    )
    result = clean_data_frame(load_to_pandas(source))
    assert result.to_dict("records") == [
        {
            "source_node": "lat: exemplum",
            "edge_type": "rel:etymological_origin_of",
            "target_node": "eng: example",
            "source_language": "lat",
            "source_word": "exemplum",
            "target_language": "eng",
            "target_word": "example",
        }
    ]


def test_preserves_colons_unicode_and_variable_length_languages():
    result = clean_data_frame(
        frame(
            [
                "p_gem: Category: café: one",
                "rel:has_derived_form",
                "eng: Category: café",
            ]
        )
    )
    assert result.loc[0, "source_language"] == "p_gem"
    assert result.loc[0, "source_word"] == "Category: café: one"
    assert result.loc[0, "target_word"] == "Category: café"


def test_normalizes_only_relationship_column_and_does_not_mutate_input():
    original = frame(
        ["eng: root", "rel:derived", "eng: leaf"],
        ["eng: root", "rel:etymologically", "eng: other"],
    )
    original["note"] = "rel:derived"
    original.index = [7, 12]
    before = original.copy(deep=True)
    result = clean_data_frame(original, drop_rel_types=False)
    assert result.edge_type.tolist() == [
        "rel:is_derived_from",
        "rel:etymologically_related",
    ]
    assert result.note.tolist() == ["rel:derived", "rel:derived"]
    assert result.index.tolist() == [7, 12]
    assert_frame_equal(original, before)


def test_default_filter_keeps_only_root_to_derivative_edges():
    original = frame(
        ["eng: root", "rel:etymological_origin_of", "eng: leaf"],
        ["eng: root", "rel:has_derived_form", "eng: leaf"],
        ["eng: leaf", "rel:etymology", "eng: root"],
        ["eng: leaf", "rel:derived", "eng: root"],
        ["eng: root", "rel:etymologically_related", "eng: leaf"],
        ["eng: root", "rel:variant:orthography", "eng: leaf"],
    )
    before = original.copy(deep=True)
    result = clean_data_frame(original)
    assert result.edge_type.tolist() == [
        "rel:etymological_origin_of",
        "rel:has_derived_form",
    ]
    assert_frame_equal(original, before)


@pytest.mark.parametrize("drop_rel_types", [True, False])
def test_empty_input_has_complete_schema(drop_rel_types):
    result = clean_data_frame(frame(), drop_rel_types=drop_rel_types)
    assert result.empty
    assert set(result.columns) == set(EDGE_LIST_COLUMN_NAMES + EDGE_ATTRIBUTES)


def test_fully_filtered_input_has_complete_schema():
    result = clean_data_frame(frame(["eng: leaf", "rel:etymology", "eng: root"]))
    assert result.empty
    assert set(result.columns) == set(EDGE_LIST_COLUMN_NAMES + EDGE_ATTRIBUTES)


@pytest.mark.parametrize("column", ["source_node", "target_node"])
@pytest.mark.parametrize(
    "value", [None, 42, "", "word", "eng:word", ": word", "eng: ", "en g: word"]
)
def test_malformed_endpoints_raise_clear_error(column, value):
    original = frame(["eng: root", "rel:has_derived_form", "eng: leaf"])
    original.loc[0, column] = value
    with pytest.raises(ValueError, match=column):
        clean_data_frame(original)


def test_missing_column_raises_clear_error():
    with pytest.raises(ValueError, match="Missing required columns: target_node"):
        clean_data_frame(pd.DataFrame(columns=["source_node", "edge_type"]))


def test_duplicate_column_names_raise_clear_error():
    original = pd.DataFrame(columns=EDGE_LIST_COLUMN_NAMES + ["source_node"])
    with pytest.raises(ValueError, match="Column names must be unique"):
        clean_data_frame(original)


@pytest.mark.parametrize("value", [None, "", 42])
def test_missing_relationship_is_rejected(value):
    with pytest.raises(ValueError, match="edge_type"):
        clean_data_frame(frame(["eng: root", value, "eng: leaf"]))


@pytest.mark.parametrize("column", EDGE_LIST_COLUMN_NAMES)
def test_dataframe_nul_fields_are_rejected_without_mutation(column):
    original = frame(["eng: root", "rel:has_derived_form", "eng: leaf"])
    original.loc[0, column] += "\x00lost"
    before = original.copy(deep=True)
    with pytest.raises(ValueError, match=f"{column}.*NUL"):
        clean_data_frame(original)
    assert_frame_equal(original, before)


@pytest.mark.parametrize(
    "contents",
    [
        "eng: root\trel:has_derived_form\n",
        "eng: root\trel:has_derived_form\teng: leaf\textra\n",
        "eng: root\trel:has_derived_form\teng: leaf\neng: other\trel:has_derived_form\n",
        "eng: root\trel:has_derived_form\teng: leaf\neng: other\trel:has_derived_form\teng: leaf\textra\n",
    ],
)
def test_malformed_tsv_is_rejected(tmp_path, contents):
    source = tmp_path / "invalid.tsv"
    source.write_text(contents, encoding="utf-8")
    with pytest.raises(ValueError):
        load_to_pandas(source)


@pytest.mark.parametrize("column", EDGE_LIST_COLUMN_NAMES)
def test_tsv_nul_fields_are_rejected_before_parser_truncation(tmp_path, column):
    row = dict(
        zip(EDGE_LIST_COLUMN_NAMES, ["eng: root", "rel:has_derived_form", "eng: leaf"])
    )
    row[column] += "\x00lost"
    source = tmp_path / "nul.tsv"
    source.write_text("\t".join(row.values()) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="NUL"):
        load_to_pandas(source)


def test_nul_labels_cannot_collapse_distinct_records(tmp_path):
    source = tmp_path / "distinct.tsv"
    source.write_bytes(
        b"lat: root\trel:has_derived_form\teng: leaf\n"
        b"lat: root\trel:has_derived_form\teng: leaf\x00lost\n"
    )
    with pytest.raises(ValueError, match="NUL"):
        load_to_pandas(source)


@pytest.mark.parametrize("offset", [1024 * 1024 - 1, 1024 * 1024, 1024 * 1024 + 1])
def test_tsv_nul_rejection_at_scan_chunk_boundaries(tmp_path, offset):
    source = tmp_path / "later-nul.tsv"
    prefix = b"eng: "
    source.write_bytes(
        prefix
        + b"a" * (offset - len(prefix))
        + b"\x00lost\trel:has_derived_form\teng: leaf\n"
    )
    with pytest.raises(ValueError, match="NUL"):
        load_to_pandas(source)


def test_tsv_preserves_literal_quotes_and_na(tmp_path):
    source = tmp_path / "literal.tsv"
    source.write_text('eng: "quoted"\tNA\teng: café\n', encoding="utf-8")
    result = clean_data_frame(load_to_pandas(source), drop_rel_types=False)
    assert result.loc[0, "source_word"] == '"quoted"'
    assert result.loc[0, "target_word"] == "café"
    assert result.loc[0, "edge_type"] == "NA"


def test_empty_file(tmp_path):
    source = tmp_path / "empty.tsv"
    source.touch()
    assert_frame_equal(load_to_pandas(source), frame())


def test_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_to_pandas(tmp_path / "missing.tsv")


def test_default_path_is_relative_to_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "data" / "raw" / "etymologies.tsv"
    source.parent.mkdir(parents=True)
    source.write_text("eng: root\trel:has_derived_form\teng: leaf\n", encoding="utf-8")
    assert len(load_to_pandas()) == 1
