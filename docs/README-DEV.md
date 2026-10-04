# Developing polyphasia

The project targets Python 3.12 and uses [uv](https://docs.astral.sh/uv/) for dependency management. Run the following commands from the repository root.

## Core development

Install the package and development tools from the lockfile:

```bash
uv sync --frozen
```

The package requires pandas and NetworkX. Notebook and visualization dependencies are optional, so the core test suite does not require Jupyter or the full Etymological WordNet dataset.

Run the tests directly, or use the script to run the same suite with coverage:

```bash
uv run pytest
uv run ./run_tests.sh
```

Tests cover loading and cleaning small TSV inputs, graph behavior, and local experimental export output. They do not execute historical notebooks or validate a Neo4j database import.

CI runs these tests with core coverage, checks formatting and types, builds the distributions, and runs the sample against the installed wheel outside the checkout. The coverage gate is 90% across core statements and branches. The wheel contains only `polyphasia`; the source distribution also includes the example, tests, and experiments.

Run the repository checks:

```bash
uv run pre-commit run --all-files
```

When changing dependencies, update both `pyproject.toml` and the lockfile:

```bash
uv lock
uv sync --frozen
```

Keep reusable data and graph logic in `polyphasia/` and add a regression test for changes to its behavior. Put analysis-specific workflows in `experiments/` or `notebooks/`. New workflows should accept explicit input and output paths and avoid machine-specific locations or work at import time.

## Historical notebooks

Install the optional analysis environment:

```bash
uv sync --frozen --extra notebooks
uv run --extra notebooks python -m ipykernel install --user --name polyphasia --display-name "Python 3.12 (polyphasia)"
```

Download and extract the dataset linked in the [README](../README.md) to `data/raw/etymologies.tsv`. Existing notebook cells assume a working directory of `notebooks/`, so launch Jupyter there:

```bash
cd notebooks
uv run --extra notebooks jupyter lab
```

Select the `Python 3.12 (polyphasia)` kernel. The notebooks are historical research artifacts and are not verified end to end by CI. Expect to update analysis cells and dataset paths as needed. In particular, the loader's default path is now relative to the current working directory; from a notebook, pass `Path("../data/raw/etymologies.tsv")` explicitly.

## Experimental Neo4j export

From the repository root:

```bash
uv run python -m experiments.neo4j_export examples/sample.tsv data/processed/neo4j-export
```

The exporter takes an input file and output directory rather than relying on a local Neo4j installation path. Its automated tests verify local CSV generation only. Changes to the export schema require separate validation against the intended Neo4j import workflow.
