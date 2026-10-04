# Research and historical notebooks

`polyphasia` began as an open-ended investigation of Etymological WordNet relationships using pandas and NetworkX. The notebooks preserve that exploration, including directed and undirected graph analysis and visualizations. They are useful research material, but they are not verified end to end by the automated test suite.

For the small, runnable example, start with the [project README](../README.md). For package development and checks, use the [developer guide](README-DEV.md). Neither the example nor the core tests require the full dataset or a notebook environment.

## Scope

- **Reusable core:** `polyphasia/` contains tested TSV loading, cleaning, relationship constants, and graph helpers. Its runtime dependencies are pandas and NetworkX. The public API may change while the project remains at version 0.1.
- **Historical notebooks:** `notebooks/` contains analysis that depends on the full dataset and optional notebook packages. Expect to update analysis cells and paths when revisiting it.
- **Experimental export:** `experiments/` contains source-only workflows outside the installed package. The Neo4j exporter has tests for local CSV generation, but no live database import is tested. See the [experiment guide](../experiments/README.md) for commands and output details.

## Dataset and provenance

The historical input is Etymological WordNet 2013-02-08, primarily mined from English Wiktionary with some manual additions. It is approximately 300 MB uncompressed and contains about six million relationships.

The [data source notes](../data/data_source.md) provide the download link. Read the preserved [upstream README](../data/data_source_readme.txt) for the dataset format, credits, license, and citation requirements. The dataset has its own license; do not assume the repository's code license applies to it.

Place the extracted TSV at `data/raw/etymologies.tsv`, renaming it if necessary. This download is only needed for full-data exploration.

## Notebook setup

Use Python 3.12. From the repository root, install the optional analysis environment and register its kernel:

```bash
uv sync --frozen --extra notebooks
uv run --extra notebooks python -m ipykernel install --user --name polyphasia --display-name "Python 3.12 (polyphasia)"
```

Existing notebook cells assume a working directory of `notebooks/`. Launch Jupyter there:

```bash
cd notebooks
uv run --extra notebooks jupyter lab
```

Select the `Python 3.12 (polyphasia)` kernel. The loader's default data path is relative to the current working directory, so notebook calls should pass `Path("../data/raw/etymologies.tsv")` explicitly, with `Path` imported from `pathlib`.

## Research roadmap

- Use the [data audit and explicit projections](data-audit.md) to measure inverse
  coverage and information loss before interpreting graph results.
- Validate relationship directionality and information loss from filtering on the full dataset. The current classifications reflect the original analysis, not a complete linguistic model or a guarantee that every reverse relationship exists.
- Refresh historical visualizations and make the notebooks reproducible end to end.
- Develop and verify a complete Neo4j import workflow.
- Measure memory use and graph-algorithm performance on the full dataset.
