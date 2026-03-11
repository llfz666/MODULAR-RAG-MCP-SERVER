"""Core data models for Smart Agent Hub."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """Task status enumeration."""

    CREATED = "created"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Action(BaseModel):
    """Tool invocation action."""

    tool_name: str = Field(..., description="Tool name")
    tool_input: dict[str, Any] = Field(..., description="Tool input parameters")


class Observation(BaseModel):
    """Tool execution result."""

    success: bool = Field(..., description="Whether execution succeeded")
    result: Any = Field(None, description="Tool result")
    error: Optional[str] = Field(None, description="Error message if failed")
    latency_ms: float = Field(..., description="Execution time in milliseconds")


class Thought(BaseModel):
    """Thinking process."""

    content: str = Field(..., description="Thought content")
    action: Optional[Action] = Field(None, description="Decided action")
    is_final: bool = Field(False, description="Whether this is the final answer")
    final_answer: Optional[str] = Field(None, description="Final answer if is_final=True")


class TaskStep(BaseModel):
    """Task execution step."""

    step_id: str = Field(..., description="Step ID")
    thought: Thought = Field(..., description="Thought")
    observation: Optional[Observation] = Field(None, description="Observation result")
    created_at: datetime = Field(default_factory=datetime.now)


class Task(BaseModel):
    """Task definition."""

    task_id: str = Field(..., description="Task ID")
    session_id: str = Field(..., description="Session ID")
    user_query: str = Field(..., description="User query")
    status: TaskStatus = Field(TaskStatus.CREATED, description="Task status")
    steps: list[TaskStep] = Field(default_factory=list, description="List of steps")
    final_result: Optional[str] = Field(None, description="Final result")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class AgentState(BaseModel):
    """Agent state."""

    session_id: str
    current_task: Optional[Task] = None
    conversation_history: list[dict] = Field(default_factory=list)
    short_term_memory: list[str] = Field(default_factory=list)