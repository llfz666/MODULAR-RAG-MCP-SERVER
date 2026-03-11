"""JSONL Logger for Smart Agent Hub - Trajectory recording."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


class JSONLLogger:
    """JSONL Logger for recording agent trajectories.
    
    This logger writes events to a JSONL file for later analysis
    and dashboard visualization.
    """
    
    def __init__(self, log_path: str = "data/logs/agent_traces.jsonl"):
        """Initialize JSONL Logger.
        
        Args:
            log_path: Path to the JSONL log file.
        """
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
    
    def log(self, event: dict[str, Any]) -> None:
        """Log an event.
        
        Args:
            event: Event dictionary to log.
        """
        event["timestamp"] = datetime.now().isoformat()
        
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    
    def log_thought(
        self,
        session_id: str,
        task_id: str,
        content: str,
        step_index: int = 0,
    ) -> None:
        """Log a thought event.
        
        Args:
            session_id: Session ID.
            task_id: Task ID.
            content: Thought content.
            step_index: Step index in the task.
        """
        self.log({
            "type": "thought",
            "session_id": session_id,
            "task_id": task_id,
            "step_index": step_index,
            "content": content,
        })
    
    def log_action(
        self,
        session_id: str,
        task_id: str,
        tool: str,
        tool_input: dict[str, Any],
        step_index: int = 0,
    ) -> None:
        """Log an action event.
        
        Args:
            session_id: Session ID.
            task_id: Task ID.
            tool: Tool name.
            tool_input: Tool input arguments.
            step_index: Step index in the task.
        """
        self.log({
            "type": "action",
            "session_id": session_id,
            "task_id": task_id,
            "step_index": step_index,
            "tool": tool,
            "input": tool_input,
        })
    
    def log_observation(
        self,
        session_id: str,
        task_id: str,
        result: Any,
        latency_ms: float,
        step_index: int = 0,
        error: Optional[str] = None,
    ) -> None:
        """Log an observation event.
        
        Args:
            session_id: Session ID.
            task_id: Task ID.
            result: Tool execution result.
            latency_ms: Execution latency in milliseconds.
            step_index: Step index in the task.
            error: Optional error message.
        """
        self.log({
            "type": "observation",
            "session_id": session_id,
            "task_id": task_id,
            "step_index": step_index,
            "result": result,
            "latency_ms": latency_ms,
            "error": error,
        })
    
    def log_final_answer(
        self,
        session_id: str,
        task_id: str,
        content: str,
        success: bool = True,
    ) -> None:
        """Log a final answer event.
        
        Args:
            session_id: Session ID.
            task_id: Task ID.
            content: Final answer content.
            success: Whether the task was successful.
        """
        self.log({
            "type": "final_answer",
            "session_id": session_id,
            "task_id": task_id,
            "content": content,
            "success": success,
        })
    
    def log_error(
        self,
        session_id: str,
        task_id: str,
        error: str,
        error_type: str = "unknown",
    ) -> None:
        """Log an error event.
        
        Args:
            session_id: Session ID.
            task_id: Task ID.
            error: Error message.
            error_type: Type of error.
        """
        self.log({
            "type": "error",
            "session_id": session_id,
            "task_id": task_id,
            "error": error,
            "error_type": error_type,
        })
    
    def get_events(self, session_id: Optional[str] = None) -> list[dict[str, Any]]:
        """Load events from the log file.
        
        Args:
            session_id: Optional session ID to filter events.
            
        Returns:
            List of events.
        """
        if not self.log_path.exists():
            return []
        
        events = []
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                event = json.loads(line.strip())
                if session_id is None or event.get("session_id") == session_id:
                    events.append(event)
        
        return events
    
    def get_session_events(self, session_id: str) -> list[dict[str, Any]]:
        """Get all events for a specific session.
        
        Args:
            session_id: Session ID.
            
        Returns:
            List of events for the session.
        """
        return self.get_events(session_id)
    
    def get_task_events(
        self,
        session_id: str,
        task_id: str,
    ) -> list[dict[str, Any]]:
        """Get all events for a specific task.
        
        Args:
            session_id: Session ID.
            task_id: Task ID.
            
        Returns:
            List of events for the task.
        """
        events = self.get_events(session_id)
        return [e for e in events if e.get("task_id") == task_id]