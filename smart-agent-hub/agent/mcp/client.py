"""MCP Client for connecting to MCP Servers.

This client uses stdio transport to communicate with MCP servers.
It can discover available tools and invoke them remotely.

The key insight is that stdio_client() returns an async context manager
that manages background tasks for reading from stdin and writing to stdout.
These background tasks must continue running while we communicate with the server.
"""

from __future__ import annotations

import asyncio
import sys
from contextlib import asynccontextmanager
from typing import Any, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MCPClient:
    """MCP Client - Connects to external MCP Server."""

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
        self._tools_cache: list[dict] = []
        self._connected = False
        self._stdio_cm = None  # Store context manager
        self._read_stream = None
        self._write_stream = None
        self._cleanup_task: Optional[asyncio.Task] = None

    @property
    def is_connected(self) -> bool:
        """Check if client is connected to server."""
        return self._connected and self.session is not None

    async def connect(self, timeout: Optional[int] = None) -> None:
        """Connect to MCP Server.

        This method:
        1. Starts the MCP server subprocess via stdio_client
        2. Creates a ClientSession
        3. Initializes the session (sends initialize request)
        4. Fetches available tools
        """
        from pathlib import Path
        
        timeout = timeout or self.server_config.get("timeout", 120)

        # Resolve cwd to absolute path and validate
        cwd = self.server_config.get("cwd", ".")
        cwd_path = Path(cwd)
        if not cwd_path.is_absolute():
            cwd_path = Path.cwd() / cwd
            cwd_path = cwd_path.resolve()
        
        if not cwd_path.exists():
            raise RuntimeError(f"MCP Server cwd does not exist: {cwd_path}")
        
        if not cwd_path.is_dir():
            raise RuntimeError(f"MCP Server cwd is not a directory: {cwd_path}")
        
        print(f"[DEBUG] Starting MCP Server: {self.server_config['command']} {' '.join(self.server_config.get('args', []))}", file=sys.stderr)
        print(f"[DEBUG] Working directory: {cwd_path}", file=sys.stderr)
        
        server_params = StdioServerParameters(
            command=self.server_config["command"],
            args=self.server_config.get("args", []),
            cwd=str(cwd_path),
        )

        # The stdio_client context manager starts background tasks for:
        # - Reading from subprocess stdout (read_stream)
        # - Writing to subprocess stdin (write_stream)
        # We need to enter the context and keep it open
        self._stdio_cm = stdio_client(server_params)
        
        print(f"[DEBUG] Entering stdio context...", file=sys.stderr)
        
        # Enter the context manager - this starts the subprocess and background tasks
        self._read_stream, self._write_stream = await self._stdio_cm.__aenter__()
        
        print(f"[DEBUG] stdio context entered. read={type(self._read_stream)}, write={type(self._write_stream)}", file=sys.stderr)

        # Create the session - this does NOT start any I/O yet
        self.session = ClientSession(self._read_stream, self._write_stream)
        
        print(f"[DEBUG] Created ClientSession, initializing...", file=sys.stderr)
        
        # Initialize session - this sends the initialize request and waits for response
        # The read_stream background task receives the response
        await asyncio.wait_for(self.session.initialize(), timeout=timeout)
        
        print(f"[DEBUG] Session initialized successfully", file=sys.stderr)

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
        print(f"[DEBUG] Connected to MCP Server successfully", file=sys.stderr)
        print(f"[DEBUG] Available tools: {[t['name'] for t in self._tools_cache]}", file=sys.stderr)

    async def disconnect(self) -> None:
        """Disconnect from MCP Server.
        
        This properly closes the session and the stdio context.
        """
        print(f"[DEBUG] Disconnecting from MCP Server...", file=sys.stderr)
        
        if self.session:
            try:
                await self.session.close()
            except Exception as e:
                print(f"[DEBUG] Error closing session: {e}", file=sys.stderr)
            self.session = None
        
        if self._stdio_cm:
            try:
                await self._stdio_cm.__aexit__(None, None, None)
            except Exception as e:
                print(f"[DEBUG] Error closing stdio context: {e}", file=sys.stderr)
        
        self._connected = False
        self._tools_cache = []
        print(f"[DEBUG] Disconnected", file=sys.stderr)

    def get_available_tools(self) -> list[dict]:
        """Get list of available tools from the server."""
        return self._tools_cache.copy()

    def get_tool_schema(self, tool_name: str) -> Optional[dict]:
        """Get schema for a specific tool."""
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