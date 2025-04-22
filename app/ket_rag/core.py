"""
KET-RAG: Knowledge-Enhanced Two-layer Retrieval Augmented Generation
Core implementation for immigration document system
"""

import logging
import numpy as np
from typing import List, Dict, Any, Optional
import networkx as nx
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import spacy

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class KETRAG:
    """
    Knowledge-Enhanced Two-layer Retrieval Augmented Generation
    
    Implements a cost-effective approach to knowledge graphs by:
    1. Using PageRank to identify important chunks 
    2. Building a sparse knowledge graph on important chunks only
    3. Creating a keyword-chunk bipartite graph for efficient retrieval
    """
    
    def __init__(self, embedding_model_name="all-MiniLM-L6-v2"):
        """Initialize the KET-RAG system"""
        self.nlp = spacy.load("en_core_web_sm")
        self.embedding_model = SentenceTransformer(embedding_model_name)
        
        # Knowledge Graph Skeleton (Layer 1)
        self.knowledge_graph = nx.DiGraph()
        
        # Keyword-Chunk Bipartite Graph (Layer 2)
        self.keyword_chunk_graph = nx.Graph()
        
        # Storage for chunks and embeddings
        self.chunks = []  # List of {text: str, metadata: Dict}
        self.chunk_embeddings = []  # Numpy array of embeddings
        
        # Immigration-specific vocabulary
        self.immigration_keywords = {
            "EB1": ["extraordinary ability", "outstanding professor", "multinational executive", 
                   "national award", "scholarly articles", "high salary"],
            "EB2": ["advanced degree", "exceptional ability", "national interest waiver", 
                   "substantial merit", "labor certification"]
        }
    
    def process_document(self, text: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a document with KET-RAG - simplified version for initial testing
        """
        try:
            # 1. Simple document chunking by paragraphs
            chunks = self._chunk_document(text, metadata)
            chunk_texts = [chunk["text"] for chunk in chunks]
            
            # Store chunks
            self.chunks.extend(chunks)
            
            # 2. Create embeddings
            embeddings = self.embedding_model.encode(chunk_texts)
            
            # Store embeddings
            if len(self.chunk_embeddings) == 0:
                self.chunk_embeddings = embeddings
            else:
                self.chunk_embeddings = np.vstack([self.chunk_embeddings, embeddings])
            
            # Return basic results for testing
            return {
                "chunks": chunks,
                "embeddings": embeddings,
                "metadata": metadata
            }
            
        except Exception as e:
            logger.error(f"Error processing document: {str(e)}")
            raise e
    
    def _chunk_document(self, text: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Split document into chunks by paragraphs
        """
        # Split by paragraphs
        paragraphs = [p for p in text.split('\n\n') if p.strip()]
        
        chunks = []
        for i, para in enumerate(paragraphs):
            chunk_metadata = {
                **metadata,
                "chunk_index": len(chunks),
                "paragraph_index": i
            }
            chunks.append({
                "text": para,
                "metadata": chunk_metadata
            })
        
        return chunks
    
    def retrieve(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Simple vector-based retrieval for initial testing
        """
        if len(self.chunks) == 0 or len(self.chunk_embeddings) == 0:
            return []
        
        # Get query embedding
        query_embedding = self.embedding_model.encode([query])[0]
        
        # Calculate similarity
        similarities = cosine_similarity([query_embedding], self.chunk_embeddings)[0]
        
        # Get top results
        top_indices = similarities.argsort()[-top_k:][::-1]
        
        # Return results
        results = []
        for idx in top_indices:
            results.append({
                'chunk_idx': idx,
                'text': self.chunks[idx]["text"],
                'metadata': self.chunks[idx]["metadata"],
                'score': float(similarities[idx])
            })
        
        return results
    
    def format_for_llm(self, query: str, results: List[Dict[str, Any]]) -> str:
        """
        Format retrieval results for LLM prompt
        """
        formatted = f"Query: {query}\n\nRelevant information:\n\n"
        
        for i, result in enumerate(results):
            formatted += f"[{i+1}] {result['text']}\n\n"
        
        return formatted