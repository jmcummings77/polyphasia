# Auditing assertions and graph projections

[Data format](data-format.md) · [Graph behavior](graph-behavior.md) · [Research](research.md)

The audit compares explicit graph-construction policies without deleting cyclic
nodes or losing the original assertions. It is an additive workflow: the existing
`clean_data_frame`, `DirectedGraph`, and `UndirectedGraph` APIs retain their behavior.

The [analysis workflow](reproducible-analysis.md) incorporates this audit and adds
query comparisons, rankings, source traces, figures, and execution provenance.

## Run an audit

From the repository root with the core development environment installed:

```sh
uv run python -m polyphasia.audit examples/sample.tsv \
  --output data/processed/audit-sample \
  --dataset-version synthetic-sample
```

For the full dataset, first follow the [source notes](../data/data_source.md),
then run:

```sh
uv run python -m polyphasia.audit data/raw/etymologies.tsv \
  --output data/processed/audit-20130208 \
  --dataset-version 2013-02-08 \
  --source-url http://etym.org/etymwn-20130208.zip
```

The command requires a **new** output directory and never replaces an existing
run. It does not download data. Both `data/raw/` and `data/processed/` are ignored
by Git. Use explicit paths when running elsewhere.

Outputs:

- `assertions.tsv`: every validated input record, with its original three fields,
  a record ID, a normalized relationship label, and parsed language/word fields.
- `audit.json`: deterministic data-quality counts and summaries of both graph
  projections. Reordering the same records does not change this report.
- `manifest.json`: source path, SHA-256 and size, supplied version/source URL,
  creation timestamp, package versions, implementation hashes, policy versions,
  and artifact hashes. Version and URL are caller-provided provenance labels;
  they are not independently authenticated by the command.

The full audit loads the assertion table and one graph projection at a time into
memory. It uses strongly connected components rather than enumerating all simple
cycles. Large datasets still require substantial memory.

## Assertion identity and preservation

`prepare_assertions(raw)` retains the original `source_node`, `edge_type`, and
`target_node` text. Aliases change only `normalized_edge_type`. No valid record
is removed, including duplicates, unknown relationships, and relationships
excluded from the ancestry projections. Extra caller-supplied DataFrame columns
are omitted; derived fields cannot be replaced with caller metadata.

An `assertion_id` is the **one-based nonblank parsed record ordinal** in the input.
It is not a physical line number. The source checksum and this ordinal together
identify the record. Reordering a file changes its checksum and record IDs but
does not change graph topology or aggregated relationship meaning.

The output table is a **headered, CSV-quoted TSV**, whereas the raw input is
headerless and treats quotes literally. To read the output without interpreting
values such as `NA` as nulls:

```python
import pandas as pd

assertions = pd.read_csv(
    "data/processed/audit-sample/assertions.tsv",
    sep="\t",
    keep_default_na=False,
    dtype=str,
)
assertions["assertion_id"] = assertions["assertion_id"].astype("int64")
```

Malformed rows/endpoints fail validation before an output directory is created.
The audit does not silently discard or repair malformed records. The original
source file remains the byte-for-byte source of truth.

## Projection policies version 1

`project_assertions(assertions, policy=...)` returns a directed NetworkX graph.
Node identity is the exact original `language: word` string; no case folding,
Unicode normalization, sense disambiguation, or whitespace trimming is inferred.

| Policy | Relationships represented |
| --- | --- |
| `root_only` | Keep normalized `rel:etymological_origin_of` and `rel:has_derived_form` assertions in their recorded direction. This matches the legacy cleaner's selection. |
| `normalized` | Also reverse `rel:etymology` into `rel:etymological_origin_of`, and `rel:is_derived_from` into `rel:has_derived_form`. The `rel:derived` alias participates after normalization. |

Symmetric relationships (`rel:etymologically_related`, including its alias, and
`rel:variant:orthography`) and unknown types remain in the assertion table. Both
policies exclude them from the ancestry graph and account for their raw labels
in `excluded_raw_relationship_counts`. The root-only policy also excludes inverse
assertions. No missing inverse record is manufactured.

Only endpoints of retained assertions enter each graph. Self-loops and other
cycles remain. A node is a recorded word label, not necessarily a unique sense,
historical stage, or independently established linguistic entity. These policies
formalize the project's relationship interpretation; normalization does not
establish linguistic truth or source completeness.

Each ordered endpoint pair becomes one edge with:

- `relationship_types`: the sorted tuple of canonical forward types;
- `assertion_count`: number of contributing input records;
- `raw_relationship_counts`: counts by original relationship label;
- `assertion_ids`: the sorted contributing record IDs.

Node attributes hold `language` and `word`. Multiple relationship types are
aggregated rather than overwritten. Duplicate and inverse assertions count as
recorded evidence, **not independent corroboration or confidence weights**.

## Reading the audit

Input metrics distinguish raw exact duplicates from duplicates after alias
normalization. Both are counts of excess records after the first occurrence.
Language counts measure distinct node labels across both endpoint columns, not
numbers of speakers or the prevalence of a language.

Inverse coverage is calculated per semantic relationship family on unique
ordered pairs: forward pairs `F`, and reversed inverse pairs `I`. The report
gives matched pairs, forward-only pairs, and inverse-only pairs. Forward coverage
is `|F ∩ I| / |F|`; inverse coverage is `|F ∩ I| / |I|`. An empty denominator is
reported as JSON `null`. Duplicate rows cannot inflate these fractions.

For each projection:

- Input assertions equal retained plus excluded assertions. The raw label
  breakdowns account for both sides.
- Input nodes equal projected plus excluded nodes; language breakdowns also
  reconcile.
- `edges` counts ordered endpoint pairs. `canonical_relationship_facts` counts
  distinct canonical types on those pairs. `assertions_beyond_first_per_edge`
  includes both duplicate evidence and multiple types, so it is **not** an exact
  duplicate count.
- A cyclic strongly connected component (SCC) has more than one node, or is a
  singleton with a self-loop. SCC counts are **not counts of simple cycles**.
  `edges_incident_to_cyclic_nodes` measures edges that deleting all cyclic nodes
  would remove, including edges to nodes outside the cyclic components.

Compare the two policies on the same input and cycle-preservation rules. Raw
reciprocal rows should not be interpreted as ancestral cycles before direction
normalization. Graph summaries describe this dataset under these policies; they
do not establish a complete history of words.

## Verified 2013-02-08 snapshot

The full audit was run against the TSV checksum pinned in the
[source notes](../data/data_source.md), using projection policy version 1. All
6,031,431 assertions passed validation. A separate streaming comparison verified
that every original field and record ID survived in the output assertion table;
source, implementation, and artifact hashes were also checked.

| Metric | Root-only | Inverse-normalized |
| --- | ---: | ---: |
| Retained assertions | 2,738,177 | 5,476,356 |
| Nodes | 2,743,118 | 2,743,119 |
| Ordered endpoint pairs | 2,692,096 | 2,692,097 |
| Pairs carrying both canonical relationship types | 46,081 | 46,081 |
| Cyclic strongly connected components | 2,693 | 2,693 |
| Nodes participating in cycles | 3,881 | 3,881 |
| Edges incident to cyclic nodes | 56,622 | 56,622 |

Every word-origin pair has its inverse. Derivational relationships contain one
inverse-only pair after alias normalization: `p_gem: forana` has `rel:derived`
pointing to `p_gem: fora`. Reversing it recovers one additional edge and node.
There are no exact duplicate raw assertions; one duplicate appears after alias
normalization. Both policies exclude the 555,075 related/orthographic assertions
from ancestry semantics (root-only additionally excludes inverse assertions).

For this snapshot, the historical reverse-edge redundancy assumption is nearly
complete. Preserving the two relationship types on 46,081 shared endpoint pairs
and avoiding deletion of 56,622 cycle-incident edges are larger analytical issues.
These results apply to this pinned input and policy; regenerate them for other
versions. Full local outputs are written to `data/processed/audit-20130208/` by
the command above and are not committed.
