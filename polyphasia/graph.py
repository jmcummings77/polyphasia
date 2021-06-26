"""Module with graph classes that mostly wrap networkx logic to provide more reusable/testable logic for use in the notebooks"""

from typing import Optional, List, Any
from pandas import DataFrame
from polyphasia.constants import EDGE_ATTRIBUTES, SourceColumnNames
import networkx as nx
from networkx.algorithms.dag import is_directed_acyclic_graph
from networkx.algorithms.cycles import simple_cycles
from networkx.algorithms.dag import dag_longest_path
from networkx.algorithms.components import connected_components
from networkx.algorithms.traversal import bfs_tree


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
        return nx.info(self._nx_digraph)

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
        Remove any cycles found in the underlying graph so it can be acyclic
        :return: None
        :rtype: None
        """
        cycle_nodes = [node for cycle in self.get_cycles() for node in cycle]
        self._nx_digraph.remove_nodes_from(cycle_nodes)

    def get_longest_path(self) -> List[Any]:
        """
        Get the longest path in the graph
        :return: a list of nodes
        :rtype: List[Any]
        """
        longest_path = dag_longest_path(self._nx_digraph)
        return longest_path

    def roots(self) -> List[Any]:
        """
        Returns any nodes that do not have ancestors
        :return: a list of nodes
        :rtype: List[Any]
        """
        roots = [
            node
            for node in nx.nodes(self._nx_digraph)
            if len(nx.ancestors(self._nx_digraph, node)) == 0
        ]
        return roots

    def language_nodes(
        self, language: Optional[str] = "eng", roots: Optional[List[Any]] = None
    ):
        """
        Find the nodes pertaining to the language provided
        :param language: the prefix string for the language
        :type language: str
        :param roots: the list of root nodes, recalculated if not provided
        :type roots: List[Any]
        :return: the list of nodes with the given prefix or connected to such a node
        :rtype: List[Any]
        """
        if roots is None:
            roots = self.roots()
        nodes = [
            nx.descendants(self._nx_digraph, root)
            for root in roots
            if list(
                filter(
                    lambda x: x[0:3] == language, nx.descendants(self._nx_digraph, root)
                )
            )
        ]
        return nodes

    def language_subgraph(
        self, language: Optional[str] = "eng", nodes: Optional[List[Any]] = None
    ):
        """
        Get the subgraph with nodes pertaining to a specific language.

        Finds the root nodes
        :param language: prefix for the language we want to filter to
        :type language: str
        :param nodes: list of nodes to use as base for subgraph, defaults to language nodes if not provided
        :type nodes: Optional[List[Any]]
        :return: a subgraph view of the graph, filtered to nodes connected to nodes from the specified language
        :rtype: subgraph
        """
        if nodes is None:
            nodes = self.language_nodes(language)
        graph = self._nx_digraph.subgraph([node for desc in nodes for node in desc])
        return graph

    @staticmethod
    def nodes_by_degree(subgraph) -> List[Any]:
        """
        Return a list of nodes in the specified subgraph, sorted in decreasing order by degree
        :param subgraph: the subgraph to sort
        :type subgraph: subgraph
        :return: a list of nodes
        :rtype: List[Any]
        """
        nodes = sorted(subgraph.degree, key=lambda x: x[1], reverse=True)
        return nodes

    @staticmethod
    def subgraph_info(subgraph) -> str:
        """
        Gets summary info about the subgraph including number of nodes and edges

        :return: Summary info about the graph
        :rtype: str
        """
        return nx.info(subgraph)


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
        return nx.info(self._nx_graph)

    @property
    def connected_components(self) -> List[List[Any]]:
        """
        Find the connected components of the graph
        :return: a list of connected components
        :rtype: List[List[Any]]
        """
        conn_components = list(connected_components(self._nx_graph))
        return conn_components

    def language_nodes(self, language: Optional[str] = "eng"):
        """
        Find the nodes pertaining to the language provided
        :param language: the prefix string for the language
        :type language: str
        :return: the list of nodes with the given prefix or connected to such a node
        :rtype: List[Any]
        """
        bfs_language_nodes = [n for n in self._nx_graph.nodes() if n[0:3] == language]
        return bfs_language_nodes

    def language_subgraph(
        self, language: Optional[str] = "eng", nodes: Optional[List[Any]] = None
    ):
        """
        Get the subgraph with nodes pertaining to a specific language.

        Finds the root nodes
        :param language: prefix for the language we want to filter to
        :type language: str
        :param nodes: list of nodes to use as base for subgraph, defaults to language nodes if not provided
        :type nodes: Optional[List[Any]]
        :return: a subgraph view of the graph, filtered to nodes connected to nodes from the specified language
        :rtype: subgraph
        """
        # grab the nodes that have the eng tag, then build the connected graph by searching outwards from those
        if nodes is None:
            nodes = self.language_nodes(language)
        bfs_nodes_to_add = []
        # add nodes inside loop to avoid having to flatten later
        [
            bfs_nodes_to_add.extend(bfs_tree(self._nx_graph, source=node))
            for node in nodes
        ]
        bfs_graph = self._nx_graph.subgraph(bfs_nodes_to_add)
        return bfs_graph

    @staticmethod
    def subgraph_info(subgraph) -> str:
        """
        Gets summary info about the subgraph including number of nodes and edges

        :return: Summary info about the graph
        :rtype: str
        """
        return nx.info(subgraph)

    @staticmethod
    def nodes_by_degree(subgraph) -> List[Any]:
        """
        Return a list of nodes in the specified subgraph, sorted in decreasing order by degree
        :param subgraph: the subgraph to sort
        :type subgraph: subgraph
        :return: a list of nodes
        :rtype: List[Any]
        """
        nodes = sorted(subgraph.degree, key=lambda x: x[1], reverse=True)
        return nodes
