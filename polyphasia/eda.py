from pathlib import Path

import networkx as nx
import pandas as pd

from networkx.algorithms.traversal import bfs_tree

"""
import pydot
import matplotlib.pyplot as plt
"""

base_directory = Path(__file__).parent.parent.absolute()
source_data_path = base_directory / "data" / "raw" / "etymwn.tsv"

processed_dir = base_directory / "data" / "processed"
output_graph_yaml_file = processed_dir / "graph_output.yaml"
output_graph_dot_file = processed_dir / "graph_output.dot"
output_graph_png = processed_dir / "graph_output.png"
cleaned_df = pd.read_csv(
    source_data_path, sep="\t", names=["source_node", "edge_type", "target_node"]
)

rel_types = [
    "rel:etymology" "rel:etymological_origin_of",
    "rel:is_derived_from",
    "rel:has_derived_form",
    "rel:etymologically_related",
    "rel:variant:orthography",
]
"""
<- A is the source of B
-> B is the source of A

<-
->
<-
->
<->
<->
<->
<->


"""

# filter out bidirectional relationships and select one directionality to normalize the graph
# would normally clean to fix a handful of malformed tags as below but we are dropping those edge types anyway
# cleaned_df = cleaned_df.replace("rel:etymologically", "rel:etymologically_related").replace("rel:derived", "rel:is_derived_from")
# so instead we will stick to the edge types that point from root words to derived words
root_first_rel_types = ["rel:etymological_origin_of", "rel:has_derived_form"]
cleaned_df = cleaned_df.loc[(cleaned_df["edge_type"].isin(root_first_rel_types))]
cleaned_df[["source_language", "source_word"]] = cleaned_df.source_node.str.split(
    ": ", expand=True
)

cleaned_df[["target_language", "target_word", "crud"]] =  cleaned_df.target_node.str.split(": ", expand=True)


"""
cleaned_df = cleaned_df.replace("words derived from: ", "words derived from ").replace("fil: ", "rel ")

split_target = cleaned_df.target_node.str.split(
    ": ", expand=True
)
split_target = split_target.dropna()

unique_languages = set(cleaned_df["source_language"].unique()).union(set(cleaned_df["target_language"].unique()))
print(unique_languages)

"""



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

undirected_graph = graph.to_undirected()
print(nx.info(undirected_graph))

connected_components = undirected_graph.connected_components()
print(len(connected_components))

# create english specific subgraph
# grab the nodes that have the eng tag, then build the connected graph from those

english_nodes = [n for n in graph.nodes() if n[0:3] == 'eng']
nodes_to_add = []
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
