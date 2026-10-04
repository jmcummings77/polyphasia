"""Deterministic query comparisons, degree rankings, and bounded evidence traces.

These metrics describe recorded assertions under explicit projection policies.
They are not estimates of linguistic confidence, historical age, or completeness.
The caller supplies input provenance; this module performs no file I/O.
"""

import hashlib
import heapq
import json
from collections import Counter, deque
from collections.abc import Iterable, Iterator
from itertools import chain, combinations
from typing import Any

import networkx as nx
import pandas as pd

from polyphasia.assertions import INVERSE_RELATIONSHIPS, project_assertions
from polyphasia.queries import (
    ancestor_subgraph,
    component_subgraph,
    descendant_subgraph,
    language_nodes,
    root_family_subgraph,
)

_QUERIES = {
    "ancestors": ancestor_subgraph,
    "descendants": descendant_subgraph,
    "root_families": root_family_subgraph,
    "components": component_subgraph,
}
_RELATIONSHIPS = {
    "word_origin": "rel:etymological_origin_of",
    "derivation": "rel:has_derived_form",
}
_MASK = "_analysis_query_mask"
_TRACE_EVIDENCE_LIMIT = 5


def _selected_summary(
    graph: nx.DiGraph, selected: nx.DiGraph, seeds: set[str], bit: int
) -> dict[str, Any]:
    digest = hashlib.sha256(b"[")
    languages: Counter[str] = Counter()
    seed_count = 0
    # Stream the JSON encoding; do not materialize another full label string.
    for index, node in enumerate(sorted(selected)):
        if index:
            digest.update(b",")
        digest.update(json.dumps(node, ensure_ascii=False).encode("utf-8"))
        attributes = graph.nodes[node]
        attributes[_MASK] = attributes.get(_MASK, 0) | bit
        languages[attributes["language"]] += 1
        seed_count += node in seeds
    digest.update(b"]")
    return {
        "nodes": sum(languages.values()),
        "seeds_included": seed_count,
        "node_languages": dict(sorted(languages.items())),
        "selected_nodes_sha256": digest.hexdigest(),
    }


def _degree_counts(
    graph: nx.DiGraph, relationship: str, direction: str
) -> Iterator[tuple[str, int]]:
    edges = graph.out_edges if direction == "out_degree" else graph.in_edges
    for node, attributes in graph.nodes(data=True):
        if not attributes.get(_MASK, 0) & 1:
            continue
        count = 0
        for source, target, evidence in edges(node, data=True):
            neighbor = target if direction == "out_degree" else source
            if (
                graph.nodes[neighbor].get(_MASK, 0) & 1
                and relationship in evidence["relationship_types"]
            ):
                count += 1
        if count:
            yield node, count


def _rankings(graph: nx.DiGraph, facts: Counter[str], top_n: int) -> dict[str, Any]:
    result: dict[str, Any] = {"scope": "ancestors"}
    for family, relationship in _RELATIONSHIPS.items():
        ranking: dict[str, Any] = {
            "relationship_type": relationship,
            "facts": facts[relationship],
        }
        for direction in ("out_degree", "in_degree"):
            top = heapq.nsmallest(
                top_n,
                _degree_counts(graph, relationship, direction),
                key=lambda item: (-item[1], item[0]),
            )
            ranking[direction] = [
                {
                    "node": node,
                    "language": graph.nodes[node]["language"],
                    "word": graph.nodes[node]["word"],
                    "neighbors": count,
                    "affix_like": graph.nodes[node]["word"].startswith("-")
                    or graph.nodes[node]["word"].endswith("-"),
                }
                for node, count in top
            ]
        result[family] = ranking
    return result


def _trace(
    graph: nx.DiGraph, word: str, max_depth: int, max_nodes: int
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "word": word,
        "status": "missing",
        "path": [],
        "distance": None,
        "visited_nodes": 0,
        "bounds_hit": [],
        "edges": [],
    }
    if word not in graph:
        return result
    toward_word: dict[str, str | None] = {word: None}
    pending = deque([(word, 0)])
    root = word if graph.in_degree(word) == 0 else None
    depth_limited = False
    while pending and root is None:
        node, depth = pending.popleft()
        if depth == max_depth:
            depth_limited |= any(
                parent not in toward_word for parent in graph.predecessors(node)
            )
            continue
        for parent in sorted(graph.predecessors(node)):
            if parent in toward_word:
                continue
            if len(toward_word) == max_nodes:
                result.update(
                    status="bounded",
                    visited_nodes=len(toward_word),
                    bounds_hit=["max_nodes"],
                )
                return result
            toward_word[parent] = node
            if graph.in_degree(parent) == 0:
                root = parent
                break
            pending.append((parent, depth + 1))
    result["visited_nodes"] = len(toward_word)
    if root is None:
        result["status"] = "bounded" if depth_limited else "rootless"
        result["bounds_hit"] = ["max_depth"] if depth_limited else []
        return result
    path = []
    current: str | None = root
    while current is not None:
        path.append(current)
        current = toward_word[current]
    result.update(status="found", path=path, distance=len(path) - 1)
    for source, target in zip(path, path[1:]):
        attributes = graph[source][target]
        result["edges"].append(
            {
                "source_node": source,
                "target_node": target,
                "relationship_types": list(attributes["relationship_types"]),
                "assertion_count": attributes["assertion_count"],
                # Resolve these bounded ID samples against the original rows
                # after all traces are known, without a full ID-to-row index.
                "evidence_sample": list(
                    attributes["assertion_ids"][:_TRACE_EVIDENCE_LIMIT]
                ),
                "evidence_truncated": attributes["assertion_count"]
                > _TRACE_EVIDENCE_LIMIT,
            }
        )
    return result


def _attach_evidence(traces: list[dict[str, Any]], assertions: pd.DataFrame) -> None:
    needed = {
        assertion_id
        for trace in traces
        for edge in trace["edges"]
        for assertion_id in edge["evidence_sample"]
    }
    if not needed:
        return
    columns = [
        "assertion_id",
        "source_node",
        "edge_type",
        "target_node",
        "normalized_edge_type",
    ]
    sample = assertions.loc[assertions.assertion_id.isin(needed), columns]
    records = {}
    for assertion_id, source, raw_type, target, normalized in sample.itertuples(
        index=False, name=None
    ):
        records[int(assertion_id)] = {
            "assertion_id": int(assertion_id),
            "source_node": source,
            "edge_type": raw_type,
            "target_node": target,
            "normalized_edge_type": normalized,
            "reversed": normalized in INVERSE_RELATIONSHIPS,
        }
    for trace in traces:
        for edge in trace["edges"]:
            edge["evidence_sample"] = [
                records[assertion_id] for assertion_id in edge["evidence_sample"]
            ]


def _analyze_projection(
    graph: nx.DiGraph,
    assertions: pd.DataFrame,
    language: str,
    raw_language_count: int,
    top_n: int,
    trace_words: tuple[str, ...],
    trace_max_depth: int,
    trace_max_nodes: int,
) -> dict[str, Any]:
    seeds = language_nodes(graph, language)
    selections = {}
    for index, (name, query) in enumerate(_QUERIES.items()):
        selected = query(graph, seeds)
        selections[name] = _selected_summary(graph, selected, seeds, 1 << index)
        del selected

    # Six pairwise comparisons need only 16 membership-mask counts, not four
    # retained full node sets. Edge counts likewise need one shared graph pass.
    node_masks = Counter(attrs.get(_MASK, 0) for _, attrs in graph.nodes(data=True))
    edge_masks: Counter[int] = Counter()
    facts: Counter[str] = Counter()
    for source, target, attributes in graph.edges(data=True):
        mask = graph.nodes[source].get(_MASK, 0) & graph.nodes[target].get(_MASK, 0)
        edge_masks[mask] += 1
        if mask & 1:
            facts.update(attributes["relationship_types"])
    for index, name in enumerate(_QUERIES):
        selections[name]["edges"] = sum(
            count for mask, count in edge_masks.items() if mask & (1 << index)
        )
    overlaps = []
    for (left_index, left), (right_index, right) in combinations(
        enumerate(_QUERIES), 2
    ):
        intersection = sum(
            count
            for mask, count in node_masks.items()
            if mask & (1 << left_index) and mask & (1 << right_index)
        )
        left_count, right_count = selections[left]["nodes"], selections[right]["nodes"]
        union = left_count + right_count - intersection
        overlaps.append(
            {
                "left": left,
                "right": right,
                "intersection_nodes": intersection,
                "union_nodes": union,
                "left_only_nodes": left_count - intersection,
                "right_only_nodes": right_count - intersection,
                "jaccard": intersection / union if union else None,
            }
        )
    traces = [
        _trace(graph, word, trace_max_depth, trace_max_nodes) for word in trace_words
    ]
    _attach_evidence(traces, assertions)
    return {
        "policy_version": graph.graph["policy_version"],
        "nodes": len(graph),
        "edges": graph.number_of_edges(),
        "seeds": len(seeds),
        "raw_language_nodes_excluded": raw_language_count - len(seeds),
        "queries": selections,
        "overlaps": overlaps,
        "rankings": _rankings(graph, facts, top_n),
        "traces": traces,
    }


def analysis_parameters(
    *,
    language: str = "eng",
    policies: Iterable[str] = ("root_only", "normalized"),
    top_n: int = 10,
    trace_words: Iterable[str] = (),
    trace_max_depth: int = 8,
    trace_max_nodes: int = 1000,
) -> dict[str, Any]:
    """Validate options before corpus loading and return report-ready parameters."""
    if not isinstance(language, str) or not language:
        raise ValueError("language must be a nonempty string")
    policies = tuple(policies)
    if not policies or len(set(policies)) != len(policies):
        raise ValueError("policies must be nonempty and unique")
    if any(policy not in {"root_only", "normalized"} for policy in policies):
        raise ValueError("policies must contain only 'root_only' or 'normalized'")
    for name, value, minimum in (
        ("top_n", top_n, 0),
        ("trace_max_depth", trace_max_depth, 0),
        ("trace_max_nodes", trace_max_nodes, 1),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
            raise ValueError(f"{name} must be an integer >= {minimum}")
    trace_words = tuple(trace_words)
    if any(not isinstance(word, str) for word in trace_words):
        raise ValueError("trace_words must contain strings")
    trace_words = tuple(sorted(set(trace_words)))
    return {
        "language": language,
        "policies": list(policies),
        "top_n": top_n,
        "trace_words": list(trace_words),
        "trace_max_depth": trace_max_depth,
        "trace_max_nodes": trace_max_nodes,
        "trace_evidence_limit": _TRACE_EVIDENCE_LIMIT,
    }


def analyze_assertions(
    assertions: pd.DataFrame,
    *,
    language: str = "eng",
    policies: Iterable[str] = ("root_only", "normalized"),
    top_n: int = 10,
    trace_words: Iterable[str] = (),
    trace_max_depth: int = 8,
    trace_max_nodes: int = 1000,
) -> dict[str, Any]:
    """Analyze a validated assertion table without changing it or deleting cycles.

    Rankings count distinct direct neighbors of each canonical relationship type
    inside the same combined ancestor selection. Zero-degree nodes are omitted;
    ties use exact label order. ``affix_like`` means only a literal leading or
    trailing hyphen in the word, not an independently verified linguistic class.

    Selected-set hashes encode sorted labels as compact UTF-8 JSON arrays with
    ``ensure_ascii=False``. Empty-union Jaccard is ``None``. Trace paths follow a
    deterministic reverse BFS to a nearest zero-indegree root in the projection.
    Rootless means the complete reverse search found no root; bounded means that
    could not be established. Trace limits bound visited nodes and path length,
    not execution time. Evidence samples retain at most five original records
    per edge, ordered by their input assertion IDs.
    """
    parameters = analysis_parameters(
        language=language,
        policies=policies,
        top_n=top_n,
        trace_words=trace_words,
        trace_max_depth=trace_max_depth,
        trace_max_nodes=trace_max_nodes,
    )
    policies = tuple(parameters["policies"])
    trace_words = tuple(parameters["trace_words"])
    raw_seeds = {
        node
        for node in chain(assertions.source_node, assertions.target_node)
        if node.partition(": ")[0] == language
    }
    report: dict[str, Any] = {
        "schema_version": 1,
        "parameters": parameters,
        "input": {
            "assertions": len(assertions),
            "raw_language_nodes": len(raw_seeds),
        },
        "projections": {},
    }
    for policy in policies:
        graph = project_assertions(assertions, policy)
        try:
            report["projections"][policy] = _analyze_projection(
                graph,
                assertions,
                language,
                len(raw_seeds),
                top_n,
                trace_words,
                trace_max_depth,
                trace_max_nodes,
            )
        finally:
            # Cached NetworkX views can form reference cycles. Clearing the
            # locally owned graph releases its large payload before policy 2.
            graph.clear()
    return report
