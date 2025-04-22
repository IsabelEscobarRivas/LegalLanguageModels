"""
Test script for atomic memory letter generation
"""
from app.ket_rag.generator import LetterGenerator
import json

def test_atomic_memory_letter():
    """Test generating a letter using atomic memory"""
    generator = LetterGenerator()
    
    # Use an actual case ID from your database
    case_id = "Pereira"  # Replace with an actual case ID
    profession = "engineer"  # Or appropriate profession
    
    # Generate letter
    letter = generator.generate_letter(case_id, profession)
    
    # Print results
    print(f"Generated letter for case {case_id}")
    print("=" * 50)
    print(letter["full_letter"])
    print("=" * 50)
    
    # Print source tracing information
    print("Source citations by section:")
    for section, metadata in letter["section_metadata"].items():
        print(f"\n{section.upper()}:")
        for part, citations in metadata.get("source_citations", {}).items():
            print(f"  {part}:")
            for i, citation in enumerate(citations):
                print(f"    - {citation['filename']}")
    
    # Save result to file for inspection
    with open("letter_with_atomic_memory.json", "w") as f:
        # Convert to dict first to make it serializable
        serializable = {
            "letter": letter["full_letter"],
            "metadata": {
                "case": letter["metadata"],
                "sections": letter["section_metadata"]
            }
        }
        json.dump(serializable, f, indent=2)
    
    print("\nFull results saved to letter_with_atomic_memory.json")

if __name__ == "__main__":
    test_atomic_memory_letter()