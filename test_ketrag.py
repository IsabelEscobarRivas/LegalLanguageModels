"""
Test KET-RAG basic functionality
"""
from app.ket_rag.core import KETRAG
from app.ket_rag.corpus_builder import CorpusBuilder
import os

def test_ketrag_basic():
    """Test basic KET-RAG functionality"""
    print("Initializing KET-RAG...")
    ket_rag = KETRAG()
   
    # Sample test documents
    test_docs = [
        {
            "text": """EB1 visa is for aliens with extraordinary ability.
            It requires meeting at least 3 of 10 criteria set by USCIS.
            National awards, high salary, and original contributions are examples of criteria.""",
            "metadata": {"case_id": "test1", "visa_type": "EB1", "category": "informational"}
        },
        {
            "text": """EB2 visas are for individuals with advanced degrees or exceptional ability.
            The National Interest Waiver (NIW) allows applicants to self-petition without labor certification.
            Applicants must demonstrate that their work is in the national interest of the United States.""",
            "metadata": {"case_id": "test2", "visa_type": "EB2", "category": "informational"}
        }
    ]
   
    # Process test documents
    print("Processing test documents...")
    for doc in test_docs:
        result = ket_rag.process_document(doc["text"], doc["metadata"])
        print(f"Processed document with {len(result['chunks'])} chunks")
   
    # Test retrieval
    print("\nTesting retrieval...")
    queries = [
        "What criteria are needed for EB1?",
        "How does the National Interest Waiver work?",
        "What is required for extraordinary ability?"
    ]
   
    for query in queries:
        print(f"\nQuery: {query}")
        results = ket_rag.retrieve(query)
        print(f"Found {len(results)} results")
        if results:
            print("Top result:")
            print(f"Score: {results[0]['score']:.2f}")
            print(f"Text: {results[0]['text'][:100]}...")
       
        # Format for LLM
        formatted = ket_rag.format_for_llm(query, results)
        print("\nFormatted for LLM:")
        print("-" * 40)
        print(formatted[:200] + "...")
        print("-" * 40)
   
    print("\nKET-RAG basic test completed successfully!")

def test_case_connections():
    """Test that documents within the same case are properly connected in the knowledge graph"""
    print("\n--- Testing Case Connections in Knowledge Graph ---\n")
    
    # Load the model if available, otherwise run database build
    builder = CorpusBuilder()
    corpus_path = "ket_rag_corpus.pkl"
    
    if os.path.exists(corpus_path):
        print(f"Loading existing corpus from {corpus_path}")
        ket_rag = builder.load_model(corpus_path)
    else:
        print("Building new corpus from database")
        ket_rag = builder.build_from_database()
        builder.save_model(corpus_path)
    
    # Extract document and case information
    case_docs = {}
    doc_id_to_filename = {}
    
    for i, chunk in enumerate(ket_rag.chunks):
        case_id = chunk["metadata"].get("case_id", "unknown")
        doc_id = chunk["metadata"].get("id", "unknown")
        filename = chunk["metadata"].get("filename", f"doc_{doc_id}")
        
        if doc_id != "unknown":
            case_docs.setdefault(case_id, set()).add(doc_id)
            doc_id_to_filename[doc_id] = filename
    
    # Check connections between documents in each case
    print("\nChecking document connections within each case:")
    
    for case_id, doc_ids in case_docs.items():
        if len(doc_ids) < 2:
            print(f"\nCase {case_id} only has {len(doc_ids)} document(s), skipping")
            continue
            
        print(f"\nCase: {case_id}")
        print(f"Contains {len(doc_ids)} documents: {', '.join([doc_id_to_filename.get(id, id) for id in doc_ids])}")
        
        doc_ids_list = list(doc_ids)
        connection_count = 0
        missing_connections = []
        
        # Check each pair of documents
        for i in range(len(doc_ids_list)):
            for j in range(i+1, len(doc_ids_list)):
                doc1_id = doc_ids_list[i]
                doc2_id = doc_ids_list[j]
                
                # Find chunk IDs for these documents
                doc1_chunks = []
                doc2_chunks = []
                
                for node_id, node_data in ket_rag.knowledge_graph.nodes(data=True):
                    meta = node_data.get('metadata', {})
                    if meta.get('id') == doc1_id:
                        doc1_chunks.append(node_id)
                    elif meta.get('id') == doc2_id:
                        doc2_chunks.append(node_id)
                
                if not doc1_chunks or not doc2_chunks:
                    print(f"  ⚠️ Could not find chunks for one or both documents: {doc1_id} and {doc2_id}")
                    continue
                
                # Check for connections between any chunks from the two documents
                connected = False
                edge_types = set()
                
                for n1 in doc1_chunks:
                    for n2 in doc2_chunks:
                        if ket_rag.knowledge_graph.has_edge(n1, n2):
                            edge_data = ket_rag.knowledge_graph.get_edge_data(n1, n2)
                            edge_types.add(edge_data.get('edge_type', 'unknown'))
                            connected = True
                        elif ket_rag.knowledge_graph.has_edge(n2, n1):
                            edge_data = ket_rag.knowledge_graph.get_edge_data(n2, n1)
                            edge_types.add(edge_data.get('edge_type', 'unknown'))
                            connected = True
                
                doc1_name = doc_id_to_filename.get(doc1_id, doc1_id)
                doc2_name = doc_id_to_filename.get(doc2_id, doc2_id)
                
                if connected:
                    connection_count += 1
                    edge_types_str = ", ".join(edge_types)
                    print(f"  ✅ Documents connected: {doc1_name} and {doc2_name} via {edge_types_str}")
                else:
                    missing_connections.append((doc1_name, doc2_name))
                    print(f"  ❌ Documents NOT connected: {doc1_name} and {doc2_name}")
        
        total_pairs = len(doc_ids) * (len(doc_ids) - 1) // 2
        print(f"\n  Summary: {connection_count}/{total_pairs} document pairs are connected")
        
        if missing_connections:
            print(f"  Missing connections: {', '.join([f'{d1}-{d2}' for d1, d2 in missing_connections])}")
        else:
            print("  All documents within this case are properly connected! ✓")
    
    print("\nCase connection test completed.")
    return ket_rag

if __name__ == "__main__":
    # test_ketrag_basic()  # Uncomment this to run the basic test
    test_case_connections()  # Comment this out if you want to run the basic test instead