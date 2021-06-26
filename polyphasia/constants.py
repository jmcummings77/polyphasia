from enum import Enum
from pathlib import Path
from typing import List, Dict


class EdgeDirections(Enum):
    """An enumeration of the possible graph relationship directions"""

    BIDIRECTIONAL = "BIDIRECTIONAL"
    FROM_ROOT = "FROM_ROOT"
    FROM_LEAF = "FROM_LEAF"


class RelationshipTypes(Enum):
    """An enumeration of the valid relationship types in the source data"""

    ETYMOLOGY = "rel:etymology"
    ETYMOLOGICAL_ORIGIN_OF = "rel:etymological_origin_of"
    IS_DERIVED_FROM = "rel:is_derived_from"
    HAS_DERIVED_FORM = "rel:has_derived_form"
    ETYMOLOGICALLY_RELATED = "rel:etymologically_related"
    VARIANT_ORTHOGRAPHY = "rel:variant:orthography"


class InvalidRelationshipTypes(Enum):
    """An enumeration of the invalid relationship types in the source data"""

    ETYMOLOGICALLY = "rel:etymologically"
    DERIVED = "rel:derived"


class SourceColumnNames(Enum):
    """An enumeration of the columns names to apply to the source data"""

    SOURCE_NODE = "source_node"
    EDGE_TYPE = "edge_type"
    TARGET_NODE = "target_node"


class ParsedColumnNames(Enum):
    """An enumeration of the columns names to apply to the parsed data"""

    SOURCE_LANGUAGE = "source_language"
    TARGET_LANGUAGE = "target_language"
    SOURCE_WORD = "source_word"
    TARGET_WORD = "target_word"


# A list of the valid relationship types as strings
VALID_RELATIONSHIP_TYPES_LIST: List[str] = [
    rel_type.value for rel_type in RelationshipTypes
]

# A list of the invalid relationship types as strings
INVALID_RELATIONSHIP_TYPES_LIST: List[str] = [
    rel_type.value for rel_type in InvalidRelationshipTypes
]

# Mapping between the possible directions and the relationship types that represent that direction in the source data
RELATIONSHIP_TYPE_DIRECTION_MAP: Dict[EdgeDirections, List[str]] = {
    EdgeDirections.BIDIRECTIONAL: [
        RelationshipTypes.ETYMOLOGICALLY_RELATED.value,
        RelationshipTypes.VARIANT_ORTHOGRAPHY.value,
    ],
    EdgeDirections.FROM_LEAF: [
        RelationshipTypes.ETYMOLOGY.value,
        RelationshipTypes.IS_DERIVED_FROM.value,
    ],
    EdgeDirections.FROM_ROOT: [
        RelationshipTypes.ETYMOLOGICAL_ORIGIN_OF.value,
        RelationshipTypes.HAS_DERIVED_FORM.value,
    ],
}

# Mapping between the invalid relationship types in the source data and their corrected values
INVALID_RELATIONSHIP_TYPE_MAP: Dict[str, str] = {
    InvalidRelationshipTypes.ETYMOLOGICALLY.value: RelationshipTypes.ETYMOLOGICALLY_RELATED.value,
    InvalidRelationshipTypes.DERIVED.value: RelationshipTypes.IS_DERIVED_FROM.value,
}

# Default relative path to the source TSV file
RELATIVE_PATH_TO_SOURCE: Path = Path("data") / "raw" / "etymologies.tsv"

# List of attributes to be associated with each edge in the output graph
EDGE_ATTRIBUTES: List[str] = [
    SourceColumnNames.EDGE_TYPE.value,
    ParsedColumnNames.SOURCE_LANGUAGE.value,
    ParsedColumnNames.SOURCE_WORD.value,
    ParsedColumnNames.TARGET_LANGUAGE.value,
    ParsedColumnNames.TARGET_WORD.value,
]

# The prefix tag used to separate languages from words in the source data
LANGUAGE_PREFIX_TAG: str = ": "

# The list of column names as strings to be used when parsing the source data
EDGE_LIST_COLUMN_NAMES: List[str] = [
    SourceColumnNames.SOURCE_NODE.value,
    SourceColumnNames.EDGE_TYPE.value,
    SourceColumnNames.TARGET_NODE.value,
]
