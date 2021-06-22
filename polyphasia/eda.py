from pathlib import Path

import networkx as nx
import pandas as pd

from networkx.algorithms.traversal import bfs_tree
import pydot
import matplotlib.pyplot as plt

"""
Load data from file
"""

# set up some paths for ins and outs
base_directory = Path.cwd().parent.absolute()
source_data_path = base_directory / "data" / "raw" / "etymwn.tsv"
processed_directory = base_directory / "data" / "processed"
output_graph_yaml_file = processed_directory / "graph_output.yaml"
output_graph_dot_file = processed_directory / "graph_output.dot"
output_graph_png = processed_directory / "graph_output.png"

# load from CSV
cleaned_df = pd.read_csv(
    source_data_path, sep="\t", names=["source_node", "edge_type", "target_node"]
)


"""
Clean data
"""

# filter out bidirectional relationships and select one directionality to normalize the graph
# I would normally clean to fix a handful of malformed tags as below but we are dropping those edge types anyway
# so instead we will stick to the edge types that point from root words to derived words
root_first_rel_types = ["rel:etymological_origin_of", "rel:has_derived_form"]
cleaned_df = cleaned_df.loc[(cleaned_df["edge_type"].isin(root_first_rel_types))]
cleaned_df[["source_language", "source_word"]] = cleaned_df.source_node.str.split(
    ": ", expand=True
)

# there are a handful of nodes that include strange characters or a :Category: tag that introduces a third
# column for no reason. This data is uninteresting so we can just ignore it and no include it in the graph when we construct it
cleaned_df[["target_language", "target_word", "crud"]] =  cleaned_df.target_node.str.split(": ", expand=True)


"""
Get list of unique languages in data set.

Not super necessary but helpful for understanding the likely subgraph structure. I would guess that the individual
languages will be highly connected/clustered. I suspect the boundaries will blur a bit around the proto- and ancient languages, particularly for languages with
many ancestors in the data set, e.g., Latin

unique_languages = set(cleaned_df["source_language"].unique()).union(set(cleaned_df["target_language"].unique()))
print(sorted(unique_languages))

"""


"""
Construct networkx graph
"""

# start with directed so we can preserve directionality data, retaining the option to convert to undirected later to use networkx undirected algorithms
graph = nx.from_pandas_edgelist(
    cleaned_df,
    edge_attr=[
        "edge_type",
        "source_language",
        "source_word",
        "target_language",
        "target_word",
    ],
    source="source_node",
    target="target_node",
    create_using=nx.DiGraph,
)
print(nx.info(graph))

"""
DAG analysis

Check if graph is directed acyclic
"""

from networkx.algorithms.dag import is_directed_acyclic_graph
is_dag = is_directed_acyclic_graph(graph)
print(is_dag)

"""
Undirected graph analysis

Construct undirected graph
"""

# convert to undirected so we can apply undirected algorithms
undirected_graph = graph.to_undirected()
print(nx.info(undirected_graph))

"""
Undirected graph analysis

Check for connected components
"""

from networkx.algorithms.components import connected_components

# check for connected components. may be a way to prune subgraphs that do not relate to English etymology
count = sum([1 for _ in connected_components(undirected_graph)])
print(count)


"""
Create English-related subgraph
"""

# grab the nodes that have the eng tag, then build the connected graph from those
english_nodes = [n for n in graph.nodes() if n[0:3] == 'eng']
nodes_to_add = []
# add nodes inside loop to avoid having to flatten later
[nodes_to_add.extend(bfs_tree(graph, source=node)) for node in english_nodes]

english_graph = graph.subgraph(nodes_to_add)
print(nx.info(english_graph))


nodes_by_degree = sorted(english_graph.degree, key=lambda x: x[1], reverse=True)
print(nodes_by_degree[0:99])


"""
nx.readwrite.nx_yaml.write_yaml(graph, output_graph_yaml_file)
pydot_graph = nx.drawing.nx_pydot.to_pydot(graph)
pydot_graph.write_raw(output_graph_dot_file)
pydot_graph.write_png(output_graph_png)

"""