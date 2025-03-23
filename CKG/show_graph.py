import pickle
import networkx as nx
import matplotlib.pyplot as plt

# Load the graph from the pickle file
with open('/home/veteran/projects/multiAgent/TestPlanAgent/CKG/rec_movies_graph.pkl', 'rb') as f:
    G = pickle.load(f)

# Draw the graph with adjusted parameters
plt.figure(figsize=(40, 40))  # Increase the figure size for better visibility

# Adjust layout parameters for better spacing
pos = nx.spring_layout(G, k=0.5)  # Increase k for more spacing, try adjusting this value

# Draw the graph with smaller node sizes and font size
nx.draw(G, pos, with_labels=True, node_size=10, node_color="skyblue", font_size=3, font_weight="bold", edge_color="gray", alpha=0.6)

plt.title("Graph Visualization")

# Save the graph to a file with high DPI
plt.savefig('/home/veteran/projects/multiAgent/TestPlanAgent/CKG/rec_movies_graph.png', format='PNG', dpi=600)
plt.close()
