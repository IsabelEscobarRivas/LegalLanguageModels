"""
Template registry for KET-RAG letter generation
"""
import logging
from typing import Dict, Any, Tuple, Optional, List, Set

logger = logging.getLogger(__name__)

class TemplateRegistry:
    """
    Registry for letter templates organized by profession, visa type, and section
    """
    
    def __init__(self):
        """Initialize the template registry"""
        self.templates = {}
        self._initialize_default_templates()
    
    def _initialize_default_templates(self):
        """Load default templates into the registry"""
        # Add profession-based templates
        for profession, sections in self._default_profession_templates().items():
            for section, template in sections.items():
                self.add_template(profession, "ANY", section, template)
        
        # Add visa-based templates
        for visa_type, sections in self._default_visa_templates().items():
            for section, template in sections.items():
                self.add_template("ANY", visa_type, section, template)
    
    def _default_profession_templates(self) -> Dict[str, Dict[str, str]]:
        """Default templates organized by profession type and section"""
        return {
            "engineer": {
                "background": """
                {name} holds a {degree} in {field} from {university}.
                Their academic background has provided them with expertise in {expertise_areas}.
                """,
                "experience": """
                {name} has {years} years of experience in {industry}.
                Their key accomplishments include {accomplishments}.
                """,
                "expert_opinion": """
                Based on {name}'s credentials, they demonstrate exceptional ability in {field}.
                Their work on {projects} has significant implications for {impact_areas}.
                """
            },
            "medical": {
                "background": """
                Dr. {name} completed their medical education at {university},
                specializing in {specialty}. Their academic training included {training_details}.
                """,
                "experience": """
                Dr. {name} has practiced medicine for {years} years,
                with particular focus on {focus_areas}.
                Their clinical work has included {clinical_experience}.
                """,
                "expert_opinion": """
                Based on Dr. {name}'s extensive experience in {specialty},
                they have demonstrated exceptional ability through {achievements}.
                Their research on {research_topics} has advanced the field of {field}.
                """
            },
            # Add more profession templates as needed
        }
    
    def _default_visa_templates(self) -> Dict[str, Dict[str, str]]:
        """Default templates organized by visa type and section"""
        return {
            "EB1": {
                "introduction": """
                I am writing in strong support of {{applicant_name}}'s petition for classification as an Alien of Extraordinary Ability in the field of {{field}}. 
                After reviewing {{applicant_name}}'s credentials and achievements in detail, I can confidently state that {{he_she}} meets the criteria for this classification.
                """,
                
                "achievements": """
                {{applicant_name}} has demonstrated extraordinary ability through {{achievements_overview}}.
                
                {{key_achievements}}
                
                These accomplishments clearly demonstrate that {{applicant_name}} has risen to the very top of {{his_her}} field of endeavor.
                """,
                
                "conclusion": """
                Based on the evidence presented, it is my professional opinion that {{applicant_name}} clearly meets the criteria for classification as an alien of extraordinary ability.
                
                {{final_recommendation}}
                
                I strongly recommend that USCIS approve this petition.
                """
            },
            "EB2": {
                "introduction": """
                I am writing in support of {{applicant_name}}'s petition for an employment-based immigrant visa with a National Interest Waiver.
                As an expert in {{field}}, I am well-qualified to evaluate {{applicant_name}}'s contributions and their importance to the United States.
                """,
                
                "national_interest": """
                {{applicant_name}}'s work is of substantial merit and national importance because {{national_importance_rationale}}.
                
                {{applicant_name}} is well positioned to advance the proposed endeavor, as evidenced by {{positioning_evidence}}.
                
                On balance, it would be beneficial to the United States to waive the requirements of a job offer and labor certification because {{waiver_justification}}.
                """,
                
                "conclusion": """
                In conclusion, {{applicant_name}} clearly qualifies for the National Interest Waiver based on {{conclusion_summary}}.
                
                {{final_recommendation}}
                
                I strongly recommend that USCIS approve this petition with a National Interest Waiver.
                """
            }
        }
    
    def get_template(self, profession: str, visa_type: str, section: str) -> str:
        """
        Get a template for a specific profession, visa type and section
        
        Strategy:
        1. Try exact match (profession, visa_type, section)
        2. Try profession wildcard (profession, "ANY", section)
        3. Try visa wildcard ("ANY", visa_type, section)
        4. Try generic (fallback to empty string)
        """
        # Check for exact match
        exact_key = (profession, visa_type, section)
        if exact_key in self.templates:
            return self.templates[exact_key]
        
        # Check for profession-specific template
        profession_key = (profession, "ANY", section)
        if profession_key in self.templates:
            return self.templates[profession_key]
            
        # Check for visa-specific template
        visa_key = ("ANY", visa_type, section)
        if visa_key in self.templates:
            return self.templates[visa_key]
        
        # Return empty string if no match
        return ""
    
    def add_template(self, profession: str, visa_type: str, section: str, template: str):
        """Add or update a template"""
        key = (profession, visa_type, section)
        self.templates[key] = template
        logger.info(f"Added template for {profession}/{visa_type}/{section}")
    
    def get_sections(self, profession: str, visa_type: str) -> List[str]:
        """Get all available sections for a specific profession and visa type"""
        sections = set()
        
        # Check for exact profession and visa
        for (p, v, s) in self.templates.keys():
            if (p == profession or p == "ANY") and (v == visa_type or v == "ANY"):
                sections.add(s)
        
        return sorted(list(sections))