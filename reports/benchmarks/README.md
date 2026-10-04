# Published query benchmark

[Benchmark guide](../../docs/query-benchmarks.md) · [Recorded reports](../README.md)

[query-benchmark.json](query-benchmark.json) is the unchanged result of the
bounded synthetic query suite completed on **2026-10-04 at 03:36:12 UTC**. It was
copied from `data/processed/query-benchmark.json`; publication did not rerun the
measurements or rewrite the JSON.

| Identity | Value |
| --- | --- |
| Bytes | 68,529 |
| SHA-256 | `aa2a528d6466d09e8afc5d731a7a62cf683461163788910156b9babb2a52a290` |
| Environment | Python 3.12.9, NetworkX 3.3, macOS 26.5.1, arm64 |
| Main graph sizes | 128, 256, 512 nodes |
| Complete directed SCC sizes | 6, 7, 8 nodes |
| Measurements | 15 comparisons; three repetitions of two methods; 90 fresh workers |

The recorded implementation SHA-256 values identify the measured source:

```text
benchmark_queries.py  1e42335f77178d5e3e78f3b2112e48ab0ac40e70395500a6f5ad65ab683b8001
queries.py            5c690469ee8f9406e5a353df97c61bd4af6cb85ed92ec9ad2eddd959cc6d1dcb
```

Publication checks verified the file identity, both source hashes, all 90 input
and result fingerprints, repetition coverage, medians/minima/maxima, and every
reported timing ratio. The JSON retains every individual measurement. It records
implementation hashes rather than a Git revision; no commit identity has been
retroactively inserted.

## Measurement boundary

Each worker performs one untimed warmup and garbage collection before timing a
single query, including selected-node materialization. Input construction,
fingerprinting, and process startup are outside that timer. Input and selected-set
parity are required before reporting a timing ratio. The
[benchmark guide](../../docs/query-benchmarks.md) specifies each baseline and
graph topology and provides commands to generate a new report.

Peak RSS is the complete worker process high-water mark, including imports and
warmup. In particular, NetworkX cycle enumeration initialized the installed
pandas/NumPy/SciPy stack during this run's warmup. Its higher RSS is not a measure
of incremental cycle-enumeration allocation. The small graphs and three
repetitions do not establish full-corpus speedups or general memory savings.

These inputs are generated synthetic graphs; this report contains no extracted
Etymological Wordnet records. The separate [full-corpus report](../20130208/README.md)
documents its own source attribution and reuse terms. The repository's
[MIT license](../../LICENSE) covers the benchmark code.

## Render the recorded measurements

From the repository root, use a new output directory:

```sh
uv run --frozen --extra analysis python -m scripts.build_portfolio_figures \
  --analysis reports/20130208 \
  --benchmark reports/benchmarks/query-benchmark.json \
  --output data/processed/portfolio-figures
```

The renderer validates the saved inputs and draws the recorded measurements; it
does not execute the benchmark. Its `runtime-memory-scaling.png` figure shows
root-family and component queries across the three main graph sizes, with
median and minimum–maximum measurements. The
[published figure](../../docs/figures/runtime-memory-scaling.png) uses this report.
