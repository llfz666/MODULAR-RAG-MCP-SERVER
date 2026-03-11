"""Unit tests for MCP Client."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.mcp.client import MCPClient
from agent.mcp.tool_registry import ToolRegistry


class TestMCPClientInitialization:
    """Tests for MCPClient initialization."""

    def test_init_with_minimal_config(self):
        """Test initialization with minimal config."""
        config = {"command": "python"}
        client = MCPClient(config)

        assert client.server_config == config
        assert client.session is None
        assert client._connected is False
        assert client._tools_cache == []

    def test_init_with_full_config(self):
        """Test initialization with full config."""
        config = {
            "command": "python",
            "args": ["main.py"],
            "cwd": "/path/to/server",
            "timeout": 120,
        }
        client = MCPClient(config)

        assert client.server_config["command"] == "python"
        assert client.server_config["args"] == ["main.py"]
        assert client.server_config["cwd"] == "/path/to/server"
        assert client.server_config["timeout"] == 120

    def test_is_connected_property(self):
        """Test is_connected property."""
        config = {"command": "python"}
        client = MCPClient(config)

        assert client.is_connected is False

        # Simulate connection
        client._connected = True
        client.session = MagicMock()
        assert client.is_connected is True

        # Session is None
        client.session = None
        assert client.is_connected is False


class TestMCPClientConnect:
    """Tests for MCPClient connect method."""

    @pytest.mark.asyncio
    async def test_connect_success(self):
        """Test successful connection."""
        config = {"command": "python", "args": ["main.py"]}

        # Mock stdio_client context manager using AsyncMock
        mock_read = MagicMock()
        mock_write = MagicMock()
        mock_stdio_cm = AsyncMock()
        mock_stdio_cm.__aenter__.return_value = (mock_read, mock_write)

        # Mock session
        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        
        # Create proper mock tool with attributes
        mock_tool = MagicMock()
        type(mock_tool).name = "search"
        type(mock_tool).description = "Search tool"
        type(mock_tool).inputSchema = {}
        mock_session.list_tools.return_value.tools = [mock_tool]

        with patch("agent.mcp.client.stdio_client", return_value=mock_stdio_cm):
            with patch("agent.mcp.client.ClientSession", return_value=mock_session):
                client = MCPClient(config)
                await client.connect()

                assert client._connected is True
                assert client.session is not None
                assert len(client._tools_cache) == 1
                assert client._tools_cache[0]["name"] == "search"

    @pytest.mark.asyncio
    async def test_connect_with_timeout(self):
        """Test connection with custom timeout."""
        config = {"command": "python"}

        mock_read = MagicMock()
        mock_write = MagicMock()
        mock_stdio_cm = AsyncMock()
        mock_stdio_cm.__aenter__.return_value = (mock_read, mock_write)

        with patch("agent.mcp.client.stdio_client", return_value=mock_stdio_cm):
            with patch("agent.mcp.client.ClientSession") as mock_session_class:
                mock_session = AsyncMock()
                mock_session.initialize = AsyncMock()
                mock_session_class.return_value = mock_session

                client = MCPClient(config)
                await client.connect(timeout=30)

                # Verify initialize was called
                mock_session.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_timeout_raises(self):
        """Test that timeout raises asyncio.TimeoutError."""
        config = {"command": "python"}

        mock_read = MagicMock()
        mock_write = MagicMock()
        mock_stdio_cm = AsyncMock()
        mock_stdio_cm.__aenter__.return_value = (mock_read, mock_write)

        with patch("agent.mcp.client.stdio_client", return_value=mock_stdio_cm):
            with patch("agent.mcp.client.ClientSession") as mock_session_class:
                mock_session = AsyncMock()
                mock_session.initialize = AsyncMock(
                    side_effect=asyncio.TimeoutError()
                )
                mock_session_class.return_value = mock_session

                client = MCPClient(config)

                with pytest.raises(asyncio.TimeoutError):
                    await client.connect(timeout=1)


class TestMCPClientDisconnect:
    """Tests for MCPClient disconnect method."""

    @pytest.mark.asyncio
    async def test_disconnect_success(self):
        """Test successful disconnection."""
        config = {"command": "python"}
        client = MCPClient(config)

        # Simulate connected state
        mock_session = AsyncMock()
        mock_session.close = AsyncMock()
        client.session = mock_session
        client._connected = True

        mock_stdio = AsyncMock()
        mock_stdio.__aexit__ = AsyncMock()
        client._stdio_context = mock_stdio

        await client.disconnect()

        assert client.session is None
        assert client._connected is False
        mock_session.close.assert_called_once()
        mock_stdio.__aexit__.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect_no_session(self):
        """Test disconnect when no session exists."""
        config = {"command": "python"}
        client = MCPClient(config)

        # Should not raise
        await client.disconnect()

        assert client.session is None
        assert client._connected is False


class TestMCPClientTools:
    """Tests for MCPClient tool methods."""

    def test_get_available_tools(self):
        """Test getting available tools."""
        config = {"command": "python"}
        client = MCPClient(config)

        # Set up mock tools
        client._tools_cache = [
            {"name": "search", "description": "Search tool", "schema": {}},
            {"name": "list", "description": "List tool", "schema": {}},
        ]

        tools = client.get_available_tools()

        assert len(tools) == 2
        assert tools[0]["name"] == "search"
        assert tools[1]["name"] == "list"

    def test_get_tool_schema_found(self):
        """Test getting tool schema when found."""
        config = {"command": "python"}
        client = MCPClient(config)

        client._tools_cache = [
            {"name": "search", "description": "Search", "schema": {"type": "object"}},
        ]

        schema = client.get_tool_schema("search")

        assert schema is not None
        assert schema["name"] == "search"
        assert schema["schema"] == {"type": "object"}

    def test_get_tool_schema_not_found(self):
        """Test getting tool schema when not found."""
        config = {"command": "python"}
        client = MCPClient(config)

        client._tools_cache = []

        schema = client.get_tool_schema("nonexistent")

        assert schema is None

    @pytest.mark.asyncio
    async def test_call_tool_success(self):
        """Test successful tool call."""
        config = {"command": "python"}
        client = MCPClient(config)

        # Set up mock session
        mock_session = AsyncMock()
        mock_result = {"result": "success"}
        mock_session.call_tool = AsyncMock(return_value=mock_result)
        client.session = mock_session
        client._connected = True
        client._tools_cache = [
            {"name": "search", "description": "Search", "schema": {}}
        ]

        result = await client.call_tool("search", {"query": "test"})

        assert result == mock_result
        mock_session.call_tool.assert_called_once_with("search", {"query": "test"})

    @pytest.mark.asyncio
    async def test_call_tool_not_connected(self):
        """Test tool call when not connected."""
        config = {"command": "python"}
        client = MCPClient(config)

        client.session = None

        with pytest.raises(RuntimeError, match="Not connected"):
            await client.call_tool("search", {})

    @pytest.mark.asyncio
    async def test_call_tool_unknown_tool(self):
        """Test tool call with unknown tool."""
        config = {"command": "python"}
        client = MCPClient(config)

        mock_session = AsyncMock()
        client.session = mock_session
        client._connected = True
        client._tools_cache = []

        with pytest.raises(ValueError, match="Unknown tool"):
            await client.call_tool("nonexistent", {})

    @pytest.mark.asyncio
    async def test_call_tool_with_timeout(self):
        """Test tool call with custom timeout."""
        config = {"command": "python", "timeout": 30}
        client = MCPClient(config)

        mock_session = AsyncMock()
        mock_result = {"result": "success"}
        mock_session.call_tool = AsyncMock(return_value=mock_result)
        client.session = mock_session
        client._connected = True
        client._tools_cache = [
            {"name": "search", "description": "Search", "schema": {}}
        ]

        with patch("asyncio.wait_for", return_value=mock_result) as mock_wait:
            result = await client.call_tool("search", {"query": "test"}, timeout=60)

            assert result == mock_result
            mock_wait.assert_called_once()


class TestMCPClientContextManager:
    """Tests for MCPClient context manager."""

    @pytest.mark.asyncio
    async def test_connection_context_manager(self):
        """Test connection context manager."""
        config = {"command": "python"}
        client = MCPClient(config)

        with patch.object(client, "connect", new_callable=AsyncMock) as mock_connect:
            with patch.object(client, "disconnect", new_callable=AsyncMock) as mock_disconnect:
                async with client.connection() as c:
                    assert c is client
                    mock_connect.assert_called_once()

                mock_disconnect.assert_called_once()


class TestToolRegistry:
    """Tests for ToolRegistry."""

    def setup_method(self):
        """Reset registry before each test."""
        ToolRegistry.reset()

    def test_singleton_instance(self):
        """Test singleton pattern."""
        registry1 = ToolRegistry()
        registry2 = ToolRegistry()

        assert registry1 is registry2

    def test_register_mcp_client(self):
        """Test registering MCP client."""
        registry = ToolRegistry()
        mock_client = MagicMock(spec=MCPClient)
        mock_client.get_available_tools.return_value = [
            {"name": "search", "description": "Search tool", "schema": {}}
        ]

        registry.register_mcp_client("rag_server", mock_client)

        assert registry.get_client("rag_server") is mock_client
        assert registry.is_tool_available("search")
        assert registry.get_server_for_tool("search") == "rag_server"

    def test_unregister_client(self):
        """Test unregistering MCP client."""
        registry = ToolRegistry()
        mock_client = MagicMock(spec=MCPClient)
        mock_client.get_available_tools.return_value = [
            {"name": "search", "description": "Search tool", "schema": {}}
        ]

        registry.register_mcp_client("rag_server", mock_client)
        registry.unregister_client("rag_server")

        assert registry.get_client("rag_server") is None
        assert not registry.is_tool_available("search")

    def test_get_tool_schema(self):
        """Test getting tool schema."""
        registry = ToolRegistry()
        mock_client = MagicMock(spec=MCPClient)
        mock_client.get_available_tools.return_value = [
            {"name": "search", "description": "Search", "schema": {"type": "object"}}
        ]

        registry.register_mcp_client("rag_server", mock_client)

        schema = registry.get_tool_schema("search")

        assert schema is not None
        assert schema["name"] == "search"
        assert schema["description"] == "Search"

    def test_get_all_tools_description(self):
        """Test getting tools description for prompts."""
        registry = ToolRegistry()
        mock_client = MagicMock(spec=MCPClient)
        mock_client.get_available_tools.return_value = [
            {"name": "search", "description": "Search tool", "schema": {}},
            {"name": "list", "description": "List tool", "schema": {}},
        ]

        registry.register_mcp_client("rag_server", mock_client)

        desc = registry.get_all_tools_description()

        assert "- search: Search tool" in desc
        assert "- list: List tool" in desc

    def test_list_tools(self):
        """Test listing tool names."""
        registry = ToolRegistry()
        mock_client = MagicMock(spec=MCPClient)
        mock_client.get_available_tools.return_value = [
            {"name": "search", "description": "", "schema": {}},
            {"name": "list", "description": "", "schema": {}},
        ]

        registry.register_mcp_client("rag_server", mock_client)

        tools = registry.list_tools()

        assert "search" in tools
        assert "list" in tools
        assert len(tools) == 2

    def test_get_all_tools(self):
        """Test getting all tools."""
        registry = ToolRegistry()
        mock_client = MagicMock(spec=MCPClient)
        mock_client.get_available_tools.return_value = [
            {"name": "search", "description": "Search", "schema": {}}
        ]

        registry.register_mcp_client("rag_server", mock_client)

        tools = registry.get_all_tools()

        assert len(tools) == 1
        assert tools[0]["name"] == "search"

    def test_no_tools_available(self):
        """Test with no tools registered."""
        registry = ToolRegistry()

        assert registry.list_tools() == []
        assert registry.get_all_tools() == []
        assert not registry.is_tool_available("search")
        assert registry.get_all_tools_description() == "No tools available."