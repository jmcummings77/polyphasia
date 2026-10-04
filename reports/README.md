# Recorded analysis runs

These directories contain intentionally published, compact run artifacts. Raw
data and ordinary generated runs remain in Git-ignored `data/raw/` and
`data/processed/`. The working improvement plan remains local.

- [2013-02-08 corpus](20130208/README.md): full source run recorded on 2026-10-04
  UTC, with query comparisons, rankings, source traces, figures, and a manifest.
- [Synthetic query benchmarks](benchmarks/README.md): the unchanged report from
  15 equivalent-query comparisons and 90 fresh-worker measurements, with input
  and selected-set fingerprints, implementation hashes, timings, and process RSS.

The corpus snapshot preserves its generated files without editing their contents.
Validate it with `polyphasia.analysis.validate_run`. The
[verified notebook](../notebooks/verified_analysis.ipynb) can consume a snapshot
without rebuilding the graphs or downloading the original corpus. Regenerating
the metrics and independently checking assertion ordinals require the pinned
source input. See the [workflow guide](../docs/reproducible-analysis.md).

The benchmark uses a separate JSON schema. Its provenance notes record the
unchanged file hash and checks of repetition coverage, parity, and summary
arithmetic; the [portfolio figure renderer](../scripts/build_portfolio_figures.py)
validates these measurements before plotting them. They describe bounded
synthetic workloads, not measured full-corpus speedups.

Data-derived corpus artifacts and assertion excerpts retain the source's
attribution and **CC-BY-SA 3.0** terms. See the
[source notes](../data/data_source.md), [upstream README](../data/data_source_readme.txt),
and [corpus reuse statement](20130208/README.md#source-and-reuse). The code's MIT
license does not replace the dataset's license. The synthetic benchmark contains
no source-corpus records.
