"""
Case-specific context and retrieval for KET-RAG
"""
import logging
from typing import List, Dict, Any
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)

class CaseContext:
    """
    Context manager for case-specific operations in KET-RAG
    """
    
    def __init__(self, ket_rag, case_id: str):
        """Initialize with a KETRAG instance and case ID"""
        self.ket_rag = ket_rag
        self.case_id = case_id
        logger.info(f"Created case context for case: {case_id}")
    
    def retrieve_for_case(self, query: str, top_k: int = 5):
        """Retrieve documents for a specific case only"""
        # Get query embedding
        query_embedding = self.ket_rag.embedding_model.encode([query])[0]
        
        # Filter chunks by case_id first
        case_chunk_indices = [i for i, chunk in enumerate(self.ket_rag.chunks) 
                            if chunk["metadata"].get("case_id") == self.case_id]
        
        if not case_chunk_indices:
            logger.warning(f"No chunks found for case: {self.case_id}")
            return []
        
        # Get embeddings for only the filtered chunks
        case_embeddings = self.ket_rag.chunk_embeddings[case_chunk_indices]
        
        # Calculate similarity
        similarities = cosine_similarity([query_embedding], case_embeddings)[0]
        
        # Get top results
        top_indices = similarities.argsort()[-top_k:][::-1]
        
        # Map back to original indices
        original_indices = [case_chunk_indices[i] for i in top_indices]
        
        # Return results
        results = []
        for idx in original_indices:
            results.append({
                'chunk_idx': idx,
                'text': self.ket_rag.chunks[idx]["text"],
                'metadata': self.ket_rag.chunks[idx]["metadata"],
                'score': float(similarities[top_indices[original_indices.index(idx)]])
            })
        
        return results
    
    def get_all_case_chunks(self):
        """Get all chunks for this case"""
        case_chunks = []
        for i, chunk in enumerate(self.ket_rag.chunks):
            if chunk["metadata"].get("case_id") == self.case_id:
                case_chunks.append({
                    'chunk_idx': i,
                    'text': chunk["text"],
                    'metadata': chunk["metadata"]
                })
        return case_chunks
    
    def get_case_metadata(self):
        """Get aggregated metadata for this case"""
        case_chunks = self.get_all_case_chunks()
        visa_types = set()
        categories = set()
        filenames = set()
        
        for chunk in case_chunks:
            meta = chunk['metadata']
            if 'visa_type' in meta:
                visa_types.add(meta['visa_type'])
            if 'category' in meta:
                categories.add(meta['category'])
            if 'filename' in meta:
                filenames.add(meta['filename'])
        
        return {
            'case_id': self.case_id,
            'visa_types': list(visa_types),
            'categories': list(categories),
            'document_count': len(filenames)
        }