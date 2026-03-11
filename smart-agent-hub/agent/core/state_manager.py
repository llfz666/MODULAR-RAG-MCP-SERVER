"""State Manager for Smart Agent Hub - SQLite persistence."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


class StateManager:
    """State Manager - SQLite persistence for agent sessions.
    
    This manager handles:
    1. Session storage and retrieval
    2. Step persistence
    3. Conversation history
    """
    
    def __init__(self, db_path: str = "data/db/agent_sessions.db"):
        """Initialize State Manager.
        
        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT
            )
        """)
        
        # Tasks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                session_id TEXT,
                user_query TEXT,
                status TEXT DEFAULT 'created',
                final_result TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            )
        """)
        
        # Steps table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                task_id TEXT,
                step_index INTEGER,
                thought TEXT,
                action TEXT,
                action_input TEXT,
                observation TEXT,
                error TEXT,
                latency_ms REAL,
                is_final INTEGER DEFAULT 0,
                final_answer TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id),
                FOREIGN KEY (task_id) REFERENCES tasks(task_id)
            )
        """)
        
        # Create indexes for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_steps_session 
            ON steps(session_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_steps_task 
            ON steps(task_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tasks_session 
            ON tasks(session_id)
        """)
        
        conn.commit()
        conn.close()
    
    def save_session(
        self,
        session_id: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """Save or update a session.
        
        Args:
            session_id: Unique session identifier.
            metadata: Session metadata dictionary.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO sessions (session_id, updated_at, metadata)
            VALUES (?, CURRENT_TIMESTAMP, ?)
        """, (session_id, json.dumps(metadata or {})))
        
        conn.commit()
        conn.close()
    
    def load_session(
        self,
        session_id: str,
    ) -> Optional[dict[str, Any]]:
        """Load a session by ID.
        
        Args:
            session_id: Session identifier.
            
        Returns:
            Session metadata or None if not found.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT metadata FROM sessions WHERE session_id = ?
        """, (session_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return json.loads(row[0])
        return None
    
    def save_task(
        self,
        task_id: str,
        session_id: str,
        user_query: str,
        status: str = "created",
    ) -> None:
        """Save a task.
        
        Args:
            task_id: Unique task identifier.
            session_id: Parent session ID.
            user_query: User's query string.
            status: Task status.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO tasks (task_id, session_id, user_query, status, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (task_id, session_id, user_query, status))
        
        conn.commit()
        conn.close()
    
    def update_task_status(
        self,
        task_id: str,
        status: str,
        final_result: Optional[str] = None,
    ) -> None:
        """Update task status.
        
        Args:
            task_id: Task identifier.
            status: New status value.
            final_result: Optional final result.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if final_result is not None:
            cursor.execute("""
                UPDATE tasks 
                SET status = ?, final_result = ?, updated_at = CURRENT_TIMESTAMP
                WHERE task_id = ?
            """, (status, final_result, task_id))
        else:
            cursor.execute("""
                UPDATE tasks 
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE task_id = ?
            """, (status, task_id))
        
        conn.commit()
        conn.close()
    
    def save_step(
        self,
        session_id: str,
        task_id: str,
        step_index: int,
        thought: Optional[str] = None,
        action: Optional[str] = None,
        action_input: Optional[dict[str, Any]] = None,
        observation: Optional[str] = None,
        error: Optional[str] = None,
        latency_ms: float = 0.0,
        is_final: bool = False,
        final_answer: Optional[str] = None,
    ) -> None:
        """Save a step.
        
        Args:
            session_id: Session ID.
            task_id: Task ID.
            step_index: Step index.
            thought: Thought content.
            action: Action/tool name.
            action_input: Action input arguments.
            observation: Observation result.
            error: Error message if any.
            latency_ms: Execution latency.
            is_final: Whether this is the final step.
            final_answer: Final answer content.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO steps (
                session_id, task_id, step_index, thought, action, action_input,
                observation, error, latency_ms, is_final, final_answer
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id,
            task_id,
            step_index,
            json.dumps(thought) if thought else None,
            action,
            json.dumps(action_input) if action_input else None,
            observation,
            error,
            latency_ms,
            1 if is_final else 0,
            final_answer,
        ))
        
        conn.commit()
        conn.close()
    
    def get_session_steps(
        self,
        session_id: str,
        task_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Get steps for a session.
        
        Args:
            session_id: Session ID.
            task_id: Optional task ID to filter.
            
        Returns:
            List of step dictionaries.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if task_id:
            cursor.execute("""
                SELECT step_index, thought, action, action_input, observation,
                       error, latency_ms, is_final, final_answer, created_at
                FROM steps
                WHERE session_id = ? AND task_id = ?
                ORDER BY step_index
            """, (session_id, task_id))
        else:
            cursor.execute("""
                SELECT step_index, thought, action, action_input, observation,
                       error, latency_ms, is_final, final_answer, created_at
                FROM steps
                WHERE session_id = ?
                ORDER BY step_index
            """, (session_id,))
        
        steps = []
        for row in cursor.fetchall():
            steps.append({
                "step_index": row[0],
                "thought": json.loads(row[1]) if row[1] else None,
                "action": row[2],
                "action_input": json.loads(row[3]) if row[3] else None,
                "observation": row[4],
                "error": row[5],
                "latency_ms": row[6],
                "is_final": bool(row[7]),
                "final_answer": row[8],
                "created_at": row[9],
            })
        
        conn.close()
        return steps
    
    def get_session_tasks(self, session_id: str) -> list[dict[str, Any]]:
        """Get tasks for a session.
        
        Args:
            session_id: Session ID.
            
        Returns:
            List of task dictionaries.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT task_id, user_query, status, final_result, created_at, updated_at
            FROM tasks
            WHERE session_id = ?
            ORDER BY created_at DESC
        """, (session_id,))
        
        tasks = []
        for row in cursor.fetchall():
            tasks.append({
                "task_id": row[0],
                "user_query": row[1],
                "status": row[2],
                "final_result": row[3],
                "created_at": row[4],
                "updated_at": row[5],
            })
        
        conn.close()
        return tasks
    
    def get_task(self, task_id: str) -> Optional[dict[str, Any]]:
        """Get a task by ID.
        
        Args:
            task_id: Task identifier.
            
        Returns:
            Task dictionary or None if not found.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT task_id, session_id, user_query, status, final_result, created_at, updated_at
            FROM tasks
            WHERE task_id = ?
        """, (task_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "task_id": row[0],
                "session_id": row[1],
                "user_query": row[2],
                "status": row[3],
                "final_result": row[4],
                "created_at": row[5],
                "updated_at": row[6],
            }
        return None
    
    def list_sessions(self, limit: int = 50) -> list[dict[str, Any]]:
        """List recent sessions.
        
        Args:
            limit: Maximum number of sessions to return.
            
        Returns:
            List of session summaries.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT session_id, created_at, updated_at, metadata
            FROM sessions
            ORDER BY updated_at DESC
            LIMIT ?
        """, (limit,))
        
        sessions = []
        for row in cursor.fetchall():
            sessions.append({
                "session_id": row[0],
                "created_at": row[1],
                "updated_at": row[2],
                "metadata": json.loads(row[3]) if row[3] else {},
            })
        
        conn.close()
        return sessions
    
    def delete_session(self, session_id: str) -> None:
        """Delete a session and all related data.
        
        Args:
            session_id: Session identifier.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Delete steps first (foreign key constraint)
        cursor.execute("DELETE FROM steps WHERE session_id = ?", (session_id,))
        
        # Delete tasks
        cursor.execute("DELETE FROM tasks WHERE session_id = ?", (session_id,))
        
        # Delete session
        cursor.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        
        conn.commit()
        conn.close()