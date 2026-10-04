# polyphasia

Etymological WordNet graph analysis with pandas and NetworkX.

`polyphasia` began as an exploration of relationships extracted from Wiktionary. Its reusable core now has automated tests and a small example that runs without downloading the full dataset. It remains a version 0.1 research project: the notebooks preserve exploratory work, and the public API may change.

## Quick start

Use Python 3.12 and [uv](https://docs.astral.sh/uv/). From the repository root:

```bash
uv sync --frozen
uv run python - <<'PY'
from pathlib import Path

from polyphasia.graph import DirectedGraph
from polyphasia.loader import clean_data_frame, load_to_pandas

edges = clean_data_frame(load_to_pandas(Path("examples/sample.tsv")))
graph = DirectedGraph(edges)
print(graph.info)    # DiGraph with 4 nodes and 3 edges
print(graph.is_dag)  # True
PY
uv run pytest
```

The example contains three synthetic relationships for demonstrating the API; it is not a linguistic reference. Tests use small fixtures and require no external dataset, database, or notebook environment.

## What is reusable?

| Location | Purpose and validation boundary |
| --- | --- |
| `polyphasia/` | Tested TSV loading, cleaning, relationship constants, and directed/undirected graph helpers. Runtime dependencies are pandas and NetworkX. |
| `examples/sample.tsv` | A small input for the quick start and manual exploration. |
| `notebooks/` | Historical analysis and visualizations. These depend on the full dataset and optional notebook packages; they are not exercised by the automated test suite. |
| `experiments/neo4j_export.py` | Experimental CSV export with an explicit input path and output directory. Local file generation is tested; importing into a running Neo4j database is not. |

For development and notebook setup, see [the developer guide](docs/README-DEV.md).

## Loading and cleaning data

Input is a headerless TSV with three columns: source node, relationship type, and target node. Each endpoint uses a language prefix followed by `: ` and a word:

```tsv
aaq: Pawanobskewi	rel:etymological_origin_of	eng: Penobscot
```

`load_to_pandas(path)` reads those columns as `source_node`, `edge_type`, and `target_node`. Prefer an explicit path; without one, it reads `data/raw/etymologies.tsv` relative to the current working directory.

`clean_data_frame(frame)` returns a copy with `source_language`, `source_word`, `target_language`, and `target_word` columns. It splits each endpoint at the first `: `, preserving any later colons or punctuation in the word. Malformed endpoints raise `ValueError`. An empty input, including a result with no retained relationships, produces a valid empty frame.

Cleaning normalizes the known relationship aliases in `edge_type` only. By default it keeps the root-to-leaf relationship types below. Pass `drop_rel_types=False` to retain all relationship types after alias normalization; this does not reverse their direction or infer missing relationships.

| Relationship type | Direction used by this project |
| --- | --- |
| `rel:etymological_origin_of` | Root to leaf; retained by default |
| `rel:has_derived_form` | Root to leaf; retained by default |
| `rel:etymology` | Leaf to root |
| `rel:is_derived_from` | Leaf to root |
| `rel:etymologically_related` | Related without a root-to-leaf direction |
| `rel:variant:orthography` | Orthographic variants without a root-to-leaf direction |

The aliases `rel:etymologically` and `rel:derived` map to `rel:etymologically_related` and `rel:is_derived_from`, respectively. These classifications reflect the original analysis; they are not a complete linguistic model or a guarantee that every reverse relationship exists in the source data.

The historical dataset is available [from the author's website](https://cs.rutgers.edu/~gd343/downloads/etymwn-20130208.zip). It is approximately 300 MB uncompressed and contains about six million relationships. The download is only needed for full-data exploration.

## Graph behavior and limits

`DirectedGraph` follows the retained source-to-target edges. Its language families include a root and all of that root's descendants when any member has the requested language prefix. `UndirectedGraph.language_subgraph()` includes entire connected components containing a node in that language. Language matching uses the complete prefix before `: `.

Both wrappers use simple graphs, so repeated edges between the same pair of nodes collapse. Directed root-family selection does not cover components with no roots. Longest-path analysis requires a DAG, and `remove_cycles()` removes all nodes participating in cycles, including their other incident edges. Cycle enumeration can be expensive on the full dataset. These are analysis choices to consider before using the helpers for other graph problems.

## Experimental Neo4j export

Choose the source TSV and a local output directory explicitly:

```bash
uv run python -m experiments.neo4j_export examples/sample.tsv data/processed/neo4j-export
```

The exporter writes CSV files for further experimentation. It does not connect to a database. The export schema and a complete Neo4j import workflow are experimental.

## Research roadmap

- Validate relationship directionality and information loss from filtering on the full dataset.
- Develop and verify a complete Neo4j import workflow.
- Refresh the historical visualizations and make notebooks reproducible end to end.
- Measure memory use and graph-algorithm performance on the full dataset.
