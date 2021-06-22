from dataclasses import dataclass, field
from typing import Optional, List, Dict
from pathlib import Path

import pandas as pd

from enum import Enum


class EdgeDirections(Enum):
    """ """

    BIDIRECTIONAL = "BIDIRECTIONAL"
    FROM_ROOT = "FROM_ROOT"
    FROM_LEAF = "FROM_LEAF"


class RelationshipTypes(Enum):
    """ """

    ETYMOLOGY = "rel:etymology"
    ETYMOLOGICAL_ORIGIN_OF = "rel:etymological_origin_of"
    IS_DERIVED_FROM = "rel:is_derived_from"
    HAS_DERIVED_FORM = "rel:has_derived_form"
    ETYMOLOGICALLY_RELATED = "rel:etymologically_related"
    VARIANT_ORTHOGRAPHY = "rel:variant:orthography"


class InvalidRelationshipTypes(Enum):
    """ """

    ETYMOLOGICALLY = "rel:etymologically"
    DERIVED = "rel:derived"


VALID_RELATIONSHIP_TYPES_LIST = [rel_type.value for rel_type in RelationshipTypes]
INVALID_RELATIONSHIP_TYPES_LIST = [
    rel_type.value for rel_type in InvalidRelationshipTypes
]

RELATIONSHIP_TYPE_DIRECTION_MAP = {
    EdgeDirections.BIDIRECTIONAL: [
        RelationshipTypes.ETYMOLOGICALLY_RELATED,
        RelationshipTypes.VARIANT_ORTHOGRAPHY,
    ],
    EdgeDirections.FROM_LEAF: [
        RelationshipTypes.ETYMOLOGY,
        RelationshipTypes.IS_DERIVED_FROM,
    ],
    EdgeDirections.FROM_ROOT: [
        RelationshipTypes.ETYMOLOGICAL_ORIGIN_OF,
        RelationshipTypes.HAS_DERIVED_FORM,
    ],
}

INVALID_RELATIONSHIP_TYPE_MAP = {
    InvalidRelationshipTypes.ETYMOLOGICALLY: RelationshipTypes.ETYMOLOGICALLY_RELATED,
    InvalidRelationshipTypes.DERIVED: RelationshipTypes.IS_DERIVED_FROM,
}


@dataclass
class WordNode:
    """ """

    value: str = ""
    language: str = ""

    @property
    def node_id(self) -> str:
        return f"{self.language}: {self.value}"


@dataclass
class Edge:
    """ """

    relationship_type: RelationshipTypes = RelationshipTypes.ETYMOLOGICAL_ORIGIN_OF
    source_node: WordNode = field(default_factory=WordNode)
    target_node: WordNode = field(default_factory=WordNode)


class DataSet:
    def __init__(self, source_file: Optional[Path] = None):
        """

        :param source_file:
        :type source_file:
        """
        if source_file == None:
            base_directory = Path.cwd().parent.absolute()
            source_data_path = base_directory / "data" / "raw" / "etymwn.tsv"
            source_file = source_data_path
        self._source_file: Path = source_file
        self._data: Dict[str, WordNode] = {}
        self.edge_list: List[Edge] = []
        self.loaded: bool = False

    def load(self, limit_to_from_root_relationships: Optional[bool] = False) -> None:
        """

        :param limit_to_from_root_relationships:
        :type limit_to_from_root_relationships:
        :return:
        :rtype:
        """
        data_frame = pd.read_csv(self._source_file, sep="\t")
        if limit_to_from_root_relationships:
            data_frame.apply(self._parse_root_only, index=1)
        else:
            data_frame.apply(self._parse, index=1)
        self.loaded = True

    def _parse(self, source_node: str, edge_type: str, target_node: str) -> None:
        """

        :param source_node:
        :type source_node:
        :param edge_type:
        :type edge_type:
        :param target_node:
        :type target_node:
        :return:
        :rtype:
        """
        self._parse_input_row(source_node, edge_type, target_node, False)

    def _parse_root_only(
        self, source_node: str, edge_type: str, target_node: str
    ) -> None:
        """

        :param source_node:
        :type source_node:
        :param edge_type:
        :type edge_type:
        :param target_node:
        :type target_node:
        :return:
        :rtype:
        """
        self._parse_input_row(source_node, edge_type, target_node, True)

    def _parse_node(self, node: str) -> WordNode:
        """

        :param node:
        :type node:
        :return:
        :rtype:
        """
        if node not in self._data:
            source_node_content = node.split(": ")
            word = WordNode(source_node_content[0], source_node_content[1])
            self._data[node] = word
        return self._data[node]

    @staticmethod
    def _parse_edge(edge_type: str) -> RelationshipTypes:
        """

        :param edge_type:
        :type edge_type:
        :return:
        :rtype:
        """
        if edge_type in VALID_RELATIONSHIP_TYPES_LIST:
            parsed_edge_type = RelationshipTypes[edge_type]
        elif edge_type in INVALID_RELATIONSHIP_TYPES_LIST:
            parsed_edge_type = INVALID_RELATIONSHIP_TYPE_MAP[edge_type]
        else:
            raise ValueError(
                f"Relationship type not found in list of valid or cleanable relationships. Valid relationships: {VALID_RELATIONSHIP_TYPES_LIST}. Invalid: {INVALID_RELATIONSHIP_TYPES_LIST}"
            )
        return parsed_edge_type

    def _parse_input_row(
        self,
        source_node: str,
        edge_type: str,
        target_node: str,
        limit_to_from_root: bool,
    ):
        """

        :param source_node:
        :type source_node:
        :param edge_type:
        :type edge_type:
        :param target_node:
        :type target_node:
        :param limit_to_from_root:
        :type limit_to_from_root:
        :return:
        :rtype:
        """
        source = self._parse_node(source_node)
        target = self._parse_node(target_node)
        parsed_edge_type = DataSet._parse_edge(edge_type)
        if (
            not limit_to_from_root
            or RELATIONSHIP_TYPE_DIRECTION_MAP[parsed_edge_type]
            == EdgeDirections.FROM_ROOT
        ):
            self.edge_list.append(
                Edge(
                    source_node=source,
                    target_node=target,
                    relationship_type=parsed_edge_type,
                )
            )
