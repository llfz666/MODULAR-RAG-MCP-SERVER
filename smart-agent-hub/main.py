"""Main entry point for Smart Agent Hub."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Add agent package to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


async def main():
    """Main entry point."""
    from agent.core.settings import get_settings

    settings = get_settings()

    print("Smart Agent Hub")
    print("=" * 50)
    print(f"LLM Provider: {settings.llm.provider}/{settings.llm.model}")
    print(f"Max Iterations: {settings.agent.max_iterations}")
    print(f"Reflection: {settings.agent.enable_reflection}")
    print(f"Memory: {settings.agent.enable_memory}")
    print("=" * 50)

    # TODO: Implement main agent loop
    print("\nAgent pipeline is under construction.")
    print("Use 'python cli.py <query>' to interact with the agent.")


if __name__ == "__main__":
    asyncio.run(main())