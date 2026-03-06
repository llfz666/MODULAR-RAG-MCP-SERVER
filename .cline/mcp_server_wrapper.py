#!/usr/bin/env python3
"""MCP Server wrapper for Cline - ensures clean startup without stdout pollution.

CRITICAL: DO NOT redirect stdout to stderr!
MCP stdio protocol requires:
- stdin: read JSON-RPC requests from client
- stdout: send JSON-RPC responses to client  <-- MUST remain intact!
- stderr: log messages only
"""

import sys
import os

# Set environment variables BEFORE any imports
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUNBUFFERED'] = '1'
os.environ['PYTHONWARNINGS'] = 'ignore'
os.environ['TOKENIZERS_PARALLELISM'] = 'false'

if __name__ == "__main__":
    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Project root is the parent directory of .cline
    project_dir = os.path.dirname(script_dir)
    
    # Change to project directory
    os.chdir(project_dir)
    
    # Add project directory to Python path
    sys.path.insert(0, project_dir)
    
    # Import and run server (server.py handles its own stdout/stderr management)
    from src.mcp_server.server import main
    sys.exit(main())
