"""Small, self-contained graph contracts; no downloaded dataset is required."""

import networkx as nx
import pandas as pd
import pytest

from polyphasia.constants import EDGE_ATTRIBUTES, EDGE_LIST_COLUMN_NAMES
from polyphasia.graph import DirectedGraph, UndirectedGraph


def edge_frame(*edges):
    """Build parsed rows independently of the loader under test elsewhere."""
    rows = []
    for source, target in edges:
        source_language, source_word = source.split(": ", 1)
        target_language, target_word = target.split(": ", 1)
        rows.append(
            {
                "source_node": source,
                "target_node": target,
                "edge_type": "rel:has_derived_form",
                "source_language": source_language,
                "source_word": source_word,
                "target_language": target_language,
                "target_word": target_word,
            }
        )
    columns = list(dict.fromkeys(EDGE_LIST_COLUMN_NAMES + EDGE_ATTRIBUTES))
    return pd.DataFrame(rows, columns=columns)


@pytest.mark.parametrize("graph_type", [DirectedGraph, UndirectedGraph])
def test_one_edge_preserves_attributes_and_expected_direction(graph_type):
    frame = edge_frame(("lat: radix", "eng: root"))
    graph = graph_type(frame)
    subgraph = graph.language_subgraph("eng")

    assert set(subgraph.nodes) == {"lat: radix", "eng: root"}
    assert subgraph.number_of_edges() == 1
    assert subgraph.has_edge("lat: radix", "eng: root")
    assert subgraph.is_directed() is (graph_type is DirectedGraph)
    assert subgraph.has_edge("eng: root", "lat: radix") is (
        graph_type is UndirectedGraph
    )
    assert subgraph.edges["lat: radix", "eng: root"] == {
        name: frame.loc[0, name] for name in EDGE_ATTRIBUTES
    }
    assert "2 nodes and 1 edges" in graph.info
    assert graph.subgraph_info(subgraph) == str(subgraph)


@pytest.mark.parametrize("graph_type", [DirectedGraph, UndirectedGraph])
def test_empty_frame_and_unmatched_language_return_empty_graphs(graph_type):
    graph = graph_type(edge_frame())
    assert graph.language_nodes() == []
    assert len(graph.language_subgraph()) == 0
    assert graph.nodes_by_degree(graph.language_subgraph()) == []

    graph = graph_type(edge_frame(("lat: radix", "eng: root")))
    assert len(graph.language_subgraph("fra")) == 0
    assert len(graph.language_subgraph(nodes=[])) == 0


def test_dag_roots_and_longest_path():
    graph = DirectedGraph(
        edge_frame(
            ("lat: a", "eng: b"),
            ("eng: b", "eng: c"),
            ("eng: c", "eng: d"),
            ("lat: a", "fra: sibling"),
            ("deu: other", "ita: other"),
        )
    )

    assert graph.is_dag is True
    assert graph.get_cycles() == []
    assert set(graph.roots()) == {"lat: a", "deu: other"}
    assert graph.get_longest_path() == ["lat: a", "eng: b", "eng: c", "eng: d"]


def test_cycles_are_reported_and_removal_deletes_all_cycle_nodes():
    graph = DirectedGraph(
        edge_frame(
            ("lat: a", "eng: b"),
            ("eng: b", "lat: a"),
            ("eng: b", "eng: tail"),
            ("deu: loop", "deu: loop"),
            ("fra: root", "fra: leaf"),
        )
    )

    assert graph.is_dag is False
    assert {frozenset(cycle) for cycle in graph.get_cycles()} == {
        frozenset({"lat: a", "eng: b"}),
        frozenset({"deu: loop"}),
    }
    with pytest.raises(nx.NetworkXUnfeasible):
        graph.get_longest_path()

    graph.remove_cycles()

    assert graph.is_dag is True
    assert graph.get_cycles() == []
    assert set(graph.roots()) == {"eng: tail", "fra: root"}
    assert graph.get_longest_path() == ["fra: root", "fra: leaf"]
    assert set(graph.language_subgraph("eng")) == {"eng: tail"}


def test_directed_language_family_includes_root_and_other_language_branches():
    graph = DirectedGraph(
        edge_frame(
            ("lat: root", "eng: child"),
            ("lat: root", "fra: sibling"),
            ("eng: child", "ita: descendant"),
            ("deu: unrelated", "spa: unrelated"),
        )
    )
    expected_nodes = {"lat: root", "eng: child", "fra: sibling", "ita: descendant"}

    assert graph.language_nodes("eng") == [expected_nodes]
    subgraph = graph.language_subgraph("eng")
    assert set(subgraph) == expected_nodes
    assert set(subgraph.edges) == {
        ("lat: root", "eng: child"),
        ("lat: root", "fra: sibling"),
        ("eng: child", "ita: descendant"),
    }
    assert graph.language_nodes("lat") == [expected_nodes]
    assert graph.language_nodes("eng", roots=["deu: unrelated"]) == []
    assert graph.language_nodes("eng", roots=[]) == []


def test_directed_language_selection_omits_rootless_components_unless_seeded():
    graph = DirectedGraph(edge_frame(("eng: a", "fra: b"), ("fra: b", "eng: a")))

    assert graph.roots() == []
    assert graph.language_nodes("eng") == []
    assert graph.language_nodes("eng", roots=["fra: b"]) == [{"eng: a", "fra: b"}]


def test_self_loop_has_no_root_but_can_be_selected_explicitly():
    graph = DirectedGraph(edge_frame(("eng: loop", "eng: loop")))

    assert graph.is_dag is False
    assert graph.get_cycles() == [["eng: loop"]]
    assert graph.roots() == []
    assert graph.language_nodes("eng") == []
    assert graph.language_subgraph("eng").number_of_nodes() == 0
    assert graph.language_nodes("eng", roots=["eng: loop"]) == [{"eng: loop"}]


def test_directed_explicit_node_sets_are_used_without_expansion():
    graph = DirectedGraph(
        edge_frame(("lat: root", "eng: child"), ("eng: child", "fra: leaf"))
    )
    subgraph = graph.language_subgraph("missing", nodes=[{"lat: root"}, {"eng: child"}])

    assert set(subgraph) == {"lat: root", "eng: child"}
    assert set(subgraph.edges) == {("lat: root", "eng: child")}


@pytest.mark.parametrize("graph_type", [DirectedGraph, UndirectedGraph])
@pytest.mark.parametrize("language", ["en", "ine-pro", "eng"])
def test_language_matching_uses_the_complete_variable_length_token(
    graph_type, language
):
    graph = graph_type(
        edge_frame(
            (f"{language}: word", "lat: root"),
            (f"{language}-other: word", "deu: other"),
        )
    )

    assert set(graph.language_subgraph(language)) == {
        f"{language}: word",
        "lat: root",
    }


def test_undirected_language_selection_expands_seeds_to_connected_components():
    graph = UndirectedGraph(
        edge_frame(
            ("lat: root", "eng: child"),
            ("lat: root", "fra: sibling"),
            ("eng: child", "ita: descendant"),
            ("deu: unrelated", "spa: unrelated"),
        )
    )
    family = {"lat: root", "eng: child", "fra: sibling", "ita: descendant"}

    assert graph.language_nodes("eng") == ["eng: child"]
    assert {frozenset(nodes) for nodes in graph.connected_components} == {
        frozenset(family),
        frozenset({"deu: unrelated", "spa: unrelated"}),
    }
    assert set(graph.language_subgraph("eng")) == family
    assert set(graph.language_subgraph("missing", nodes=["fra: sibling"])) == family


@pytest.mark.parametrize("graph_type", [DirectedGraph, UndirectedGraph])
def test_degree_ordering_returns_pairs_in_descending_order_with_stable_ties(
    graph_type,
):
    graph = graph_type(
        edge_frame(
            ("lat: root", "eng: center"),
            ("eng: center", "eng: leaf1"),
            ("eng: center", "eng: leaf2"),
        )
    )

    assert graph.nodes_by_degree(graph.language_subgraph()) == [
        ("eng: center", 3),
        ("lat: root", 1),
        ("eng: leaf1", 1),
        ("eng: leaf2", 1),
    ]


@pytest.mark.parametrize("graph_type", [DirectedGraph, UndirectedGraph])
def test_language_subgraph_is_a_view_with_shared_edge_attributes(graph_type):
    graph = graph_type(edge_frame(("lat: radix", "eng: root")))
    subgraph = graph.language_subgraph()
    subgraph.edges["lat: radix", "eng: root"]["edge_type"] = "changed"

    assert graph.language_subgraph().edges["lat: radix", "eng: root"] == (
        subgraph.edges["lat: radix", "eng: root"]
    )
    with pytest.raises(nx.NetworkXError):
        subgraph.add_node("eng: extra")


def test_root_family_union_matches_explicit_overlapping_families():
    graph = DirectedGraph(
        edge_frame(
            ("lat: first", "eng: shared"),
            ("deu: second", "eng: shared"),
            ("lat: first", "fra: sibling"),
            ("eng: shared", "ita: child"),
            ("eng: isolated-cycle", "eng: isolated-cycle"),
        )
    )
    explicit = graph.language_subgraph(nodes=graph.language_nodes("eng"))
    optimized = graph.language_subgraph("eng")
    assert set(optimized) == {
        "lat: first",
        "deu: second",
        "eng: shared",
        "fra: sibling",
        "ita: child",
    }
    assert dict(optimized.nodes(data=True)) == dict(explicit.nodes(data=True))
    assert dict(optimized.edges) == dict(explicit.edges)


def test_cycle_removal_does_not_enumerate_cycles(monkeypatch):
    graph = DirectedGraph(
        edge_frame(
            ("eng: a", "eng: b"),
            ("eng: b", "eng: a"),
            ("eng: b", "eng: tail"),
            ("eng: self", "eng: self"),
        )
    )

    def enumeration_is_unnecessary():
        raise AssertionError("Removal must use cyclic membership, not all cycles")

    monkeypatch.setattr(graph, "get_cycles", enumeration_is_unnecessary)
    graph.remove_cycles()
    assert graph.roots() == ["eng: tail"]
    assert graph.is_dag


def test_undirected_selection_accepts_repeated_seeds_without_repeated_components():
    graph = UndirectedGraph(
        edge_frame(
            ("lat: root", "eng: one"),
            ("eng: one", "eng: two"),
            ("fra: other", "fra: leaf"),
        )
    )
    selected = graph.language_subgraph(nodes=["eng: one", "eng: one", "eng: two"])
    assert set(selected) == {"lat: root", "eng: one", "eng: two"}
    assert selected.number_of_edges() == 2


def test_undirected_wrapper_preserves_missing_seed_error_type():
    graph = UndirectedGraph(edge_frame(("lat: root", "eng: leaf")))
    with pytest.raises(nx.NetworkXError, match="missing"):
        graph.language_subgraph(nodes=["eng: leaf", "missing"])
