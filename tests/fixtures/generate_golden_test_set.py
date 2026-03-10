"""Generate Golden Test Set with expected chunk IDs for Custom Evaluator.

This script:
1. Ingests sample documents into the knowledge base
2. Creates test queries with known expected chunk IDs
3. Saves the golden test set to tests/fixtures/golden_test_set.json

Usage:
    python tests/fixtures/generate_golden_test_set.py
"""

import json
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.core.settings import Settings
from src.ingestion.document_manager import DocumentManager
from src.core.query_engine.hybrid_search import HybridSearch


def get_sample_chunk_ids_for_query(query: str, all_chunks: list, top_k: int = 5) -> list:
    """Get expected chunk IDs for a query based on content matching.
    
    This is a helper to manually curate expected chunk IDs by examining
    chunk content. In production, these would come from annotated data.
    """
    # Simple keyword matching to find relevant chunks
    query_words = query.lower().split()
    scored_chunks = []
    
    for chunk in all_chunks:
        chunk_text = chunk.get('text', chunk.get('content', '')).lower()
        score = sum(1 for word in query_words if word in chunk_text)
        if score > 0:
            chunk_id = chunk.get('id', chunk.get('chunk_id', ''))
            scored_chunks.append((chunk_id, score))
    
    # Sort by score and return top chunk IDs
    scored_chunks.sort(key=lambda x: x[1], reverse=True)
    return [chunk_id for chunk_id, _ in scored_chunks[:top_k]]


def main():
    """Generate golden test set."""
    print("=" * 60)
    print("Golden Test Set Generator")
    print("=" * 60)
    
    # Initialize settings
    settings = Settings()
    
    # Sample documents to ingest
    sample_docs_dir = Path(__file__).parent / "sample_documents"
    sample_files = [
        sample_docs_dir / "sample.txt",
        sample_docs_dir / "simple.pdf",
        sample_docs_dir / "blogger_intro.pdf",
    ]
    
    print(f"\n1. Ingesting sample documents...")
    print(f"   Files: {[str(f) for f in sample_files]}")
    
    try:
        # Ingest documents
        doc_manager = DocumentManager(settings=settings)
        
        ingested_docs = []
        for file_path in sample_files:
            if file_path.exists():
                print(f"   Ingesting: {file_path.name}")
                result = doc_manager.ingest_file(str(file_path))
                ingested_docs.append(result)
            else:
                print(f"   Skipping (not found): {file_path.name}")
        
        if not ingested_docs:
            print("\n   No documents were ingested. Creating mock test set.")
            create_mock_golden_test_set()
            return
        
        print(f"   Ingested {len(ingested_docs)} documents.")
        
        # Get all chunks for curation
        print("\n2. Retrieving all chunks for curation...")
        hybrid_search = HybridSearch(settings=settings)
        
        # Query with empty string to get all chunks (or use a wildcard approach)
        all_chunks = []
        try:
            # Try to get chunks from the collection
            collection_name = settings.vector_store.collection_name
            from src.ingestion.storage.vector_upserter import VectorStoreManager
            
            vsm = VectorStoreManager(settings=settings)
            all_chunks = vsm.get_all_chunks(collection=collection_name)
            print(f"   Retrieved {len(all_chunks)} chunks from vector store.")
        except Exception as e:
            print(f"   Could not retrieve chunks: {e}")
            print("   Creating mock test set instead.")
            create_mock_golden_test_set()
            return
        
        # Display chunk info for manual curation
        print("\n3. Chunk Information (for manual curation):")
        print("-" * 60)
        for i, chunk in enumerate(all_chunks[:20]):  # Show first 20
            chunk_id = chunk.get('id', chunk.get('chunk_id', 'unknown'))
            chunk_text = chunk.get('text', chunk.get('content', ''))[:100]
            print(f"   [{i}] ID: {chunk_id}")
            print(f"       Text: {chunk_text}...")
            print()
        
        # Define test queries
        test_queries = [
            {
                "query": "What is Modular RAG?",
                "description": "Tests retrieval of RAG concept chunks"
            },
            {
                "query": "How does the ingestion pipeline work?",
                "description": "Tests retrieval of pipeline-related chunks"
            },
            {
                "query": "What embedding models are supported?",
                "description": "Tests retrieval of embedding configuration chunks"
            },
            {
                "query": "Explain the hybrid search mechanism",
                "description": "Tests retrieval of search/fusion chunks"
            },
            {
                "query": "How to configure the LLM provider?",
                "description": "Tests retrieval of LLM configuration chunks"
            },
        ]
        
        # Create golden test set
        golden_test_set = {
            "description": "Golden test set for Modular RAG MCP Server evaluation. Contains test queries with expected chunk IDs for IR metrics and optional reference answers for LLM-as-Judge metrics.",
            "version": "1.1",
            "generated_at": str(Path(__file__).stat().st_mtime),
            "source_documents": [str(f.name) for f in sample_files if f.exists()],
            "test_cases": []
        }
        
        print("\n4. Creating test cases...")
        for test_query in test_queries:
            query = test_query["query"]
            print(f"\n   Query: {query}")
            print(f"   Description: {test_query['description']}")
            
            # Get relevant chunk IDs using keyword matching
            expected_ids = get_sample_chunk_ids_for_query(query, all_chunks, top_k=3)
            
            print(f"   Expected chunk IDs: {expected_ids}")
            
            test_case = {
                "query": query,
                "expected_chunk_ids": expected_ids,
                "expected_sources": [],  # Can be populated from chunk metadata
                "reference_answer": f"Reference answer for: {query}",
                "notes": test_query["description"]
            }
            golden_test_set["test_cases"].append(test_case)
        
        # Save golden test set
        output_path = Path(__file__).parent / "golden_test_set.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(golden_test_set, f, indent=2, ensure_ascii=False)
        
        print(f"\n5. Golden Test Set saved to: {output_path}")
        print(f"   Total test cases: {len(golden_test_set['test_cases'])}")
        
        # Print summary
        print("\n" + "=" * 60)
        print("Summary:")
        print(f"   - Documents ingested: {len(ingested_docs)}")
        print(f"   - Total chunks: {len(all_chunks)}")
        print(f"   - Test cases created: {len(golden_test_set['test_cases'])}")
        print("=" * 60)
        
    except Exception as e:
        print(f"\nError during generation: {e}")
        import traceback
        traceback.print_exc()
        print("\nCreating mock golden test set as fallback...")
        create_mock_golden_test_set()


def create_mock_golden_test_set():
    """Create a mock golden test set when actual ingestion is not possible.
    
    This provides a working test set structure that can be used for testing
    the Custom Evaluator even without a populated vector store.
    """
    mock_golden_test_set = {
        "description": "Golden test set for Modular RAG MCP Server evaluation. Contains test queries with expected chunk IDs for IR metrics and optional reference answers for LLM-as-Judge metrics.",
        "version": "1.1-mock",
        "note": "This is a mock test set. Run the script with a populated vector store to generate real expected_chunk_ids.",
        "test_cases": [
            {
                "query": "What is Modular RAG?",
                "expected_chunk_ids": [
                    "chunk_001",
                    "chunk_002",
                    "chunk_003"
                ],
                "expected_sources": ["sample.txt", "simple.pdf"],
                "reference_answer": "Modular RAG is a Retrieval-Augmented Generation system built with modular, pluggable components that can be configured and swapped independently."
            },
            {
                "query": "How to configure Azure OpenAI?",
                "expected_chunk_ids": [
                    "chunk_010",
                    "chunk_011"
                ],
                "expected_sources": ["sample.txt"],
                "reference_answer": "Configure Azure OpenAI by setting the provider to 'azure' in settings.yaml, along with the deployment_name, azure_endpoint, api_version, and api_key fields."
            },
            {
                "query": "What is hybrid search and how does it work?",
                "expected_chunk_ids": [
                    "chunk_020",
                    "chunk_021",
                    "chunk_022"
                ],
                "expected_sources": ["blogger_intro.pdf"],
                "reference_answer": "Hybrid search combines dense retrieval (semantic embeddings) and sparse retrieval (BM25 keyword matching), then fuses results using Reciprocal Rank Fusion (RRF) for better recall."
            },
            {
                "query": "Explain the chunking strategy",
                "expected_chunk_ids": [
                    "chunk_030",
                    "chunk_031"
                ],
                "expected_sources": ["sample.txt"],
                "reference_answer": "Documents are split into chunks using configurable strategies (recursive, semantic, or fixed-length). Chunks are then refined and enriched with metadata before storage."
            },
            {
                "query": "What evaluation metrics are supported?",
                "expected_chunk_ids": [
                    "chunk_040",
                    "chunk_041",
                    "chunk_042"
                ],
                "expected_sources": ["simple.pdf"],
                "reference_answer": "The system supports hit_rate, MRR (custom metrics), and Ragas LLM-as-Judge metrics including faithfulness, answer_relevancy, and context_precision."
            }
        ]
    }
    
    output_path = Path(__file__).parent / "golden_test_set.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(mock_golden_test_set, f, indent=2, ensure_ascii=False)
    
    print(f"Mock Golden Test Set saved to: {output_path}")


if __name__ == "__main__":
    main()