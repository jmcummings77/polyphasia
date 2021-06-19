from pathlib import Path

import networkx as nx
import pandas as pd

"""
import pydot
import matplotlib.pyplot as plt
"""

base_directory = Path(__file__).parent.parent.absolute()
source_data_path = base_directory / "data" / "raw" / "etymwn.tsv"

processed_dir = base_directory / "data" / "processed"
output_graph_dot_file = processed_dir / "graph_output.dot"
output_graph_png = processed_dir / "graph_output.png"
cleaned_df = pd.read_csv(source_data_path, sep='\t', names=["source_node", "edge_type", "target_node"])

cleaned_df = cleaned_df.loc[(cleaned_df['source_node'].str.startswith("eng")) | (cleaned_df['target_node'].str.startswith("eng"))]

graph = nx.from_pandas_edgelist(
    cleaned_df,
    edge_attr=["edge_type"],
    source="source_node",
    target="target_node",
    create_using=nx.DiGraph
    )

print(nx.info(graph))

pydot_graph = nx.drawing.nx_pydot.to_pydot(graph)
pydot_graph.write_raw(output_graph_dot_file)
pydot_graph.write_png(output_graph_png)

rel_types = [
    'rel:etymological_origin_of',
    'rel:is_derived_from',
    'rel:etymologically',
    'rel:has_derived_form',
    'rel:derived',
    'rel:variant:orthography',
    'rel:etymologically_related',
    'rel:etymology'
    ]
