"""
Letter processor for handling successful letter examples
"""
import logging
from typing import Dict, List, Any, Optional
import uuid

logger = logging.getLogger(__name__)

class LetterProcessor:
    """
    Processes, stores, and indexes successful letter examples for retrieval
    """
    
    def __init__(self, ketrag):
        """Initialize with a reference to the KET-RAG system"""
        self.ketrag = ketrag
        self.letter_registry = {}  # Store metadata about processed letters
    
    def process_letter(self, letter_text: str, metadata: Dict[str, Any], sections: Optional[Dict[str, str]] = None) -> str:
        """
        Process a successful letter for indexing and retrieval
        
        Args:
            letter_text: The full text of the letter
            metadata: Dict containing visa_type, profession, outcome, etc.
            sections: Optional dict mapping section IDs to section text
            
        Returns:
            letter_id: Unique ID of the processed letter
        """
        letter_id = metadata.get("letter_id", str(uuid.uuid4()))
        
        # Store letter metadata
        metadata["letter_id"] = letter_id
        self.letter_registry[letter_id] = metadata
        
        # Process the whole letter if sections not provided
        if not sections:
            # Process the full letter text
            self.ketrag.process_document(
                letter_text,
                {
                    **metadata,
                    "document_type": "successful_letter",
                    "is_letter_example": True
                }
            )
            logger.info(f"Processed full letter {letter_id} for {metadata.get('visa_type', 'unknown')}")
            return letter_id
            
        # Process letter by sections
        for section_id, section_text in sections.items():
            # Process each section separately
            self.ketrag.process_document(
                section_text,
                {
                    **metadata,
                    "document_type": "successful_letter",
                    "is_letter_example": True,
                    "section_id": section_id
                }
            )
            logger.info(f"Processed section {section_id} of letter {letter_id}")
        
        return letter_id
    
    def retrieve_letter_examples(self, 
                                visa_type: str, 
                                profession: str, 
                                section_id: str, 
                                query: str,
                                top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Retrieve relevant examples from successful letters
        
        Args:
            visa_type: Type of visa (EB1, EB2, etc.)
            profession: Profession category
            section_id: Specific section to retrieve
            query: Query text to match against
            top_k: Number of examples to retrieve
            
        Returns:
            List of relevant chunks from successful letters
        """
        # Create a filter function for letter examples
        def letter_filter(chunk):
            metadata = chunk.get("metadata", {})
            return (
                metadata.get("is_letter_example", False) and
                metadata.get("visa_type") == visa_type and
                (not profession or metadata.get("profession") == profession) and
                (not section_id or metadata.get("section_id") == section_id)
            )
        
        # Retrieve relevant examples
        results = self.ketrag.retrieve(
            query=query,
            top_k=top_k,
            filter_fn=letter_filter
        )
        
        return results
    
    def get_letter_metadata(self, letter_id: str) -> Dict[str, Any]:
        """Get metadata for a specific letter"""
        return self.letter_registry.get(letter_id, {})
    
    def get_all_letters(self, visa_type: Optional[str] = None, profession: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all registered letters, optionally filtered by visa type or profession
        
        Returns list of letter metadata dictionaries
        """
        results = []
        for letter_id, metadata in self.letter_registry.items():
            if visa_type and metadata.get("visa_type") != visa_type:
                continue
            if profession and metadata.get("profession") != profession:
                continue
            results.append(metadata)
        return results