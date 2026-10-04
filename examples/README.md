# Synthetic examples

[Project overview](../README.md) · [Data audit](../docs/data-audit.md) · [Graph queries](../docs/graph-behavior.md)

Both TSV files in this directory are **synthetic fixtures**. Their relationships
are invented to demonstrate software behavior, even where labels resemble real
words. They are not a linguistic reference, a corpus sample, or evidence about
the prevalence of any language or relationship. No records were extracted from
the full Etymological Wordnet dataset for these fixtures.

`sample.tsv` is the three-record introduction used by the README. The expanded
`analysis-fixture.tsv` exercises the reproducible analysis workflow and CI without
a download. A separate run against the [pinned full corpus](../data/data_source.md)
is necessary for corpus findings. Passing the fixture establishes software
contracts; it does not establish linguistic accuracy or full-data performance.

## Expanded fixture identity

- Format: headerless UTF-8 TSV, three literal fields per record, LF line endings.
- Records: **37**; bytes: **1,743**; distinct raw node labels: **36**.
- SHA-256: `74a6e1421bfb78260cb7b9a2e400a2c27e7d86adf9b82c6175d725a53de790a3`.
- Assertion IDs are one-based record ordinals. There are no blank records.

The checksum and independently specified graph/selection contracts are checked
in `tests/test_analysis_fixture.py`. A deliberate fixture change must update its
identity and expected results together.

| Records | Purpose |
| --- | --- |
| 1–12 | Multiple roots, a sibling branch, a root reaching only that sibling, inverse pairs, an exact duplicate, and two relationship types on one pair. |
| 13–15 | An inverse-only `rel:derived` alias and an inverse-only origin assertion. Normalization recovers nodes absent from the forward-only graph. |
| 16–20 | A rootless two-node cycle with an acyclic English leaf, plus a separate self-loop with an outgoing French leaf. |
| 21–24 | Related/orthographic and unknown assertions whose endpoints occur only in excluded evidence. An alias produces an additional duplicate after normalization. |
| 25–34 | Deliberately prominent `-ness` and `un-` fanouts, a second parent of `kindness`, an inverse pair, and another pair carrying both canonical relationship types. |
| 35–36 | A disconnected non-English component. |
| 37 | Literal `NA` and quote characters in word labels. Greek text, French accents, and a `p_gem` language token occur elsewhere. |

## Independent accounting contracts

There is **one exact duplicate**, **two duplicates after alias normalization**,
and **two alias records**. Four records are excluded from both ancestry policies:
three related/orthographic assertions and one unknown relationship. The original
assertion table still retains all of them.

| Projection | Retained assertions | Nodes | Endpoint pairs | Canonical relationship facts | English seeds |
| --- | ---: | ---: | ---: | ---: | ---: |
| `root_only` | 25 | 28 | 22 | 24 | 17 |
| `normalized` | 33 | 31 | 24 | 26 | 19 |

The raw input contains **22 English labels**. Three occur only in excluded
assertions: `eng: excluded`, `eng: excluded-alt`, and `eng: mystery`.
`eng: orphan` and `eng: cafe` additionally disappear under `root_only`.
Comparisons must distinguish raw English labels from each graph's valid seeds.

Two endpoint pairs carry both canonical types. In the normalized graph there are
eight origin facts and eighteen derivational facts; their sum is larger than the
twenty-four endpoint pairs. Counting evidence rows as distinct graph edges would
give a different, incorrect quantity.

Both projections contain exactly three cyclic nodes: `eng: loop-a`,
`deu: loop-b`, and `eng: mirror`. They form two cyclic strongly connected
components. Deleting those nodes would remove five incident edges. The acyclic
`eng: loop-leaf` also lacks any path from a zero-indegree root, illustrating why
root-family exclusions cannot be described simply as cyclic-node exclusions.

## Query and trace contracts

With every English node in the selected projection used as a seed:

| Query | `root_only` nodes / edges / included seeds | `normalized` nodes / edges / included seeds |
| --- | --- | --- |
| Ancestors | 20 / 16 / 17 | 24 / 18 / 19 |
| Descendants | 20 / 16 / 17 | 22 / 16 / 19 |
| Root families | 18 / 14 / 14 | 23 / 17 / 16 |
| Weak components | 24 / 20 / 17 | 29 / 23 / 19 |

For the single trace target **`eng: examples`**, both policies select:

- Ancestors: `lat: exemplum`, `grc: παράδειγμα`, `eng: example`, and
  `eng: examples` (**4 nodes, 3 edges**).
- Root families: those four plus `fra: exemple` and `eng: example-set`
  (**6 nodes, 5 edges**).
- Weak component: those six plus `deu: Quelle` (**7 nodes, 6 edges**).

The edge `eng: example → eng: examples` traces back to records **4, 5, 6, 7, 8**
in the normalized projection. Its five recorded assertions represent one endpoint
pair with two canonical types, not five independent corroborating sources.

For the rootless trace target **`eng: loop-leaf`**, ancestors and weak components
contain the target plus `eng: loop-a` and `deu: loop-b` (**3 nodes, 3 edges**).
Root-family selection is empty; descendants contain just the target. The cycle
does not need to be removed to answer those queries.

The planted ranking example has unique outdegree **4** at `eng: -ness` and **3**
at `eng: un-`; every other node has outdegree at most **2**. These are synthetic
graph properties, not measured linguistic influence. A hyphen-based affix flag
is a label heuristic, and these deliberately chosen labels do not validate it on
arbitrary corpus entries.
