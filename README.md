# polyphasia

## One-minute introduction

Etymological WordNet stores word relationships as flat TSV rows, making derivation paths and language families hard to inspect. Polyphasia turns those rows into directed and undirected NetworkX graphs.

The bundled three-edge sample produces:

```text
DiGraph with 4 nodes and 3 edges
Acyclic: True
```

Two engineering decisions shape the project:

1. **Keep the reusable core small and tested.** pandas and NetworkX handle parsing and graphs. Notebook dependencies are optional, and experimental export scripts live outside the installed package.
2. **Make graph assumptions explicit.** Cleaning keeps root-to-derivative relationships by default; simple graphs collapse repeated edges. These choices simplify traversal but can discard relationship information.

Run the example with Python 3.12 and [uv](https://docs.astral.sh/uv/) from the repository root:

```bash
uv sync --frozen
uv run python - <<'PY'
from pathlib import Path
from polyphasia.graph import DirectedGraph
from polyphasia.loader import clean_data_frame, load_to_pandas

edges = clean_data_frame(load_to_pandas(Path("examples/sample.tsv")))
graph = DirectedGraph(edges)
print(graph.info)
print(f"Acyclic: {graph.is_dag}")
PY
```

The sample is synthetic. No dataset download, notebook environment, or database is needed.

## Reproducible analysis

The [analysis workflow](docs/reproducible-analysis.md) compares relationship
policies and ancestry/context queries, separates origin and derivation rankings,
and traces example paths to source assertions. Start with the 37-record synthetic
fixture; the verified notebook consumes generated, checksummed artifacts and
runs from a fresh kernel in CI.

The [recorded full-corpus run](reports/20130208/README.md) publishes query
comparisons, relationship-specific rankings, and traceable examples with its
input and implementation fingerprints.

## Documentation

| Guide | What it covers |
| --- | --- |
| [Data format and cleaning](docs/data-format.md) | TSV schema, validation, relationship filtering, and aliases |
| [Data audit and projections](docs/data-audit.md) | Source provenance, assertion preservation, inverse coverage, and cycle diagnostics |
| [Graph queries and behavior](docs/graph-behavior.md) | Explicit ancestry/context queries, cycles, condensation, and wrapper contracts |
| [Query benchmarks](docs/query-benchmarks.md) | Equivalent-result comparisons with isolated timing and memory measurements |
| [Reproducible analysis](docs/reproducible-analysis.md) | Fixture/full-data commands, analytical boundaries, artifacts, and verified notebook |
| [Development](docs/README-DEV.md) | Setup, tests, quality checks, and packaging |
| [Research and notebooks](docs/research.md) | Project background, dataset provenance, notebook setup, and roadmap |
| [Experimental Neo4j export](experiments/README.md) | Portable CSV export and its validation limits |
