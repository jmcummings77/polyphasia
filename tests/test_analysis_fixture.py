"""Hand-specified contracts for the synthetic analysis input, not its metrics code."""

import hashlib
from collections import Counter
from pathlib import Path

import pytest

from polyphasia.assertions import prepare_assertions, project_assertions
from polyphasia.audit import audit_assertions
from polyphasia.loader import load_to_pandas
from polyphasia.queries import (
    ancestor_subgraph,
    component_subgraph,
    cyclic_nodes,
    descendant_subgraph,
    language_nodes,
    root_family_subgraph,
)

SOURCE = Path(__file__).resolve().parents[1] / "examples" / "analysis-fixture.tsv"
SOURCE_SHA256 = "74a6e1421bfb78260cb7b9a2e400a2c27e7d86adf9b82c6175d725a53de790a3"
NORMALIZED_EDGES = {
    ("lat: exemplum", "eng: example"),
    ("lat: exemplum", "fra: exemple"),
    ("eng: example", "eng: examples"),
    ("grc: παράδειγμα", "eng: example"),
    ("deu: Quelle", "fra: exemple"),
    ("eng: examples", "eng: example-set"),
    ("p_gem: synthetic-root", "eng: orphan"),
    ("fra: café", "eng: cafe"),
    ("fra: café", "fra: cafés"),
    ("eng: loop-a", "deu: loop-b"),
    ("deu: loop-b", "eng: loop-a"),
    ("deu: loop-b", "eng: loop-leaf"),
    ("eng: mirror", "eng: mirror"),
    ("eng: mirror", "fra: reflet"),
    ("eng: -ness", "eng: kindness"),
    ("eng: -ness", "eng: darkness"),
    ("eng: -ness", "eng: plainness"),
    ("eng: -ness", "fra: synthetic-ness"),
    ("eng: un-", "eng: unkind"),
    ("eng: un-", "eng: unclear"),
    ("eng: un-", "eng: undone"),
    ("eng: kind", "eng: kindness"),
    ("lat: origo", "ita: esempio"),
    ("eng: NA", 'eng: "quoted"'),
}
INVERSE_ONLY_EDGES = {
    ("p_gem: synthetic-root", "eng: orphan"),
    ("fra: café", "eng: cafe"),
}
CYCLIC_NODES = {"eng: loop-a", "deu: loop-b", "eng: mirror"}


@pytest.fixture
def assertions():
    return prepare_assertions(load_to_pandas(SOURCE))


def test_fixture_bytes_raw_labels_and_alias_identity_are_pinned(assertions):
    contents = SOURCE.read_bytes()
    assert len(contents) == 1743
    assert hashlib.sha256(contents).hexdigest() == SOURCE_SHA256
    assert len(assertions) == 37
    assert assertions.assertion_id.tolist() == list(range(1, 38))
    raw_nodes = set(assertions.source_node) | set(assertions.target_node)
    assert len(raw_nodes) == 36
    assert Counter(node.partition(": ")[0] for node in raw_nodes) == {
        "deu": 2,
        "eng": 22,
        "fra": 5,
        "grc": 1,
        "ita": 2,
        "lat": 2,
        "p_gem": 1,
        "spa": 1,
    }
    alias_rows = assertions.loc[
        assertions.edge_type != assertions.normalized_edge_type, "assertion_id"
    ]
    assert alias_rows.tolist() == [13, 23]
    assert assertions.iloc[-1].source_word == "NA"
    assert assertions.iloc[-1].target_word == '"quoted"'


@pytest.mark.parametrize("policy", ["root_only", "normalized"])
def test_projection_topology_matches_independently_enumerated_edges(assertions, policy):
    graph = project_assertions(assertions, policy)
    expected = NORMALIZED_EDGES
    if policy == "root_only":
        expected = expected - INVERSE_ONLY_EDGES

    assert set(graph.edges) == expected
    assert set(graph) == {node for edge in expected for node in edge}
    assert cyclic_nodes(graph) == CYCLIC_NODES
    assert sum(s in CYCLIC_NODES or t in CYCLIC_NODES for s, t in graph.edges) == 5


def test_fixture_audit_counts_have_hand_calculated_expectations(assertions):
    report = audit_assertions(assertions)
    source = report["input"]
    assert source["exact_duplicate_assertions"] == 1
    assert source["normalized_duplicate_assertions"] == 2
    assert source["alias_normalizations"] == 2
    assert source["unknown_relationship_counts"] == {"rel:unknown": 1}
    assert source["ordered_pairs_with_multiple_normalized_types"] == 3
    for policy, retained, nodes, edges, facts, seeds in [
        ("root_only", 25, 28, 22, 24, 17),
        ("normalized", 33, 31, 24, 26, 19),
    ]:
        projected = report["projections"][policy]
        assert projected["retained_assertions"] == retained
        assert projected["excluded_assertions"] == 37 - retained
        assert projected["nodes"] == nodes
        assert projected["edges"] == edges
        assert projected["canonical_relationship_facts"] == facts
        assert projected["node_languages"]["eng"] == seeds
        assert projected["pairs_with_multiple_relationship_types"] == 2
        assert projected["strongly_connected_components"]["cyclic_count"] == 2
    origin = report["inverse_coverage"]["rel:etymological_origin_of"]
    assert (origin["unique_forward_pairs"], origin["unique_inverse_pairs"]) == (7, 5)
    assert (origin["matched_pairs"], origin["inverse_only_pairs"]) == (4, 1)
    derivation = report["inverse_coverage"]["rel:has_derived_form"]
    assert (derivation["unique_forward_pairs"], derivation["unique_inverse_pairs"]) == (
        17,
        3,
    )
    assert (derivation["matched_pairs"], derivation["inverse_only_pairs"]) == (2, 1)


def test_parallel_types_preserve_traceable_record_evidence(assertions):
    graph = project_assertions(assertions)
    edge = graph["eng: example"]["eng: examples"]

    assert edge["assertion_ids"] == (4, 5, 6, 7, 8)
    assert edge["assertion_count"] == 5
    assert edge["relationship_types"] == (
        "rel:etymological_origin_of",
        "rel:has_derived_form",
    )
    assert edge["raw_relationship_counts"] == {
        "rel:etymological_origin_of": 1,
        "rel:etymology": 1,
        "rel:has_derived_form": 2,
        "rel:is_derived_from": 1,
    }
    fact_counts = Counter(
        kind
        for _, _, data in graph.edges(data=True)
        for kind in data["relationship_types"]
    )
    assert fact_counts == {
        "rel:etymological_origin_of": 8,
        "rel:has_derived_form": 18,
    }


@pytest.mark.parametrize("policy", ["root_only", "normalized"])
def test_trace_target_exposes_ancestor_family_and_component_differences(
    assertions, policy
):
    graph = project_assertions(assertions, policy)
    seed = {"eng: examples"}
    ancestors = {"lat: exemplum", "grc: παράδειγμα", "eng: example", "eng: examples"}
    family = ancestors | {"fra: exemple", "eng: example-set"}
    component = family | {"deu: Quelle"}

    for query, expected, edge_count in [
        (ancestor_subgraph, ancestors, 3),
        (descendant_subgraph, {"eng: examples", "eng: example-set"}, 1),
        (root_family_subgraph, family, 5),
        (component_subgraph, component, 6),
    ]:
        result = query(graph, seed)
        assert set(result) == expected
        assert result.number_of_edges() == edge_count


@pytest.mark.parametrize("policy", ["root_only", "normalized"])
def test_rootless_trace_includes_an_acyclic_seed(assertions, policy):
    graph = project_assertions(assertions, policy)
    seed = {"eng: loop-leaf"}
    expected = seed | {"eng: loop-a", "deu: loop-b"}

    assert "eng: loop-leaf" not in cyclic_nodes(graph)
    assert set(root_family_subgraph(graph, seed)) == set()
    assert set(descendant_subgraph(graph, seed)) == seed
    for query in (ancestor_subgraph, component_subgraph):
        result = query(graph, seed)
        assert set(result) == expected
        assert result.number_of_edges() == 3


@pytest.mark.parametrize(
    "policy, expected_counts",
    [
        ("root_only", [(20, 16, 17), (20, 16, 17), (18, 14, 14), (24, 20, 17)]),
        ("normalized", [(24, 18, 19), (22, 16, 19), (23, 17, 16), (29, 23, 19)]),
    ],
)
def test_all_english_queries_use_their_own_graph_seed_denominator(
    assertions, policy, expected_counts
):
    graph = project_assertions(assertions, policy)
    seeds = language_nodes(graph)

    for query, expected in zip(
        (
            ancestor_subgraph,
            descendant_subgraph,
            root_family_subgraph,
            component_subgraph,
        ),
        expected_counts,
        strict=True,
    ):
        result = query(graph, seeds)
        assert (
            len(result),
            result.number_of_edges(),
            len(seeds & set(result)),
        ) == expected
    assert seeds - set(root_family_subgraph(graph, seeds)) == {
        "eng: loop-a",
        "eng: loop-leaf",
        "eng: mirror",
    }


def test_affix_fanout_is_an_explicit_synthetic_ranking_example(assertions):
    graph = project_assertions(assertions)

    assert graph.out_degree("eng: -ness") == 4
    assert graph.out_degree("eng: un-") == 3
    assert (
        max(
            degree
            for node, degree in graph.out_degree
            if node not in {"eng: -ness", "eng: un-"}
        )
        == 2
    )
