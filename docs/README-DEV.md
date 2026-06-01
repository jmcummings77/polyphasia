# Developing for polyphasia

==========================================================

This project uses [uv](https://docs.astral.sh/uv/) for dependency management.

Set up the full local environment:

```bash
uv sync --all-groups
```

Register the project kernel for Jupyter or VS Code:

```bash
uv run python -m ipykernel install --user --name polyphasia --display-name "Python 3.12 (polyphasia)"
```

The project targets Python 3.12. If you only need the dev tooling, use:

```bash
uv sync --only-group dev
```

Run the test script:

```bash
uv run ./run_tests.sh
```

Run pre-commit checks:

```bash
uv run pre-commit run --all-files
```

Update the lockfile after changing dependencies:

```bash
uv lock
```
