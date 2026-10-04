"""Evidence preservation and explicit projection policy regressions."""

import networkx as nx
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from polyphasia.assertions import (
    ASSERTION_COLUMN_NAMES,
    prepare_assertions,
    project_assertions,
)
from polyphasia.constants import EDGE_LIST_COLUMN_NAMES
from polyphasia.loader import load_to_pandas


def frame(*rows):
    return pd.DataFrame(rows, columns=EDGE_LIST_COLUMN_NAMES)


def test_preparation_preserves_literals_and_all_records():
    raw = frame(
        ["eng: Category: café", "rel:derived", "lat: root"],
        ['eng: "NA"', "rel:etymologically", "p_gem: word: suffix"],
        ["eng: unknown", "NA", "eng:  spaced word "],
    )
    raw.index = [100, 100, -7]
    before = raw.copy(deep=True)
    result = prepare_assertions(raw)

    assert_frame_equal(result[EDGE_LIST_COLUMN_NAMES], before)
    assert result.index.tolist() == [100, 100, -7]
    assert result.assertion_id.tolist() == [1, 2, 3]
    assert result.normalized_edge_type.tolist() == [
        "rel:is_derived_from",
        "rel:etymologically_related",
        "NA",
    ]
    assert result.source_word.tolist() == ["Category: café", '"NA"', "unknown"]
    assert result.target_language.tolist() == ["lat", "p_gem", "eng"]
    assert result.target_word.tolist() == ["root", "word: suffix", " spaced word "]
    assert_frame_equal(raw, before)


def test_reserved_caller_columns_cannot_replace_evidence():
    raw = frame(["eng: leaf", "rel:derived", "eng: root"])
    for column in ASSERTION_COLUMN_NAMES[3:] + ["note"]:
        raw[column] = "caller metadata"
    before = raw.copy(deep=True)
    result = prepare_assertions(raw)

    assert result.columns.tolist() == ASSERTION_COLUMN_NAMES
    assert result.iloc[0].to_dict() == {
        "source_node": "eng: leaf",
        "edge_type": "rel:derived",
        "target_node": "eng: root",
        "assertion_id": 1,
        "normalized_edge_type": "rel:is_derived_from",
        "source_language": "eng",
        "source_word": "leaf",
        "target_language": "eng",
        "target_word": "root",
    }
    assert_frame_equal(raw, before)


@pytest.mark.parametrize("policy", ["root_only", "normalized"])
def test_empty_schema_and_projection(policy):
    result = prepare_assertions(frame())
    assert result.empty
    assert result.columns.tolist() == ASSERTION_COLUMN_NAMES
    assert result.assertion_id.dtype == "int64"
    graph = project_assertions(result, policy)
    assert list(graph) == []
    assert graph.graph == {"policy": policy, "policy_version": "1"}


def test_record_ordinals_do_not_count_blank_lines(tmp_path):
    source = tmp_path / "records.tsv"
    source.write_text(
        "\neng: root\trel:has_derived_form\teng: leaf\n\n"
        "eng: root\trel:has_derived_form\teng: leaf\n",
        encoding="utf-8",
    )
    assertions = prepare_assertions(load_to_pandas(source))
    assert assertions.assertion_id.tolist() == [1, 2]
    assert len(assertions) == 2


def test_preparation_rejects_invalid_endpoint_even_for_excluded_relationship():
    with pytest.raises(ValueError, match="target_node"):
        prepare_assertions(frame(["eng: root", "unknown", "bad endpoint"]))


def test_preparation_rejects_duplicate_columns():
    with pytest.raises(ValueError, match="Column names must be unique"):
        prepare_assertions(pd.DataFrame(columns=EDGE_LIST_COLUMN_NAMES + ["note"] * 2))


def test_projection_aggregates_duplicates_and_parallel_types():
    assertions = prepare_assertions(
        frame(
            ["lat: root", "rel:has_derived_form", "eng: leaf"],
            ["lat: root", "rel:has_derived_form", "eng: leaf"],
            ["lat: root", "rel:etymological_origin_of", "eng: leaf"],
            ["eng: leaf", "rel:derived", "lat: root"],
            ["eng: leaf", "rel:etymology", "lat: root"],
        )
    )
    before = assertions.copy(deep=True)
    graph = project_assertions(assertions)

    assert list(graph.nodes(data=True)) == [
        ("eng: leaf", {"language": "eng", "word": "leaf"}),
        ("lat: root", {"language": "lat", "word": "root"}),
    ]
    assert list(graph.edges) == [("lat: root", "eng: leaf")]
    assert graph["lat: root"]["eng: leaf"] == {
        "relationship_types": ("rel:etymological_origin_of", "rel:has_derived_form"),
        "assertion_count": 5,
        "raw_relationship_counts": {
            "rel:derived": 1,
            "rel:etymological_origin_of": 1,
            "rel:etymology": 1,
            "rel:has_derived_form": 2,
        },
        "assertion_ids": (1, 2, 3, 4, 5),
    }
    assert_frame_equal(assertions, before)


def test_evidence_counts_and_provenance_are_independent_between_edges():
    assertions = prepare_assertions(
        frame(
            ["eng: root", "rel:has_derived_form", "eng: a"],
            ["eng: a", "rel:is_derived_from", "eng: root"],
            ["eng: root", "rel:has_derived_form", "eng: b"],
        )
    )
    graph = project_assertions(assertions)
    first = graph["eng: root"]["eng: a"]
    second = graph["eng: root"]["eng: b"]
    assert first["assertion_ids"] == (1, 2)
    assert second["assertion_ids"] == (3,)
    assert first["assertion_count"] == 2
    assert second["assertion_count"] == 1
    assert second["raw_relationship_counts"] == {"rel:has_derived_form": 1}
    first["raw_relationship_counts"]["rel:has_derived_form"] = 100
    assert second["raw_relationship_counts"] == {"rel:has_derived_form": 1}
    assert project_assertions(assertions)["eng: root"]["eng: a"][
        "raw_relationship_counts"
    ] == {"rel:has_derived_form": 1, "rel:is_derived_from": 1}


@pytest.mark.parametrize(
    ("relationship", "canonical"),
    [
        ("rel:etymology", "rel:etymological_origin_of"),
        ("rel:is_derived_from", "rel:has_derived_form"),
        ("rel:derived", "rel:has_derived_form"),
    ],
)
def test_inverse_only_evidence_is_reversed_once(relationship, canonical):
    assertions = prepare_assertions(
        frame(["eng: leaf", relationship, "lat: Category: root"])
    )
    normalized = project_assertions(assertions)
    assert list(normalized.edges) == [("lat: Category: root", "eng: leaf")]
    assert normalized.nodes["lat: Category: root"] == {
        "language": "lat",
        "word": "Category: root",
    }
    assert normalized["lat: Category: root"]["eng: leaf"] == {
        "relationship_types": (canonical,),
        "assertion_count": 1,
        "raw_relationship_counts": {relationship: 1},
        "assertion_ids": (1,),
    }
    assert len(project_assertions(assertions, "root_only")) == 0


def test_root_only_keeps_only_forward_evidence():
    assertions = prepare_assertions(
        frame(
            ["eng: root", "rel:has_derived_form", "eng: leaf"],
            ["eng: leaf", "rel:is_derived_from", "eng: root"],
            ["eng: root", "rel:etymological_origin_of", "eng: other"],
        )
    )
    graph = project_assertions(assertions, "root_only")
    assert set(graph.edges) == {
        ("eng: root", "eng: leaf"),
        ("eng: root", "eng: other"),
    }
    assert graph["eng: root"]["eng: leaf"]["assertion_count"] == 1
    assert graph["eng: root"]["eng: leaf"]["assertion_ids"] == (1,)


@pytest.mark.parametrize("policy", ["root_only", "normalized"])
def test_symmetric_and_unknown_relations_do_not_introduce_nodes(policy):
    assertions = prepare_assertions(
        frame(
            *(
                ["eng: a", relationship, "eng: b"]
                for relationship in [
                    "rel:etymologically_related",
                    "rel:etymologically",
                    "rel:variant:orthography",
                    "rel:unknown",
                ]
            )
        )
    )
    assert len(assertions) == 4
    assert len(project_assertions(assertions, policy)) == 0


@pytest.mark.parametrize("policy", ["root_only", "normalized"])
def test_cycles_and_self_loops_survive(policy):
    assertions = prepare_assertions(
        frame(
            ["eng: a", "rel:has_derived_form", "eng: b"],
            ["eng: b", "rel:has_derived_form", "eng: a"],
            ["eng: c", "rel:has_derived_form", "eng: c"],
        )
    )
    graph = project_assertions(assertions, policy)
    assert set(graph.edges) == {
        ("eng: a", "eng: b"),
        ("eng: b", "eng: a"),
        ("eng: c", "eng: c"),
    }
    assert not nx.is_directed_acyclic_graph(graph)


@pytest.mark.parametrize("policy", ["root_only", "normalized"])
def test_semantics_and_insertion_order_are_independent_of_record_order(policy):
    raw = frame(
        ["eng: b", "rel:has_derived_form", "eng: c"],
        ["eng: a", "rel:etymological_origin_of", "eng: c"],
        ["eng: c", "rel:derived", "eng: a"],
        ["eng: a", "rel:has_derived_form", "eng: c"],
        ["eng: b", "rel:has_derived_form", "eng: c"],
    )
    assertions = prepare_assertions(raw)
    original = project_assertions(assertions, policy)
    shuffled_prepared = project_assertions(assertions.iloc[::-1], policy)
    assert list(original.nodes(data=True)) == list(shuffled_prepared.nodes(data=True))
    assert list(original.edges(data=True)) == list(shuffled_prepared.edges(data=True))

    reordered_input = project_assertions(prepare_assertions(raw.iloc[::-1]), policy)
    assert list(original.nodes(data=True)) == list(reordered_input.nodes(data=True))
    assert list(original.edges) == list(reordered_input.edges)
    for source, target, attrs in original.edges(data=True):
        other_attrs = reordered_input[source][target]
        assert {
            key: value for key, value in attrs.items() if key != "assertion_ids"
        } == {
            key: value for key, value in other_attrs.items() if key != "assertion_ids"
        }


def test_invalid_policy_has_clear_error():
    with pytest.raises(ValueError, match="policy must be 'root_only' or 'normalized'"):
        project_assertions(prepare_assertions(frame()), "unknown")


def test_raw_input_is_not_mistaken_for_prepared_assertions():
    with pytest.raises(ValueError, match="Missing assertion columns"):
        project_assertions(frame())


def test_projection_rejects_duplicate_columns():
    assertions = prepare_assertions(frame())
    assertions = pd.concat([assertions, assertions[["assertion_id"]]], axis=1)
    with pytest.raises(ValueError, match="Column names must be unique"):
        project_assertions(assertions)
