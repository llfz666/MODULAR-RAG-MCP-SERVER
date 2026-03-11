"""MCP Client for connecting to MCP Servers."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MCPClient:
    """MCP Client - Connects to external MCP Server.

    This client uses stdio transport to communicate with MCP servers.
    It can discover available tools and invoke them remotely.
    """

    def __init__(self, server_config: dict):
        """Initialize MCP Client.

        Args:
            server_config: Server configuration with keys:
                - command: Command to run (e.g., "python")
                - args: Command arguments (e.g., ["main.py"])
                - cwd: Working directory (default: ".")
                - timeout: Connection timeout in seconds (default: 60)
        """
        self.server_config = server_config
        self.session: Optional[ClientSession] = None
        self._stdio_context = None
        self._tools_cache: list[dict] = []
        self._connected = False

    @property
    def is_connected(self) -> bool:
        """Check if client is connected to server."""
        return self._connected and self.session is not None

    async def connect(self, timeout: Optional[int] = None) -> None:
        """Connect to MCP Server.

        Args:
            timeout: Connection timeout in seconds. Uses config value if not provided.
        """
        timeout = timeout or self.server_config.get("timeout", 60)

        server_params = StdioServerParameters(
            command=self.server_config["command"],
            args=self.server_config.get("args", []),
            cwd=self.server_config.get("cwd", "."),
        )

        self._stdio_context = stdio_client(server_params)
        read, write = await asyncio.wait_for(
            self._stdio_context.__aenter__(),
            timeout=timeout,
        )

        self.session = ClientSession(read, write)
        await asyncio.wait_for(self.session.initialize(), timeout=timeout)

        # Get available tools
        tools_response = await self.session.list_tools()
        self._tools_cache = [
            {
                "name": t.name,
                "description": t.description,
                "schema": t.inputSchema,
            }
            for t in tools_response.tools
        ]

        self._connected = True

    async def disconnect(self) -> None:
        """Disconnect from MCP Server."""
        if self.session:
            await self.session.close()
            self.session = None
        if self._stdio_context:
            await self._stdio_context.__aexit__(None, None, None)
        self._connected = False

    def get_available_tools(self) -> list[dict]:
        """Get list of available tools from the server.

        Returns:
            List of tool definitions with name, description, and schema.
        """
        return self._tools_cache.copy()

    def get_tool_schema(self, tool_name: str) -> Optional[dict]:
        """Get schema for a specific tool.

        Args:
            tool_name: Name of the tool.

        Returns:
            Tool schema or None if tool not found.
        """
        for tool in self._tools_cache:
            if tool["name"] == tool_name:
                return tool
        return None

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        timeout: Optional[int] = None,
    ) -> Any:
        """Call a tool on the server.

        Args:
            name: Tool name.
            arguments: Tool arguments as a dictionary.
            timeout: Call timeout in seconds. Uses config value if not provided.

        Returns:
            Tool result.

        Raises:
            RuntimeError: If not connected to server.
            ValueError: If tool not found.
            asyncio.TimeoutError: If call times out.
        """
        if not self.session:
            raise RuntimeError("Not connected to MCP Server")

        # Check if tool exists
        tool = self.get_tool_schema(name)
        if tool is None:
            available = [t["name"] for t in self._tools_cache]
            raise ValueError(
                f"Unknown tool: {name}. Available tools: {available}"
            )

        timeout = timeout or self.server_config.get("timeout", 60)
        result = await asyncio.wait_for(
            self.session.call_tool(name, arguments),
            timeout=timeout,
        )

        return result

    @asynccontextmanager
    async def connection(self):
        """Context manager for connection lifecycle.

        Usage:
            async with client.connection():
                result = await client.call_tool("search", {"query": "test"})
        """
        await self.connect()
        try:
            yield self
        finally:
            await self.disconnect()