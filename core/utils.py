import pipmaster as pm

if not pm.is_installed("pyvis"):
    pm.install("pyvis")
if not pm.is_installed("networkx"):
    pm.install("networkx")

import numpy as np
import tiktoken
import networkx as nx
from pyvis.network import Network
import random
from pathlib import Path
import uuid

def gen_html_graph(knowledge_path):
    print(f'knowledge_path: {knowledge_path}')
    graphml_path = Path(knowledge_path) / "graph_chunk_entity_relation.graphml"
    
    # Load the GraphML file
    G = nx.read_graphml(graphml_path)

    # Create a Pyvis network
    net = Network(height="100vh", notebook=True)

    # Convert NetworkX graph to Pyvis network
    net.from_nx(G)

    # Add colors and title to nodes
    for node in net.nodes:
        node["color"] = "#{:06x}".format(random.randint(0, 0xFFFFFF))
        if "description" in node:
            node["title"] = node["description"]

    # Add title to edges
    for edge in net.edges:
        if "description" in edge:
            edge["title"] = edge["description"]

    n = f'{uuid.uuid4()}.html'
    print(Path(n).resolve())
    net.save_graph(n)
    html_text = open(n).read()
    # Path(n).unlink()
    return html_text
