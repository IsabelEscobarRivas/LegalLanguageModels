"""
Visualization tools for the KET-RAG model
"""

import pickle
import logging
from pathlib import Path
import networkx as nx
import matplotlib.pyplot as plt
from pyvis.network import Network

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_model(model_path="ket_rag_corpus.pkl"):
    """Load the saved KETRAG model"""
    logger.info(f"Loading model from {model_path}")
    with open(model_path, 'rb') as f:
        ket_rag = pickle.load(f)
    return ket_rag

def visualize_customer_tree(ket_rag, output_path="customer_tree.html"):
    """Create an interactive visualization of the customer tree"""
    if not hasattr(ket_rag, 'customer_tree'):
        logger.error("No customer tree found in the model")
        return
    
    logger.info("Creating customer tree visualization...")
    
    # Create a network
    net = Network(height="800px", width="100%", notebook=False, heading="Knowledge Graph v2")
    
    # Node colors by type
    colors = {
        "root": "#8A2BE2",  # BlueViolet
        "case": "#4682B4",  # SteelBlue
        "visa_type": "#20B2AA",  # LightSeaGreen
        "category": "#FF8C00",  # DarkOrange
        "document": "#CD5C5C"   # IndianRed
    }
    
    # Add nodes with colors based on type
    for node_id in ket_rag.customer_tree.nodes():
        node_data = ket_rag.customer_tree.nodes[node_id]
        node_type = node_data.get("node_type", "unknown")
        
        # Prepare node label and title (hover text)
        if node_type == "root":
            label = "All Cases"
            title = "Root Node - All Cases"
        elif node_type == "case":
            case_id = node_data.get("case_id", "unknown")
            label = f"Case: {case_id}"
            title = f"Case ID: {case_id}"
        elif node_type == "visa_type":
            visa_type = node_data.get("visa_type", "unknown")
            label = visa_type
            title = f"Visa Type: {visa_type}\nCase: {node_data.get('case_id', 'unknown')}"
        elif node_type == "category":
            category = node_data.get("category", "unknown")
            # Shorten category name for display
            short_category = category
            if len(short_category) > 30:
                short_category = short_category[:27] + "..."
            label = short_category
            title = f"Category: {category}\nVisa: {node_data.get('visa_type', 'unknown')}"
        elif node_type == "document":
            chunk_id = node_data.get('chunk_id', '')
            if chunk_id != '' and chunk_id < len(ket_rag.chunks):
                filename = ket_rag.chunks[chunk_id]["metadata"].get("filename", f"Doc {chunk_id}")
                label = filename
            else:
                label = f"Doc {chunk_id}"
            title = node_data.get("text", "")[:200] + "..."
        else:
            label = str(node_id)
            title = str(node_data)
        
        # Add the node
        net.add_node(
            node_id, 
            label=label, 
            title=title,
            color=colors.get(node_type, "#CCCCCC")
        )
    
    # Add edges
    for u, v in ket_rag.customer_tree.edges():
        net.add_edge(u, v)
    
    # Configure physics
    net.set_options("""
    {
      "physics": {
        "hierarchicalRepulsion": {
          "nodeDistance": 120,
          "centralGravity": 0.0,
          "springLength": 100,
          "springConstant": 0.01,
          "damping": 0.09
        },
        "solver": "hierarchicalRepulsion",
        "stabilization": {
          "iterations": 100
        }
      },
      "layout": {
        "hierarchical": {
          "enabled": true,
          "direction": "UD",
          "sortMethod": "directed",
          "levelSeparation": 150
        }
      },
      "interaction": {
        "navigationButtons": true,
        "keyboard": true
      }
    }
    """)
    
    # Save the visualization
    net.save_graph(output_path)
    logger.info(f"Customer tree visualization saved to {output_path}")
    
    return output_path

def visualize_knowledge_graph(ket_rag, output_path="knowledge_graph.html"):
    """Create an interactive visualization of the knowledge graph"""
    if ket_rag.knowledge_graph.number_of_nodes() == 0:
        logger.error("Knowledge graph is empty")
        return
    
    logger.info("Creating knowledge graph visualization...")
    
    # Create a network
    net = Network(height="800px", width="100%", notebook=False)
    
    # Add nodes
    for i in ket_rag.knowledge_graph.nodes():
        # Get metadata
        node_data = ket_rag.knowledge_graph.nodes[i]
        metadata = node_data.get("metadata", {})
        
        # Prepare label and title
        case_id = metadata.get("case_id", "unknown")
        visa_type = metadata.get("visa_type", "unknown")
        category = metadata.get("category", "unknown")
        filename = metadata.get("filename", f"Doc {i}")
        label = f"{filename}: {visa_type}"
        title = f"Case: {case_id}\nVisa: {visa_type}\nCategory: {category}\n\n{ket_rag.chunks[i]['text'][:200]}..."
        
        # Color by visa type
        if visa_type == "EB1":
            color = "#4169E1"  # RoyalBlue
        elif visa_type == "EB2":
            color = "#32CD32"  # LimeGreen
        else:
            color = "#A9A9A9"  # DarkGray
        
        # Size by PageRank