"""
Letter generation module with atomic memory for KET-RAG
"""
import logging
import pickle
from typing import Dict, Any, List, Optional
import uuid

from app.ket_rag.case_context import CaseContext
from app.ket_rag.templates import TemplateRegistry
from app.ket_rag.atomic_memory import AtomicMemory

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
        # Get all chunks
        letter_examples = []
        
        for i, chunk in enumerate(self.ketrag.chunks):
            metadata = chunk.get("metadata", {})
            
            # Check if this is a letter example matching criteria
            if (metadata.get("is_letter_example", False) and
                metadata.get("visa_type") == visa_type and
                (not profession or metadata.get("profession") == profession) and
                (not section_id or metadata.get("section_id") == section_id)):
                
                # Calculate similarity to query
                # This is a simplification - use embed/retrieval in real version
                letter_examples.append({
                    "text": chunk["text"],
                    "metadata": metadata,
                    "chunk_id": i
                })
                
                if len(letter_examples) >= top_k:
                    break
        
        return letter_examples
    
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


class LetterGenerator:
    """
    Generate visa application letters using KET-RAG with atomic memory
    """
    
    def __init__(self, model_path: str = "ket_rag_corpus.pkl"):
        """Initialize with a saved KET-RAG model"""
        with open(model_path, 'rb') as f:
            self.ket_rag = pickle.load(f)
        self.template_registry = TemplateRegistry()
        self.atomic_memory = AtomicMemory()
        self.letter_processor = LetterProcessor(self.ket_rag)
        logger.info("Letter generator initialized with atomic memory")
    
    def format_chunks(self, chunks: List[Dict[str, Any]]) -> str:
        """Format chunks for inclusion in prompts"""
        formatted = ""
        for i, chunk in enumerate(chunks):
            formatted += f"--- Document {i+1}: {chunk['metadata'].get('filename', 'Unknown')} ---\n"
            formatted += chunk['text']
            formatted += "\n\n"
        return formatted
    
    def format_letter_examples(self, examples: List[Dict[str, Any]]) -> str:
        """Format letter examples for inclusion in prompts"""
        if not examples:
            return ""
            
        formatted = "\n\nEXAMPLES FROM SUCCESSFUL LETTERS:\n"
        for i, example in enumerate(examples):
            visa_type = example['metadata'].get('visa_type', 'Unknown')
            profession = example['metadata'].get('profession', 'Unknown')
            formatted += f"--- Example {i+1} ({visa_type}, {profession}) ---\n"
            formatted += example['text']
            formatted += "\n\n"
        return formatted
    
    def generate_section(self, case_id: str, section: str, profession: str, 
                        visa_type: str = "EB2", use_examples: bool = True, 
                        llm_client=None):
        """Generate a specific section for a case letter using atomic memory"""
        # Create case context
        case_context = CaseContext(self.ket_rag, case_id)
        
        # Get section requirements from atomic memory
        section_reqs = self.atomic_memory.get_section_requirements(section)
        
        # Get chunks focused on required document types
        primary_categories = section_reqs.get("primary_categories", [])
        all_chunks = []
        
        if primary_categories:
            # Get chunks from each relevant category
            for category in primary_categories:
                query = f"Information for {section} from {category}"
                category_chunks = case_context.retrieve_for_case(query, top_k=3)
                all_chunks.extend(category_chunks)
        else:
            # Fallback if no categories defined
            query = f"Information for {section} section"
            all_chunks = case_context.retrieve_for_case(query, top_k=5)
        
        # Get letter examples if enabled
        letter_examples = []
        if use_examples:
            query = f"{section} for {profession} {visa_type}"
            letter_examples = self.letter_processor.retrieve_letter_examples(
                visa_type=visa_type,
                profession=profession,
                section_id=section,
                query=query,
                top_k=2
            )
        
        if not all_chunks and not letter_examples:
            logger.warning(f"No chunks or examples found for case {case_id}, section {section}")
            return {
                "content": f"[No information available for {section}]",
                "source_mapping": {},
                "chunks_used": [],
                "letter_examples_used": []
            }
        
        # Map chunks to specific template parts
        template_mapping = self.atomic_memory.map_chunks_to_parts(section, all_chunks)
        
        # Map letter examples to template parts if available
        letter_mapping = {}
        if letter_examples:
            letter_mapping = self.atomic_memory.map_letter_examples_to_parts(section, letter_examples)
        
        # Get template
        template = self.template_registry.get_template(profession, visa_type, section)
        
        # Generate content for each template part
        part_contents = {}
        source_citations = {}
        letter_citations = {}
        
        for part, part_chunks in template_mapping.items():
            # Get letter examples for this part
            part_examples = letter_mapping.get(part, [])
            
            # Format chunks
            chunks_formatted = self.format_chunks(part_chunks)
            examples_formatted = self.format_letter_examples(part_examples)
            
            # Format prompt for this specific part
            part_prompt = f"""
            Generate the '{part}' portion of the '{section}' section for a {visa_type} visa application letter for a {profession}.
            
            Use ONLY the following information from the applicant's documents:
            {chunks_formatted}
            
            {examples_formatted}
            
            Your response should be factual, professional, and based primarily on the provided documents.
            Do not invent or assume information not present in the documents.
            Focus specifically on information relevant to the '{part}' aspect.
            """
            
            # Generate with LLM
            if llm_client:
                part_contents[part] = llm_client.generate(part_prompt)
            else:
                # Placeholder for testing
                examples_used = f" with {len(part_examples)} letter examples" if part_examples else ""
                part_contents[part] = f"[Generated {part} for {section} based on {len(part_chunks)} chunks{examples_used}]"
            
            # Store source citations
            source_citations[part] = [
                {
                    'filename': chunk['metadata'].get('filename', 'Unknown'),
                    'text_snippet': chunk['text'][:100] + '...' if len(chunk['text']) > 100 else chunk['text']
                }
                for chunk in part_chunks
            ]
            
            # Store letter citations
            letter_citations[part] = [
                {
                    'letter_id': example['metadata'].get('letter_id', 'Unknown'),
                    'visa_type': example['metadata'].get('visa_type', 'Unknown'),
                    'profession': example['metadata'].get('profession', 'Unknown'),
                    'text_snippet': example['text'][:100] + '...' if len(example['text']) > 100 else example['text']
                }
                for example in part_examples
            ]
        
        # Try to format template with part contents
        try:
            section_content = template.format(**part_contents)
        except KeyError as e:
            logger.error(f"Template formatting error: {e}")
            # Fallback to concatenation
            section_content = "\n\n".join(part_contents.values())
        
        # Store in atomic memory
        for part, content in part_contents.items():
            self.atomic_memory.add_section_data(
                section_name=section,
                field_name=part,
                content=content,
                source_chunks=template_mapping.get(part, []),
                letter_refs=letter_mapping.get(part, [])
            )
        
        return {
            "content": section_content,
            "source_mapping": template_mapping,
            "source_citations": source_citations,
            "letter_examples_mapping": letter_mapping,
            "letter_citations": letter_citations,
            "chunks_used": all_chunks,
            "letter_examples_used": letter_examples
        }
    
    def generate_letter(self, case_id: str, profession: str, visa_type: str = "EB2", 
                      use_examples: bool = True, llm_client=None):
        """Generate a complete visa application letter with atomic memory tracing"""
        case_context = CaseContext(self.ket_rag, case_id)
        case_metadata = case_context.get_case_metadata()
        
        # Get sections for this visa type and profession
        sections = self.template_registry.get_sections(profession, visa_type)
        
        # Add default sections if none found in templates
        if not sections:
            sections = [
                "introduction",
                "background", 
                "experience",
                "expert_opinion",
                "conclusion"
            ]
        
        letter_content = {}
        section_metadata = {}
        
        for section in sections:
            section_result = self.generate_section(
                case_id=case_id, 
                section=section, 
                profession=profession,
                visa_type=visa_type,
                use_examples=use_examples,
                llm_client=llm_client
            )
            letter_content[section] = section_result["content"]
            section_metadata[section] = {
                "source_citations": section_result.get("source_citations", {}),
                "letter_citations": section_result.get("letter_citations", {}),
                "chunk_count": len(section_result.get("chunks_used", [])),
                "example_count": len(section_result.get("letter_examples_used", []))
            }
        
        # Assemble complete letter
        complete_letter = f"""
        # {visa_type} Visa Application Letter for Case {case_id}
        
        """
        
        # Add each section in order
        for section in sections:
            if section in letter_content:
                complete_letter += f"## {section.capitalize()}\n"
                complete_letter += letter_content[section]
                complete_letter += "\n\n"
        
        return {
            "full_letter": complete_letter,
            "sections": letter_content,
            "metadata": case_metadata,
            "section_metadata": section_metadata,
            "case_id": case_id,
            "visa_type": visa_type,
            "profession": profession,
            "letter_examples_used": bool(use_examples)
        }
    
    def add_successful_letter(self, letter_text: str, metadata: Dict[str, Any], 
                             sections: Optional[Dict[str, str]] = None) -> str:
        """
        Add a successful letter to the system for future reference
        
        Args:
            letter_text: The full text of the letter
            metadata: Dict with visa_type, profession, etc.
            sections: Optional dict mapping section names to their text
            
        Returns:
            letter_id: ID of the added letter
        """
        return self.letter_processor.process_letter(letter_text, metadata, sections)