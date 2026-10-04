"""Module with graph classes that mostly wrap networkx logic to provide more reusable/testable logic for use in the notebooks"""

from typing import Any, List, Optional, Set, Tuple

import networkx as nx
from networkx.algorithms.components import connected_components
from networkx.algorithms.cycles import simple_cycles
from networkx.algorithms.dag import dag_longest_path, is_directed_acyclic_graph
from networkx.algorithms.traversal import bfs_tree
from pandas import DataFrame

from polyphasia.constants import EDGE_ATTRIBUTES, LANGUAGE_PREFIX_TAG, SourceColumnNames


class DirectedGraph:
    def __init__(self, data_frame: DataFrame):
        """
        Class for handling directed graphs
        :param data_frame: the data frame containing the edge list
        :type data_frame: DataFrame
        """
        self._nx_digraph: nx.DiGraph = nx.from_pandas_edgelist(
            data_frame,
            edge_attr=EDGE_ATTRIBUTES,
            source=SourceColumnNames.SOURCE_NODE.value,
            target=SourceColumnNames.TARGET_NODE.value,
            create_using=nx.DiGraph,
        )

    @property
    def info(self) -> str:
        """
        Gets summary info about the graph including number of nodes and edges

        :return: Summary info about the graph
        :rtype: str
        """
        return str(self._nx_digraph)

    @property
    def is_dag(self) -> bool:
        """
        Check if graph is directed acyclic

        :return: bool indicating if graph is directed acyclic
        :rtype: bool
        """
        return is_directed_acyclic_graph(self._nx_digraph)

    def get_cycles(self) -> List[List[Any]]:
        """
        Get the list of simple cycles in the graph
        :return: a list of a list of nodes
        :rtype: List[List[Any]]
        """
        cycles = list(simple_cycles(self._nx_digraph))
        return cycles

    def remove_cycles(self) -> None:
        """
        Remove all nodes participating in cycles, including their incident edges.

        This mutates the graph and can also disconnect nodes outside the cycles.
        :return: None
        :rtype: None
        """
        cycle_nodes = [node for cycle in self.get_cycles() for node in cycle]
        self._nx_digraph.remove_nodes_from(cycle_nodes)

    def get_longest_path(self) -> List[Any]:
        """
        Get the longest path in a DAG; raises NetworkXUnfeasible for a cycle.
        :return: a list of nodes
        :rtype: List[Any]
        """
        longest_path = dag_longest_path(self._nx_digraph)
        return longest_path

    def roots(self) -> List[Any]:
        """
        Return nodes with no incoming edges, excluding nodes with self-loops.
        :return: a list of nodes
        :rtype: List[Any]
        """
        roots = [node for node, degree in self._nx_digraph.in_degree() if degree == 0]
        return roots

    def language_nodes(
        self, language: str = "eng", roots: Optional[List[Any]] = None
    ) -> List[Set[Any]]:
        """
        Return each root and all its descendants when that family has a match.

        A match compares the complete language token before ``": "`` in a node
        label. A matching root is included, as are descendants in other languages
        and sibling branches. Families may overlap when a node has multiple roots.
        Components with no root (for example, an isolated cycle) are omitted unless
        a starting node is supplied explicitly in ``roots``.

        :param language: the language token to match exactly
        :type language: str
        :param roots: the list of root nodes, recalculated if not provided
        :type roots: List[Any]
        :return: a list of matching root families, each represented as a node set
        :rtype: List[Set[Any]]
        """
        if roots is None:
            roots = self.roots()
        nodes = []
        for root in roots:
            family = {root} | nx.descendants(self._nx_digraph, root)
            if any(
                node.partition(LANGUAGE_PREFIX_TAG)[0] == language for node in family
            ):
                nodes.append(family)
        return nodes

    def language_subgraph(
        self, language: str = "eng", nodes: Optional[List[Set[Any]]] = None
    ) -> nx.DiGraph:
        """
        Return the induced view containing matching root families.

        By default, uses ``language_nodes`` and retains roots, descendants, and
        their original edge directions. When ``nodes`` is supplied, its union is
        used exactly; no language filtering or graph traversal is performed.
        An empty list returns an empty view. Attribute edits on the view are
        shared with the original graph.

        :param language: the language token to match exactly
        :type language: str
        :param nodes: list of nodes to use as base for subgraph, defaults to language nodes if not provided
        :type nodes: Optional[List[Set[Any]]]
        :return: a subgraph view of the graph, filtered to nodes connected to nodes from the specified language
        :rtype: subgraph
        """
        if nodes is None:
            nodes = self.language_nodes(language)
        graph = self._nx_digraph.subgraph([node for desc in nodes for node in desc])
        return graph

    @staticmethod
    def nodes_by_degree(subgraph: Any) -> List[Tuple[Any, int]]:
        """
        Return (node, degree) pairs in decreasing order by total degree.

        Ties preserve the graph's node iteration order. For directed graphs,
        total degree is the sum of incoming and outgoing degrees.
        :param subgraph: the subgraph to sort
        :type subgraph: subgraph
        :return: a list of node and degree pairs
        :rtype: List[Tuple[Any, int]]
        """
        nodes = sorted(subgraph.degree, key=lambda x: x[1], reverse=True)
        return nodes

    @staticmethod
    def subgraph_info(subgraph: Any) -> str:
        """
        Gets summary info about the subgraph including number of nodes and edges

        :return: Summary info about the graph
        :rtype: str
        """
        return str(subgraph)


class UndirectedGraph:
    def __init__(self, data_frame: DataFrame):
        """
        Class for handling undirected graphs
        :param data_frame: the data frame containing the edge list
        :type data_frame: DataFrame
        """
        self._nx_graph: nx.Graph = nx.from_pandas_edgelist(
            data_frame,
            edge_attr=EDGE_ATTRIBUTES,
            source=SourceColumnNames.SOURCE_NODE.value,
            target=SourceColumnNames.TARGET_NODE.value,
            create_using=nx.DiGraph,
        ).to_undirected()

    @property
    def info(self) -> str:
        """
        Gets summary info about the graph including number of nodes and edges

        :return: Summary info about the graph
        :rtype: str
        """
        return str(self._nx_graph)

    @property
    def connected_components(self) -> List[Set[Any]]:
        """
        Find the connected components of the graph
        :return: a list of connected components
        :rtype: List[Set[Any]]
        """
        conn_components = list(connected_components(self._nx_graph))
        return conn_components

    def language_nodes(self, language: str = "eng") -> List[Any]:
        """
        Find nodes whose complete language token before ``": "`` matches.

        Only directly matching nodes are returned; ``language_subgraph`` expands
        these seeds to their connected components.
        :param language: the language token to match exactly
        :type language: str
        :return: the list of matching node labels
        :rtype: List[Any]
        """
        bfs_language_nodes = [
            node
            for node in self._nx_graph.nodes()
            if node.partition(LANGUAGE_PREFIX_TAG)[0] == language
        ]
        return bfs_language_nodes

    def language_subgraph(
        self, language: str = "eng", nodes: Optional[List[Any]] = None
    ) -> nx.Graph:
        """
        Return the induced view of components containing matching language nodes.

        By default, matching nodes from ``language_nodes`` seed the traversal.
        Explicit ``nodes`` replace those seeds and bypass language filtering;
        every node connected to a seed is included. An empty seed list returns
        an empty view. Attribute edits on the view are shared with the original
        graph.

        :param language: the language token to match exactly
        :type language: str
        :param nodes: list of nodes to use as base for subgraph, defaults to language nodes if not provided
        :type nodes: Optional[List[Any]]
        :return: a subgraph view of the graph, filtered to nodes connected to nodes from the specified language
        :rtype: subgraph
        """
        if nodes is None:
            nodes = self.language_nodes(language)
        bfs_nodes_to_add: List[Any] = []
        for node in nodes:
            bfs_nodes_to_add.extend(bfs_tree(self._nx_graph, source=node))
        bfs_graph = self._nx_graph.subgraph(bfs_nodes_to_add)
        return bfs_graph

    @staticmethod
    def subgraph_info(subgraph: Any) -> str:
        """
        Gets summary info about the subgraph including number of nodes and edges

        :return: Summary info about the graph
        :rtype: str
        """
        return str(subgraph)

    @staticmethod
    def nodes_by_degree(subgraph: Any) -> List[Tuple[Any, int]]:
        """
        Return (node, degree) pairs in decreasing order by degree.

        Ties preserve the graph's node iteration order.
        :param subgraph: the subgraph to sort
        :type subgraph: subgraph
        :return: a list of node and degree pairs
        :rtype: List[Tuple[Any, int]]
        """
        nodes = sorted(subgraph.degree, key=lambda x: x[1], reverse=True)
        return nodes
