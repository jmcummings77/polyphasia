# Developing polyphasia

[Project introduction](../README.md) · [Data format](data-format.md) · [Graph behavior](graph-behavior.md)

This guide covers the reusable package and its checks. For notebook setup and full-data exploration, use the [research guide](research.md). The [Neo4j experiment](../experiments/README.md) has its own export instructions.

## Set up the core environment

Use Python 3.12 and [uv](https://docs.astral.sh/uv/). Run commands from the repository root:

```bash
uv sync --frozen
```

This installs the package and development tools from the lockfile. The core's runtime dependencies are pandas and NetworkX; Jupyter and visualization packages are optional. Neither tests nor the [quick-start example](../README.md#one-minute-introduction) require the full dataset.

## Run the checks

Run the tests directly, or use the script for the same suite with coverage:

```bash
uv run --extra analysis pytest
uv run --extra analysis ./run_tests.sh
```

Run formatting, lint, type, and whitespace checks:

```bash
uv run pre-commit run --all-files
```

The full test suite uses the optional `analysis` extra for figure generation.
Tests cover small TSV inputs, graph behavior, reproducible analysis artifacts,
and local experimental CSV generation. Historical notebooks and live Neo4j
imports are outside the automated test suite.

Query tests include independently specified selections and comparisons against
NetworkX on small generated cyclic graphs and DAGs. The benchmark CLI has a small
worker-process smoke test; full benchmark runs are manual and have no CI timing
thresholds. See [query benchmarks](query-benchmarks.md).

CI runs the checks above, builds distributions, and runs the sample against an installed wheel outside the checkout. The coverage gate is 90% across core statements and branches.

A separate CI job generates the [synthetic analysis fixture](../examples/README.md)
and executes `notebooks/verified_analysis.ipynb` in a fresh Python kernel. It
validates artifact checksums, renders the saved figures, and exercises source
traces. The full corpus is run separately and is not a CI dependency.

## Update dependencies and build

After changing `pyproject.toml`, update the lockfile and environment together:

```bash
uv lock
uv sync --frozen
```

Build the source distribution and wheel:

```bash
uv build
```

The wheel contains only `polyphasia`; install `polyphasia[analysis]` to render the
workflow's figures. The source distribution also includes examples, tests,
experiments, and the verified notebook with its execution script.

## Choose where code belongs

Keep reusable loading, graph logic, and verified analysis contracts in
`polyphasia/`, and add regression tests for behavior changes. Put ad hoc workflows
in `experiments/` or `notebooks/`. Workflows should accept explicit input and
output paths and avoid file or database operations at import time.

The version 0.1 API is still evolving. Update the [data-format reference](data-format.md) or [graph reference](graph-behavior.md) when behavior changes, and preserve the distinction between tested package behavior and research assumptions.
