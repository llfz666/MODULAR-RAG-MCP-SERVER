"""Unit tests for Executor and SafetyGate."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from agent.core.executor import (
    Executor,
    Action,
    Observation,
    SafetyGate,
)
from agent.mcp.tool_registry import ToolRegistry


class TestObservation:
    """Tests for Observation dataclass."""

    def test_default_values(self):
        """Test default observation values."""
        obs = Observation(success=True)
        assert obs.success is True
        assert obs.result is None
        assert obs.error is None
        assert obs.latency_ms == 0.0

    def test_with_result(self):
        """Test observation with result."""
        obs = Observation(success=True, result={"data": "test"}, latency_ms=100.0)
        assert obs.success is True
        assert obs.result == {"data": "test"}
        assert obs.latency_ms == 100.0

    def test_with_error(self):
        """Test observation with error."""
        obs = Observation(success=False, error="Test error", latency_ms=50.0)
        assert obs.success is False
        assert obs.error == "Test error"
        assert obs.latency_ms == 50.0


class TestAction:
    """Tests for Action dataclass."""

    def test_default_values(self):
        """Test action creation."""
        action = Action(tool_name="search", tool_input={"query": "test"})
        assert action.tool_name == "search"
        assert action.tool_input == {"query": "test"}


class TestSafetyGate:
    """Tests for SafetyGate."""

    def test_default_no_approval(self):
        """Test safety gate with no approval required."""
        gate = SafetyGate(require_approval=False)
        assert gate.requires_approval("any_tool") is False
        assert gate.requires_approval("delete_file") is False

    def test_with_approval_dangerous_tools(self):
        """Test safety gate with approval for dangerous tools."""
        gate = SafetyGate(require_approval=True)
        assert gate.requires_approval("delete_file") is True
        assert gate.requires_approval("execute_code") is True
        assert gate.requires_approval("write_file") is True
        assert gate.requires_approval("shell") is True
        assert gate.requires_approval("search") is False

    def test_with_approval_safe_tools(self):
        """Test safety gate with safe tools."""
        gate = SafetyGate(require_approval=True)
        assert gate.requires_approval("search") is False
        assert gate.requires_approval("list_collections") is False
        assert gate.requires_approval("preview_document") is False

    @pytest.mark.asyncio
    async def test_wait_for_approval_denied(self, monkeypatch):
        """Test waiting for approval - denied."""
        gate = SafetyGate(require_approval=True)
        monkeypatch.setattr("builtins.input", lambda _: "n")
        
        action = Action(tool_name="delete_file", tool_input={"path": "test.txt"})
        result = await gate.wait_for_approval(action)
        assert result is False

    @pytest.mark.asyncio
    async def test_wait_for_approval_approved(self, monkeypatch):
        """Test waiting for approval - approved."""
        gate = SafetyGate(require_approval=True)
        monkeypatch.setattr("builtins.input", lambda _: "y")
        
        action = Action(tool_name="delete_file", tool_input={"path": "test.txt"})
        result = await gate.wait_for_approval(action)
        assert result is True


class TestExecutor:
    """Tests for Executor."""

    @pytest.fixture
    def mock_tool_registry(self):
        """Create a mock tool registry."""
        registry = MagicMock(spec=ToolRegistry)
        registry.execute_tool = AsyncMock()
        return registry

    @pytest.fixture
    def executor(self, mock_tool_registry):
        """Create executor with mock registry."""
        return Executor(tool_registry=mock_tool_registry)

    @pytest.mark.asyncio
    async def test_execute_success(self, executor, mock_tool_registry):
        """Test successful tool execution."""
        mock_tool_registry.execute_tool.return_value = {"result": "test data"}
        
        action = Action(tool_name="search", tool_input={"query": "test"})
        result = await executor.execute(action)
        
        assert result.success is True
        assert result.result == {"result": "test data"}
        assert result.error is None
        assert result.latency_ms >= 0
        mock_tool_registry.execute_tool.assert_called_once_with(
            "search",
            {"query": "test"},
        )

    @pytest.mark.asyncio
    async def test_execute_error(self, executor, mock_tool_registry):
        """Test tool execution with error."""
        mock_tool_registry.execute_tool.side_effect = Exception("Test error")
        
        action = Action(tool_name="search", tool_input={"query": "test"})
        result = await executor.execute(action)
        
        assert result.success is False
        assert "Test error" in result.error
        assert result.result is None

    @pytest.mark.asyncio
    async def test_execute_with_safety_gate_approval(
        self, mock_tool_registry
    ):
        """Test execution with safety gate approval."""
        gate = SafetyGate(require_approval=True)
        # Mock the wait_for_approval to return True
        gate.wait_for_approval = AsyncMock(return_value=True)
        
        executor = Executor(
            tool_registry=mock_tool_registry,
            safety_gate=gate,
        )
        
        mock_tool_registry.execute_tool.return_value = {"result": "data"}
        
        action = Action(tool_name="delete_file", tool_input={"path": "test.txt"})
        result = await executor.execute(action)
        
        assert result.success is True
        gate.wait_for_approval.assert_called_once_with(action)

    @pytest.mark.asyncio
    async def test_execute_with_safety_gate_denied(
        self, mock_tool_registry
    ):
        """Test execution with safety gate denial."""
        gate = SafetyGate(require_approval=True)
        # Mock the wait_for_approval to return False
        gate.wait_for_approval = AsyncMock(return_value=False)
        
        executor = Executor(
            tool_registry=mock_tool_registry,
            safety_gate=gate,
        )
        
        action = Action(tool_name="delete_file", tool_input={"path": "test.txt"})
        result = await executor.execute(action)
        
        assert result.success is False
        assert "User denied" in result.error
        mock_tool_registry.execute_tool.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_measures_latency(self, executor, mock_tool_registry):
        """Test that execution measures latency."""
        mock_tool_registry.execute_tool.return_value = {"result": "data"}
        
        action = Action(tool_name="search", tool_input={"query": "test"})
        result = await executor.execute(action)
        
        assert result.latency_ms >= 0
        assert isinstance(result.latency_ms, float)