"""Module with functions for loading and cleaning the source data"""

from typing import Optional
from pathlib import Path

import pandas as pd

from polyphasia.constants import (
    EdgeDirections,
    ParsedColumnNames,
    SourceColumnNames,
    LANGUAGE_PREFIX_TAG,
    EDGE_LIST_COLUMN_NAMES,
    RELATIVE_PATH_TO_SOURCE,
    INVALID_RELATIONSHIP_TYPE_MAP,
    RELATIONSHIP_TYPE_DIRECTION_MAP,
)


def load_to_pandas(source_file: Optional[Path] = None) -> pd.DataFrame:
    """
    Parses the provided TSV file to a pandas DataFrame
    :param source_file: the TSV file from which to load the data
    :type source_file: Optional[Path]
    :return: a data frame with the three TSV columns loaded
    :rtype: pd.DataFrame
    """
    if source_file is None:
        source_file = Path.cwd().parent.absolute() / RELATIVE_PATH_TO_SOURCE
    data_frame = pd.read_csv(source_file, sep="\t", names=EDGE_LIST_COLUMN_NAMES)
    return data_frame


def clean_data_frame(
    data_frame: pd.DataFrame, drop_rel_types: Optional[bool] = True
) -> pd.DataFrame:
    """
    # Cleaning notes

    ## Relationship types found in source data

    Relationships are recorded bidirectionally. So a root word will link to its derivatives, and each derivative will link back to the root. To simplify the
    graph, I will drop edges that point from derivatives to roots, since that information is already encoded in the root-to-leaf edge and networkx can handle
    bidirectional traversal without requiring multiple edges to link the same pair of nodes.

    Below are the types of relationships extracted from the data, with comments indicating their directionality.


    <- A is the source of B

    -> B is the source of A


    - "rel:etymology"               ->
    - "rel:etymological_origin_of"  <-
    - "rel:is_derived_from"         ->
    - "rel:has_derived_form"        <-
    - "rel:etymologically_related"  <->
    - "rel:variant:orthography"     <->

    source data also includes a handful of malformed values, which should be dropped or replaced
    - "rel:etymologically" -> "rel:etymologically_related"
    - "rel:derived" -> "rel:is_derived_from"



    :param data_frame: the data frame to clean
    :type data_frame: pd.DataFrame
    :param drop_rel_types: flag indicating whether to drop edges that have unwanted directionality for the analysis
    :type drop_rel_types: bool
    :return: a cleaned DataFrame with additional columns for the parsed target and source words and languages
    :rtype: pd.DataFrame
    """

    if drop_rel_types:
        from_root_relationships = RELATIONSHIP_TYPE_DIRECTION_MAP[
            EdgeDirections.FROM_ROOT
        ]
        data_frame = data_frame.loc[
            (
                data_frame[SourceColumnNames.EDGE_TYPE.value].isin(
                    from_root_relationships
                )
            )
        ]
    else:
        for rel_type, valid_value in INVALID_RELATIONSHIP_TYPE_MAP:
            data_frame = data_frame.replace(rel_type, valid_value)
    data_frame[
        [ParsedColumnNames.SOURCE_LANGUAGE.value, ParsedColumnNames.SOURCE_WORD.value]
    ] = data_frame.source_node.str.split(LANGUAGE_PREFIX_TAG, expand=True)

    # there are a handful of nodes that include strange characters or a :Category: tag that introduces a third
    # column for no reason. This data is uninteresting so we can just ignore it and no include it in the graph when we construct it
    data_frame[
        [
            ParsedColumnNames.TARGET_LANGUAGE.value,
            ParsedColumnNames.TARGET_WORD.value,
            "_",
        ]
    ] = data_frame.target_node.str.split(LANGUAGE_PREFIX_TAG, expand=True)
    data_frame.drop(["_"], axis=1)
    return data_frame
