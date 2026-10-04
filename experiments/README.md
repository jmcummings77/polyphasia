# Exploratory scripts

These source-only experiments are separate from the installed `polyphasia`
package. The supported loader and NetworkX graph helpers live in `polyphasia/`;
the notebooks and scripts here preserve exploratory work.

## Neo4j CSV export

After installing the project, run this from the repository root:

```sh
python -m experiments.neo4j_export data/raw/etymologies.tsv data/processed/neo4j
```

Both arguments are required and may be absolute paths. The command creates the
output directory and writes `nodes.csv` and `edges.csv`, replacing existing files
with those names. It shares the package loader's endpoint parsing and root-first
relationship filtering, preserves complete node IDs, and writes nodes in a
stable order without pandas index columns. Importing the module performs no file
reads or writes.

The tests verify CSV contents and command-line execution using small fixtures.
No live Neo4j import or database operation is tested or performed. This remains
a prototype: the original exploration found that the full graph needed useful
subgraph annotations before it could be visualized effectively. Review the CSV
schema and the import requirements of your Neo4j version before using it with a
database.
