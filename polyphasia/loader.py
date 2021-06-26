from typing import Optional, Dict
from pathlib import Path

import pandas as pd

from polyphasia.schema import (
    Word,
    Relationship,
    RelationshipCategory,
    InvalidRelationshipCategory,
    VALID_RELATIONSHIP_CATEGORY_LIST,
    INVALID_RELATIONSHIP_CATEGORY_LIST,
    INVALID_RELATIONSHIP_CATEGORY_MAP,
    RELATIONSHIP_CATEGORY_DIRECTION_MAP,
    RelationshipDirection,
    WordGraphEdgeList,
    )

base_directory = Path.cwd().parent.absolute()
default_source_file = base_directory / "data" / "raw" / "etymologies.tsv"


def _parse_node(node: str, data: Dict[str, Word]) -> Word:
    """

    :param node:
    :type node:
    :param data:
    :type data:
    :return:
    :rtype:
    """
    if node not in data:
        source_node_content = node.split(": ")
        data[node] = Word(source_node_content[0], source_node_content[1])
    return data[node]


def _parse_edge(edge_type: str) -> RelationshipCategory:
    """

    :param edge_type:
    :type edge_type:
    :return:
    :rtype:
    """
    if edge_type in VALID_RELATIONSHIP_CATEGORY_LIST:
        parsed_edge_type = RelationshipCategory[edge_type]
    elif edge_type in INVALID_RELATIONSHIP_CATEGORY_LIST:
        parsed_edge_type = INVALID_RELATIONSHIP_CATEGORY_MAP[
            InvalidRelationshipCategory[edge_type]
            ]
    else:
        raise ValueError(
            f"""Relationship category not found in list of valid or cleanable relationships.
            Valid relationships: {VALID_RELATIONSHIP_CATEGORY_LIST}. Invalid: {INVALID_RELATIONSHIP_CATEGORY_LIST}"""
            )
    return parsed_edge_type


def _parse_input_row(
    source_node: str, edge_type: str, target_node: str, from_root_only: bool
        ) -> Relationship:
    """

    :param source_node:
    :type source_node:
    :param edge_type:
    :type edge_type:
    :param target_node:
    :type target_node:
    :param from_root_only:
    :type from_root_only:
    :return:
    :rtype:
    """
    loaded_nodes = {}
    source = _parse_node(source_node, loaded_nodes)
    target = _parse_node(target_node, loaded_nodes)
    parsed_edge_type = _parse_edge(edge_type)
    is_from_root = (
        RELATIONSHIP_CATEGORY_DIRECTION_MAP[parsed_edge_type]
        == RelationshipDirection.FROM_ROOT
        )
    if not from_root_only or is_from_root:
        return Relationship(
            source_node=source, target_node=target, category=parsed_edge_type
            )


def load(
    source_file: Optional[Path] = None, from_root_only: Optional[bool] = False
        ) -> WordGraphEdgeList:
    """

    :param source_file:
    :type source_file:
    :param from_root_only:
    :type from_root_only:
    :return:
    :rtype:
    """
    if source_file is None:
        source_file = default_source_file
    data_frame = pd.read_csv(source_file, sep="\t")
    result = WordGraphEdgeList(
        relationships=data_frame.apply(
            lambda x: _parse_input_row(x[0], x[1], x[2], from_root_only), index=1
            )
        )
    return result

