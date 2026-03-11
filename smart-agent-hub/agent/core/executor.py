"""Executor for Smart Agent Hub - Tool execution with safety gate."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Optional

from agent.mcp.tool_registry import ToolRegistry


@dataclass
class Action:
    """Action to execute."""
    tool_name: str
    tool_input: dict[str, Any]


@dataclass
class Observation:
    """Observation from tool execution."""
    success: bool
    result: Any = None
    error: Optional[str] = None
    latency_ms: float = 0.0


class SafetyGate:
    """Safety Gate for dangerous operations.
    
    Currently a no-op implementation. Can be extended to require
    user approval for destructive operations.
    """
    
    # List of potentially dangerous tools that might require approval
    DESTRUCTIVE_TOOLS = {"delete_file", "execute_code", "write_file", "shell"}
    
    def __init__(self, require_approval: bool = False):
        """Initialize Safety Gate.
        
        Args:
            require_approval: Whether to require user approval for dangerous tools.
        """
        self.require_approval = require_approval
    
    def requires_approval(self, tool_name: str) -> bool:
        """Check if tool requires user approval.
        
        Args:
            tool_name: Name of the tool.
            
        Returns:
            True if approval is required.
        """
        if not self.require_approval:
            return False
        return tool_name in self.DESTRUCTIVE_TOOLS
    
    async def wait_for_approval(self, action: Action) -> bool:
        """Wait for user approval.
        
        Args:
            action: Action to approve.
            
        Returns:
            True if approved, False otherwise.
        """
        print(f"\n⚠️ 危险操作确认：{action.tool_name}")
        print(f"参数：{action.tool_input}")
        response = input("是否继续？(y/n): ")
        return response.lower() == "y"


class Executor:
    """Executor - Tool execution dispatcher.
    
    This executor handles:
    1. Safety checks before execution
    2. Tool invocation via registry
    3. Error handling and timing
    """
    
    def __init__(
        self,
        tool_registry: ToolRegistry,
        safety_gate: Optional[SafetyGate] = None,
    ):
        """Initialize Executor.
        
        Args:
            tool_registry: Tool registry for execution.
            safety_gate: Optional safety gate for dangerous operations.
        """
        self.tool_registry = tool_registry
        self.safety_gate = safety_gate or SafetyGate(require_approval=False)
    
    async def execute(self, action: Action) -> Observation:
        """Execute a tool action.
        
        Args:
            action: Action to execute.
            
        Returns:
            Observation with execution result.
        """
        start_time = time.time()
        
        # Safety check
        if self.safety_gate.requires_approval(action.tool_name):
            approved = await self.safety_gate.wait_for_approval(action)
            if not approved:
                return Observation(
                    success=False,
                    error="User denied the action",
                    latency_ms=(time.time() - start_time) * 1000,
                )
        
        # Execute tool
        try:
            result = await self.tool_registry.execute_tool(
                action.tool_name,
                action.tool_input,
            )
            return Observation(
                success=True,
                result=result,
                latency_ms=(time.time() - start_time) * 1000,
            )
        except Exception as e:
            return Observation(
                success=False,
                error=str(e),
                latency_ms=(time.time() - start_time) * 1000,
            )