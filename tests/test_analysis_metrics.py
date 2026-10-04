"""Independent expected values for analytical comparisons and source traces."""

import hashlib
import json

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from polyphasia.analysis_metrics import analysis_parameters, analyze_assertions
from polyphasia.assertions import prepare_assertions
from polyphasia.constants import EDGE_LIST_COLUMN_NAMES

ORIGIN = "rel:etymological_origin_of"
DERIVATION = "rel:has_derived_form"


def assertions(*rows):
    return prepare_assertions(pd.DataFrame(rows, columns=EDGE_LIST_COLUMN_NAMES))


def fingerprint(nodes):
    return hashlib.sha256(
        json.dumps(sorted(nodes), ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


@pytest.fixture
def family_assertions():
    return assertions(
        ("lat: a", ORIGIN, "eng: seed"),
        ("lat: a", ORIGIN, "fra: sibling"),
        ("eng: seed", DERIVATION, "eng: child"),
        ("deu: b", ORIGIN, "fra: sibling"),
        ("eng: cycle", DERIVATION, "eng: cycle"),
        ("eng: cycle", DERIVATION, "eng: tail"),
        ("eng: hidden", "rel:etymologically_related", "eng: ignored"),
    )


def test_query_counts_denominators_languages_and_fingerprints(family_assertions):
    result = analyze_assertions(family_assertions)
    assert result["input"] == {"assertions": 7, "raw_language_nodes": 6}
    expected = {
        "ancestors": {
            "nodes": {"lat: a", "eng: seed", "eng: child", "eng: cycle", "eng: tail"},
            "edges": 4,
            "seeds_included": 4,
            "node_languages": {"eng": 4, "lat": 1},
        },
        "descendants": {
            "nodes": {"eng: seed", "eng: child", "eng: cycle", "eng: tail"},
            "edges": 3,
            "seeds_included": 4,
            "node_languages": {"eng": 4},
        },
        "root_families": {
            "nodes": {"lat: a", "eng: seed", "eng: child", "fra: sibling"},
            "edges": 3,
            "seeds_included": 2,
            "node_languages": {"eng": 2, "fra": 1, "lat": 1},
        },
        "components": {
            "nodes": {
                "lat: a",
                "eng: seed",
                "eng: child",
                "fra: sibling",
                "deu: b",
                "eng: cycle",
                "eng: tail",
            },
            "edges": 6,
            "seeds_included": 4,
            "node_languages": {"deu": 1, "eng": 4, "fra": 1, "lat": 1},
        },
    }
    for projection in result["projections"].values():
        assert projection["nodes"] == 7
        assert projection["edges"] == 6
        assert projection["seeds"] == 4
        assert projection["raw_language_nodes_excluded"] == 2
        for query, values in expected.items():
            assert projection["queries"][query] == {
                "nodes": len(values["nodes"]),
                "edges": values["edges"],
                "seeds_included": values["seeds_included"],
                "node_languages": values["node_languages"],
                "selected_nodes_sha256": fingerprint(values["nodes"]),
            }


def test_all_six_overlaps_and_differences_have_independent_expected_counts(
    family_assertions,
):
    result = analyze_assertions(family_assertions, policies=("normalized",))
    overlaps = result["projections"]["normalized"]["overlaps"]
    expected = [
        ("ancestors", "descendants", 4, 5, 1, 0),
        ("ancestors", "root_families", 3, 6, 2, 1),
        ("ancestors", "components", 5, 7, 0, 2),
        ("descendants", "root_families", 2, 6, 2, 2),
        ("descendants", "components", 4, 7, 0, 3),
        ("root_families", "components", 4, 7, 0, 3),
    ]
    assert len(overlaps) == len(expected)
    for row, (left, right, intersection, union, left_only, right_only) in zip(
        overlaps, expected
    ):
        assert row == {
            "left": left,
            "right": right,
            "intersection_nodes": intersection,
            "union_nodes": union,
            "left_only_nodes": left_only,
            "right_only_nodes": right_only,
            "jaccard": intersection / union,
        }


def test_rankings_split_types_in_same_combined_ancestor_selection():
    data = assertions(
        ("lat: -a", ORIGIN, "eng: x"),
        ("lat: -a", ORIGIN, "eng: x"),
        ("eng: x", "rel:etymology", "lat: -a"),
        ("lat: -a", DERIVATION, "eng: x"),
        ("lat: -a", ORIGIN, "eng: y"),
        ("lat: b-", ORIGIN, "eng: x"),
        ("lat: -a", ORIGIN, "fra: unselected sibling"),
        ("eng: x", DERIVATION, "eng: z"),
        ("eng: y", DERIVATION, "eng: z"),
    )
    projection = analyze_assertions(data, top_n=2)["projections"]["normalized"]
    rankings = projection["rankings"]
    assert rankings["scope"] == "ancestors"
    origin, derivation = rankings["word_origin"], rankings["derivation"]
    assert origin["facts"] == 3
    assert derivation["facts"] == 3
    assert origin["relationship_type"] == ORIGIN
    assert derivation["relationship_type"] == DERIVATION
    assert origin["out_degree"] == [
        {
            "node": "lat: -a",
            "language": "lat",
            "word": "-a",
            "neighbors": 2,
            "affix_like": True,
        },
        {
            "node": "lat: b-",
            "language": "lat",
            "word": "b-",
            "neighbors": 1,
            "affix_like": True,
        },
    ]
    assert [(row["node"], row["neighbors"]) for row in origin["in_degree"]] == [
        ("eng: x", 2),
        ("eng: y", 1),
    ]
    assert [(row["node"], row["neighbors"]) for row in derivation["out_degree"]] == [
        ("eng: x", 1),
        ("eng: y", 1),
    ]
    assert [(row["node"], row["neighbors"]) for row in derivation["in_degree"]] == [
        ("eng: z", 2),
        ("eng: x", 1),
    ]
    assert not any(row["affix_like"] for row in derivation["out_degree"])


def test_affix_heuristic_does_not_strip_words_and_zero_top_n_keeps_facts():
    data = assertions(
        ("lat:  -spaced ", ORIGIN, "eng: x"),
        ("lat: middle-hyphen", ORIGIN, "eng: y"),
    )
    ranking = analyze_assertions(data)["projections"]["normalized"]["rankings"][
        "word_origin"
    ]
    assert all(not row["affix_like"] for row in ranking["out_degree"])
    empty_top = analyze_assertions(data, top_n=0)["projections"]["normalized"][
        "rankings"
    ]["word_origin"]
    assert empty_top == {
        "relationship_type": ORIGIN,
        "facts": 2,
        "out_degree": [],
        "in_degree": [],
    }


def test_inverse_only_projection_changes_denominator_and_preserves_alias_evidence():
    data = assertions(("eng: leaf", "rel:derived", "lat: root"))
    result = analyze_assertions(data, trace_words=["eng: leaf"])
    root_only, normalized = (
        result["projections"]["root_only"],
        result["projections"]["normalized"],
    )
    assert root_only["nodes"] == 0
    assert root_only["seeds"] == 0
    assert root_only["raw_language_nodes_excluded"] == 1
    assert root_only["traces"][0]["status"] == "missing"
    assert normalized["seeds"] == 1
    assert normalized["raw_language_nodes_excluded"] == 0
    trace = normalized["traces"][0]
    assert trace["path"] == ["lat: root", "eng: leaf"]
    assert trace["status"] == "found"
    assert trace["distance"] == 1
    assert trace["edges"][0] == {
        "source_node": "lat: root",
        "target_node": "eng: leaf",
        "relationship_types": [DERIVATION],
        "assertion_count": 1,
        "evidence_sample": [
            {
                "assertion_id": 1,
                "source_node": "eng: leaf",
                "edge_type": "rel:derived",
                "target_node": "lat: root",
                "normalized_edge_type": "rel:is_derived_from",
                "reversed": True,
            }
        ],
        "evidence_truncated": False,
    }


def test_traces_find_nearest_root_and_break_equal_depth_ties_deterministically():
    data = assertions(
        ("lat: farther", ORIGIN, "lat: middle"),
        ("lat: middle", ORIGIN, "eng: leaf"),
        ("lat: z", ORIGIN, "eng: leaf"),
        ("lat: a", ORIGIN, "eng: leaf"),
    )
    traces = analyze_assertions(data, trace_words=["eng: leaf", "lat: a"])[
        "projections"
    ]["normalized"]["traces"]
    assert traces[0]["path"] == ["lat: a", "eng: leaf"]
    assert traces[0]["distance"] == 1
    assert traces[0]["edges"][0]["evidence_sample"][0]["assertion_id"] == 4
    assert traces[0]["edges"][0]["evidence_sample"][0]["reversed"] is False
    assert traces[1]["path"] == ["lat: a"]
    assert traces[1]["distance"] == 0
    assert traces[1]["edges"] == []


def test_cycle_and_downstream_leaf_have_rootless_status(family_assertions):
    traces = analyze_assertions(
        family_assertions,
        trace_words=["eng: cycle", "eng: tail", "eng: absent", "eng: child"],
    )["projections"]["normalized"]["traces"]
    by_word = {trace["word"]: trace for trace in traces}
    assert by_word["eng: absent"]["status"] == "missing"
    assert by_word["eng: absent"]["visited_nodes"] == 0
    assert by_word["eng: child"]["path"] == ["lat: a", "eng: seed", "eng: child"]
    for word in ("eng: cycle", "eng: tail"):
        assert by_word[word]["status"] == "rootless"
        assert by_word[word]["path"] == []
        assert by_word[word]["bounds_hit"] == []
    assert by_word["eng: tail"]["visited_nodes"] == 2


def test_root_reaching_cycle_produces_finite_shortest_trace():
    data = assertions(
        ("lat: root", ORIGIN, "eng: a"),
        ("eng: a", DERIVATION, "eng: b"),
        ("eng: b", DERIVATION, "eng: a"),
    )
    trace = analyze_assertions(data, trace_words=["eng: b"])["projections"][
        "normalized"
    ]["traces"][0]
    assert trace["status"] == "found"
    assert trace["path"] == ["lat: root", "eng: a", "eng: b"]


@pytest.mark.parametrize(
    ("options", "bound", "visited"),
    [
        ({"trace_max_depth": 0}, "max_depth", 1),
        ({"trace_max_depth": 1}, "max_depth", 2),
        ({"trace_max_nodes": 1}, "max_nodes", 1),
        ({"trace_max_nodes": 2}, "max_nodes", 2),
    ],
)
def test_trace_bounds_are_explicit_without_claiming_rootlessness(
    options, bound, visited
):
    data = assertions(
        ("lat: root", ORIGIN, "eng: middle"), ("eng: middle", DERIVATION, "eng: leaf")
    )
    trace = analyze_assertions(data, trace_words=["eng: leaf"], **options)[
        "projections"
    ]["normalized"]["traces"][0]
    assert trace["status"] == "bounded"
    assert trace["bounds_hit"] == [bound]
    assert trace["visited_nodes"] == visited
    assert trace["path"] == []
    assert trace["distance"] is None


def test_exact_bounds_allow_root_and_complete_rootless_diagnosis():
    rooted = assertions(("lat: root", ORIGIN, "eng: leaf"))
    trace = analyze_assertions(
        rooted, trace_words=["eng: leaf"], trace_max_depth=1, trace_max_nodes=2
    )["projections"]["normalized"]["traces"][0]
    assert trace["status"] == "found"
    cycle = assertions(
        ("eng: a", DERIVATION, "eng: b"), ("eng: b", DERIVATION, "eng: a")
    )
    trace = analyze_assertions(
        cycle, trace_words=["eng: a"], trace_max_depth=1, trace_max_nodes=2
    )["projections"]["normalized"]["traces"][0]
    assert trace["status"] == "rootless"


def test_trace_evidence_sample_is_bounded_but_total_counts_are_complete():
    data = assertions(*[("lat: root", ORIGIN, "eng: leaf")] * 7)
    edge = analyze_assertions(data, trace_words=["eng: leaf"])["projections"][
        "normalized"
    ]["traces"][0]["edges"][0]
    assert edge["assertion_count"] == 7
    assert edge["evidence_truncated"] is True
    assert [row["assertion_id"] for row in edge["evidence_sample"]] == [1, 2, 3, 4, 5]


def test_empty_and_absent_language_results_are_serializable():
    for data, language in (
        (assertions(), "eng"),
        (assertions(("lat: café", ORIGIN, "fra: café")), "eng"),
    ):
        report = analyze_assertions(
            data, language=language, trace_words=["eng: missing"]
        )
        assert json.loads(json.dumps(report, allow_nan=False)) == report
        for projection in report["projections"].values():
            assert projection["seeds"] == 0
            assert all(
                query["nodes"] == query["edges"] == 0
                for query in projection["queries"].values()
            )
            assert all(row["jaccard"] is None for row in projection["overlaps"])
            assert projection["traces"][0]["status"] == "missing"


def test_output_is_deterministic_without_mutating_assertion_table():
    data = assertions(
        ("lat: café", ORIGIN, "eng: word"),
        ("eng: word", "rel:derived", "lat: café"),
        ("eng: word", DERIVATION, "eng: words"),
    )
    data.index = [50, -1, 50]
    before = data.copy(deep=True)
    kwargs = {"trace_words": ["eng: words", "eng: word", "eng: word"]}
    expected = analyze_assertions(data, **kwargs)
    assert analyze_assertions(data, **kwargs) == expected
    assert analyze_assertions(data.iloc[::-1], **kwargs) == expected
    assert expected["parameters"]["trace_words"] == ["eng: word", "eng: words"]
    assert expected["projections"]["normalized"]["queries"]["ancestors"][
        "selected_nodes_sha256"
    ] == fingerprint(["lat: café", "eng: word", "eng: words"])
    assert_frame_equal(data, before)


@pytest.mark.parametrize(
    "options",
    [
        {"language": 4},
        {"language": ""},
        {"policies": ()},
        {"policies": ("normalized", "normalized")},
        {"policies": ("unknown",)},
        {"top_n": -1},
        {"top_n": True},
        {"trace_max_depth": -1},
        {"trace_max_depth": 1.5},
        {"trace_max_nodes": 0},
        {"trace_words": [5]},
    ],
)
def test_invalid_options_fail_clearly(options):
    with pytest.raises(ValueError):
        analyze_assertions(assertions(), **options)
    with pytest.raises(ValueError):
        analysis_parameters(**options)


def test_parameters_normalize_generators_before_loading_a_corpus():
    parameters = analysis_parameters(
        language="fra",
        policies=iter(["normalized"]),
        top_n=3,
        trace_words=iter(["fra: z", "fra: a", "fra: z"]),
        trace_max_depth=0,
        trace_max_nodes=1,
    )
    assert parameters == {
        "language": "fra",
        "policies": ["normalized"],
        "top_n": 3,
        "trace_words": ["fra: a", "fra: z"],
        "trace_max_depth": 0,
        "trace_max_nodes": 1,
        "trace_evidence_limit": 5,
    }
    arguments = {
        key: value for key, value in parameters.items() if key != "trace_evidence_limit"
    }
    assert analyze_assertions(assertions(), **arguments)["parameters"] == parameters
