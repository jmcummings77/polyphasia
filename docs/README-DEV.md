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
uv run pytest
uv run ./run_tests.sh
```

Run formatting, lint, type, and whitespace checks:

```bash
uv run pre-commit run --all-files
```

Tests cover small TSV inputs, graph behavior, and local experimental CSV generation. Historical notebooks and live Neo4j imports are outside the automated test suite.

CI runs the checks above, builds distributions, and runs the sample against an installed wheel outside the checkout. The coverage gate is 90% across core statements and branches.

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

The wheel contains only `polyphasia`. The source distribution also includes the example, tests, and experiments.

## Choose where code belongs

Keep reusable loading and graph logic in `polyphasia/`, and add regression tests for behavior changes. Put analysis-specific workflows in `experiments/` or `notebooks/`. New workflows should accept explicit input and output paths and avoid file or database operations at import time.

The version 0.1 API is still evolving. Update the [data-format reference](data-format.md) or [graph reference](graph-behavior.md) when behavior changes, and preserve the distinction between tested package behavior and research assumptions.
