"""Explicit graph selections and non-destructive cycle diagnostics.

Selections return induced NetworkX views. Their structure cannot be edited, but
node, edge, and graph attribute dictionaries are shared with the source graph;
call ``.copy()`` on a result before changing its attributes independently.
"""

from collections.abc import Hashable, Iterable
from itertools import islice

import networkx as nx


def _require_directed(graph: nx.Graph) -> None:
    if not graph.is_directed():
        raise nx.NetworkXNotImplemented("This query requires a directed graph")


def _validated_seeds(graph: nx.Graph, seeds: Iterable[Hashable]) -> set[Hashable]:
    selected: set[Hashable] = set()
    for seed in seeds:
        if seed not in graph:
            raise nx.NodeNotFound(f"Seed node {seed!r} is not in the graph")
        selected.add(seed)
    return selected


def _reachable(
    graph: nx.DiGraph, seeds: set[Hashable], *, reverse: bool = False
) -> set[Hashable]:
    visited = seeds.copy()
    pending = list(seeds)
    neighbors = graph.predecessors if reverse else graph.successors
    while pending:
        for neighbor in neighbors(pending.pop()):
            if neighbor not in visited:
                visited.add(neighbor)
                pending.append(neighbor)
    return visited


def language_nodes(graph: nx.Graph, language: str = "eng") -> set[str]:
    """Select string labels whose exact prefix before the first ``: `` matches.

    Other node types and strings without that separator are ignored. Node
    attributes are not consulted; language identity follows the source label.
    """
    selected: set[str] = set()
    for node in graph:
        if isinstance(node, str):
            prefix, separator, _ = node.partition(": ")
            if separator and prefix == language:
                selected.add(node)
    return selected


def ancestor_subgraph(graph: nx.DiGraph, seeds: Iterable[Hashable]) -> nx.DiGraph:
    """View seeds and all nodes that reach them, retaining cycles and evidence.

    Seeds are inclusive. All seed memberships are checked before a shared
    reverse traversal, so overlapping ancestry is visited once.
    """
    _require_directed(graph)
    selected = _validated_seeds(graph, seeds)
    return graph.subgraph(_reachable(graph, selected, reverse=True))


def descendant_subgraph(graph: nx.DiGraph, seeds: Iterable[Hashable]) -> nx.DiGraph:
    """View seeds and all nodes they reach using one shared forward traversal."""
    _require_directed(graph)
    selected = _validated_seeds(graph, seeds)
    return graph.subgraph(_reachable(graph, selected))


def root_family_subgraph(graph: nx.DiGraph, seeds: Iterable[Hashable]) -> nx.DiGraph:
    """View complete descendant families of zero-indegree roots reaching seeds.

    Siblings and other descendants of those roots are included. A seed in a
    rootless component is omitted unless some zero-indegree root reaches it.
    This is a root-family context query, not an ancestor-only selection.
    """
    _require_directed(graph)
    selected = _validated_seeds(graph, seeds)
    ancestors = _reachable(graph, selected, reverse=True)
    roots = {node for node in ancestors if graph.in_degree(node) == 0}
    return graph.subgraph(_reachable(graph, roots))


def component_subgraph(graph: nx.Graph, seeds: Iterable[Hashable]) -> nx.Graph:
    """View the connected components containing seeds, visiting each node once.

    Directed graphs use weak connectivity: an edge can be traversed in either
    direction. The returned view retains the original graph's directions and
    attributes. Disconnected components containing no seed are excluded.
    """
    visited = _validated_seeds(graph, seeds)
    pending = list(visited)
    adjacency = graph.to_undirected(as_view=True) if graph.is_directed() else graph
    while pending:
        for neighbor in adjacency.neighbors(pending.pop()):
            if neighbor not in visited:
                visited.add(neighbor)
                pending.append(neighbor)
    return graph.subgraph(visited)


def cyclic_nodes(graph: nx.DiGraph) -> set[Hashable]:
    """Identify cyclic nodes in linear time using strongly connected components.

    An SCC is cyclic if it has multiple nodes or a singleton self-loop. No cycle
    enumeration or deletion is needed; the source graph remains unchanged.
    """
    _require_directed(graph)
    result: set[Hashable] = set()
    for component in nx.strongly_connected_components(graph):
        if len(component) > 1:
            result.update(component)
        else:
            node = next(iter(component))
            if graph.has_edge(node, node):
                result.add(node)
    return result


def condensation_graph(graph: nx.DiGraph) -> nx.DiGraph:
    """Return the DAG formed by contracting strongly connected components.

    ``result.graph['mapping']`` maps original nodes to component IDs, and each
    component's ``members`` attribute retains its original node labels. IDs need
    not be stable across graph insertion orders. This is a structural summary:
    original node attributes and edge evidence are not copied or aggregated.
    Keep the source graph to inspect those assertions. Paths in this DAG are
    component-level paths, not necessarily paths through distinct original words.
    """
    _require_directed(graph)
    return nx.condensation(graph)


def cycle_examples(
    graph: nx.DiGraph, *, limit: int = 5, max_length: int = 6
) -> list[list[Hashable]]:
    """Return at most ``limit`` simple cycles with at most ``max_length`` nodes.

    Output is generated lazily and its ordering is not a ranking. Output-count
    and cycle-length bounds do not guarantee a runtime bound: locating cycles
    can still be expensive. Prefer :func:`cyclic_nodes` for complete diagnosis.
    """
    _require_directed(graph)
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
        raise ValueError("limit must be a nonnegative integer")
    if (
        isinstance(max_length, bool)
        or not isinstance(max_length, int)
        or max_length < 1
    ):
        raise ValueError("max_length must be a positive integer")
    if limit == 0:
        return []
    return list(islice(nx.simple_cycles(graph, length_bound=max_length), limit))
