"""Unit tests for Memory System."""

import json
import os
import tempfile
from pathlib import Path

import pytest

from agent.core.memory import (
    ConversationTurn,
    LongTermMemory,
    MemoryEntry,
    MemorySystem,
    ShortTermMemory,
)


class TestShortTermMemory:
    """Tests for ShortTermMemory class."""

    def test_init(self):
        """Test initialization."""
        stm = ShortTermMemory(max_turns=10, summary_threshold=5)
        assert stm.max_turns == 10
        assert stm.summary_threshold == 5
        assert len(stm.turns) == 0
        assert stm.summary == ""

    def test_add_turn(self):
        """Test adding conversation turns."""
        stm = ShortTermMemory(max_turns=10)
        stm.add_turn("user", "Hello")
        stm.add_turn("assistant", "Hi there!")

        assert len(stm.turns) == 2
        assert stm.turns[0].role == "user"
        assert stm.turns[0].content == "Hello"
        assert stm.turns[1].role == "assistant"
        assert stm.turns[1].content == "Hi there!"

    def test_add_turn_with_metadata(self):
        """Test adding turn with metadata."""
        stm = ShortTermMemory()
        stm.add_turn("user", "Test", metadata={"key": "value"})

        assert len(stm.turns) == 1
        assert stm.turns[0].metadata == {"key": "value"}

    def test_get_recent_turns(self):
        """Test getting recent turns."""
        stm = ShortTermMemory()
        for i in range(5):
            stm.add_turn("user", f"Message {i}")

        # Get all turns
        all_turns = stm.get_recent_turns()
        assert len(all_turns) == 5

        # Get last 3 turns
        recent = stm.get_recent_turns(n=3)
        assert len(recent) == 3
        assert recent[0].content == "Message 2"

    def test_get_messages_for_llm(self):
        """Test formatting for LLM API."""
        stm = ShortTermMemory()
        stm.add_turn("system", "You are helpful")
        stm.add_turn("user", "Hello")
        stm.add_turn("assistant", "Hi!")

        messages = stm.get_messages_for_llm()
        assert len(messages) == 3
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert messages[2]["role"] == "assistant"

    def test_summarize_and_trim(self):
        """Test summarization when over limit."""
        stm = ShortTermMemory(max_turns=5, summary_threshold=3)

        # Add more turns than max
        for i in range(6):
            stm.add_turn("user", f"Message {i}")

        # Should have trimmed
        assert len(stm.turns) <= stm.max_turns
        # Should have summary
        assert len(stm.summary) > 0

    def test_clear(self):
        """Test clearing memory."""
        stm = ShortTermMemory()
        stm.add_turn("user", "Hello")
        stm.add_turn("assistant", "Hi")

        stm.clear()

        assert len(stm.turns) == 0
        assert stm.summary == ""

    def test_get_context_string(self):
        """Test context string generation."""
        stm = ShortTermMemory()
        stm.add_turn("user", "Hello world")

        context = stm.get_context_string()
        assert "Recent Turns" in context
        assert "user" in context


class TestLongTermMemory:
    """Tests for LongTermMemory class."""

    @pytest.fixture
    def temp_memory_file(self):
        """Create temporary memory file."""
        with tempfile.NamedTemporaryFile(
            suffix=".jsonl", delete=False, mode="w"
        ) as f:
            f.write("")
            path = f.name

        yield path

        # Cleanup
        if Path(path).exists():
            Path(path).unlink()

    def test_init(self, temp_memory_file):
        """Test initialization."""
        ltm = LongTermMemory(storage_path=temp_memory_file)
        assert ltm.storage_path == Path(temp_memory_file)
        assert len(ltm._entries) == 0

    def test_add_entry(self, temp_memory_file):
        """Test adding memory entry."""
        ltm = LongTermMemory(storage_path=temp_memory_file)
        entry = ltm.add_entry(
            content="Test experience",
            entry_type="experience",
            importance=0.8,
        )

        assert entry.content == "Test experience"
        assert entry.entry_type == "experience"
        assert entry.importance == 0.8
        assert entry.id is not None

        # Should be saved to file
        assert len(ltm._entries) == 1

    def test_add_entry_persistence(self, temp_memory_file):
        """Test that entries persist across instances."""
        # Create and add entry
        ltm1 = LongTermMemory(storage_path=temp_memory_file)
        ltm1.add_entry(content="Persistent entry", importance=0.9)

        # Load in new instance
        ltm2 = LongTermMemory(storage_path=temp_memory_file)
        assert len(ltm2._entries) == 1
        assert ltm2._entries[0].content == "Persistent entry"

    def test_search(self, temp_memory_file):
        """Test searching memories."""
        ltm = LongTermMemory(storage_path=temp_memory_file)

        # Add entries
        ltm.add_entry(content="RAG retrieval system", importance=0.8)
        ltm.add_entry(content="LLM generation", importance=0.7)
        ltm.add_entry(content="Vector database", importance=0.6)

        # Search
        results = ltm.search("RAG retrieval", limit=5)
        assert len(results) >= 1
        assert "RAG" in results[0].content

    def test_search_by_importance(self, temp_memory_file):
        """Test search respects importance threshold."""
        ltm = LongTermMemory(storage_path=temp_memory_file)

        ltm.add_entry(content="Important thing", importance=0.9)
        ltm.add_entry(content="Unimportant thing", importance=0.1)

        # Should only return important entry
        results = ltm.search("thing", min_importance=0.5)
        assert len(results) == 1
        assert results[0].importance == 0.9

    def test_search_by_type(self, temp_memory_file):
        """Test search by entry type."""
        ltm = LongTermMemory(storage_path=temp_memory_file)

        ltm.add_entry(content="Experience 1", entry_type="experience")
        ltm.add_entry(content="Lesson 1", entry_type="lesson")

        results = ltm.search("1", entry_type="lesson")
        assert len(results) == 1
        assert results[0].entry_type == "lesson"

    def test_get_entries_by_type(self, temp_memory_file):
        """Test getting entries by type."""
        ltm = LongTermMemory(storage_path=temp_memory_file)

        ltm.add_entry(content="Exp 1", entry_type="experience", importance=0.8)
        ltm.add_entry(content="Exp 2", entry_type="experience", importance=0.9)
        ltm.add_entry(content="Lesson 1", entry_type="lesson")

        entries = ltm.get_entries_by_type("experience")
        assert len(entries) == 2
        # Should be sorted by importance
        assert entries[0].importance == 0.9

    def test_delete_entry(self, temp_memory_file):
        """Test deleting an entry."""
        ltm = LongTermMemory(storage_path=temp_memory_file)
        entry = ltm.add_entry(content="To delete")

        result = ltm.delete_entry(entry.id)
        assert result is True
        assert len(ltm._entries) == 0

        # Delete non-existent
        result = ltm.delete_entry("nonexistent")
        assert result is False

    def test_get_stats(self, temp_memory_file):
        """Test getting statistics."""
        ltm = LongTermMemory(storage_path=temp_memory_file)

        ltm.add_entry(content="Test 1", entry_type="experience", importance=0.8)
        ltm.add_entry(content="Test 2", entry_type="lesson", importance=0.6)

        stats = ltm.get_stats()

        assert stats["total_entries"] == 2
        assert stats["by_type"]["experience"] == 1
        assert stats["by_type"]["lesson"] == 1
        assert stats["avg_importance"] == pytest.approx(0.7, rel=0.01)

    def test_access_count_increments(self, temp_memory_file):
        """Test that access count increments on search."""
        ltm = LongTermMemory(storage_path=temp_memory_file)
        entry = ltm.add_entry(content="Searchable content", importance=0.8)

        assert entry.access_count == 0

        # Search should increment access_count
        ltm.search("searchable")

        # Reload to check
        ltm2 = LongTermMemory(storage_path=temp_memory_file)
        assert ltm2._entries[0].access_count >= 1


class TestMemorySystem:
    """Tests for unified MemorySystem class."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_init(self, temp_dir):
        """Test initialization."""
        memory_system = MemorySystem(
            short_term_max_turns=10,
            long_term_storage_path=f"{temp_dir}/memory.jsonl",
        )

        assert memory_system.short_term.max_turns == 10
        assert memory_system.long_term.storage_path == Path(
            f"{temp_dir}/memory.jsonl"
        )

    def test_add_conversation(self, temp_dir):
        """Test adding conversation."""
        memory_system = MemorySystem(long_term_storage_path=f"{temp_dir}/mem.jsonl")

        memory_system.add_conversation("user", "Hello")
        memory_system.add_conversation("assistant", "Hi there")

        assert len(memory_system.short_term.turns) == 2

    def test_add_experience(self, temp_dir):
        """Test adding experience to long-term memory."""
        memory_system = MemorySystem(long_term_storage_path=f"{temp_dir}/mem.jsonl")

        entry = memory_system.add_experience(
            content="Learned something important",
            importance=0.9,
        )

        assert entry.content == "Learned something important"
        assert entry.importance == 0.9

        # Check in long-term memory
        entries = memory_system.long_term.get_entries_by_type("experience")
        assert len(entries) == 1

    def test_add_lesson(self, temp_dir):
        """Test adding lesson."""
        memory_system = MemorySystem(long_term_storage_path=f"{temp_dir}/mem.jsonl")

        entry = memory_system.add_lesson(
            content="Always check API limits",
            importance=0.95,
        )

        assert entry.entry_type == "lesson"
        assert entry.importance == 0.95

    def test_search_relevant_memories(self, temp_dir):
        """Test searching memories."""
        memory_system = MemorySystem(long_term_storage_path=f"{temp_dir}/mem.jsonl")

        # Add some memories
        memory_system.add_experience(content="RAG system uses vector search")
        memory_system.add_experience(content="LLM generates responses")

        # Search
        results = memory_system.search_relevant_memories("RAG vector", limit=5)
        assert len(results) >= 1
        assert "RAG" in results[0].content

    def test_get_stats(self, temp_dir):
        """Test getting system stats."""
        memory_system = MemorySystem(long_term_storage_path=f"{temp_dir}/mem.jsonl")

        memory_system.add_conversation("user", "Hello")
        memory_system.add_experience(content="Test")

        stats = memory_system.get_stats()

        assert "short_term_turns" in stats
        assert "total_entries" in stats
        assert stats["short_term_turns"] == 1

    def test_clear(self, temp_dir):
        """Test clearing short-term memory."""
        memory_system = MemorySystem(long_term_storage_path=f"{temp_dir}/mem.jsonl")

        memory_system.add_conversation("user", "Test")
        memory_system.add_experience(content="Persistent")

        memory_system.clear()

        # STM should be cleared
        assert len(memory_system.short_term.turns) == 0

        # LTM should still have entry
        assert len(memory_system.long_term.get_all_entries()) == 1

    def test_get_context_for_llm(self, temp_dir):
        """Test getting LLM context."""
        memory_system = MemorySystem(long_term_storage_path=f"{temp_dir}/mem.jsonl")

        memory_system.add_conversation("user", "What is RAG?")
        memory_system.add_conversation("assistant", "RAG is...")

        context = memory_system.get_context_for_llm()

        assert "Recent Conversation" in context
        assert "What is RAG?" in context


class TestMemoryEntry:
    """Tests for MemoryEntry dataclass."""

    def test_default_values(self):
        """Test default field values."""
        entry = MemoryEntry()

        assert entry.id is not None
        assert entry.content == ""
        assert entry.entry_type == "conversation"
        assert entry.importance == 0.5
        assert entry.access_count == 0

    def test_custom_values(self):
        """Test custom field values."""
        entry = MemoryEntry(
            content="Test content",
            entry_type="experience",
            importance=0.9,
            metadata={"key": "value"},
        )

        assert entry.content == "Test content"
        assert entry.entry_type == "experience"
        assert entry.importance == 0.9
        assert entry.metadata == {"key": "value"}


class TestConversationTurn:
    """Tests for ConversationTurn dataclass."""

    def test_default_values(self):
        """Test default field values."""
        turn = ConversationTurn(role="user", content="Hello")

        assert turn.role == "user"
        assert turn.content == "Hello"
        assert turn.timestamp is not None
        assert turn.metadata == {}

    def test_custom_metadata(self):
        """Test custom metadata."""
        turn = ConversationTurn(
            role="assistant",
            content="Response",
            metadata={"tokens": 100},
        )

        assert turn.metadata == {"tokens": 100}