"""Independently specified query meanings and NetworkX differential checks."""

import copy
import random

import networkx as nx
import pytest

from polyphasia.assertions import prepare_assertions, project_assertions
from polyphasia.loader import load_to_pandas
from polyphasia.queries import (
    ancestor_subgraph,
    component_subgraph,
    condensation_graph,
    cycle_examples,
    cyclic_nodes,
    descendant_subgraph,
    language_nodes,
    root_family_subgraph,
)

SELECTIONS = [
    ancestor_subgraph,
    descendant_subgraph,
    root_family_subgraph,
    component_subgraph,
]


@pytest.fixture
def family_graph():
    graph = nx.DiGraph(
        [
            ("root1", "middle"),
            ("root2", "middle"),
            ("middle", "eng: seed"),
            ("eng: seed", "child"),
            ("root1", "sibling"),
            ("root2", "other sibling"),
            ("unrelated root", "sibling"),
            ("cycle1", "cycle2"),
            ("cycle2", "cycle1"),
            ("cycle2", "cycle child"),
            ("self", "self"),
        ]
    )
    graph.add_node("isolated")
    return graph


def test_query_meanings_differ_on_multiple_roots_siblings_and_weak_connections(
    family_graph,
):
    seeds = ["eng: seed"]
    assert set(ancestor_subgraph(family_graph, seeds)) == {
        "root1",
        "root2",
        "middle",
        "eng: seed",
    }
    assert set(descendant_subgraph(family_graph, seeds)) == {"eng: seed", "child"}
    family = {
        "root1",
        "root2",
        "middle",
        "eng: seed",
        "child",
        "sibling",
        "other sibling",
    }
    assert set(root_family_subgraph(family_graph, seeds)) == family
    assert set(component_subgraph(family_graph, seeds)) == family | {"unrelated root"}


def test_rootless_cycles_remain_available_to_reachability_queries(family_graph):
    assert set(ancestor_subgraph(family_graph, ["cycle1"])) == {"cycle1", "cycle2"}
    assert set(descendant_subgraph(family_graph, ["cycle1"])) == {
        "cycle1",
        "cycle2",
        "cycle child",
    }
    assert set(component_subgraph(family_graph, ["cycle1"])) == {
        "cycle1",
        "cycle2",
        "cycle child",
    }
    assert len(root_family_subgraph(family_graph, ["cycle1"])) == 0
    assert len(root_family_subgraph(family_graph, ["self"])) == 0


def test_root_reaching_a_cycle_includes_cycle_in_root_family(family_graph):
    family_graph.add_edge("cycle root", "cycle1")
    selected = root_family_subgraph(family_graph, ["cycle2"])
    assert set(selected) == {"cycle root", "cycle1", "cycle2", "cycle child"}
    assert ("cycle1", "cycle2") in selected.edges
    assert ("cycle2", "cycle1") in selected.edges


@pytest.mark.parametrize("selection", SELECTIONS)
def test_isolated_seeds_are_inclusive_and_generators_and_duplicates_work(
    family_graph, selection
):
    assert set(selection(family_graph, (seed for seed in ["isolated"] * 2))) == {
        "isolated"
    }
    expected = set(selection(family_graph, ["eng: seed", "isolated"]))
    assert (
        set(selection(family_graph, (seed for seed in ["eng: seed", "isolated"] * 2)))
        == expected
    )


@pytest.mark.parametrize("selection", SELECTIONS)
def test_empty_seeds_produce_empty_views(family_graph, selection):
    selected = selection(family_graph, iter(()))
    assert len(selected) == 0
    assert nx.is_frozen(selected)


@pytest.mark.parametrize("selection", SELECTIONS)
def test_unknown_seed_is_rejected_even_after_a_valid_seed(family_graph, selection):
    with pytest.raises(nx.NodeNotFound, match="missing"):
        selection(family_graph, iter(["eng: seed", "missing"]))


@pytest.mark.parametrize("selection", SELECTIONS)
def test_empty_graph_and_missing_seed(selection):
    graph = nx.DiGraph()
    assert len(selection(graph, [])) == 0
    with pytest.raises(nx.NodeNotFound):
        selection(graph, ["missing"])


def test_language_selection_matches_only_exact_label_prefixes():
    graph = nx.Graph()
    graph.add_nodes_from(
        [
            "eng: word",
            "eng: Category: word",
            "england: word",
            "eng:missing space",
            "eng",
            "p_gem: word",
            1,
            ("eng", "word"),
        ]
    )
    graph.nodes["england: word"]["language"] = "eng"
    assert language_nodes(graph) == {"eng: word", "eng: Category: word"}
    assert language_nodes(graph, "p_gem") == {"p_gem: word"}
    assert language_nodes(graph, "eng: Category") == set()
    assert language_nodes(graph, "missing") == set()


def test_component_selection_accepts_undirected_graphs():
    graph = nx.Graph([(0, 1), (2, 3)])
    graph.add_node(4)
    selected = component_subgraph(graph, [1, 3])
    assert not selected.is_directed()
    assert set(selected) == {0, 1, 2, 3}
    assert set(component_subgraph(graph, [4])) == {4}


@pytest.mark.parametrize(
    "query",
    [ancestor_subgraph, descendant_subgraph, root_family_subgraph],
)
def test_directed_selections_reject_undirected_graphs(query):
    with pytest.raises(nx.NetworkXNotImplemented, match="directed graph"):
        query(nx.Graph(), [])


@pytest.mark.parametrize("query", [cyclic_nodes, condensation_graph, cycle_examples])
def test_cycle_utilities_reject_undirected_graphs(query):
    with pytest.raises(nx.NetworkXNotImplemented, match="directed graph"):
        query(nx.Graph())


@pytest.mark.parametrize("selection", SELECTIONS)
def test_views_preserve_assertion_evidence_and_source_graph(selection, tmp_path):
    source = tmp_path / "evidence.tsv"
    source.write_text(
        "lat: root\trel:has_derived_form\teng: seed\n"
        "eng: seed\trel:is_derived_from\tlat: root\n"
        "eng: seed\trel:has_derived_form\teng: child\n",
        encoding="utf-8",
    )
    graph = project_assertions(prepare_assertions(load_to_pandas(source)))
    before = copy.deepcopy(graph)
    selected = selection(graph, ["lat: root", "eng: seed"])
    assert selected is not graph
    assert selected.is_directed()
    assert nx.is_frozen(selected)
    assert selected.graph == {"policy": "normalized", "policy_version": "1"}
    assert selected.nodes["eng: seed"] == {"language": "eng", "word": "seed"}
    assert selected["lat: root"]["eng: seed"] == {
        "relationship_types": ("rel:has_derived_form",),
        "assertion_count": 2,
        "raw_relationship_counts": {
            "rel:has_derived_form": 1,
            "rel:is_derived_from": 1,
        },
        "assertion_ids": (1, 2),
    }
    assert selected["lat: root"]["eng: seed"] is graph["lat: root"]["eng: seed"]
    assert list(graph.nodes(data=True)) == list(before.nodes(data=True))
    assert list(graph.edges(data=True)) == list(before.edges(data=True))
    assert graph.graph == before.graph


def test_cycle_diagnosis_and_condensation_preserve_original_graph(family_graph):
    family_graph.edges["cycle1", "cycle2"]["assertion_ids"] = (42,)
    before = copy.deepcopy(family_graph)
    assert cyclic_nodes(family_graph) == {"cycle1", "cycle2", "self"}
    summary = condensation_graph(family_graph)
    assert nx.is_directed_acyclic_graph(summary)
    mapping = summary.graph["mapping"]
    assert set(mapping) == set(family_graph)
    assert mapping["cycle1"] == mapping["cycle2"]
    assert summary.nodes[mapping["cycle1"]]["members"] == {"cycle1", "cycle2"}
    assert summary.nodes[mapping["self"]]["members"] == {"self"}
    assert set(summary.edges) == {
        (mapping[source], mapping[target])
        for source, target in family_graph.edges
        if mapping[source] != mapping[target]
    }
    assert all(not attrs for _, _, attrs in summary.edges(data=True))
    assert list(family_graph.nodes(data=True)) == list(before.nodes(data=True))
    assert list(family_graph.edges(data=True)) == list(before.edges(data=True))


def test_empty_cycle_utilities():
    graph = nx.DiGraph()
    assert cyclic_nodes(graph) == set()
    assert len(condensation_graph(graph)) == 0
    assert condensation_graph(graph).graph["mapping"] == {}
    assert cycle_examples(graph) == []


def test_cycle_examples_obey_count_and_length_bounds():
    graph = nx.DiGraph([(0, 0), (1, 2), (2, 1), (3, 4), (4, 5), (5, 3), (5, 6), (6, 3)])
    assert cycle_examples(graph, limit=0) == []
    assert cycle_examples(graph, limit=10, max_length=1) == [[0]]
    cycles = cycle_examples(graph, limit=10, max_length=2)
    assert {frozenset(cycle) for cycle in cycles} == {frozenset({0}), frozenset({1, 2})}
    limited = cycle_examples(graph, limit=2, max_length=4)
    assert len(limited) == 2
    for cycle in limited:
        assert 1 <= len(cycle) <= 4
        assert len(cycle) == len(set(cycle))
        assert all(
            graph.has_edge(source, target)
            for source, target in zip(cycle, cycle[1:] + cycle[:1])
        )


@pytest.mark.parametrize("limit", [-1, 1.5, True, "2"])
def test_cycle_examples_reject_invalid_limits(limit):
    with pytest.raises(ValueError, match="limit must be a nonnegative integer"):
        cycle_examples(nx.DiGraph(), limit=limit)


@pytest.mark.parametrize("max_length", [0, -1, 1.5, True, "2"])
def test_cycle_examples_reject_invalid_length_bounds(max_length):
    with pytest.raises(ValueError, match="max_length must be a positive integer"):
        cycle_examples(nx.DiGraph(), max_length=max_length)


@pytest.mark.parametrize("acyclic", [False, True])
@pytest.mark.parametrize("random_seed", range(8))
def test_queries_match_networkx_on_small_generated_graphs(acyclic, random_seed):
    rng = random.Random(random_seed)
    graph = nx.DiGraph()
    graph.add_nodes_from(range(9))
    graph.add_edges_from(
        (source, target)
        for source in graph
        for target in graph
        if (not acyclic or source < target) and rng.random() < 0.2
    )
    seeds = set(rng.sample(list(graph), 3))
    expected_ancestors = seeds | set().union(
        *(nx.ancestors(graph, seed) for seed in seeds)
    )
    expected_descendants = seeds | set().union(
        *(nx.descendants(graph, seed) for seed in seeds)
    )
    expected_family = set()
    for root in graph:
        if graph.in_degree(root) == 0 and any(
            nx.has_path(graph, root, seed) for seed in seeds
        ):
            expected_family.add(root)
            expected_family.update(nx.descendants(graph, root))
    expected_components = set().union(
        *(
            component
            for component in nx.weakly_connected_components(graph)
            if component & seeds
        )
    )
    assert set(ancestor_subgraph(graph, seeds)) == expected_ancestors
    assert set(descendant_subgraph(graph, seeds)) == expected_descendants
    assert set(root_family_subgraph(graph, seeds)) == expected_family
    assert set(component_subgraph(graph, seeds)) == expected_components
    expected_cyclic = set().union(*(set(cycle) for cycle in nx.simple_cycles(graph)))
    assert cyclic_nodes(graph) == expected_cyclic
    assert nx.is_directed_acyclic_graph(condensation_graph(graph))
