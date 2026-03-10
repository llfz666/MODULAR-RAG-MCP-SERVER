"""Integration tests for Custom Evaluator with Golden Test Set.

This module tests the Custom Evaluator with real golden test set data,
verifying hit_rate and MRR computation against expected chunk IDs.

Usage:
    pytest tests/integration/test_custom_evaluator_integration.py -v
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import Mock

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.core.settings import Settings
from src.libs.evaluator.custom_evaluator import CustomEvaluator
from src.libs.evaluator.evaluator_factory import EvaluatorFactory


@pytest.fixture
def golden_test_set_path():
    """Path to the golden test set file."""
    return Path(__file__).parent.parent / "fixtures" / "golden_test_set.json"


@pytest.fixture
def loaded_golden_test_set(golden_test_set_path):
    """Load the golden test set from file."""
    with open(golden_test_set_path, 'r', encoding='utf-8') as f:
        return json.load(f)


@pytest.fixture
def custom_evaluator():
    """Create a CustomEvaluator instance."""
    return CustomEvaluator(metrics=["hit_rate", "mrr"])


class TestGoldenTestSetLoading:
    """Test golden test set loading and validation."""
    
    def test_golden_test_set_exists(self, golden_test_set_path):
        """Test that golden test set file exists."""
        assert golden_test_set_path.exists(), f"Golden test set not found at {golden_test_set_path}"
    
    def test_golden_test_set_structure(self, loaded_golden_test_set):
        """Test golden test set has required structure."""
        assert "description" in loaded_golden_test_set
        assert "version" in loaded_golden_test_set
        assert "test_cases" in loaded_golden_test_set
        assert isinstance(loaded_golden_test_set["test_cases"], list)
        assert len(loaded_golden_test_set["test_cases"]) > 0
    
    def test_test_case_structure(self, loaded_golden_test_set):
        """Test each test case has required fields."""
        required_fields = ["query", "expected_chunk_ids"]
        
        for i, test_case in enumerate(loaded_golden_test_set["test_cases"]):
            for field in required_fields:
                assert field in test_case, f"Test case {i} missing '{field}'"
            
            # Validate expected_chunk_ids is a list
            assert isinstance(test_case["expected_chunk_ids"], list), \
                f"Test case {i}: expected_chunk_ids must be a list"
    
    def test_test_case_has_content(self, loaded_golden_test_set):
        """Test that test cases have non-empty content."""
        for i, test_case in enumerate(loaded_golden_test_set["test_cases"]):
            assert test_case["query"].strip(), f"Test case {i}: query cannot be empty"
            # Note: expected_chunk_ids can be empty for negative testing


class TestCustomEvaluatorWithGoldenSet:
    """Test Custom Evaluator using golden test set data."""
    
    def test_hit_rate_with_perfect_retrieval(self, custom_evaluator):
        """Test hit_rate when all expected chunks are retrieved."""
        test_case = {
            "query": "Test query",
            "expected_chunk_ids": ["chunk_001", "chunk_002"]
        }
        
        # Simulate perfect retrieval
        retrieved_chunks = [
            {"id": "chunk_001"},
            {"id": "chunk_002"},
            {"id": "chunk_003"},
        ]
        
        metrics = custom_evaluator.evaluate(
            query=test_case["query"],
            retrieved_chunks=retrieved_chunks,
            ground_truth=test_case["expected_chunk_ids"]
        )
        
        assert metrics["hit_rate"] == 1.0
        assert metrics["mrr"] == 1.0  # First result is a hit
    
    def test_hit_rate_with_partial_retrieval(self, custom_evaluator):
        """Test hit_rate when some expected chunks are retrieved."""
        test_case = {
            "query": "Test query",
            "expected_chunk_ids": ["chunk_001", "chunk_002", "chunk_003"]
        }
        
        # Simulate partial retrieval - only chunk_002 is retrieved
        retrieved_chunks = [
            {"id": "chunk_004"},
            {"id": "chunk_002"},  # Hit at position 2
            {"id": "chunk_005"},
        ]
        
        metrics = custom_evaluator.evaluate(
            query=test_case["query"],
            retrieved_chunks=retrieved_chunks,
            ground_truth=test_case["expected_chunk_ids"]
        )
        
        assert metrics["hit_rate"] == 1.0  # At least one hit
        assert metrics["mrr"] == 0.5  # Hit at position 2
    
    def test_hit_rate_with_no_retrieval(self, custom_evaluator):
        """Test hit_rate when no expected chunks are retrieved."""
        test_case = {
            "query": "Test query",
            "expected_chunk_ids": ["chunk_001", "chunk_002"]
        }
        
        # Simulate no relevant retrieval
        retrieved_chunks = [
            {"id": "chunk_003"},
            {"id": "chunk_004"},
            {"id": "chunk_005"},
        ]
        
        metrics = custom_evaluator.evaluate(
            query=test_case["query"],
            retrieved_chunks=retrieved_chunks,
            ground_truth=test_case["expected_chunk_ids"]
        )
        
        assert metrics["hit_rate"] == 0.0
        assert metrics["mrr"] == 0.0
    
    def test_mrr_position_sensitivity(self, custom_evaluator):
        """Test that MRR correctly reflects hit position."""
        ground_truth = ["target_chunk"]
        
        # Hit at position 1
        result1 = custom_evaluator.evaluate(
            "q", [{"id": "target_chunk"}], ground_truth=ground_truth
        )
        assert result1["mrr"] == 1.0
        
        # Hit at position 3
        result3 = custom_evaluator.evaluate(
            "q",
            [{"id": "a"}, {"id": "b"}, {"id": "target_chunk"}],
            ground_truth=ground_truth
        )
        assert result3["mrr"] == pytest.approx(0.333, rel=0.01)
        
        # Hit at position 5
        result5 = custom_evaluator.evaluate(
            "q",
            [{"id": "a"}, {"id": "b"}, {"id": "c"}, {"id": "d"}, {"id": "target_chunk"}],
            ground_truth=ground_truth
        )
        assert result5["mrr"] == 0.2


class TestEvaluatorFactoryIntegration:
    """Test Evaluator Factory integration."""
    
    def test_factory_creates_custom_evaluator(self):
        """Test that factory creates CustomEvaluator correctly."""
        settings = Mock()
        settings.evaluation.enabled = True
        settings.evaluation.provider = "custom"
        settings.evaluation.metrics = ["hit_rate", "mrr"]
        
        evaluator = EvaluatorFactory.create(settings)
        
        assert isinstance(evaluator, CustomEvaluator)
        assert "hit_rate" in evaluator.metrics
        assert "mrr" in evaluator.metrics
    
    def test_factory_with_golden_set_workflow(self, loaded_golden_test_set):
        """Test complete evaluation workflow with golden test set."""
        # Create evaluator via factory
        settings = Mock()
        settings.evaluation.enabled = True
        settings.evaluation.provider = "custom"
        settings.evaluation.metrics = ["hit_rate", "mrr"]
        
        evaluator = EvaluatorFactory.create(settings)
        
        # Simulate evaluation for each test case
        results = []
        for test_case in loaded_golden_test_set["test_cases"]:
            # Simulate retrieved chunks (mock retrieval)
            # In real scenario, this would come from actual retrieval
            retrieved_chunks = self._simulate_retrieval(test_case)
            
            metrics = evaluator.evaluate(
                query=test_case["query"],
                retrieved_chunks=retrieved_chunks,
                ground_truth=test_case["expected_chunk_ids"]
            )
            results.append({
                "query": test_case["query"],
                "metrics": metrics
            })
        
        # Verify all test cases produced results
        assert len(results) == len(loaded_golden_test_set["test_cases"])
        assert all("hit_rate" in r["metrics"] for r in results)
        assert all("mrr" in r["metrics"] for r in results)
    
    def _simulate_retrieval(self, test_case: Dict[str, Any]) -> List[Dict[str, str]]:
        """Simulate retrieval for testing.
        
        In real scenario, this would be actual retrieval from vector store.
        This simulation creates a mix of relevant and irrelevant chunks.
        """
        expected_ids = test_case.get("expected_chunk_ids", [])
        
        # Simulate: include some expected IDs and some random IDs
        retrieved = []
        
        # Add some expected chunks (if any)
        for i, chunk_id in enumerate(expected_ids[:2]):  # Add up to 2 relevant
            retrieved.append({"id": chunk_id})
        
        # Add some noise
        noise_ids = ["noise_001", "noise_002", "noise_003"]
        for noise_id in noise_ids:
            retrieved.append({"id": noise_id})
        
        return retrieved


class TestAggregateMetrics:
    """Test aggregate metric computation across test set."""
    
    def test_compute_average_metrics(self, custom_evaluator, loaded_golden_test_set):
        """Test computing average metrics across all test cases."""
        all_hit_rates = []
        all_mrrs = []
        
        for test_case in loaded_golden_test_set["test_cases"]:
            # Simulate retrieval with varying quality
            retrieved_chunks = self._simulate_varied_retrieval(
                test_case["expected_chunk_ids"],
                test_case["query"]
            )
            
            metrics = custom_evaluator.evaluate(
                query=test_case["query"],
                retrieved_chunks=retrieved_chunks,
                ground_truth=test_case["expected_chunk_ids"]
            )
            
            all_hit_rates.append(metrics["hit_rate"])
            all_mrrs.append(metrics["mrr"])
        
        # Compute averages
        avg_hit_rate = sum(all_hit_rates) / len(all_hit_rates)
        avg_mrr = sum(all_mrrs) / len(all_mrrs)
        
        # Verify metrics are in valid range
        assert 0.0 <= avg_hit_rate <= 1.0
        assert 0.0 <= avg_mrr <= 1.0
        
        print(f"\nAggregate Metrics:")
        print(f"  Average Hit Rate: {avg_hit_rate:.4f}")
        print(f"  Average MRR: {avg_mrr:.4f}")
        print(f"  Test Cases: {len(all_hit_rates)}")
    
    def _simulate_varied_retrieval(
        self,
        expected_ids: List[str],
        query: str
    ) -> List[Dict[str, str]]:
        """Simulate retrieval with varied quality based on query hash."""
        import hashlib
        
        # Use query hash to create deterministic but varied retrieval
        query_hash = int(hashlib.md5(query.encode()).hexdigest()[:8], 16)
        
        retrieved = []
        
        if expected_ids:
            # Add some expected IDs based on hash
            num_relevant = (query_hash % 3) + 1  # 1-3 relevant chunks
            for i, chunk_id in enumerate(expected_ids[:num_relevant]):
                retrieved.append({"id": chunk_id})
        
        # Always add some noise
        num_noise = (query_hash % 3) + 2  # 2-4 noise chunks
        for i in range(num_noise):
            retrieved.append({"id": f"noise_{query_hash}_{i}"})
        
        return retrieved


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_empty_expected_ids(self, custom_evaluator):
        """Test handling of empty expected_chunk_ids."""
        retrieved_chunks = [{"id": "chunk_001"}]
        
        metrics = custom_evaluator.evaluate(
            query="test",
            retrieved_chunks=retrieved_chunks,
            ground_truth=[]
        )
        
        # With no ground truth, metrics should be 0
        assert metrics["hit_rate"] == 0.0
        assert metrics["mrr"] == 0.0
    
    def test_single_expected_chunk(self, custom_evaluator):
        """Test with single expected chunk ID."""
        retrieved_chunks = [
            {"id": "other_001"},
            {"id": "target"},
            {"id": "other_002"},
        ]
        
        metrics = custom_evaluator.evaluate(
            query="test",
            retrieved_chunks=retrieved_chunks,
            ground_truth=["target"]
        )
        
        assert metrics["hit_rate"] == 1.0
        assert metrics["mrr"] == 0.5  # Hit at position 2
    
    def test_multiple_expected_chunks_single_hit(self, custom_evaluator):
        """Test with multiple expected chunks but only one retrieved."""
        retrieved_chunks = [
            {"id": "noise_001"},
            {"id": "target_2"},  # One of the expected
            {"id": "noise_002"},
        ]
        
        metrics = custom_evaluator.evaluate(
            query="test",
            retrieved_chunks=retrieved_chunks,
            ground_truth=["target_1", "target_2", "target_3"]
        )
        
        assert metrics["hit_rate"] == 1.0
        assert metrics["mrr"] == 0.5


if __name__ == "__main__":
    # Allow running directly with python
    pytest.main([__file__, "-v", "-s"])