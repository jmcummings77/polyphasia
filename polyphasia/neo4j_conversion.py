"""
Initial attempt to munge the graph into a neo4j-compatible format. I am new to neo4j, so it is... ugly. Much cleaning up left to do.

These first efforts to get this translated into a graph database worked, but were not very useful. There are too many nodes to render or filter usefully in
neo4j without first annotating the nodes/edges with useful attributes.

I think I will work on getting the rest of the pipeline mapped out into a more stable architecture, then tack on a conversion layer to neo4j. I'll use networkx
to identify interesting subgraphs, and label the constituent nodes accordingly so that they can be visualized in a neo4j-based viz layer more easily.

In the mean time, I will commit this terrible code so I can revisit later.
"""

from pathlib import Path

import pandas as pd
import csv


"""
Load data from file
"""

# set up some paths for ins and outs
base_directory = Path.cwd().parent.absolute()
source_data_path = base_directory / "data" / "raw" / "etymwn.tsv"
processed_directory = base_directory / "data" / "processed"
output_graph_csv = processed_directory / "graph_output.csv"

# load from TSV
cleaned_df = pd.read_csv(
    source_data_path,
    sep="\t",
    names=["source:START_ID", "relType:TYPE", "target:END_ID"],
)

"""
Clean data


"""

# filter out bidirectional relationships and select one directionality to normalize the graph
# I would normally clean to fix a handful of malformed tags as below but we are dropping those edge types anyway
# so instead we will stick to the edge types that point from root words to derived words
root_first_rel_types = ["rel:etymological_origin_of", "rel:has_derived_form"]
cleaned_df = cleaned_df.loc[(cleaned_df["relType:TYPE"].isin(root_first_rel_types))]

nodes = set(cleaned_df["source:START_ID"].unique()).union(
    cleaned_df["target:END_ID"].unique()
)

df = pd.DataFrame(nodes, columns=["wordId:ID"])
df[["language:LABEL", "word", "crud"]] = df["wordId:ID"].str.split(": ", expand=True)
df.drop(columns=["crud"])

# there are a handful of nodes that include strange characters or a :Category: tag that introduces a third
# column for no reason. This data is uninteresting so we can just ignore it and no include it in the graph when we construct it
# cleaned_df[["target_language", "target_word", "crud"]] =  cleaned_df.target_node.str.split(": ", expand=True)
# need to find a better way to get the neo4j import folder path
df.to_csv(
    "/Users/jmcummings/Library/Application Support/Neo4j Desktop/Application/relate-data/projects/project-3f1dd71b-b53a-4736-8727-0b730b1f638f/nodes.csv",
    quoting=csv.QUOTE_NONNUMERIC,
)
cleaned_df.to_csv(
    "/Users/jmcummings/Library/Application Support/Neo4j Desktop/Application/relate-data/projects/project-3f1dd71b-b53a-4736-8727-0b730b1f638f/edges.csv",
    quoting=csv.QUOTE_NONNUMERIC,
)


"""
should add code to cd to the right directory and to run this script

bin/neo4j-admin import --database=polyphasia --nodes=import/nodes.csv --relationships=import/edges.csv


should probably also drop/clear database because neo4j can only import csvs to empty db

"""
