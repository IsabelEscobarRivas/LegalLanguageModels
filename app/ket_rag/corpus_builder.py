import boto3
import os
import pickle
import logging
from typing import List

import networkx as nx
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from app.ket_rag.core import KETRAG
from app.config import settings
from app.database import get_db
from app.models import Document

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CorpusBuilder:
    """
    Builds a KET-RAG corpus from documents stored in S3 or database
    """

    def __init__(self):
        self.ket_rag = KETRAG()
        self.s3_client = boto3.client(
            's3',
            region_name="us-east-2",
            aws_access_key_id=settings.AWS_ACCESS_KEY,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
        )

    def build_from_database(self, visa_types: List[str] = ["EB1", "EB2"]) -> KETRAG:
        logger.info("Building corpus from database...")
        db = next(get_db())

        for visa_type in visa_types:
            logger.info(f"Processing {visa_type} documents...")
            documents = db.query(Document).filter(Document.visa_type == visa_type).all()
            logger.info(f"Found {len(documents)} documents for {visa_type}")

            for doc in documents:
                if not doc.extracted_text:
                    logger.warning(f"No extracted text for document {doc.id} - skipping")
                    continue
                logger.info(f"Processing document: {doc.filename}")
                self.ket_rag.process_document(
                    doc.extracted_text,
                    {
                        "id": doc.id,
                        "case_id": doc.case_id,
                        "visa_type": doc.visa_type,
                        "category": doc.category,
                        "document_type": getattr(doc, 'document_type', None),
                        "relevant_sections": getattr(doc, 'relevant_sections', None),
                        "filename": doc.filename,
                        "s3_url": doc.s3_url,
                        "document_metadata": doc.document_metadata
                    }
                )

        logger.info("Building knowledge graph...")
        self._build_knowledge_graph()

        logger.info("Building customer tree structure...")
        self.build_customer_tree()

        return self.ket_rag

    def build_from_s3(self, bucket_name: str = settings.S3_BUCKET_NAME, visa_types: List[str] = ["EB1", "EB2"]) -> KETRAG:
        logger.info(f"Building corpus from S3 bucket: {bucket_name}...")
        db = next(get_db())

        for visa_type in visa_types:
            logger.info(f"Processing {visa_type} documents...")
            documents = db.query(Document).filter(
                Document.visa_type == visa_type,
                Document.extracted_text.isnot(None)
            ).all()
            logger.info(f"Found {len(documents)} documents with extracted text for {visa_type}")

            for doc in documents:
                try:
                    s3_key = doc.s3_url.split(f"{settings.S3_BUCKET_NAME}.s3.amazonaws.com/")[1]
                except Exception:
                    logger.warning(f"Could not parse S3 key from URL: {doc.s3_url}")
                    s3_key = None

                logger.info(f"Processing document: {doc.filename}")
                self.ket_rag.process_document(
                    doc.extracted_text,
                    {
                        "id": doc.id,
                        "case_id": doc.case_id,
                        "visa_type": doc.visa_type,
                        "category": doc.category,
                        "document_type": getattr(doc, 'document_type', None),
                        "relevant_sections": getattr(doc, 'relevant_sections', None),
                        "filename": doc.filename,
                        "s3_key": s3_key,
                        "s3_url": doc.s3_url,
                        "document_metadata": doc.document_metadata
                    }
                )

        logger.info("Building knowledge graph...")
        self._build_knowledge_graph()

        return self.ket_rag

    def _build_knowledge_graph(self) -> None:
        if len(self.ket_rag.chunks) == 0:
            logger.warning("No chunks processed, cannot build knowledge graph")
            return

        logger.info(f"Building isolated knowledge graph from {len(self.ket_rag.chunks)} chunks...")
        self.ket_rag.knowledge_graph.clear()
        case_chunks = {}
        document_chunks = {}

        for i, chunk in enumerate(self.ket_rag.chunks):
            self.ket_rag.knowledge_graph.add_node(i, text=chunk["text"], metadata=chunk["metadata"])
            case_id = chunk["metadata"].get("case_id", "unknown")
            case_chunks.setdefault(case_id, []).append((i, chunk))
            doc_id = chunk["metadata"].get("id", f"unknown_{i}")
            doc_key = f"{case_id}_{doc_id}"
            document_chunks.setdefault(doc_key, []).append(i)

        for case_id, case_data in case_chunks.items():
            if len(case_data) < 2:
                continue

            case_doc_ids = set()
            for _, chunk in case_data:
                doc_id = chunk["metadata"].get("id", "unknown")
                case_doc_ids.add(doc_id)

            case_doc_ids = list(case_doc_ids)
            for i in range(len(case_doc_ids)):
                for j in range(i + 1, len(case_doc_ids)):
                    doc1_id = case_doc_ids[i]
                    doc2_id = case_doc_ids[j]
                    doc1_key = f"{case_id}_{doc1_id}"
                    doc2_key = f"{case_id}_{doc2_id}"
                    doc1_chunks = document_chunks.get(doc1_key, [])
                    doc2_chunks = document_chunks.get(doc2_key, [])
                    if doc1_chunks and doc2_chunks:
                        # Create bi-directional edges between documents in the same case
                        self.ket_rag.knowledge_graph.add_edge(
                            doc1_chunks[0], doc2_chunks[0],
                            weight=0.5,
                            edge_type="same_case_explicit"
                        )
                        # Add the reverse edge to make it bi-directional
                        self.ket_rag.knowledge_graph.add_edge(
                            doc2_chunks[0], doc1_chunks[0],
                            weight=0.5,
                            edge_type="same_case_explicit"
                        )

            case_indices = [idx for idx, _ in case_data]
            case_embeddings = self.ket_rag.chunk_embeddings[case_indices]
            similarity_matrix = cosine_similarity(case_embeddings)
            logger.info(f"Similarity matrix for case {case_id} with {len(case_indices)} chunks:")
            logger.info(similarity_matrix)

            threshold = 0.4
            for i in range(len(case_indices)):
                for j in range(len(case_indices)):
                    if i != j and similarity_matrix[i, j] > threshold:
                        self.ket_rag.knowledge_graph.add_edge(
                            case_indices[i], case_indices[j],
                            weight=float(similarity_matrix[i, j]),
                            edge_type="same_case_similarity"
                        )

        pagerank = nx.pagerank(self.ket_rag.knowledge_graph)
        for node, score in pagerank.items():
            self.ket_rag.knowledge_graph.nodes[node]['pagerank'] = score

        self.ket_rag.keyword_chunk_graph.clear()
        for i, chunk in enumerate(self.ket_rag.chunks):
            case_id = chunk["metadata"].get("case_id", "unknown")
            doc = self.ket_rag.nlp(chunk["text"])
            keywords = set()
            for token in doc:
                if token.pos_ in ["NOUN", "PROPN"] and len(token.text) > 2:
                    keywords.add(token.lemma_.lower())
            for keyword in keywords:
                scoped_keyword = f"case_{case_id}_kw_{keyword}"
                self.ket_rag.keyword_chunk_graph.add_edge(scoped_keyword, f"chunk_{i}")

        logger.info(f"Built case-isolated knowledge graph with {self.ket_rag.knowledge_graph.number_of_nodes()} nodes and {self.ket_rag.knowledge_graph.number_of_edges()} edges")

    def build_customer_tree(self) -> nx.DiGraph:
        case_ids = set(chunk["metadata"].get("case_id") for chunk in self.ket_rag.chunks if chunk["metadata"].get("case_id"))
        logger.info(f"Building trees for {len(case_ids)} unique customers")
        tree_graph = nx.DiGraph()
        tree_graph.add_node("root", node_type="root", text="All Cases")

        for case_id in case_ids:
            tree_graph.add_node(f"case_{case_id}", node_type="case", case_id=case_id)
            tree_graph.add_edge("root", f"case_{case_id}")

        for chunk in self.ket_rag.chunks:
            case_id = chunk["metadata"].get("case_id")
            visa_type = chunk["metadata"].get("visa_type")
            if case_id and visa_type:
                visa_node_id = f"case_{case_id}_visa_{visa_type}"
                if not tree_graph.has_node(visa_node_id):
                    tree_graph.add_node(visa_node_id, node_type="visa_type", case_id=case_id, visa_type=visa_type)
                    tree_graph.add_edge(f"case_{case_id}", visa_node_id)

        for chunk in self.ket_rag.chunks:
            case_id = chunk["metadata"].get("case_id")
            visa_type = chunk["metadata"].get("visa_type")
            category = chunk["metadata"].get("category")
            if case_id and visa_type and category:
                visa_node_id = f"case_{case_id}_visa_{visa_type}"
                category_node_id = f"{visa_node_id}_cat_{category}"
                if not tree_graph.has_node(category_node_id):
                    tree_graph.add_node(category_node_id, node_type="category", case_id=case_id, visa_type=visa_type, category=category)
                    tree_graph.add_edge(visa_node_id, category_node_id)

        for i, chunk in enumerate(self.ket_rag.chunks):
            case_id = chunk["metadata"].get("case_id")
            visa_type = chunk["metadata"].get("visa_type")
            category = chunk["metadata"].get("category")
            if case_id and visa_type and category:
                category_node_id = f"case_{case_id}_visa_{visa_type}_cat_{category}"
                doc_node_id = f"{category_node_id}_doc_{i}"
                tree_graph.add_node(doc_node_id, node_type="document", case_id=case_id, visa_type=visa_type, category=category, chunk_id=i, text=chunk["text"][:100])
                tree_graph.add_edge(category_node_id, doc_node_id)

        self.ket_rag.customer_tree = tree_graph
        logger.info(f"Built customer tree with {tree_graph.number_of_nodes()} nodes and {tree_graph.number_of_edges()} edges")
        return tree_graph

    def save_model(self, output_path: str = "ket_rag_model.pkl") -> None:
        logger.info(f"Saving model to {output_path}...")
        with open(output_path, 'wb') as f:
            pickle.dump(self.ket_rag, f)
        logger.info("Model saved successfully")

    def load_model(self, input_path: str = "ket_rag_model.pkl") -> KETRAG:
        logger.info(f"Loading model from {input_path}...")
        with open(input_path, 'rb') as f:
            self.ket_rag = pickle.load(f)
        logger.info("Model loaded successfully")
        return self.ket_rag


def build_knowledge_graph(self):
    from app.ket_rag.corpus_builder import CorpusBuilder
    builder = CorpusBuilder()
    builder.ket_rag = self
    builder._build_knowledge_graph()

KETRAG.build_knowledge_graph = build_knowledge_graph


def test_corpus_builder():
    builder = CorpusBuilder()
    ket_rag = builder.build_from_database()
    builder.save_model("ket_rag_corpus.pkl")

    test_queries = [
        "What is required for an EB1 visa?",
        "How do I demonstrate extraordinary ability?",
        "What is a National Interest Waiver?",
        "Requirements for EB2 visa"
    ]

    for query in test_queries:
        print(f"\nQuery: {query}")
        results = ket_rag.retrieve(query, top_k=2)
        if results:
            print(f"Found {len(results)} results:")
            for i, result in enumerate(results):
                print(f"Result {i+1}:")
                print(f"Score: {result['score']:.4f}")
                print(f"Text snippet: {result['text'][:150]}...")
                print(f"Document: {result['metadata'].get('filename', 'unknown')}")
                print("-" * 80)
    return ket_rag


if __name__ == "__main__":
    test_corpus_builder()