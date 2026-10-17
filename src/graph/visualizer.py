"""
Graph Visualizer using Matplotlib and NetworkX.
==============================================

This script loads a .graphml file and generates a simple PNG visualization.
It's useful for a quick check of the graph structure.
"""

import networkx as nx
import matplotlib.pyplot as plt
import os

def visualize_graph(graphml_path, output_png_path):
    if not os.path.exists(graphml_path):
        print(f"Error: {graphml_path} not found. Run the graph builder first.")
        return

    # Load the graph
    G = nx.read_graphml(graphml_path)
    print(f"Loaded graph with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges.")

    # Create figure
    plt.figure(figsize=(15, 12))
    
    # Try using a spring layout for better node separation
    pos = nx.spring_layout(G, k=0.5, iterations=50)
    
    # Color nodes by type
    node_colors = []
    for node, data in G.nodes(data=True):
        ntype = data.get('type', 'unknown')
        if ntype == 'file':
            node_colors.append('#3498db') # Blue
        elif ntype == 'class':
            node_colors.append('#f1c40f') # Yellow
        elif ntype == 'function':
            node_colors.append('#2ecc71') # Green
        else:
            node_colors.append('#95a5a6') # Gray

    # Draw nodes
    nx.draw_networkx_nodes(G, pos, node_size=1500, node_color=node_colors, alpha=0.8)
    
    # Draw edges
    nx.draw_networkx_edges(G, pos, width=1.5, alpha=0.5, edge_color='gray', arrows=True, arrowsize=20)
    
    # Draw labels
    # We use only the last part of the node name for readability in the image
    labels = {node: node.split(':')[-1] for node in G.nodes()}
    nx.draw_networkx_labels(G, pos, labels, font_size=8, font_family='sans-serif', font_weight='bold')

    plt.title("Codebase Dependency Graph Visualization", size=20)
    plt.axis('off')
    
    # Add a legend
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], marker='o', color='w', label='File', markerfacecolor='#3498db', markersize=15),
        Line2D([0], [0], marker='o', color='w', label='Class', markerfacecolor='#f1c40f', markersize=15),
        Line2D([0], [0], marker='o', color='w', label='Function', markerfacecolor='#2ecc71', markersize=15),
    ]
    plt.legend(handles=legend_elements, loc='upper left')

    plt.tight_layout()
    plt.savefig(output_png_path, dpi=300)
    print(f"Visualization saved to {output_png_path}")

if __name__ == "__main__":
    graphml_file = os.path.join("results", "dependency_graph.graphml")
    output_file = os.path.join("results", "graph_visualization.png")
    
    # Create results dir if it doesn't exist
    os.makedirs("results", exist_ok=True)
    
    visualize_graph(graphml_file, output_file)
