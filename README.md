# polyphasia

=============================

## Short Description

Etymological WordNet dataset graph analysis project.

## Overview

This is a project to evaluate an etymology dataset parsed from Wiktionary.org using graph analysis tools. It is mostly an unstructured investigation to see what I can make of the data.

The source data can be downloaded [from the author's website here](https://cs.rutgers.edu/~gd343/downloads/etymwn-20130208.zip).

Initial data parsing and cleaning is handled with pandas, and the lovely networkx package does most of the heavy lifting for the graph algorithms.

I chose `polyphasia` (Gk., much speech) as the name because of its etymological mirroring of `aphasia` (Gk., without speech), rather than its relevance for signal processing or biological types of sleep.

## Data notes

The data are stored in a three column TSV file with no headers that is about 300mb uncompressed, with around 6m etymological relationships stored. The columns are the source word, the type of relationship, and the target word. Each source and target word is tagged with a language prefix followed by a colon, e.g. "eng: example". The type of relationship indicates how the words are etymologically related.

```tsv
aaq: Pawanobskewi	rel:etymological_origin_of	eng: Penobscot
```

I have not been able to find good documentation on the exact definitions of the etymological relationships, but after exploring the data set on the author's website, I can infer everything I need to know about them.

Relationships are recorded bidirectionally. Meaning, a root word will link to its derivatives, and each derivative will link back to the root. To simplify the graph, I drop edges that point from derivatives to roots, since that information is already encoded in the root-to-leaf edge and networkx can handle bidirectional traversal without requiring multiple edges to link the same pair of nodes (and I don't want to live with all the complexity of a multigraph anyway).

Below are the types of relationships extracted from the data, with comments indicating their directionality.

<- A is the source of B

-> B is the source of A

| relationship type | directionality | description |
| ----------- | ----------- | ----------- |
| "rel:etymology" | -> | indicates that the target word is an etymological root for the source word |
| "rel:etymological_origin_of" |  <- | indicates that the source word is an etymological root for the target word |
| "rel:is_derived_from" |  -> | indicates that the target word is part of a phrase derived from the source word |
| "rel:has_derived_form"  | <- | indicates that the source word is part of a phrase derived from the target word |
| "rel:etymologically_related"  | <-> | indicates that the two words share at least some common etymological root but does not indicate directionality |
| "rel:variant:orthography" | <-> | indicates that the two words are orthographic (spelling/written representation basically) variations of each other, so, e.g., `Chanukah` and `Hanukkah` |

The source data also includes a handful of malformed values, which should be dropped or replaced.

| malformed type | corrected type |
| ----------- | ----------- |
| "rel:etymologically" | "rel:etymologically_related" |
| "rel:derived" | "rel:is_derived_from" |

## TODO

- [x] Investigate difference between BFS and DAG approaches to filtering graph to English-related nodes
- [ ] Improve pipeline for loading data into Neo4j
- [ ] Improve visualizations
- [ ] Add tests to classes
- [ ] Improve logging
- [ ] Set up infrastructure to run on server instead of abusing my laptop
- [ ] Clean up CI/CD infrastructure so it actually runs the tests, linting, and precommit hooks
