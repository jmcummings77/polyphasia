# Historical notebook archive

[Notebook catalog](../README.md) · [Verified workflow](../../docs/reproducible-analysis.md)

These four notebooks preserve the project's original exploration. They were
moved from `notebooks/` into this directory **without changing their bytes**:

- [initial_eda.ipynb](initial_eda.ipynb): early data inspection and plotting.
- [connectivity_analysis.ipynb](connectivity_analysis.ipynb): historical
  connectivity investigation.
- [directed_acyclic_graph_analysis.ipynb](directed_acyclic_graph_analysis.ipynb):
  directed graph and root-family analysis, including cycle deletion.
- [undirected_graph_analysis.ipynb](undirected_graph_analysis.ipynb): undirected
  component exploration.

They are **archival, not verified executable analyses**. Saved outputs can be
stale, cells can reference removed APIs or undefined variables, and historical
comparisons can mix graph policies. Moving the files does not repair or validate
their code. They are not executed by CI or used to produce the published reports.

## Path and environment boundary

The move adds one directory level. Relative paths inside the preserved cells
still reflect their former location and require manual adaptation. For example,
from a kernel working in `notebooks/historical/`, a former
`../data/raw/etymologies.tsv` path would need to become
`../../data/raw/etymologies.tsv`. A path to the repository root likewise changes
from `..` to `../..`. Review every input, import, and output path against the
kernel's actual working directory before running any cells.

Path changes alone are insufficient: review API compatibility, relationship
direction, query meaning, cycle handling, and output provenance. No command in
this archive is offered as an end-to-end execution guarantee. Start current work
with [verified_analysis.ipynb](../verified_analysis.ipynb) and its artifact-based
workflow instead.

The historical input came from Etymological Wordnet. Consult the
[source notes](../../data/data_source.md) and preserved
[upstream README](../../data/data_source_readme.txt) for attribution, citation,
and **CC-BY-SA 3.0** source terms. The repository's MIT code license does not
replace the dataset's license.
