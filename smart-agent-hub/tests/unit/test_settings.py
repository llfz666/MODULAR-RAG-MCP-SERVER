"""Unit tests for Settings configuration."""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from agent.core.settings import (
    Settings,
    LLMSettings,
    AgentSettings,
    StorageSettings,
    DashboardSettings,
    MCPServerSettings,
    MCPServersSettings,
    load_settings,
    get_settings,
)


class TestLLMSettings:
    """Tests for LLMSettings."""

    def test_default_values(self):
        """Test default LLM settings values."""
        settings = LLMSettings()
        assert settings.provider == "qwen"
        assert settings.model == "qwen3.5-plus"
        assert settings.temperature == 0.0
        assert settings.max_tokens == 4096

    def test_custom_values(self):
        """Test custom LLM settings."""
        settings = LLMSettings(
            provider="openai",
            model="gpt-4",
            temperature=0.7,
            max_tokens=2048,
        )
        assert settings.provider == "openai"
        assert settings.model == "gpt-4"
        assert settings.temperature == 0.7
        assert settings.max_tokens == 2048

    def test_temperature_validation(self):
        """Test temperature validation."""
        # Valid values
        LLMSettings(temperature=0.0)
        LLMSettings(temperature=1.0)
        LLMSettings(temperature=2.0)

        # Invalid values
        with pytest.raises(Exception):
            LLMSettings(temperature=-0.1)
        with pytest.raises(Exception):
            LLMSettings(temperature=2.1)


class TestAgentSettings:
    """Tests for AgentSettings."""

    def test_default_values(self):
        """Test default agent settings values."""
        settings = AgentSettings()
        assert settings.max_iterations == 10
        assert settings.enable_reflection is True
        assert settings.enable_memory is True

    def test_max_iterations_validation(self):
        """Test max_iterations validation."""
        # Valid values
        AgentSettings(max_iterations=1)
        AgentSettings(max_iterations=10)

        # Invalid values
        with pytest.raises(Exception):
            AgentSettings(max_iterations=0)
        with pytest.raises(Exception):
            AgentSettings(max_iterations=-1)


class TestSettings:
    """Tests for main Settings class."""

    def test_default_creation(self):
        """Test creating settings with defaults."""
        settings = Settings()
        assert isinstance(settings.llm, LLMSettings)
        assert isinstance(settings.agent, AgentSettings)
        assert isinstance(settings.storage, StorageSettings)
        assert isinstance(settings.dashboard, DashboardSettings)
        assert isinstance(settings.mcp_servers, MCPServersSettings)

    def test_env_var_expansion(self):
        """Test environment variable expansion."""
        # Set a test environment variable
        os.environ["TEST_VAR"] = "test_value"

        result = Settings.expand_env_vars("${TEST_VAR}")
        assert result == "test_value"

        # Test with non-existent variable (should keep original)
        result = Settings.expand_env_vars("${NONEXISTENT_VAR}")
        assert result == "${NONEXISTENT_VAR}"

        # Clean up
        del os.environ["TEST_VAR"]

    def test_process_dict(self):
        """Test dictionary processing with env vars."""
        os.environ["API_KEY"] = "secret123"

        data = {
            "api_key": "${API_KEY}",
            "nested": {
                "value": "${API_KEY}_suffix"
            },
            "list": ["${API_KEY}", "static"],
            "number": 42,
        }

        processed = Settings.process_dict(data)

        assert processed["api_key"] == "secret123"
        assert processed["nested"]["value"] == "secret123_suffix"
        assert processed["list"][0] == "secret123"
        assert processed["list"][1] == "static"
        assert processed["number"] == 42

        del os.environ["API_KEY"]

    def test_from_yaml(self):
        """Test loading settings from YAML file."""
        config_content = """
settings:
  llm:
    provider: "test_provider"
    model: "test_model"
  agent:
    max_iterations: 5
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(config_content)
            temp_path = f.name

        try:
            settings = Settings.from_yaml(temp_path)
            assert settings.llm.provider == "test_provider"
            assert settings.llm.model == "test_model"
            assert settings.agent.max_iterations == 5
        finally:
            os.unlink(temp_path)

    def test_from_yaml_file_not_found(self):
        """Test loading settings from non-existent file."""
        with pytest.raises(FileNotFoundError):
            Settings.from_yaml("/nonexistent/path/config.yaml")

    def test_from_yaml_empty(self):
        """Test loading settings from empty file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("")
            temp_path = f.name

        try:
            with pytest.raises(ValueError):
                Settings.from_yaml(temp_path)
        finally:
            os.unlink(temp_path)


class TestLoadSettings:
    """Tests for load_settings function."""

    def test_load_from_explicit_path(self):
        """Test loading settings from explicit path."""
        config_content = """
settings:
  llm:
    provider: "explicit"
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(config_content)
            temp_path = f.name

        try:
            settings = load_settings(temp_path)
            assert settings.llm.provider == "explicit"
        finally:
            os.unlink(temp_path)

    def test_load_from_env(self):
        """Test loading settings from environment (defaults)."""
        settings = load_settings(config_path=None)
        # Should return default settings
        assert settings.llm.provider == "qwen"
        assert settings.agent.max_iterations == 10


class TestGetSettings:
    """Tests for get_settings function."""

    def test_get_settings_singleton(self):
        """Test that get_settings returns same instance."""
        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2


class TestMCPServerSettings:
    """Tests for MCPServerSettings."""

    def test_default_values(self):
        """Test default MCP server settings."""
        settings = MCPServerSettings()
        assert settings.enabled is True
        assert settings.command == "python"
        assert settings.args == []
        assert settings.cwd == "."
        assert settings.timeout == 60
        assert settings.tools == []

    def test_custom_values(self):
        """Test custom MCP server settings."""
        settings = MCPServerSettings(
            enabled=False,
            command="npx",
            args=["-y", "mcp-server"],
            cwd="/path/to/server",
            timeout=120,
            tools=["search", "list"],
        )
        assert settings.enabled is False
        assert settings.command == "npx"
        assert settings.args == ["-y", "mcp-server"]
        assert settings.cwd == "/path/to/server"
        assert settings.timeout == 120
        assert settings.tools == ["search", "list"]