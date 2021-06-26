import networkx as nx
from polyphasia.schema import WordGraphEdgeList, Relationship
from typing import Optional, List
from networkx.algorithms.dag import is_directed_acyclic_graph, dag_longest_path
from networkx.algorithms.cycles import simple_cycles


class GraphAnalysis:
    def __init__(
        self,
        data_set: Optional[WordGraphEdgeList] = None,
        limit_to_from_root_relationships: Optional[bool] = False,
    ):
        """

        :param data_set:
        :type data_set:
        :param limit_to_from_root_relationships:
        :type limit_to_from_root_relationships:
        """
        if data_set is None:
            data_set = WordGraphEdgeList()
        if not data_set.loaded:
            data_set.load(limit_to_from_root_relationships)
        self.graph = nx.from_edgelist(data_set.edge_list, nx.DiGraph)

    def info(self) -> str:
        """

        :return:
        :rtype:
        """
        summary = nx.info(self.graph)
        return summary

    def is_dag(self) -> bool:
        """
        Check if graph is directed acyclic
        :return:
        :rtype:
        """
        dag = is_directed_acyclic_graph(self.graph)
        return dag

    def cycles(self) -> List[nx.Graph]:
        """

        :return:
        :rtype:
        """
        cyc = list(simple_cycles(self.graph))
        return cyc

    def remove_cycles(self) -> None:
        """

        :return:
        :rtype:
        """
        cycle_nodes = [
            node for cycle in list(simple_cycles(self.graph)) for node in cycle
        ]
        self.graph.remove_nodes_from(cycle_nodes)

    def longest_path(self) -> List[Relationship]:
        """

        :return:
        :rtype:
        """
        d_longest_path = dag_longest_path(self.graph)
        return d_longest_path

    def english_language_subgraph(self):
        """

        :return:
        :rtype:
        """
        roots = [
            node
            for node in nx.nodes(self.graph)
            if len(nx.ancestors(self.graph, node)) == 0
        ]
        english_nodes = [
            nx.descendants(self.graph, root)
            for root in roots
            if list(filter(lambda x: x[0:3] == "eng", nx.descendants(self.graph, root)))
        ]
        english_graph = self.graph.subgraph(
            [node for desc in english_nodes for node in desc]
        )
        return english_graph

    def highest_degree_nodes(self, count: int) -> List[Relationship]:
        """

        :param count:
        :type count:
        :return:
        :rtype:
        """
        nodes_by_degree = sorted(self.graph.degree, key=lambda x: x[1], reverse=True)[
            0:count
        ]
        return nodes_by_degree
