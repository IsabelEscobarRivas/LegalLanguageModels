import sys
import os
sys.path.append('.')

from app.ket_rag.corpus_builder import CorpusBuilder
import logging

# Enable detailed logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_basic_rebuild():
    print("=" * 50)
    print("TEST 1: Basic Corpus Rebuild")
    print("=" * 50)
    
    try:
        # Create corpus builder
        print("✓ Creating CorpusBuilder...")
        builder = CorpusBuilder()
        
        # Build corpus from database
        print("✓ Building corpus from database...")
        ket_rag = builder.build_from_database()
        
        # Basic statistics
        print(f"✓ Total chunks processed: {len(ket_rag.chunks)}")
        print(f"✓ Knowledge graph nodes: {ket_rag.knowledge_graph.number_of_nodes()}")
        print(f"✓ Knowledge graph edges: {ket_rag.knowledge_graph.number_of_edges()}")
        print(f"✓ Customer tree nodes: {ket_rag.customer_tree.number_of_nodes()}")
        
        # Save enhanced corpus
        print("✓ Saving enhanced corpus...")
        builder.save_model("ket_rag_corpus_enhanced.pkl")
        
        print("\nTEST 1 PASSED: Basic rebuild successful!")
        return True, ket_rag
        
    except Exception as e:
        print(f"\n TEST 1 FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False, None

if __name__ == "__main__":
    success, ket_rag = test_basic_rebuild()
