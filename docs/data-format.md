# Data format and cleaning

[Project overview](../README.md) · [Development setup](README-DEV.md) · [Graph behavior](graph-behavior.md)

The reusable pipeline is `load_to_pandas(path)` followed by `clean_data_frame(frame)`. The [sample input](../examples/sample.tsv) contains three synthetic relationships and needs no external dataset.

## Input and paths

Input is a headerless UTF-8 TSV with exactly three fields per nonblank row:

| Column | Contents |
| --- | --- |
| `source_node` | Source endpoint, such as `lat: exemplum` |
| `edge_type` | Relationship type, such as `rel:etymological_origin_of` |
| `target_node` | Target endpoint, such as `eng: example` |

```tsv
lat: exemplum	rel:etymological_origin_of	eng: example
```

`load_to_pandas(path)` preserves fields as strings. Quotes are literal characters, and values such as `NA` are not converted to nulls. Blank lines are skipped. Rows with missing, extra, empty, or whitespace-only fields raise `ValueError`; missing files raise `FileNotFoundError`.

NUL bytes are rejected before parsing because the fast TSV parser would otherwise
silently truncate fields at them. Direct DataFrame inputs also reject NUL
characters in any of the three source columns. Labels are never repaired by
dropping a suffix or merging the resulting nodes.

Prefer an explicit path. With no argument, the loader reads `data/raw/etymologies.tsv` relative to the **current working directory**. From `notebooks/`, pass `Path("../data/raw/etymologies.tsv")` explicitly.

## Cleaning contract

`clean_data_frame(frame)` requires unique column names and the three input columns above, each containing nonblank strings. It validates every endpoint before filtering relationships, including rows that would later be dropped.

Each endpoint must have the form `language: word`. The language token must be nonempty and contain no whitespace or colons; the word must contain a non-whitespace character. Splitting happens only at the first `: `, so later colons, category tags, punctuation, and Unicode text remain part of the word. Invalid endpoints raise `ValueError`.

The result is a copy with four parsed columns added: `source_language`, `source_word`, `target_language`, and `target_word`. Original endpoint text and surviving index labels are preserved, and the caller's frame is unchanged. Empty files load with the three input columns; cleaning an empty frame, or filtering out every row, returns an empty frame with all seven core columns.

## Relationship selection

Cleaning normalizes two known aliases in `edge_type` only: `rel:etymologically` becomes `rel:etymologically_related`, and `rel:derived` becomes `rel:is_derived_from`.

By default, only the two root-to-leaf relationships are retained:

| Relationship type | Direction used by this project |
| --- | --- |
| `rel:etymological_origin_of` | Root to leaf; retained by default |
| `rel:has_derived_form` | Root to leaf; retained by default |
| `rel:etymology` | Leaf to root |
| `rel:is_derived_from` | Leaf to root |
| `rel:etymologically_related` | Related without a root-to-leaf direction |
| `rel:variant:orthography` | Orthographic variants without a root-to-leaf direction |

Pass `drop_rel_types=False` to retain every relationship type after alias normalization, including unknown types. Cleaning does not reverse edges or infer missing relationships. These classifications reflect the original analysis; they are not a complete linguistic model or a guarantee that every reverse relationship exists in the source data. See [graph behavior](graph-behavior.md) for how retained rows become edges.

For dataset downloads, provenance, and notebook setup, see the [research guide](research.md).
