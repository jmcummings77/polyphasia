# Notebook catalog

[Reproducible workflow](../docs/reproducible-analysis.md) · [Published reports](../reports/README.md)

| Notebook | Status and purpose |
| --- | --- |
| [verified_analysis.ipynb](verified_analysis.ipynb) | Verified artifact reader. Validates a completed run, then presents query comparisons, rankings, and source traces. Executed against the synthetic fixture in CI and against the recorded full run. |
| [historical/initial_eda.ipynb](historical/initial_eda.ipynb) | Archival exploration of loading, summaries, and plots; saved outputs include interrupted work. |
| [historical/connectivity_analysis.ipynb](historical/connectivity_analysis.ipynb) | Archival connectivity investigation with older APIs and unresolved cells. |
| [historical/directed_acyclic_graph_analysis.ipynb](historical/directed_acyclic_graph_analysis.ipynb) | Archival directed/root-family exploration, including deletion of cyclic nodes. |
| [historical/undirected_graph_analysis.ipynb](historical/undirected_graph_analysis.ipynb) | Archival undirected graph exploration and historical comparisons. |

Only `verified_analysis.ipynb` is part of the maintained analysis workflow.
Archival notebooks are preserved byte-for-byte; their saved results are not
reproduced evidence. Read the [archive boundary](historical/README.md) before
attempting to adapt them.

## Inspect a verified run

From the repository root, read the published corpus artifacts without downloading
the source dataset or rebuilding its graphs:

```sh
uv sync --frozen --extra notebooks
uv run --frozen --extra notebooks python scripts/execute_analysis_notebook.py \
  --artifacts reports/20130208 \
  --output data/processed/published-full-run.executed.ipynb
```

Use a new output path. The runner starts a fresh kernel with the current
interpreter and a temporary kernel specification; no global kernel registration
is needed. Any cell failure aborts execution. To generate a new synthetic or
full-data run first, follow the [workflow guide](../docs/reproducible-analysis.md).

The [source notes](../data/data_source.md) and
[upstream README](../data/data_source_readme.txt) identify the full dataset,
attribution, citation, and license. The expanded fixture is
[explicitly synthetic](../examples/README.md), so its successful execution is a
software check rather than a linguistic finding.
