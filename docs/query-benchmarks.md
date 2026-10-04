# Graph query benchmarks

[Query contracts](graph-behavior.md) · [Data audit](data-audit.md) · [Development](README-DEV.md)

The benchmark compares equivalent node selections before reporting performance.
It targets repeated traversal of overlapping paths/components and exhaustive
cycle enumeration. It does not compare ancestor selection with root-family
selection: those answer different questions.

## Reproduce the comparisons

From the repository root on Linux or macOS:

```sh
uv run python -m experiments.benchmark_queries \
  --output data/processed/query-benchmark.json
```

The default suite runs 15 comparisons, each with three repetitions of two
methods, for 90 fresh worker processes. Each worker has a 20-second timeout.
The output file must not already exist. `data/processed/` is ignored by Git.

For a quick smoke run:

```sh
uv run python -m experiments.benchmark_queries \
  --sizes 8 --cycle-sizes 3 --repeats 1 \
  --output data/processed/query-benchmark-smoke.json
```

Main graph sizes are bounded between 4 and 2,048 nodes; complete directed cycle
graphs between 2 and 8 nodes. These limits keep the exhaustive baselines usable.
A failed worker, timeout, or differing result fails the suite instead of
producing a speedup claim.

## Inputs and baselines

| Input | Default sizes | Query | Baseline | New implementation |
| --- | --- | --- | --- | --- |
| Directed chain | 128, 256, 512 | Ancestors of overlapping seeds | Call `nx.ancestors` separately for every seed | Shared reverse traversal |
| Multiple roots feeding a common chain | 128, 256, 512 | Ancestors of overlapping seeds | Call `nx.ancestors` separately for every seed | Shared reverse traversal |
| Multiple roots feeding a common chain | 128, 256, 512 | Root-family union | Collect each root's descendants separately, then select matching families | Reverse traversal to matching roots, then shared forward traversal |
| Four disjoint undirected paths | 128, 256, 512 | Components containing seeds | Build a BFS tree per seed and accumulate repeated nodes, following the original wrapper | Shared traversal of selected components |
| Complete directed graph with a self-loop | 6, 7, 8 | Cyclic nodes | Enumerate simple cycles and union their nodes | Strongly connected components |

Size always means total node count. Inputs and seed placement are deterministic;
the output records node/edge/seed counts and graph-plus-seed fingerprints. These
workloads deliberately expose overlapping work and cycle proliferation. They are
synthetic stress cases, not a representative sample of the etymological corpus.

## Measurement and correctness

Each worker constructs the same input, performs one untimed warmup, collects
garbage, and times one query with `perf_counter`. Both implementations materialize
the selected node set within the timed interval. This prevents a lazy view from
appearing faster merely because its result has not been consumed. Graph building,
fingerprinting, and subprocess startup are outside the query timer.

Peak resident memory is the fresh worker's process high-water RSS, including the
interpreter, imports, input construction, warmup, query, and fingerprinting. It is
**not incremental query allocation**. Small graph results can be dominated by the
runtime's baseline memory. Linux KiB values are converted to bytes; macOS reports
bytes. RSS measurement on other platforms is explicitly unsupported.

The driver alternates which method runs first across repetitions. It reports
median, minimum, and maximum query time and peak RSS, retains all individual
runs, and records Python/NetworkX/platform versions and implementation hashes.

All methods and repetitions must agree on the input fingerprint, selected-node
count, and selected-set fingerprint before a timing ratio is emitted. Because
the selection results are induced views of the same graph, equal node sets also
select the same original edges and attributes. Separate tests verify those view
and evidence-preservation contracts, seed validation, rootless cycles, and
condensation mappings. Tests do not assert timing thresholds.

Interpret ratios in the context of graph shape, seed overlap, input size, and
host load. Full-corpus query validation complements these controlled comparisons;
it does not provide a full-corpus baseline speedup.

## Measured example

The default suite completed on 2026-10-04 (UTC), with Python 3.12.9,
NetworkX 3.3, and macOS 26.5.1 on arm64. All 15 comparisons passed input and
result parity checks. These are the largest cases, using the median of three
fresh workers per method after the warmup described above:

| Query and input | Nodes | Baseline (ms) | Shared traversal / SCC (ms) | Time ratio |
| --- | ---: | ---: | ---: | ---: |
| Ancestors, chain | 512 | 13.588 | 0.176 | 77.2× |
| Ancestors, overlapping roots | 512 | 12.404 | 0.182 | 68.2× |
| Root families, overlapping roots | 512 | 14.508 | 0.332 | 43.7× |
| Components, disjoint paths | 512 | 28.740 | 0.190 | 151.1× |
| Cyclic nodes, complete directed graph | 8 | 11.693 | 0.030 | 393.6× |

The chain's baseline time grew from 0.845 ms at 128 nodes to 13.588 ms at 512;
shared traversal grew from 0.065 ms to 0.176 ms. This is consistent with avoiding
repeated walks through shared ancestry as both graph size and seed count grow.
It does not establish these ratios for unrelated topologies or the full corpus.
Sub-millisecond measurements are particularly sensitive to timing noise.

For the 512-node traversal cases, median process peak RSS was approximately
37.7–37.9 MiB for both methods: these small inputs do not demonstrate a meaningful
memory reduction. For the 8-node cycle case it was 101.1 MiB for exhaustive
enumeration and 37.3 MiB for SCC membership. This is whole-process memory,
including any library initialization during warmup; it must not be presented as
the cycle algorithm's incremental allocation. In this environment, NetworkX's
cycle enumeration initialized the installed pandas/NumPy/SciPy stack during
warmup, while SCC membership did not. Which optional libraries are installed can
therefore change the process-memory comparison.

The local report, `data/processed/query-benchmark.json`, retains every run and
the intermediate sizes. Its implementation SHA-256 values are:

```text
benchmark_queries.py  1e42335f77178d5e3e78f3b2112e48ab0ac40e70395500a6f5ad65ab683b8001
queries.py            5c690469ee8f9406e5a353df97c61bd4af6cb85ed92ec9ad2eddd959cc6d1dcb
```

The ignored report is not needed to rerun the suite. The command above generates
a fresh report, including fingerprints, timings, and memory measurements for
the current implementation and environment.
