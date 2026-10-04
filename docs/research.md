# Research and notebook status

`polyphasia` began as an open-ended investigation of Etymological Wordnet with
pandas and NetworkX. Current analytical work uses explicit graph policies,
cycle-preserving queries, source checksums, and reproducible artifacts. The
original exploratory notebooks remain available in a separate archive.

## Start with verified work

- [Reproducible workflow](reproducible-analysis.md): generate an audited run from
  the synthetic fixture or pinned full corpus, validate it, and execute its
  analysis notebook in a fresh kernel.
- [Published full-corpus run](../reports/20130208/README.md): recorded findings,
  query counts, rankings, traces to original assertions, and execution provenance.
- [Published query benchmarks](../reports/benchmarks/README.md): measured
  equivalent-algorithm comparisons on bounded synthetic graphs.
- [Notebook catalog](../notebooks/README.md): maintained reader and explicitly
  archival exploration, with their separate validation boundaries.

The [project README](../README.md) provides the small runnable package example.
The [developer guide](README-DEV.md) covers setup and checks. The core environment
requires pandas and NetworkX; plotting and notebook execution are optional extras.
The [synthetic fixture](../examples/README.md) makes workflow execution independent
of a full-data download. It is not a sample of corpus behavior.

## Inspect the published corpus run

From the repository root:

```sh
uv sync --frozen --extra notebooks
uv run --frozen --extra notebooks python scripts/execute_analysis_notebook.py \
  --artifacts reports/20130208 \
  --output data/processed/published-full-run.executed.ipynb
```

Choose a new output path. The runner uses a fresh kernel and validates artifact
hashes before interpretation; it does not rebuild the graphs or fetch data.
The maintained notebook runs against generated synthetic artifacts in CI and
was also executed against the recorded full run. Follow the workflow guide when
regenerating metrics instead of reading a published snapshot.

## Historical exploration

The four older notebooks now live under
[`notebooks/historical/`](../notebooks/historical/README.md). Their original bytes
and saved outputs are preserved, including stale results and unfinished cells.
They are not CI inputs and are not claimed to execute end to end.

Moving them adds a directory level; their original relative paths require manual
adaptation before use. For a kernel working in that directory, a former
`../data/` reference becomes `../../data/`. Review APIs and analytical choices as
well as paths. The archive guide documents this boundary; the verified notebook
is the entry point for new analysis.

The [experimental Neo4j exporter](../experiments/README.md) remains a separate
source-only experiment. Local CSV generation is tested; a live database import
is not part of the verified workflow.

## Dataset and interpretation

The full run uses Etymological Wordnet **2013-02-08**, primarily extracted from
English Wiktionary with manual additions. The [source notes](../data/data_source.md)
pin its archive and TSV checksums. The preserved
[upstream README](../data/data_source_readme.txt) supplies credits, citation, and
**CC-BY-SA 3.0** source terms; the code's MIT license does not replace them.
Raw data stays in ignored `data/raw/`, and ordinary generated runs stay in
ignored `data/processed/`.

The [data audit](data-audit.md) measures retained assertions, inverse coverage,
and cycle membership for the pinned snapshot. The [query contracts](graph-behavior.md)
separate ancestry from family and component context. Counts describe recorded
labels and relationships under those choices. They do not independently resolve
word senses, historical dates, uncertain origins, or source coverage. Subsequent
linguistic interpretation must inspect source evidence and preserve those limits.
