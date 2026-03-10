#!/usr/bin/env python
"""Demo script for Custom Evaluator and Cross-Encoder Reranker.

This script demonstrates:
1. Loading and using the Cross-Encoder Reranker
2. Using the Custom Evaluator with Golden Test Set
3. Running end-to-end evaluation workflow

Usage:
    python scripts/demo_evaluation.py

Requirements:
    - sentence-transformers (for Cross-Encoder)
    - pytest (for running tests)
"""

import json
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.libs.evaluator.custom_evaluator import CustomEvaluator
from src.libs.reranker.cross_encoder_reranker import CrossEncoderReranker
from src.core.settings import (
    Settings,
    load_settings,
    LLMSettings,
    EmbeddingSettings,
    VectorStoreSettings,
    RetrievalSettings,
    RerankSettings,
    EvaluationSettings,
    ObservabilitySettings,
)


def print_header(title: str):
    """Print a formatted header."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def create_demo_settings() -> Settings:
    """Create minimal demo settings for testing."""
    return Settings(
        llm=LLMSettings(
            provider="qwen",
            model="qwen3.5-plus",
            temperature=0.0,
            max_tokens=4096,
            api_key="demo-key",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        ),
        embedding=EmbeddingSettings(
            provider="qwen",
            model="text-embedding-v3",
            dimensions=1024,
            api_key="demo-key",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        ),
        vector_store=VectorStoreSettings(
            provider="chroma",
            persist_directory="data/db/chroma",
            collection_name="knowledge_hub",
        ),
        retrieval=RetrievalSettings(
            dense_top_k=20,
            sparse_top_k=20,
            fusion_top_k=10,
            rrf_k=60,
        ),
        rerank=RerankSettings(
            enabled=True,
            provider="cross_encoder",
            model="cross-encoder/ms-marco-MiniLM-L-6-v2",
            top_k=5,
        ),
        evaluation=EvaluationSettings(
            enabled=True,
            provider="custom",
            metrics=["hit_rate", "mrr"],
        ),
        observability=ObservabilitySettings(
            log_level="INFO",
            trace_enabled=True,
            trace_file="logs/traces.jsonl",
            structured_logging=True,
        ),
    )


def demo_cross_encoder_reranker():
    """Demonstrate Cross-Encoder Reranker functionality."""
    print_header("Cross-Encoder Reranker Demo")
    
    # Load settings from config file with cross-encoder model
    try:
        settings = load_settings()
        print(f"\n1. Loaded settings from config/settings.yaml")
    except Exception as e:
        print(f"\n1. Failed to load settings: {e}")
        print("   Using demo settings with cross-encoder...")
        settings = create_demo_settings()
    
    print("\n1. Loading Cross-Encoder model...")
    print(f"   Model: {settings.rerank.model}")
    
    try:
        reranker = CrossEncoderReranker(settings=settings)
        print("   ✓ Model loaded successfully!")
    except Exception as e:
        print(f"   ✗ Failed to load model: {e}")
        print("   Skipping reranker demo (PyTorch may not be available on this system)...")
        return
    
    # Sample candidates for reranking
    query = "Python programming language"
    candidates = [
        {"id": "1", "text": "The weather is nice today."},
        {"id": "2", "text": "Python is a popular programming language for data science."},
        {"id": "3", "text": "Java is another programming language."},
        {"id": "4", "text": "Python snakes are found in Africa and Asia."},
        {"id": "5", "text": "Machine learning with Python using scikit-learn."},
    ]
    
    print(f"\n2. Reranking candidates for query: '{query}'")
    print(f"   Input candidates: {len(candidates)}")
    
    # Perform reranking
    reranked = reranker.rerank(query, candidates, top_k=3)
    
    print(f"   Output candidates: {len(reranked)}")
    print("\n   Top Results:")
    for i, item in enumerate(reranked):
        print(f"   [{i+1}] Score: {item['rerank_score']:.4f} - {item['text'][:50]}...")
    
    print("\n   ✓ Cross-Encoder Reranker demo completed!")


def demo_custom_evaluator():
    """Demonstrate Custom Evaluator with Golden Test Set."""
    print_header("Custom Evaluator Demo")
    
    # Load Golden Test Set
    golden_set_path = project_root / "tests" / "fixtures" / "golden_test_set.json"
    
    print(f"\n1. Loading Golden Test Set...")
    print(f"   Path: {golden_set_path}")
    
    try:
        with open(golden_set_path, 'r', encoding='utf-8') as f:
            golden_set = json.load(f)
        print(f"   ✓ Loaded {len(golden_set['test_cases'])} test cases")
    except Exception as e:
        print(f"   ✗ Failed to load Golden Test Set: {e}")
        return
    
    # Create evaluator
    print("\n2. Creating Custom Evaluator...")
    evaluator = CustomEvaluator(metrics=["hit_rate", "mrr"])
    print("   ✓ Evaluator created with metrics: hit_rate, mrr")
    
    # Simulate evaluation for each test case
    print("\n3. Running evaluation on test cases...")
    
    all_hit_rates = []
    all_mrrs = []
    
    for i, test_case in enumerate(golden_set["test_cases"]):
        query = test_case["query"]
        expected_ids = test_case["expected_chunk_ids"]
        
        # Simulate retrieval (in real scenario, this comes from actual retrieval)
        retrieved_chunks = simulate_retrieval(expected_ids, i)
        
        # Evaluate
        metrics = evaluator.evaluate(
            query=query,
            retrieved_chunks=retrieved_chunks,
            ground_truth=expected_ids
        )
        
        all_hit_rates.append(metrics["hit_rate"])
        all_mrrs.append(metrics["mrr"])
        
        hit_status = "✓" if metrics["hit_rate"] > 0 else "✗"
        print(f"   [{i+1}] {hit_status} Query: {query[:40]}...")
        print(f"       Hit Rate: {metrics['hit_rate']:.2f}, MRR: {metrics['mrr']:.3f}")
    
    # Compute aggregate metrics
    avg_hit_rate = sum(all_hit_rates) / len(all_hit_rates) if all_hit_rates else 0
    avg_mrr = sum(all_mrrs) / len(all_mrrs) if all_mrrs else 0
    
    print(f"\n4. Aggregate Metrics:")
    print(f"   Average Hit Rate: {avg_hit_rate:.4f}")
    print(f"   Average MRR: {avg_mrr:.4f}")
    print(f"   Total Test Cases: {len(all_hit_rates)}")
    
    print("\n   ✓ Custom Evaluator demo completed!")


def simulate_retrieval(expected_ids: list, seed: int) -> list:
    """Simulate retrieval for demo purposes.
    
    In a real scenario, this would be actual retrieval from the vector store.
    """
    retrieved = []
    
    # Add some relevant chunks (simulating partial recall)
    if expected_ids:
        num_relevant = min(len(expected_ids), (seed % 2) + 1)
        for i in range(num_relevant):
            retrieved.append({"id": expected_ids[i]})
    
    # Add some noise
    for i in range(3):
        retrieved.append({"id": f"noise_{seed}_{i}"})
    
    return retrieved


def demo_end_to_end_workflow():
    """Demonstrate end-to-end evaluation workflow."""
    print_header("End-to-End Evaluation Workflow")
    
    print("\nThis workflow combines:")
    print("  1. Document ingestion (not shown in demo)")
    print("  2. Query processing and retrieval")
    print("  3. Reranking with Cross-Encoder")
    print("  4. Evaluation with Custom Evaluator")
    print("\nFor full workflow, run:")
    print("  - pytest tests/integration/test_cross_encoder_reranker_integration.py -v")
    print("  - pytest tests/integration/test_custom_evaluator_integration.py -v")
    
    print("\n   ✓ End-to-End workflow demo completed!")


def main():
    """Run all demos."""
    print_header("Modular RAG MCP Server - Evaluation Demo")
    print("\nThis demo showcases the Custom Evaluator and Cross-Encoder Reranker modules.")
    
    # Run demos
    demo_cross_encoder_reranker()
    demo_custom_evaluator()
    demo_end_to_end_workflow()
    
    print_header("Demo Complete")
    print("\nNext steps:")
    print("  1. Run integration tests for detailed validation")
    print("  2. Ingest actual documents to test with real data")
    print("  3. Update Golden Test Set with actual chunk IDs from your data")
    print("\nFor more information, see:")
    print("  - tests/integration/test_cross_encoder_reranker_integration.py")
    print("  - tests/integration/test_custom_evaluator_integration.py")
    print("  - tests/fixtures/generate_golden_test_set.py")


if __name__ == "__main__":
    main()