from dataclasses import dataclass, field
from typing import List, Dict

from enum import Enum


class RelationshipDirection(Enum):
    """ """

    BIDIRECTIONAL = "BIDIRECTIONAL"
    FROM_ROOT = "FROM_ROOT"
    FROM_LEAF = "FROM_LEAF"


class RelationshipCategory(Enum):
    """ """

    ETYMOLOGY = "rel:etymology"
    ETYMOLOGICAL_ORIGIN_OF = "rel:etymological_origin_of"
    IS_DERIVED_FROM = "rel:is_derived_from"
    HAS_DERIVED_FORM = "rel:has_derived_form"
    ETYMOLOGICALLY_RELATED = "rel:etymologically_related"
    VARIANT_ORTHOGRAPHY = "rel:variant:orthography"


class InvalidRelationshipCategory(Enum):
    """ """

    ETYMOLOGICALLY = "rel:etymologically"
    DERIVED = "rel:derived"


"""
Enum validation items converted to lists and dicts for mapping from inputs.
"""
VALID_RELATIONSHIP_CATEGORY_LIST = [rel_type.value for rel_type in RelationshipCategory]
INVALID_RELATIONSHIP_CATEGORY_LIST = [
    rel_type.value for rel_type in InvalidRelationshipCategory
]
RELATIONSHIP_CATEGORY_DIRECTION_MAP = {
    RelationshipCategory.ETYMOLOGICALLY_RELATED: RelationshipDirection.BIDIRECTIONAL,
    RelationshipCategory.VARIANT_ORTHOGRAPHY: RelationshipDirection.BIDIRECTIONAL,
    RelationshipCategory.ETYMOLOGY: RelationshipDirection.FROM_LEAF,
    RelationshipCategory.IS_DERIVED_FROM: RelationshipDirection.FROM_LEAF,
    RelationshipCategory.ETYMOLOGICAL_ORIGIN_OF: RelationshipDirection.FROM_ROOT,
    RelationshipCategory.HAS_DERIVED_FORM: RelationshipDirection.FROM_ROOT,
}
INVALID_RELATIONSHIP_CATEGORY_MAP = {
    InvalidRelationshipCategory.ETYMOLOGICALLY: RelationshipCategory.ETYMOLOGICALLY_RELATED,
    InvalidRelationshipCategory.DERIVED: RelationshipCategory.IS_DERIVED_FROM,
}


@dataclass
class Word:
    """ """

    value: str = ""
    language: str = ""

    @property
    def node_id(self) -> str:
        return f"{self.language}: {self.value}"


@dataclass
class Relationship:
    """ """

    category: RelationshipCategory = field(
        default=RelationshipCategory.ETYMOLOGICAL_ORIGIN_OF
    )
    source_node: Word = field(default_factory=Word)
    target_node: Word = field(default_factory=Word)
    attributes: Dict[str, str] = field(default_factory=dict)


@dataclass
class WordGraphEdgeList:
    """ """

    relationships: List[Relationship] = field(default_factory=list)
