"""Integration tests for Cross-Encoder Reranker with real model.

This module tests the Cross-Encoder Reranker with actual model loading
and scoring, verifying end-to-end functionality.

Usage:
    pytest tests/integration/test_cross_encoder_reranker_integration.py -v

Requirements:
    - sentence-transformers installed
    - Network access to download model (first run)
    - Sufficient disk space for model cache (~500MB)
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import Mock

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.core.settings import Settings
from src.libs.reranker.cross_encoder_reranker import (
    CrossEncoderRerankError,
    CrossEncoderReranker,
)


# Skip tests if sentence-transformers or torch is not available
try:
    import torch  # noqa: F401
    from sentence_transformers import CrossEncoder  # noqa: F401
    TORCH_AVAILABLE = True
except (ImportError, OSError):
    # OSError can occur on Windows with DLL loading issues
    TORCH_AVAILABLE = False

pytest.importorskip("sentence_transformers", reason="sentence-transformers or torch not available")


@pytest.fixture(scope="module")
def real_settings():
    """Create real settings for integration testing."""
    settings = Settings()
    # Override rerank settings for cross-encoder testing
    settings.rerank.model = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    settings.rerank.enabled = True
    settings.rerank.provider = "cross_encoder"
    return settings


@pytest.fixture(scope="module")
def loaded_reranker(real_settings):
    """Create a CrossEncoderReranker with real loaded model.
    
    This fixture loads the model once per module for efficiency.
    """
    print("\n[Integration Test] Loading Cross-Encoder model...")
    reranker = CrossEncoderReranker(settings=real_settings)
    print(f"[Integration Test] Model loaded: {type(reranker.model).__name__}")
    return reranker


@pytest.fixture
def sample_test_candidates():
    """Sample candidates for reranking tests."""
    return [
        {
            "id": "doc_001_chunk_1",
            "text": "Python is a high-level programming language known for its simplicity and readability.",
            "source": "programming_basics.pdf",
            "score": 0.75
        },
        {
            "id": "doc_002_chunk_1", 
            "text": "Machine learning is a subset of artificial intelligence that enables systems to learn from data.",
            "source": "ml_intro.pdf",
            "score": 0.80
        },
        {
            "id": "doc_003_chunk_1",
            "text": "The Python programming language is widely used in machine learning and data science due to its extensive libraries.",
            "source": "python_ml.pdf",
            "score": 0.70
        },
        {
            "id": "doc_004_chunk_1",
            "text": "Deep learning neural networks require significant computational resources and large datasets.",
            "source": "deep_learning.pdf",
            "score": 0.65
        },
        {
            "id": "doc_005_chunk_1",
            "text": "Python's scikit-learn library provides simple and efficient tools for data mining and data analysis.",
            "source": "sklearn_guide.pdf",
            "score": 0.72
        },
    ]


class TestCrossEncoderModelLoading:
    """Test real model loading functionality."""
    
    def test_model_loads_successfully(self, real_settings):
        """Test that the Cross-Encoder model loads successfully."""
        reranker = CrossEncoderReranker(settings=real_settings)
        
        assert reranker.model is not None
        assert hasattr(reranker.model, 'predict')
        print(f"\nModel type: {type(reranker.model).__name__}")
    
    def test_model_can_score_pairs(self, loaded_reranker):
        """Test that the loaded model can score query-passage pairs."""
        test_pairs = [
            ("Python programming", "Python is a popular programming language"),
            ("Python programming", "The weather is nice today"),
        ]
        
        scores = loaded_reranker._score_pairs(test_pairs)
        
        assert len(scores) == 2
        assert isinstance(scores[0], float)
        assert isinstance(scores[1], float)
        # First pair should score higher (semantically related)
        print(f"\nScores: {scores}")
        assert scores[0] > scores[1], "Related pair should score higher"


class TestCrossEncoderReranking:
    """Test end-to-end reranking with real model."""
    
    def test_rerank_orders_by_relevance(self, loaded_reranker, sample_test_candidates):
        """Test that reranking orders candidates by semantic relevance."""
        query = "Python programming language"
        
        result = loaded_reranker.rerank(query, sample_test_candidates)
        
        assert len(result) == len(sample_test_candidates)
        assert all("rerank_score" in c for c in result)
        
        # Verify scores are in descending order
        scores = [c["rerank_score"] for c in result]
        assert scores == sorted(scores, reverse=True), "Results should be sorted by score descending"
        
        # Print ranking for inspection
        print("\nReranking Results:")
        for i, item in enumerate(result):
            print(f"  [{i+1}] Score: {item['rerank_score']:.4f} - {item['text'][:60]}...")
    
    def test_rerank_with_top_k(self, loaded_reranker, sample_test_candidates):
        """Test that top_k limits the output size."""
        query = "machine learning"
        top_k = 3
        
        result = loaded_reranker.rerank(query, sample_test_candidates, top_k=top_k)
        
        assert len(result) == top_k
        assert all("rerank_score" in c for c in result)
    
    def test_rerank_preserves_candidate_fields(self, loaded_reranker, sample_test_candidates):
        """Test that reranking preserves all original candidate fields."""
        query = "Python"
        
        result = loaded_reranker.rerank(query, sample_test_candidates)
        
        for original, reranked in zip(sample_test_candidates, result):
            # Find matching candidate by ID
            original_match = next((c for c in sample_test_candidates if c["id"] == reranked["id"]), None)
            assert original_match is not None
            
            # Verify original fields are preserved
            assert reranked["text"] == original_match["text"]
            assert reranked["source"] == original_match["source"]
            assert reranked["score"] == original_match["score"]
            # Verify new field is added
            assert "rerank_score" in reranked
    
    def test_rerank_semantic_relevance(self, loaded_reranker):
        """Test that reranking captures semantic relevance, not just keyword matching."""
        query = "benefits of exercise"
        
        candidates = [
            {"id": "1", "text": "Exercise has many health benefits including improved cardiovascular health."},
            {"id": "2", "text": "The word exercise appears in this sentence about cooking recipes."},
            {"id": "3", "text": "Physical activity and working out can improve mental health and longevity."},
            {"id": "4", "text": "Random text about computers and programming languages."},
        ]
        
        result = loaded_reranker.rerank(query, candidates)
        
        # Candidates 1 and 3 should rank higher (semantically related to exercise benefits)
        top_ids = [c["id"] for c in result[:2]]
        assert "1" in top_ids, "Health benefits passage should rank high"
        assert "3" in top_ids, "Physical activity passage should rank high"
        
        print("\nSemantic Relevance Test:")
        for i, item in enumerate(result):
            print(f"  [{i+1}] Score: {item['rerank_score']:.4f} - ID: {item['id']}")


class TestCrossEncoderEdgeCases:
    """Test edge cases and error handling."""
    
    def test_empty_query_raises(self, loaded_reranker, sample_test_candidates):
        """Test that empty query raises ValueError."""
        with pytest.raises(ValueError, match="Query cannot be empty"):
            loaded_reranker.rerank("", sample_test_candidates)
    
    def test_empty_candidates_raises(self, loaded_reranker):
        """Test that empty candidates list raises ValueError."""
        with pytest.raises(ValueError, match="Candidates cannot be empty"):
            loaded_reranker.rerank("query", [])
    
    def test_invalid_top_k_raises(self, loaded_reranker, sample_test_candidates):
        """Test that invalid top_k raises ValueError."""
        with pytest.raises(ValueError, match="top_k must be a positive integer"):
            loaded_reranker.rerank("query", sample_test_candidates, top_k=0)
    
    def test_single_candidate(self, loaded_reranker):
        """Test reranking with single candidate."""
        candidate = [{"id": "1", "text": "Single passage about Python programming"}]
        
        result = loaded_reranker.rerank("Python", candidate)
        
        assert len(result) == 1
        assert "rerank_score" in result[0]
    
    def test_very_long_passage(self, loaded_reranker):
        """Test handling of very long passages."""
        long_text = "Python programming. " * 1000  # Create long text
        
        candidate = [{"id": "1", "text": long_text}]
        
        result = loaded_reranker.rerank("Python", candidate)
        
        assert len(result) == 1
        assert "rerank_score" in result[0]


class TestCrossEncoderPerformance:
    """Basic performance characteristics."""
    
    def test_batch_scoring_efficiency(self, loaded_reranker):
        """Test that batch scoring is efficient."""
        import time
        
        # Create many pairs for timing test
        num_pairs = 50
        pairs = [
            (f"Query {i}", f"Passage about topic {i} with some content")
            for i in range(num_pairs)
        ]
        
        start_time = time.time()
        scores = loaded_reranker._score_pairs(pairs)
        elapsed = time.time() - start_time
        
        assert len(scores) == num_pairs
        assert elapsed < 10.0, f"Scoring {num_pairs} pairs should take less than 10s, took {elapsed:.2f}s"
        
        print(f"\nPerformance: Scored {num_pairs} pairs in {elapsed:.3f}s")
    
    def test_model_reuse(self, loaded_reranker, sample_test_candidates):
        """Test that model can be reused for multiple queries."""
        queries = ["Python", "machine learning", "data science"]
        
        results = []
        for query in queries:
            result = loaded_reranker.rerank(query, sample_test_candidates)
            results.append(result)
        
        assert len(results) == 3
        assert all(len(r) == len(sample_test_candidates) for r in results)


if __name__ == "__main__":
    # Allow running directly with python
    pytest.main([__file__, "-v", "-s"])