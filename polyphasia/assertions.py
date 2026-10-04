"""Preserve source assertions and project explicit root-to-derivative graphs.

The assertion table is the evidence layer: every valid input record survives,
including duplicates and relationships that a particular graph policy excludes.
The graph is a derived view, with the contributing evidence attached to each edge.
"""

from dataclasses import dataclass, field

import networkx as nx
import pandas as pd

from polyphasia.constants import EDGE_LIST_COLUMN_NAMES, RelationshipTypes
from polyphasia.loader import clean_data_frame

FORWARD_RELATIONSHIPS: dict[str, str] = {
    RelationshipTypes.ETYMOLOGICAL_ORIGIN_OF.value: (
        RelationshipTypes.ETYMOLOGICAL_ORIGIN_OF.value
    ),
    RelationshipTypes.HAS_DERIVED_FORM.value: RelationshipTypes.HAS_DERIVED_FORM.value,
}
INVERSE_RELATIONSHIPS: dict[str, str] = {
    RelationshipTypes.ETYMOLOGY.value: RelationshipTypes.ETYMOLOGICAL_ORIGIN_OF.value,
    RelationshipTypes.IS_DERIVED_FROM.value: RelationshipTypes.HAS_DERIVED_FORM.value,
}
PARSED_ENDPOINT_COLUMNS = [
    "source_language",
    "source_word",
    "target_language",
    "target_word",
]
ASSERTION_COLUMN_NAMES = [
    *EDGE_LIST_COLUMN_NAMES,
    "assertion_id",
    "normalized_edge_type",
    *PARSED_ENDPOINT_COLUMNS,
]

# The two canonical types need only two bits. Shared immutable tuples replace
# per-edge sets and repeated identical tuples on large projections.
_RELATIONSHIP_FLAGS = {
    relationship: 1 << index
    for index, relationship in enumerate(sorted(FORWARD_RELATIONSHIPS))
}
_RELATIONSHIP_TYPES_BY_MASK = {
    mask: tuple(
        relationship
        for relationship, flag in _RELATIONSHIP_FLAGS.items()
        if mask & flag
    )
    for mask in range(1 << len(_RELATIONSHIP_FLAGS))
}


@dataclass(slots=True)
class _EdgeEvidence:
    relationship_mask: int = 0
    raw_counts: dict[str, int] = field(default_factory=dict)
    ids: list[int] = field(default_factory=list)


def prepare_assertions(raw: pd.DataFrame) -> pd.DataFrame:
    """Validate and preserve every raw record in a fixed assertion schema.

    The three source fields retain their exact literals; known relationship
    aliases are corrected only in ``normalized_edge_type``. ``assertion_id`` is
    the one-based input record ordinal, independent of the DataFrame index. For
    input from :func:`load_to_pandas`, it counts nonblank TSV records, not physical
    lines. IDs identify locations in this particular input, not stable identities
    across reordered files.

    The four parsed endpoint fields follow :func:`clean_data_frame`. The caller's
    frame and index are unmodified. Extra input columns are omitted, including
    any caller-supplied values in reserved derived columns. Empty input returns
    the same nine-column schema.
    """
    cleaned = clean_data_frame(raw, drop_rel_types=False)
    assertions = raw.loc[:, EDGE_LIST_COLUMN_NAMES].copy()
    assertions["assertion_id"] = range(1, len(assertions) + 1)
    assertions["normalized_edge_type"] = cleaned["edge_type"]
    for column in PARSED_ENDPOINT_COLUMNS:
        assertions[column] = cleaned[column]
    return assertions


def project_assertions(
    assertions: pd.DataFrame, policy: str = "normalized"
) -> nx.DiGraph:
    """Build an evidence-preserving graph from :func:`prepare_assertions` output.

    ``root_only`` retains the two forward relationship types, matching the
    legacy cleaner's selection. ``normalized`` also reverses ``rel:etymology``
    and ``rel:is_derived_from`` assertions into their corresponding forward
    types. Both exclude symmetric and unknown relationships and retain cycles.
    Nodes are exactly the endpoints of retained assertions, with ``language``
    and ``word`` attributes.

    Repeated endpoint pairs become one edge with sorted ``relationship_types``,
    ``raw_relationship_counts``, and ``assertion_ids``, plus ``assertion_count``.
    Counts include duplicate assertions and both members of an inverse pair;
    they measure recorded assertions, not independent supporting sources. No
    synthetic reverse evidence is added. Node/edge insertion order and semantic
    attributes are independent of record order. IDs retain input provenance.

    This function checks the policy and required columns, then trusts the
    validated table contents. Raw or externally modified tables should pass
    through :func:`prepare_assertions` before projection.
    """
    if policy not in {"root_only", "normalized"}:
        raise ValueError("policy must be 'root_only' or 'normalized'")
    if not assertions.columns.is_unique:
        raise ValueError("Column names must be unique")
    missing = set(ASSERTION_COLUMN_NAMES).difference(assertions.columns)
    if missing:
        raise ValueError(f"Missing assertion columns: {', '.join(sorted(missing))}")

    evidence: dict[tuple[str, str], _EdgeEvidence] = {}
    columns = [
        "source_node",
        "edge_type",
        "target_node",
        "assertion_id",
        "normalized_edge_type",
    ]
    # Iterate column views without allocating a five-column DataFrame copy.
    records = zip(*(assertions[column] for column in columns), strict=True)
    for source, raw_type, target, assertion_id, normalized_type in records:
        if normalized_type in FORWARD_RELATIONSHIPS:
            canonical_type = FORWARD_RELATIONSHIPS[normalized_type]
        elif policy == "normalized" and normalized_type in INVERSE_RELATIONSHIPS:
            source, target = target, source
            canonical_type = INVERSE_RELATIONSHIPS[normalized_type]
        else:
            continue
        pair = source, target
        if pair not in evidence:
            evidence[pair] = _EdgeEvidence()
        state = evidence[pair]
        state.relationship_mask |= _RELATIONSHIP_FLAGS[canonical_type]
        state.raw_counts[raw_type] = state.raw_counts.get(raw_type, 0) + 1
        state.ids.append(int(assertion_id))

    graph = nx.DiGraph(policy=policy, policy_version="1")
    languages: dict[str, str] = {}
    for node in sorted({node for pair in evidence for node in pair}):
        language, _, word = node.partition(": ")
        graph.add_node(
            node, language=languages.setdefault(language, language), word=word
        )
    # Release each accumulator as its attributed graph edge is materialized;
    # holding both complete representations would substantially raise peak RAM.
    for source, target in sorted(evidence):
        state = evidence.pop((source, target))
        state.ids.sort()
        graph.add_edge(
            source,
            target,
            relationship_types=_RELATIONSHIP_TYPES_BY_MASK[state.relationship_mask],
            assertion_count=len(state.ids),
            raw_relationship_counts=dict(sorted(state.raw_counts.items())),
            assertion_ids=tuple(state.ids),
        )
    return graph
