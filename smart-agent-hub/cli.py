"""CLI entry point for Smart Agent Hub."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import click

# Add agent package to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


@click.command()
@click.argument("query", required=False, default=None)
@click.option(
    "--session-id",
    "-s",
    default=None,
    help="Session ID to continue previous conversation",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="Enable verbose output",
)
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True),
    default=None,
    help="Path to configuration file",
)
@click.option(
    "--stream",
    is_flag=True,
    default=False,
    help="Enable streaming output",
)
def main(query: str | None, session_id: str | None, verbose: bool, config: str | None, stream: bool) -> None:
    """Smart Agent Hub - MCP Client Agent for RAG-MCP-SERVER.

    QUERY: The user query to process.

    Examples:

        python cli.py "帮我查找关于 RAG 的资料"

        python cli.py --session-id abc123 "继续上一个问题"

        python cli.py --stream "帮我对比两个文档"
    """
    # If no query provided, show help
    if query is None:
        click.echo(click.get_current_context().get_help())
        return

    # Run the agent
    asyncio.run(run_agent(query, session_id, verbose, config, stream))


async def run_agent(
    query: str,
    session_id: str | None,
    verbose: bool,
    config: str | None,
    stream: bool,
) -> None:
    """Run the agent with the given query."""
    from agent.core.agent import Agent
    from agent.core.settings import load_settings

    # Load settings
    settings = load_settings(config)

    # Build MCP server configs from settings
    mcp_server_configs = {}
    if hasattr(settings, 'mcp_servers'):
        for name, server_config in settings.mcp_servers.items():
            if server_config.get('enabled', True):
                mcp_server_configs[name] = {
                    "command": server_config["command"],
                    "args": server_config.get("args", []),
                    "cwd": server_config.get("cwd", "."),
                    "timeout": server_config.get("timeout", 60),
                }

    # Create agent
    agent = Agent(
        llm_provider=settings.llm.provider,
        llm_settings={
            "api_key": settings.llm.api_key,
            "model": settings.llm.model,
            "base_url": settings.llm.base_url,
            "temperature": settings.llm.temperature,
            "max_tokens": settings.llm.max_tokens,
        },
        mcp_server_configs=mcp_server_configs,
        state_db_path=settings.storage.db_path,
        log_path=settings.storage.log_path,
        max_iterations=settings.agent.max_iterations,
        enable_reflection=settings.agent.enable_reflection,
    )

    click.echo(f"🤔 思考中：{query}")
    click.echo(f"📋 Session ID: {session_id or 'new'}")
    click.echo(f"⚙️  LLM Provider: {settings.llm.provider}/{settings.llm.model}")
    click.echo(f"🔧 MCP Servers: {list(mcp_server_configs.keys()) if mcp_server_configs else 'none'}")
    click.echo("")

    try:
        if stream:
            # Streaming mode
            click.echo("📡 流式输出模式")
            click.echo("-" * 50)
            
            async for event in agent.run_streaming(query, session_id):
                event_type = event.get("type", "unknown")
                
                if event_type == "thought":
                    click.echo(f"🧠 思考：{event.get('content', '')}")
                elif event_type == "action":
                    click.echo(f"🔧 调用工具：{event.get('tool', '')}")
                    if verbose:
                        click.echo(f"   参数：{event.get('input', {})}")
                elif event_type == "observation":
                    result = event.get("result", "")
                    if verbose:
                        click.echo(f"📦 结果：{result}")
                    else:
                        # Truncate long results
                        result_str = str(result)[:200] + "..." if len(str(result)) > 200 else str(result)
                        click.echo(f"📦 结果：{result_str}")
                elif event_type == "error":
                    click.echo(f"❌ 错误：{event.get('error', event.get('content', ''))}")
                elif event_type == "final_answer":
                    click.echo("")
                    click.echo("=" * 50)
                    click.echo(f"✅ 答案：{event.get('content', '')}")
                    click.echo("=" * 50)
        else:
            # Non-streaming mode
            click.echo("⏳ 处理中...")
            click.echo("")
            
            result = await agent.run(query, session_id)
            
            if result.success:
                click.echo("=" * 50)
                click.echo(f"✅ 答案：{result.final_answer}")
                click.echo("=" * 50)
            else:
                click.echo("=" * 50)
                click.echo(f"❌ 失败：{result.error_message}")
                click.echo("=" * 50)
            
            if verbose:
                click.echo("")
                click.echo(f"📊 执行步骤：{len(result.steps)}")
                click.echo(f"📈 总 Token 数：{result.total_tokens}")
                
                if result.steps:
                    click.echo("")
                    click.echo("执行过程:")
                    for i, step in enumerate(result.steps):
                        click.echo(f"\n  步骤 {i + 1}:")
                        click.echo(f"    思考：{step.thought}")
                        if step.action:
                            click.echo(f"    动作：{step.action}")
                            click.echo(f"    输入：{step.action_input}")
                        if step.observation:
                            click.echo(f"    结果：{step.observation[:100]}..." if len(str(step.observation)) > 100 else f"    结果：{step.observation}")
                        if step.error:
                            click.echo(f"    错误：{step.error}")
                        if step.is_final:
                            click.echo(f"    【最终答案】{step.final_answer}")

    except Exception as e:
        click.echo(f"❌ 发生错误：{e}", err=True)
        if verbose:
            import traceback
            click.echo(traceback.format_exc())
        sys.exit(1)
    finally:
        await agent.disconnect()


if __name__ == "__main__":
    main()