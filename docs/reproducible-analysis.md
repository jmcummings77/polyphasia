# Reproducing the analysis

[Data audit](data-audit.md) · [Query contracts](graph-behavior.md) · [Synthetic fixture](../examples/README.md)

The workflow asks: **How do relationship policies and query choices change the
recorded ancestry and surrounding context of English words?** It uses the same
input, language, and cycle-preservation rule for each comparison. It generates
auditable artifacts before a notebook interprets them.

## Run the bundled fixture

Use Python 3.12 from the repository root:

```sh
uv sync --frozen --extra analysis
uv run --frozen --extra analysis python -m polyphasia.analysis \
  examples/analysis-fixture.tsv --output data/processed/analysis-fixture \
  --input-kind synthetic --dataset-version synthetic-v1 \
  --word 'eng: examples' --word 'eng: loop-leaf'
```

The 37 records are invented software test cases, not a real-data extract. Their
topology covers inverse-only evidence, duplicate assertions, multiple relations
per pair, overlapping roots, sibling branches, and rootless cycles. Expected
results and the fixed checksum are documented in the [fixture guide](../examples/README.md).
No sampling boundary or corpus representativeness is implied.

The command requires a new output directory. Malformed input, a mismatched
`--expected-sha256`, or source/code changes during computation abort the run.
Artifacts are prepared in a temporary directory and the destination is reserved
exclusively; `manifest.json` is published last. A directory without a valid
manifest is incomplete. Existing runs are never overwritten.

## Artifacts and provenance

| Artifact | Purpose |
| --- | --- |
| `audit.json` | Input accounting, inverse coverage, and both graph-policy audits. |
| `analysis.json` | Query counts, language composition, selected-set hashes, overlaps, relation-specific rankings, and bounded source traces. |
| `queries.csv` | Counts with raw-label, projected-seed, and included-seed denominators. |
| `overlaps.csv` | Pairwise query intersections, unions, differences, and Jaccard ratios within each policy. |
| `rankings.csv` | Direct incoming/outgoing neighbor rankings by relationship family. |
| `figures/*.png` | Static retention, query-size, and ranking figures. |
| `manifest.json` | Input hash/size/provenance, Git revision and dirty state, parameters, policy versions, dependency versions, implementation hashes, execution measurements, and every artifact's checksum. |

Metrics, CSVs, and figures are separate from volatile execution metadata. Repeated
runs of identical input and parameters produce identical analytical artifacts in
the same rendering environment. Figure bytes can vary with Matplotlib, FreeType,
or platform versions. Selected-set SHA-256 values use sorted labels encoded as
compact UTF-8 JSON arrays; assertion IDs still refer to the particular input's
one-based nonblank record ordinals.

The analysis does not duplicate the full assertion TSV. Keep the original input
identified by the manifest checksum; sampled trace evidence includes exact raw
fields and record IDs. Use the separate [audit command](data-audit.md) when a
complete derived assertion table is needed.

Check a saved run before consuming it:

```python
from pathlib import Path
from polyphasia.analysis import validate_run

manifest = validate_run(Path("data/processed/analysis-fixture"))
```

This verifies artifact sizes and checksums against the manifest. It does not
authenticate the manifest's author, re-download the input, or require the current
checkout to match a historical run. Provenance labels such as source URL and
dataset version are supplied by the caller. Installed wheels outside a source
checkout record null Git fields while retaining implementation hashes.

## Interpret each comparison

Relationship policy and query meaning are separate dimensions. `root_only`
keeps forward origin/derivation assertions; `normalized` also reverses their
known inverses. The audit always reports both. `--policies` can limit subsequent
query analysis to either policy. Symmetric and unknown relationships remain
accounted for in the audit but do not become ancestry facts.

Raw English labels, projected English seeds, and seeds retained by a query are
different denominators. Excluded-only labels never become valid graph seeds.
Ancestors and descendants include their seeds; root families include sibling
branches but can omit both cyclic seeds and acyclic descendants of rootless
cycles. Weak components follow edges in either direction while preserving the
original induced graph. All six query-pair overlaps are measured independently
within the same policy. Empty-union Jaccard is null.

Rankings count **distinct direct neighbors**, separately for word-origin and
derivational relationships, inside the **same combined ancestor selection**.
Incoming and outgoing counts are distinct; ties use exact label order. A pair
carrying both types contributes once to each relationship's ranking. Duplicate
or inverse assertions do not inflate neighbor counts. These are neither counts
of all reachable English descendants nor estimates of historical influence.
`affix_like` flags only a literal leading or trailing hyphen: inspect the labels
before assigning a linguistic interpretation.

`--word` takes an exact label and can be repeated. Each trace uses a deterministic
reverse breadth-first search for a nearest zero-indegree root, then reports one
root-to-word path with up to five contributing assertions per edge. Other paths
may exist. `--trace-max-depth` (default 8) and `--trace-max-nodes` (default 1,000)
bound the search; `bounded` means no conclusion about rootlessness was reached.
`rootless` means the entire ancestor closure was searched without finding a
zero-indegree root. `missing` means the label is absent from that projection.
Bounds limit search size, not wall-clock time. No cycle is deleted for tracing.

Node identity is the source's exact language-and-word string. It does not
distinguish every sense, historical stage, or uncertainty. Wiktionary extraction
coverage and these identity limits constrain every substantive interpretation;
neither deterministic output nor passing tests establish linguistic truth.

## Execute the verified notebook

The [verified notebook](../notebooks/verified_analysis.ipynb) consumes a completed
run and validates its artifacts. It never silently launches full-data analysis.

```sh
uv sync --frozen --extra notebooks
uv run --frozen --extra notebooks python scripts/execute_analysis_notebook.py \
  --artifacts data/processed/analysis-fixture \
  --output data/processed/analysis-fixture.executed.ipynb
```

The runner launches a fresh kernel using the current interpreter and a temporary
kernel specification; no user-wide registration is needed. Any cell error fails
execution, and the output path must be new. For interactive use, set
`POLYPHASIA_ANALYSIS_DIR` to the artifact directory before launching Jupyter.
CI generates the synthetic run, executes this notebook, and uploads both as
build artifacts. Other notebooks remain historical exploration.

## Run the full pinned corpus

The [recorded full run](../reports/20130208/README.md) includes a compact published
snapshot with verified findings, figures, source traces, and its original manifest.
The notebook can read it without downloading the corpus.

Acquire the source described in the [data notes](../data/data_source.md). This
workflow loads all assertions and constructs graph projections sequentially;
allow several gigabytes of RAM and several minutes on a development machine.
Run from a clean committed checkout when publishing a result:

```sh
uv run --frozen --extra analysis python -m polyphasia.analysis \
  data/raw/etymologies.tsv --output data/processed/analysis-20130208 \
  --input-kind full --dataset-version 2013-02-08 \
  --source-url http://etym.org/etymwn-20130208.zip \
  --expected-sha256 361b946fa306732357b3ee375ea01ccdcbe3db1676898c47c39a92fb9861f7da \
  --word 'eng: examples' --word 'eng: kindness' --word 'p_gem: forana'
```

The manifest records a single workflow duration through rendering and final
source verification, and process-lifetime peak RSS on Linux/macOS (null on other
platforms). These include interpreter/import/data costs and are not comparative
benchmark results. Use the [controlled query benchmarks](query-benchmarks.md)
for equivalent-algorithm timing comparisons.
