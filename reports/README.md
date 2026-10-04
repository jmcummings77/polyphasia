# Recorded analysis runs

These directories contain intentionally published, compact run artifacts. Raw
data and ordinary generated runs remain in Git-ignored `data/raw/` and
`data/processed/`. The working improvement plan remains local.

- [2013-02-08 corpus](20130208/README.md): full source run recorded on 2026-10-04
  UTC, with query comparisons, rankings, source traces, figures, and a manifest.

Each snapshot preserves its generated files without editing their contents.
Validate it with `polyphasia.analysis.validate_run`. The
[verified notebook](../notebooks/verified_analysis.ipynb) can consume a snapshot
without rebuilding the graphs or downloading the original corpus. Regenerating
the metrics and independently checking assertion ordinals require the pinned
source input. See the [workflow guide](../docs/reproducible-analysis.md).
