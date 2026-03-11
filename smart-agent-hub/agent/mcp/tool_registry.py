"""Tool Registry for managing MCP tools."""

from __future__ import annotations

from typing import Any, Optional

from agent.mcp.client import MCPClient


class ToolRegistry:
    """Tool Registry - Manages all available tools from MCP servers.

    This is a singleton class that registers MCP clients and provides
    a unified interface for tool discovery and execution.
    """

    _instance: Optional["ToolRegistry"] = None

    def __new__(cls) -> "ToolRegistry":
        """Create or return singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._clients: dict[str, MCPClient] = {}
            cls._instance._tools_index: dict[str, tuple[str, dict]] = {}
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset singleton instance (for testing)."""
        cls._instance = None

    def register_mcp_client(self, server_name: str, client: MCPClient) -> None:
        """Register an MCP Client.

        Args:
            server_name: Unique name for the server.
            client: MCPClient instance.
        """
        self._clients[server_name] = client

        # Index tools by name with server mapping
        for tool in client.get_available_tools():
            self._tools_index[tool["name"]] = (server_name, tool)

    def unregister_client(self, server_name: str) -> None:
        """Unregister an MCP Client.

        Args:
            server_name: Name of the server to unregister.
        """
        if server_name in self._clients:
            # Remove tools from this server
            tools_to_remove = [
                name for name, (srv, _) in self._tools_index.items()
                if srv == server_name
            ]
            for tool_name in tools_to_remove:
                del self._tools_index[tool_name]

            del self._clients[server_name]

    def get_tool_schema(self, tool_name: str) -> Optional[dict]:
        """Get schema for a specific tool.

        Args:
            tool_name: Name of the tool.

        Returns:
            Tool schema with name, description, and schema, or None if not found.
        """
        if tool_name in self._tools_index:
            _, tool = self._tools_index[tool_name]
            return tool
        return None

    def get_all_tools_description(self) -> str:
        """Get descriptions of all available tools (for prompts).

        Returns:
            Formatted string with tool names and descriptions.
        """
        if not self._tools_index:
            return "No tools available."

        descriptions = []
        for name, (_, tool) in sorted(self._tools_index.items()):
            desc = f"- {name}: {tool.get('description', 'No description')}"
            descriptions.append(desc)
        return "\n".join(descriptions)

    def get_all_tools(self) -> list[dict]:
        """Get all available tools.

        Returns:
            List of tool definitions with name, description, and schema.
        """
        return [
            {"name": name, **tool}
            for name, (_, tool) in self._tools_index.items()
        ]

    def list_tools(self) -> list[str]:
        """List all available tool names.

        Returns:
            List of tool names.
        """
        return list(self._tools_index.keys())

    def get_server_for_tool(self, tool_name: str) -> Optional[str]:
        """Get the server name for a specific tool.

        Args:
            tool_name: Name of the tool.

        Returns:
            Server name or None if tool not found.
        """
        if tool_name in self._tools_index:
            return self._tools_index[tool_name][0]
        return None

    async def execute_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        timeout: Optional[int] = None,
    ) -> Any:
        """Execute a tool call.

        Args:
            tool_name: Name of the tool to execute.
            arguments: Tool arguments.
            timeout: Execution timeout in seconds.

        Returns:
            Tool execution result.

        Raises:
            ValueError: If tool not found.
        """
        if tool_name not in self._tools_index:
            available = list(self._tools_index.keys())
            raise ValueError(
                f"Unknown tool: {tool_name}. Available tools: {available}"
            )

        server_name, tool = self._tools_index[tool_name]
        client = self._clients[server_name]

        if not client.is_connected:
            raise RuntimeError(
                f"Server '{server_name}' is not connected"
            )

        return await client.call_tool(tool_name, arguments, timeout)

    def get_client(self, server_name: str) -> Optional[MCPClient]:
        """Get MCP client by server name.

        Args:
            server_name: Name of the server.

        Returns:
            MCPClient instance or None if not found.
        """
        return self._clients.get(server_name)

    def get_clients(self) -> dict[str, MCPClient]:
        """Get all registered MCP clients.

        Returns:
            Dictionary mapping server names to clients.
        """
        return self._clients.copy()

    def is_tool_available(self, tool_name: str) -> bool:
        """Check if a tool is available.

        Args:
            tool_name: Name of the tool.

        Returns:
            True if tool is available, False otherwise.
        """
        return tool_name in self._tools_index