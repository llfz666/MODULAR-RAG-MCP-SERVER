"""Pytest configuration and fixtures."""

import sys
from pathlib import Path

# Add agent package to path for testing
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pytest


@pytest.fixture
def temp_config_file(tmp_path):
    """Create a temporary config file."""
    config_content = """
settings:
  llm:
    provider: "test"
    model: "test-model"
"""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(config_content)
    return config_file