# Graph behavior and limits

[Project overview](../README.md) · [Development setup](README-DEV.md) · [Data format and cleaning](data-format.md)

`DirectedGraph` and `UndirectedGraph` wrap NetworkX graphs built from the [cleaned edge frame](data-format.md#cleaning-contract). They retain the relationship type and parsed source/target language and word fields as edge attributes.

For new analysis, use the explicit queries below with the evidence-preserving
graphs returned by [`project_assertions`](data-audit.md). This separates the
choice of relationship policy from the meaning of a query.

## Explicit graph queries

```python
from pathlib import Path

from polyphasia.assertions import prepare_assertions, project_assertions
from polyphasia.loader import load_to_pandas
from polyphasia.queries import ancestor_subgraph, language_nodes

assertions = prepare_assertions(load_to_pandas(Path("examples/sample.tsv")))
graph = project_assertions(assertions, policy="normalized")
english = language_nodes(graph, "eng")
ancestry = ancestor_subgraph(graph, english)
```

All selection functions in `polyphasia.queries` take a graph and an iterable of
seed nodes. They return induced NetworkX **views**: the selected nodes retain all
original edges between them, in their original directions, with their assertion
evidence. Attribute edits are shared with the source graph. Use `.copy()` for an
independent graph structure and attribute dictionaries; nested attribute values
still follow NetworkX's shallow-copy behavior.

| Function | Selected nodes |
| --- | --- |
| `ancestor_subgraph(graph, seeds)` | Seeds plus every node that can reach a seed through directed edges. |
| `descendant_subgraph(graph, seeds)` | Seeds plus every node reachable from a seed through directed edges. |
| `root_family_subgraph(graph, seeds)` | All zero-indegree roots that can reach a seed, and all their descendants, including sibling branches. |
| `component_subgraph(graph, seeds)` | Entire connected components containing seeds; weakly connected components for a directed graph. |

For example, consider these edges and the seed `eng: root`:

```text
lat: radix -> eng: root -> eng: rooted
lat: radix -> fra: racine <- deu: Quelle
```

Ancestors include `lat: radix` and the seed. Descendants include the seed and
`eng: rooted`. Root-family context additionally includes `fra: racine`.
Component selection includes all five nodes, including `deu: Quelle`.

Ancestor, descendant, and component selection include seeds in rootless cyclic
components. Root-family context still requires a zero-indegree root; it omits a
component consisting only of a directed cycle. This is an explicit selection
policy, not a need to delete cyclic evidence. No query deletes nodes or edges.

Duplicate seeds are harmless, generator inputs are supported, empty seeds return
an empty view, and a missing seed raises `NodeNotFound`. Directed query
functions reject undirected inputs with `NetworkXNotImplemented`;
`component_subgraph` accepts either kind. `language_nodes(graph, language)` is a
separate seed selector matching the entire string token before `: `; it ignores
nonstring node labels and does not infer a language from other attributes.

Reachability uses a shared visited set across seeds. Component selection visits
each selected component once. Root-family selection finds candidate roots in a
reverse traversal, then gathers their descendants in a shared forward traversal.
These selections take linear work in graph nodes and edges plus the number of
supplied seeds, excluding the cost of subsequently consuming an induced view.

## Cycle diagnostics and condensation

`cyclic_nodes(graph)` identifies nodes belonging to strongly connected components
of size greater than one, plus singleton self-loops. It does not enumerate simple
cycles or mutate the graph. Strongly connected components identify cyclic
membership with linear work in nodes and edges.

`cycle_examples(graph, limit=5, max_length=6)` returns at most five simple cycles,
each at most six nodes long by default. `limit` must be nonnegative and
`max_length` positive. This bounds output and cycle length, **not execution
time**. Finding cycles can still be expensive; examples are for selected small
subgraphs, while `cyclic_nodes` is the appropriate full-graph diagnostic.

`condensation_graph(graph)` contracts each strongly connected component into a
single node and returns a DAG. Each component node has a `members` set; the
graph's `mapping` attribute maps original nodes to component IDs. IDs are opaque
and may differ with graph insertion order. Condensation is a structural summary:
original relationship attributes and assertion IDs are not copied onto its
edges. Keep the original graph to inspect evidence through the membership map.

```python
import networkx as nx

from polyphasia.queries import condensation_graph

dag = condensation_graph(graph)
component_path = nx.dag_longest_path(dag)
member_sets = [dag.nodes[component]["members"] for component in component_path]
```

This path describes transitions between components. It is not a longest word
lineage, and the number of component steps is not a count of etymological
generations. Ancestor queries do not require condensation or cycle removal.

## Full-corpus query validation

The normalized policy from the [pinned 2013-02-08 audit](data-audit.md) produces
2,743,119 nodes and 2,692,097 edges, including 421,972 English seeds. With cycles
retained and the same graph and seeds for all four queries:

| Selection | Nodes | Edges | English seeds included |
| --- | ---: | ---: | ---: |
| Ancestors | 456,080 | 457,126 | 421,972 |
| Descendants | 433,934 | 429,023 | 421,972 |
| Root families | 1,033,985 | 1,047,990 | 420,901 |
| Weak components | 1,608,497 | 1,690,682 | 421,972 |

Root-family context includes sibling branches while omitting 1,071 English seeds
without a path from a zero-indegree root. This explains why its size cannot be
interpreted as an ancestor count. The four selections preserve the input graph;
no cyclic nodes are removed to make them possible.

`cyclic_nodes` identifies the same 3,881 nodes as the independent phase 1 audit.
Condensation returns a verified DAG with 2,741,931 components and 2,687,373 edges.
The full-data check verified membership coverage for every original node and a
condensed edge for every edge crossing component boundaries. The source graph's
node and edge counts remain unchanged.

To reproduce the table, replace the sample path in the example above with
`data/raw/etymologies.tsv`, then run:

```python
from polyphasia.queries import (
    component_subgraph,
    descendant_subgraph,
    root_family_subgraph,
)

for query in (
    ancestor_subgraph,
    descendant_subgraph,
    root_family_subgraph,
    component_subgraph,
):
    result = query(graph, english)
    print(
        query.__name__,
        result.number_of_nodes(),
        result.number_of_edges(),
        sum(node in result for node in english),
    )
```

These are results for one pinned graph policy, not historical language population
statistics. The local verification report is
`data/processed/phase2-full-queries.json`; its timings include counting and
fingerprinting and are not comparative benchmark measurements.

## Construction and duplicate edges

`DirectedGraph` follows each retained source-to-target edge; it does not reinterpret the relationship type or add reverse edges. `UndirectedGraph` removes direction from those edges.

Both wrappers use simple graphs. Repeated edges between the same ordered pair collapse in the directed graph; opposite directions also collapse in the undirected graph. Each pair retains one set of attributes, so distinct relationships are not aggregated or preserved as parallel edges. An empty cleaned frame produces an empty graph.

## Language families

Language matching compares the complete token before `: `, with `eng` as the default. Tokens can have different lengths; `eng` does not match `eng-old`.

For `DirectedGraph`:

- `roots()` returns nodes with no incoming edges. Self-loops do not count as roots.
- `language_nodes(language)` returns a list of node sets. Each set contains a root and **all** its descendants when any member matches the language. This includes matching roots, other languages, and sibling branches. Families may overlap.
- `language_subgraph(language)` returns the induced view of those families, preserving original edge directions. Components with no roots, including isolated cycles, are omitted.

The default `language_subgraph` now uses the shared root-family traversals above.
`language_nodes` still materializes individual, potentially overlapping families;
requesting those separate sets can be much more expensive than requesting their
union with `language_subgraph` or `root_family_subgraph`.

Explicit arguments change the selection. `language_nodes(language, roots=[...])` uses the supplied starting nodes, even if they are not roots; it still checks each resulting family for a language match. `language_subgraph(nodes=[{...}, {...}])` instead uses the union of the supplied node sets directly, without traversal or language filtering.

For `UndirectedGraph`, `language_nodes(language)` returns only matching node labels. `language_subgraph(language)` expands those seeds to their entire connected components, including nodes in other languages. Passing `nodes=[...]` replaces the language-selected seeds and expands every supplied seed to its connected component. The `connected_components` property returns the component node sets.

For either wrapper, an explicit empty `nodes=[]` gives an empty subgraph. Subgraphs are NetworkX views: attribute edits are shared with the underlying graph, and their structure cannot be edited directly. Call `.copy()` on a returned view when an independent graph is needed.

## Cycles and analysis

`DirectedGraph.is_dag` reports whether the graph is acyclic. `get_cycles()` returns its simple cycles, including self-loops. `get_longest_path()` requires a DAG and raises `NetworkXUnfeasible` when a cycle is present.

`remove_cycles()` mutates the graph by deleting **every node participating in a cycle**, together with all its incident edges. This can disconnect nodes outside the cycles. It now identifies those nodes through strongly connected components, with the same removal semantics. The legacy `get_cycles()` remains exhaustive and can be expensive; new analyses should use the non-destructive diagnostics above.

Both wrappers provide `nodes_by_degree(subgraph)`, returning `(node, degree)` pairs in descending order. Directed degree counts incoming plus outgoing edges; ties preserve the graph's node iteration order.

The [data audit](data-audit.md) measures information loss on the pinned corpus.
The [query benchmarks](query-benchmarks.md) compare equivalent selection and cycle
membership algorithms on reproducible synthetic inputs. Neither establishes that
graph reachability alone is a complete linguistic model. See the
[development guide](README-DEV.md) for the automated validation boundary.
