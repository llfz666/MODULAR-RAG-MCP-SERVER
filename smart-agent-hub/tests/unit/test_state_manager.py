"""Unit tests for StateManager and JSONLLogger."""

import json
import os
import tempfile
from pathlib import Path

import pytest

from agent.core.state_manager import StateManager
from agent.storage.jsonl_logger import JSONLLogger


class TestStateManager:
    """Tests for StateManager."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            yield str(db_path)

    @pytest.fixture
    def state_manager(self, temp_db):
        """Create state manager with temp database."""
        return StateManager(db_path=temp_db)

    def test_init_creates_database(self, temp_db):
        """Test that initialization creates database file."""
        sm = StateManager(db_path=temp_db)
        assert Path(temp_db).exists()

    def test_save_and_load_session(self, state_manager):
        """Test saving and loading a session."""
        session_id = "test-session-123"
        metadata = {"query": "test query", "user": "test_user"}
        
        state_manager.save_session(session_id, metadata)
        loaded = state_manager.load_session(session_id)
        
        assert loaded == metadata

    def test_save_session_default_metadata(self, state_manager):
        """Test saving session with default metadata."""
        session_id = "test-session-456"
        
        state_manager.save_session(session_id)
        loaded = state_manager.load_session(session_id)
        
        assert loaded == {}

    def test_load_nonexistent_session(self, state_manager):
        """Test loading a non-existent session."""
        result = state_manager.load_session("nonexistent")
        assert result is None

    def test_save_and_get_task(self, state_manager):
        """Test saving and retrieving a task."""
        task_id = "task-123"
        session_id = "session-123"
        user_query = "Test query"
        
        state_manager.save_session(session_id)
        state_manager.save_task(task_id, session_id, user_query)
        
        task = state_manager.get_task(task_id)
        
        assert task is not None
        assert task["task_id"] == task_id
        assert task["session_id"] == session_id
        assert task["user_query"] == user_query
        assert task["status"] == "created"

    def test_update_task_status(self, state_manager):
        """Test updating task status."""
        task_id = "task-456"
        session_id = "session-456"
        
        state_manager.save_session(session_id)
        state_manager.save_task(task_id, session_id, "Test")
        
        state_manager.update_task_status(task_id, "completed", final_result="Result")
        
        task = state_manager.get_task(task_id)
        assert task["status"] == "completed"
        assert task["final_result"] == "Result"

    def test_save_and_get_steps(self, state_manager):
        """Test saving and retrieving steps."""
        session_id = "session-789"
        task_id = "task-789"
        
        state_manager.save_session(session_id)
        state_manager.save_task(task_id, session_id, "Test")
        
        # Save multiple steps
        state_manager.save_step(
            session_id, task_id, 0,
            thought="First thought",
            action="search",
            action_input={"query": "test"},
            observation="Result 1",
        )
        state_manager.save_step(
            session_id, task_id, 1,
            thought="Second thought",
            is_final=True,
            final_answer="Final answer",
        )
        
        steps = state_manager.get_session_steps(session_id, task_id)
        
        assert len(steps) == 2
        assert steps[0]["thought"] == "First thought"
        assert steps[0]["action"] == "search"
        assert steps[0]["observation"] == "Result 1"
        assert steps[1]["is_final"] is True
        assert steps[1]["final_answer"] == "Final answer"

    def test_get_session_tasks(self, state_manager):
        """Test getting all tasks for a session."""
        session_id = "session-tasks"
        
        state_manager.save_session(session_id)
        state_manager.save_task("task-1", session_id, "Query 1")
        state_manager.save_task("task-2", session_id, "Query 2")
        
        tasks = state_manager.get_session_tasks(session_id)
        
        assert len(tasks) == 2
        task_ids = [t["task_id"] for t in tasks]
        assert "task-1" in task_ids
        assert "task-2" in task_ids

    def test_list_sessions(self, state_manager):
        """Test listing sessions."""
        state_manager.save_session("session-1", {"name": "First"})
        state_manager.save_session("session-2", {"name": "Second"})
        
        sessions = state_manager.list_sessions(limit=10)
        
        assert len(sessions) >= 2
        session_ids = [s["session_id"] for s in sessions]
        assert "session-1" in session_ids
        assert "session-2" in session_ids

    def test_delete_session(self, state_manager):
        """Test deleting a session."""
        session_id = "session-delete"
        task_id = "task-delete"
        
        state_manager.save_session(session_id)
        state_manager.save_task(task_id, session_id, "Test")
        state_manager.save_step(session_id, task_id, 0, thought="Test")
        
        state_manager.delete_session(session_id)
        
        # Verify session is deleted
        assert state_manager.load_session(session_id) is None
        
        # Verify task is deleted
        assert state_manager.get_task(task_id) is None
        
        # Verify steps are deleted
        steps = state_manager.get_session_steps(session_id, task_id)
        assert len(steps) == 0


class TestJSONLLogger:
    """Tests for JSONLLogger."""

    @pytest.fixture
    def temp_log(self):
        """Create a temporary log file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            temp_path = f.name
        yield temp_path
        if Path(temp_path).exists():
            os.unlink(temp_path)

    @pytest.fixture
    def logger(self, temp_log):
        """Create logger with temp file."""
        return JSONLLogger(log_path=temp_log)

    def test_init_creates_directory(self, tmp_path):
        """Test that initialization creates directory."""
        log_path = tmp_path / "subdir" / "test.jsonl"
        logger = JSONLLogger(log_path=str(log_path))
        assert log_path.parent.exists()

    def test_log_event(self, logger, temp_log):
        """Test logging an event."""
        event = {"type": "test", "data": "test data"}
        logger.log(event)
        
        events = logger.get_events()
        
        assert len(events) == 1
        assert events[0]["type"] == "test"
        assert events[0]["data"] == "test data"
        assert "timestamp" in events[0]

    def test_log_thought(self, logger):
        """Test logging a thought."""
        logger.log_thought("session-1", "task-1", "This is a thought", 0)
        
        events = logger.get_events()
        
        assert len(events) == 1
        assert events[0]["type"] == "thought"
        assert events[0]["session_id"] == "session-1"
        assert events[0]["task_id"] == "task-1"
        assert events[0]["content"] == "This is a thought"

    def test_log_action(self, logger):
        """Test logging an action."""
        logger.log_action("session-1", "task-1", "search", {"query": "test"}, 0)
        
        events = logger.get_events()
        
        assert len(events) == 1
        assert events[0]["type"] == "action"
        assert events[0]["tool"] == "search"
        assert events[0]["input"] == {"query": "test"}

    def test_log_observation(self, logger):
        """Test logging an observation."""
        logger.log_observation("session-1", "task-1", "Result data", 100.5, 0)
        
        events = logger.get_events()
        
        assert len(events) == 1
        assert events[0]["type"] == "observation"
        assert events[0]["result"] == "Result data"
        assert events[0]["latency_ms"] == 100.5

    def test_log_observation_with_error(self, logger):
        """Test logging an observation with error."""
        logger.log_observation(
            "session-1", "task-1", None, 50.0, 0, error="Test error"
        )
        
        events = logger.get_events()
        
        assert events[0]["error"] == "Test error"

    def test_log_final_answer(self, logger):
        """Test logging a final answer."""
        logger.log_final_answer("session-1", "task-1", "Final answer", True)
        
        events = logger.get_events()
        
        assert len(events) == 1
        assert events[0]["type"] == "final_answer"
        assert events[0]["content"] == "Final answer"
        assert events[0]["success"] is True

    def test_log_error(self, logger):
        """Test logging an error."""
        logger.log_error("session-1", "task-1", "Something went wrong", "ValueError")
        
        events = logger.get_events()
        
        assert len(events) == 1
        assert events[0]["type"] == "error"
        assert events[0]["error"] == "Something went wrong"
        assert events[0]["error_type"] == "ValueError"

    def test_get_session_events(self, logger):
        """Test getting events for a specific session."""
        logger.log_thought("session-1", "task-1", "Thought 1")
        logger.log_thought("session-2", "task-2", "Thought 2")
        logger.log_thought("session-1", "task-3", "Thought 3")
        
        events = logger.get_session_events("session-1")
        
        assert len(events) == 2
        assert all(e["session_id"] == "session-1" for e in events)

    def test_get_task_events(self, logger):
        """Test getting events for a specific task."""
        logger.log_thought("session-1", "task-1", "Thought 1")
        logger.log_thought("session-1", "task-2", "Thought 2")
        
        events = logger.get_task_events("session-1", "task-1")
        
        assert len(events) == 1
        assert events[0]["task_id"] == "task-1"

    def test_get_events_empty_file(self, temp_log):
        """Test getting events from empty/non-existent file."""
        logger = JSONLLogger(log_path=temp_log)
        # Remove the file to test non-existent case
        if Path(temp_log).exists():
            os.unlink(temp_log)
        
        events = logger.get_events()
        assert events == []

    def test_multiple_events_appended(self, logger):
        """Test that multiple events are appended correctly."""
        logger.log({"type": "event1"})
        logger.log({"type": "event2"})
        logger.log({"type": "event3"})
        
        events = logger.get_events()
        
        assert len(events) == 3
        assert events[0]["type"] == "event1"
        assert events[1]["type"] == "event2"
        assert events[2]["type"] == "event3"