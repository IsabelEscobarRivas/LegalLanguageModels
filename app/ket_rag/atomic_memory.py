"""
Atomic memory management for letter generation
"""
import logging
from typing import Dict, List, Any, Optional, Set

logger = logging.getLogger(__name__)

class AtomicMemory:
    """
    Manages atomic memory units for letter generation with source traceability
    """
    
    def __init__(self):
        """Initialize atomic memory storage"""
        # Initialize section definitions
        self.sections = {
            "background": {
                "required_sources": ["CV", "Degree Certificates"],
                "primary_categories": ["02_Applicant_Background"],
                "template_parts": ["education", "skills", "certifications"],
                "source_mapping": {},  # Maps specific chunks to template parts
                "letter_refs": {}      # References to successful letters
            },
            "experience": {
                "required_sources": ["Work Declarations", "Recommendation Letters"],
                "primary_categories": ["04_NIW_Criterion_2", "05_NIW_Criterion_3"],
                "template_parts": ["work_history", "achievements", "impact"],
                "source_mapping": {},
                "letter_refs": {}
            },
            "expert_opinion": {
                "required_sources": ["Opinion PDF"],
                "primary_categories": ["06_Letters_of_Recommendation"],
                "template_parts": ["credentials", "evaluation", "recommendation"],
                "source_mapping": {},
                "letter_refs": {}
            }
        }
        
        # Add visa-specific sections
        self._initialize_visa_sections()
        
        # Content storage - separate from section definitions
        self.content = {}
        self.source_content_mapping = {}  # Maps section.field to source chunks
        self.letter_refs_mapping = {}     # Maps section.field to letter references
        
    def _initialize_visa_sections(self):
        """Initialize visa-specific sections"""
        # EB1 sections
        self.sections["introduction"] = {
            "required_sources": [],
            "primary_categories": ["01_General_Documents"],
            "template_parts": ["opening", "applicant_intro"],
            "source_mapping": {},
            "letter_refs": {}
        }
        
        self.sections["achievements"] = {
            "required_sources": ["Awards", "Publications", "Recognition"],
            "primary_categories": ["03_NIW_Criterion_1_Significant_Merit_and_Importance"],
            "template_parts": ["awards", "recognition", "contributions"],
            "source_mapping": {},
            "letter_refs": {}
        }
        
        # EB2 sections
        self.sections["national_interest"] = {
            "required_sources": ["Impact Statements", "Field Evidence"],
            "primary_categories": ["03_NIW_Criterion_1_Significant_Merit_and_Importance", 
                                 "05_NIW_Criterion_3_Benefit_to_USA_Without_Labor_Certification"],
            "template_parts": ["merit", "positioning", "waiver_justification"],
            "source_mapping": {},
            "letter_refs": {}
        }
        
        # Common sections
        self.sections["conclusion"] = {
            "required_sources": [],
            "primary_categories": [],
            "template_parts": ["summary", "recommendation"],
            "source_mapping": {},
            "letter_refs": {}
        }
    
    def map_chunks_to_parts(self, section_name: str, chunks: List[Dict[str, Any]]) -> Dict[str, List]:
        """Map source chunks to specific parts of a section template"""
        if section_name not in self.sections:
            logger.warning(f"Unknown section: {section_name}")
            return {}
           
        section = self.sections[section_name]
        mapping = {part: [] for part in section["template_parts"]}
       
        # Simple keyword-based mapping
        keywords = {
            # Original mappings
            "education": ["degree", "university", "education", "academic", "study"],
            "skills": ["skill", "expertise", "proficient", "knowledge", "ability"],
            "certifications": ["certif", "license", "credential", "qualification"],
            "work_history": ["work", "job", "position", "employed", "career"],
            "achievements": ["achieve", "accomplish", "success", "award", "recognition"],
            "impact": ["impact", "contribut", "influence", "effect", "result"],
            "credentials": ["credential", "qualification", "background", "expert"],
            "evaluation": ["evaluat", "assess", "review", "analysis"],
            "recommendation": ["recommend", "endorse", "support", "advocate"],
            
            # New mappings for visa-specific sections
            "opening": ["write", "support", "petition", "behalf"],
            "applicant_intro": ["applicant", "field", "background", "introduce"],
            "awards": ["award", "prize", "medal", "honor", "grant"],
            "recognition": ["recognized", "acknowledged", "distinguished", "reputation"],
            "contributions": ["contribut", "develop", "research", "advance", "innovat"],
            "merit": ["merit", "importance", "significant", "substantial", "value"],
            "positioning": ["position", "advance", "qualification", "background", "unique"],
            "waiver_justification": ["waiver", "benefit", "interest", "advantage", "important"],
            "summary": ["summary", "conclude", "therefore", "thus", "finally"],
        }
       
        # Map chunks to parts based on keyword matches
        for chunk in chunks:
            text = chunk["text"].lower()
            for part, part_keywords in keywords.items():
                if part in mapping:
                    for keyword in part_keywords:
                        if keyword in text:
                            mapping[part].append(chunk)
                            break
       
        # Ensure every part has at least one chunk
        for part in mapping:
            if not mapping[part] and chunks:
                mapping[part] = [chunks[0]]  # Assign first chunk as fallback
       
        # Store the mapping in the section
        self.sections[section_name]["source_mapping"] = mapping
        return mapping
    
    def map_letter_examples_to_parts(self, section_name: str, letter_examples: List[Dict[str, Any]]) -> Dict[str, List]:
        """Map letter examples to specific parts of a section template"""
        if section_name not in self.sections:
            logger.warning(f"Unknown section: {section_name}")
            return {}
        
        section = self.sections[section_name]
        mapping = {part: [] for part in section["template_parts"]}
        
        # Use the same keyword mapping as for chunks
        keywords = {
            # Original mappings
            "education": ["degree", "university", "education", "academic", "study"],
            "skills": ["skill", "expertise", "proficient", "knowledge", "ability"],
            "certifications": ["certif", "license", "credential", "qualification"],
            "work_history": ["work", "job", "position", "employed", "career"],
            "achievements": ["achieve", "accomplish", "success", "award", "recognition"],
            "impact": ["impact", "contribut", "influence", "effect", "result"],
            "credentials": ["credential", "qualification", "background", "expert"],
            "evaluation": ["evaluat", "assess", "review", "analysis"],
            "recommendation": ["recommend", "endorse", "support", "advocate"],
            
            # New mappings for visa-specific sections
            "opening": ["write", "support", "petition", "behalf"],
            "applicant_intro": ["applicant", "field", "background", "introduce"],
            "awards": ["award", "prize", "medal", "honor", "grant"],
            "recognition": ["recognized", "acknowledged", "distinguished", "reputation"],
            "contributions": ["contribut", "develop", "research", "advance", "innovat"],
            "merit": ["merit", "importance", "significant", "substantial", "value"],
            "positioning": ["position", "advance", "qualification", "background", "unique"],
            "waiver_justification": ["waiver", "benefit", "interest", "advantage", "important"],
            "summary": ["summary", "conclude", "therefore", "thus", "finally"],
        }
        
        # Map letter examples to parts based on keyword matches
        for example in letter_examples:
            text = example.get("text", "").lower()
            for part, part_keywords in keywords.items():
                if part in mapping:
                    for keyword in part_keywords:
                        if keyword in text:
                            mapping[part].append(example)
                            break
        
        # Store the mapping in the section
        self.sections[section_name]["letter_refs"] = mapping
        return mapping
    
    def add_section_data(self, section_name: str, field_name: str, content: str, 
                        source_chunks: Optional[List[Dict[str, Any]]] = None,
                        letter_refs: Optional[List[Dict[str, Any]]] = None):
        """
        Add content for a specific field in a section with traceability
        
        Args:
            section_name: Name of the section (e.g., "background")
            field_name: Name of the field within the section (e.g., "education_background")
            content: The text content to store
            source_chunks: Source document chunks that support this content
            letter_refs: References to successful letters that influenced this content
        """
        # Initialize section in content if not exists
        if section_name not in self.content:
            self.content[section_name] = {}
        
        # Store content
        self.content[section_name][field_name] = content
        
        # Track source chunks if provided
        if source_chunks:
            key = f"{section_name}.{field_name}"
            self.source_content_mapping[key] = source_chunks
        
        # Track letter references if provided
        if letter_refs:
            key = f"{section_name}.{field_name}"
            self.letter_refs_mapping[key] = letter_refs
    
    def get_section_data(self, section_name: str, field_name: Optional[str] = None):
        """Get data for a section or specific field"""
        if section_name not in self.content:
            return None
            
        if field_name:
            return self.content[section_name].get(field_name)
            
        return self.content[section_name]
    
    def get_section_requirements(self, section_name: str) -> Dict:
        """Get requirements for a specific section"""
        return self.sections.get(section_name, {})
    
    def get_sources(self, section_name: str, field_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get source chunks for a section or field"""
        if field_name:
            key = f"{section_name}.{field_name}"
            return self.source_content_mapping.get(key, [])
            
        # Return all sources for all fields in the section
        sources = []
        for key, chunks in self.source_content_mapping.items():
            if key.startswith(f"{section_name}."):
                sources.extend(chunks)
        return sources
    
    def get_letter_references(self, section_name: str, field_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get referenced letter examples for a section or field"""
        if field_name:
            key = f"{section_name}.{field_name}"
            return self.letter_refs_mapping.get(key, [])
            
        # Return all letter references for all fields in the section
        refs = []
        for key, letters in self.letter_refs_mapping.items():
            if key.startswith(f"{section_name}."):
                refs.extend(letters)
        return refs
    
    def fill_template(self, template: str, additional_fields: Optional[Dict[str, str]] = None) -> str:
        """Fill a template with data from all sections"""
        # Flatten all section data
        data = {}
        for section, fields in self.content.items():
            data.update(fields)
            
        # Add any additional fields
        if additional_fields:
            data.update(additional_fields)
            
        # Replace placeholders in template
        result = template
        for key, value in data.items():
            placeholder = "{{" + key + "}}"
            result = result.replace(placeholder, str(value))
            
        return result
    
    def get_all_data(self) -> Dict[str, Dict[str, str]]:
        """Get all data from all sections"""
        return self.content.copy()
    
    def get_all_sources(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get all source mappings"""
        return self.source_content_mapping.copy()
    
    def get_all_letter_refs(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get all letter references"""
        return self.letter_refs_mapping.copy()
    
    def get_referenced_letter_ids(self) -> Set[str]:
        """Get all unique letter IDs referenced in this memory"""
        letter_ids = set()
        for refs in self.letter_refs_mapping.values():
            for ref in refs:
                letter_id = ref.get("metadata", {}).get("letter_id")
                if letter_id:
                    letter_ids.add(letter_id)
        return letter_ids