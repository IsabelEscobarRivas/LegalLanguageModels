"""
Test script for the enhanced KET-RAG letter generation system
"""
import pickle
import logging
from app.ket_rag.generator import LetterGenerator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_letter_generator():
    """Test the enhanced letter generator with example letter integration"""
    
    # Initialize letter generator
    generator = LetterGenerator(model_path="ket_rag_corpus.pkl")
    
    # Step 1: Add a successful letter example
    example_letter = """
    I am writing in strong support of Dr. Jane Smith's petition for classification as an Alien of Extraordinary Ability in the field of Artificial Intelligence.
    
    Dr. Smith holds a Ph.D. in Computer Science from Stanford University and has made significant contributions to the field of machine learning. Her research on neural networks has been cited over 500 times, and she has published in top-tier journals including Nature and Science.
    
    Dr. Smith has received numerous awards including the Outstanding Young Researcher Award from the International Association for AI. She has been invited to judge grant applications for the National Science Foundation and has reviewed manuscripts for leading journals.
    
    Based on her extraordinary achievements and the evidence presented, I strongly recommend that USCIS approve her petition.
    """
    
    example_metadata = {
        "visa_type": "EB1",
        "profession": "researcher",
        "outcome": "approved",
        "field": "Artificial Intelligence"
    }
    
    example_sections = {
        "introduction": "I am writing in strong support of Dr. Jane Smith's petition for classification as an Alien of Extraordinary Ability in the field of Artificial Intelligence.",
        "background": "Dr. Smith holds a Ph.D. in Computer Science from Stanford University and has made significant contributions to the field of machine learning.",
        "achievements": "Dr. Smith has received numerous awards including the Outstanding Young Researcher Award from the International Association for AI. She has been invited to judge grant applications for the National Science Foundation and has reviewed manuscripts for leading journals.",
        "conclusion": "Based on her extraordinary achievements and the evidence presented, I strongly recommend that USCIS approve her petition."
    }
    
    letter_id = generator.add_successful_letter(
        example_letter, 
        example_metadata, 
        example_sections
    )
    
    logger.info(f"Added example letter with ID: {letter_id}")
    
    # Step 2: Generate a new letter for a test case
    test_case_id = "Rafaela"  # Use an existing case from your corpus
    test_profession = "researcher"
    test_visa_type = "EB1"
    
    # Generate with example letters
    logger.info(f"Generating letter for case {test_case_id} with example letters...")
    letter_result = generator.generate_letter(
        case_id=test_case_id,
        profession=test_profession,
        visa_type=test_visa_type,
        use_examples=True
    )
    
    # Print the result
    logger.info("Generated letter with examples:")
    print("\n" + "="*80)
    print(letter_result["full_letter"])
    print("="*80 + "\n")
    
    # Print traceability info
    print("Letter Traceability Information:")
    print(f"Case ID: {letter_result['case_id']}")
    print(f"Visa Type: {letter_result['visa_type']}")
    print(f"Profession: {letter_result['profession']}")
    
    for section, metadata in letter_result["section_metadata"].items():
        print(f"\nSection: {section}")
        print(f"Used {metadata['chunk_count']} document chunks")
        print(f"Used {metadata['example_count']} letter examples")
    
    return letter_result

if __name__ == "__main__":
    test_letter_generator()