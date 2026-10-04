# Graph behavior and limits

[Project overview](../README.md) · [Development setup](README-DEV.md) · [Data format and cleaning](data-format.md)

`DirectedGraph` and `UndirectedGraph` wrap NetworkX graphs built from the [cleaned edge frame](data-format.md#cleaning-contract). They retain the relationship type and parsed source/target language and word fields as edge attributes.

## Construction and duplicate edges

`DirectedGraph` follows each retained source-to-target edge; it does not reinterpret the relationship type or add reverse edges. `UndirectedGraph` removes direction from those edges.

Both wrappers use simple graphs. Repeated edges between the same ordered pair collapse in the directed graph; opposite directions also collapse in the undirected graph. Each pair retains one set of attributes, so distinct relationships are not aggregated or preserved as parallel edges. An empty cleaned frame produces an empty graph.

## Language families

Language matching compares the complete token before `: `, with `eng` as the default. Tokens can have different lengths; `eng` does not match `eng-old`.

For `DirectedGraph`:

- `roots()` returns nodes with no incoming edges. Self-loops do not count as roots.
- `language_nodes(language)` returns a list of node sets. Each set contains a root and **all** its descendants when any member matches the language. This includes matching roots, other languages, and sibling branches. Families may overlap.
- `language_subgraph(language)` returns the induced view of those families, preserving original edge directions. Components with no roots, including isolated cycles, are omitted.

Explicit arguments change the selection. `language_nodes(language, roots=[...])` uses the supplied starting nodes, even if they are not roots; it still checks each resulting family for a language match. `language_subgraph(nodes=[{...}, {...}])` instead uses the union of the supplied node sets directly, without traversal or language filtering.

For `UndirectedGraph`, `language_nodes(language)` returns only matching node labels. `language_subgraph(language)` expands those seeds to their entire connected components, including nodes in other languages. Passing `nodes=[...]` replaces the language-selected seeds and expands every supplied seed to its connected component. The `connected_components` property returns the component node sets.

For either wrapper, an explicit empty `nodes=[]` gives an empty subgraph. Subgraphs are NetworkX views: attribute edits are shared with the underlying graph, and their structure cannot be edited directly. Call `.copy()` on a returned view when an independent graph is needed.

## Cycles and analysis

`DirectedGraph.is_dag` reports whether the graph is acyclic. `get_cycles()` returns its simple cycles, including self-loops. `get_longest_path()` requires a DAG and raises `NetworkXUnfeasible` when a cycle is present.

`remove_cycles()` mutates the graph by deleting **every node participating in a cycle**, together with all its incident edges. This can disconnect nodes outside the cycles. Cycle enumeration can be expensive on the full dataset.

Both wrappers provide `nodes_by_degree(subgraph)`, returning `(node, degree)` pairs in descending order. Directed degree counts incoming plus outgoing edges; ties preserve the graph's node iteration order.

These choices support the original analysis. Full-dataset memory use, algorithm performance, and the information lost through relationship filtering remain research work; see the [development guide](README-DEV.md) for the automated validation boundary.
