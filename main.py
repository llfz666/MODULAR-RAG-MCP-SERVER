"""
Modular RAG MCP Server - Main Entry Point

This is the entry point for the MCP Server. It initializes the configuration,
sets up logging, and starts the server.
"""

import sys
from pathlib import Path

from src.core.settings import SettingsError, load_settings
from src.mcp_server.server import run_stdio_server


def main() -> int:
    """
    Main entry point for the MCP Server.
    
    Returns:
        int: Exit code (0 for success, non-zero for failure)
    """
    # CRITICAL: Do NOT print to stdout - MCP protocol reserves stdout for JSON-RPC messages
    # All logging must go to stderr

    settings_path = Path("config/settings.yaml")
    try:
        settings = load_settings(settings_path)
    except SettingsError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1

    # Run the MCP stdio server
    return run_stdio_server()


if __name__ == "__main__":
    sys.exit(main())
