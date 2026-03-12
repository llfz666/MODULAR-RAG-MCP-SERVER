"""Memory System for Smart Agent Hub.

This module implements the memory system for the agent:
1. Short-term working memory (conversation history)
2. Long-term experience retrieval (vector-based experience storage)

Design Principles:
- Modular: Can be enabled/disabled via configuration
- Config-Driven: All memory parameters from settings
- Observable: Memory operations are logged for debugging
- Efficient: Uses similarity search for long-term retrieval
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from agent.storage.jsonl_logger import JSONLLogger


@dataclass
class MemoryEntry:
    """A single memory entry."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: str = ""
    entry_type: str = "conversation"  # conversation, experience, lesson
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    importance: float = 0.5  # 0-1 importance score
    access_count: int = 0  # How many times accessed


@dataclass
class ConversationTurn:
    """A single conversation turn."""
    
    role: str  # user, assistant, system
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)


class ShortTermMemory:
    """Short-term working memory for conversation history.
    
    This maintains the current conversation context and provides
    efficient access to recent turns.
    
    Features:
    - Sliding window of recent turns
    - Summary of older turns to save context
    - Easy integration with LLM message history
    """
    
    def __init__(
        self,
        max_turns: int = 20,
        summary_threshold: int = 10,
    ):
        """Initialize Short-term Memory.
        
        Args:
            max_turns: Maximum conversation turns to keep.
            summary_threshold: Turns before summarization starts.
        """
        self.max_turns = max_turns
        self.summary_threshold = summary_threshold
        self.turns: list[ConversationTurn] = []
        self.summary: str = ""
    
    def add_turn(
        self,
        role: str,
        content: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """Add a conversation turn.
        
        Args:
            role: Role (user/assistant/system).
            content: Message content.
            metadata: Optional metadata.
        """
        turn = ConversationTurn(
            role=role,
            content=content,
            metadata=metadata or {},
        )
        self.turns.append(turn)
        
        # Trim if over limit
        if len(self.turns) > self.max_turns:
            self._summarize_and_trim()
    
    def _summarize_and_trim(self) -> None:
        """Summarize older turns and trim the list."""
        if len(self.turns) <= self.summary_threshold:
            return
        
        # Summarize the oldest turns
        turns_to_summarize = self.turns[:len(self.turns) - self.summary_threshold]
        summary_parts = []
        
        for turn in turns_to_summarize:
            summary_parts.append(f"{turn.role}: {turn.content[:100]}...")
        
        new_summary = "\n".join(summary_parts)
        
        # Update summary (append or replace)
        if self.summary:
            self.summary = f"{self.summary}\n\n[Older conversation]\n{new_summary}"
        else:
            self.summary = f"[Conversation Summary]\n{new_summary}"
        
        # Keep only recent turns
        self.turns = self.turns[len(turns_to_summarize):]
    
    def get_recent_turns(self, n: Optional[int] = None) -> list[ConversationTurn]:
        """Get recent conversation turns.
        
        Args:
            n: Number of turns (default: all recent).
            
        Returns:
            List of recent turns.
        """
        if n is None:
            return self.turns
        return self.turns[-n:]
    
    def get_messages_for_llm(self) -> list[dict[str, str]]:
        """Format turns for LLM API.
        
        Returns:
            List of message dictionaries.
        """
        messages = []
        
        # Add summary if exists
        if self.summary:
            messages.append({
                "role": "system",
                "content": f"Previous conversation summary:\n{self.summary}",
            })
        
        # Add recent turns
        for turn in self.turns:
            messages.append({
                "role": turn.role,
                "content": turn.content,
            })
        
        return messages
    
    def clear(self) -> None:
        """Clear all turns and summary."""
        self.turns.clear()
        self.summary = ""
    
    def get_context_string(self) -> str:
        """Get a context string for debugging.
        
        Returns:
            Formatted context string.
        """
        parts = []
        
        if self.summary:
            parts.append(f"Summary:\n{self.summary}")
        
        parts.append("\nRecent Turns:")
        for i, turn in enumerate(self.turns):
            parts.append(f"  [{i}] {turn.role}: {turn.content[:50]}...")
        
        return "\n".join(parts)


class LongTermMemory:
    """Long-term experience memory for retrieval.
    
    This stores important experiences and lessons that can be
    retrieved later for similar situations.
    
    Features:
    - JSONL-based storage for persistence
    - Importance-based filtering
    - Simple keyword matching for retrieval
    - Experience categorization
    
    Note: For production use, consider adding vector embeddings
    for semantic similarity search.
    """
    
    def __init__(
        self,
        storage_path: str = "data/logs/long_term_memory.jsonl",
        max_entries: int = 1000,
    ):
        """Initialize Long-term Memory.
        
        Args:
            storage_path: Path to JSONL storage file.
            max_entries: Maximum entries to keep.
        """
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.max_entries = max_entries
        self._entries: list[MemoryEntry] = []
        self._load()
    
    def _load(self) -> None:
        """Load entries from storage."""
        if not self.storage_path.exists():
            return
        
        with open(self.storage_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line.strip())
                    entry = MemoryEntry(
                        id=data.get("id", str(uuid.uuid4())),
                        content=data.get("content", ""),
                        entry_type=data.get("entry_type", "conversation"),
                        metadata=data.get("metadata", {}),
                        importance=data.get("importance", 0.5),
                        access_count=data.get("access_count", 0),
                    )
                    # Parse datetime
                    if "created_at" in data:
                        entry.created_at = datetime.fromisoformat(data["created_at"])
                    self._entries.append(entry)
                except (json.JSONDecodeError, KeyError):
                    continue
        
        # Sort by importance and access count
        self._entries.sort(key=lambda e: e.importance * 0.5 + e.access_count * 0.1, reverse=True)
    
    def _save(self) -> None:
        """Save entries to storage."""
        # Trim if over limit
        if len(self._entries) > self.max_entries:
            self._entries = self._entries[:self.max_entries]
        
        with open(self.storage_path, "w", encoding="utf-8") as f:
            for entry in self._entries:
                data = {
                    "id": entry.id,
                    "content": entry.content,
                    "entry_type": entry.entry_type,
                    "metadata": entry.metadata,
                    "importance": entry.importance,
                    "access_count": entry.access_count,
                    "created_at": entry.created_at.isoformat(),
                }
                f.write(json.dumps(data, ensure_ascii=False) + "\n")
    
    def add_entry(
        self,
        content: str,
        entry_type: str = "experience",
        metadata: Optional[dict[str, Any]] = None,
        importance: float = 0.5,
    ) -> MemoryEntry:
        """Add a memory entry.
        
        Args:
            content: Memory content.
            entry_type: Type of entry.
            metadata: Optional metadata.
            importance: Importance score (0-1).
            
        Returns:
            Created MemoryEntry.
        """
        entry = MemoryEntry(
            content=content,
            entry_type=entry_type,
            metadata=metadata or {},
            importance=importance,
        )
        self._entries.append(entry)
        self._save()
        return entry
    
    def search(
        self,
        query: str,
        limit: int = 5,
        min_importance: float = 0.3,
        entry_type: Optional[str] = None,
    ) -> list[MemoryEntry]:
        """Search for relevant memories.
        
        Uses keyword matching for retrieval.
        
        Args:
            query: Search query.
            limit: Maximum results.
            min_importance: Minimum importance threshold.
            entry_type: Filter by type.
            
        Returns:
            List of relevant memories.
        """
        query_keywords = set(query.lower().split())
        
        scored_entries = []
        for entry in self._entries:
            # Filter by importance
            if entry.importance < min_importance:
                continue
            
            # Filter by type
            if entry_type and entry.entry_type != entry_type:
                continue
            
            # Calculate keyword match score
            content_keywords = set(entry.content.lower().split())
            overlap = len(query_keywords & content_keywords)
            
            if overlap > 0:
                # Score = keyword overlap + importance bonus
                score = overlap + entry.importance * 0.5
                scored_entries.append((score, entry))
        
        # Sort by score and return top results
        scored_entries.sort(key=lambda x: x[0], reverse=True)
        
        # Update access counts for returned entries
        results = []
        for score, entry in scored_entries[:limit]:
            entry.access_count += 1
            results.append(entry)
        
        self._save()
        return results
    
    def get_entries_by_type(
        self,
        entry_type: str,
        limit: int = 10,
    ) -> list[MemoryEntry]:
        """Get entries by type.
        
        Args:
            entry_type: Type to filter.
            limit: Maximum results.
            
        Returns:
            List of entries.
        """
        entries = [e for e in self._entries if e.entry_type == entry_type]
        entries.sort(key=lambda e: e.importance, reverse=True)
        return entries[:limit]
    
    def delete_entry(self, entry_id: str) -> bool:
        """Delete an entry.
        
        Args:
            entry_id: Entry ID to delete.
            
        Returns:
            True if deleted.
        """
        for i, entry in enumerate(self._entries):
            if entry.id == entry_id:
                del self._entries[i]
                self._save()
                return True
        return False
    
    def get_all_entries(self) -> list[MemoryEntry]:
        """Get all entries.
        
        Returns:
            List of all entries.
        """
        return self._entries.copy()
    
    def get_stats(self) -> dict[str, Any]:
        """Get memory statistics.
        
        Returns:
            Statistics dictionary.
        """
        by_type: dict[str, int] = {}
        total_access = 0
        
        for entry in self._entries:
            by_type[entry.entry_type] = by_type.get(entry.entry_type, 0) + 1
            total_access += entry.access_count
        
        return {
            "total_entries": len(self._entries),
            "by_type": by_type,
            "total_access_count": total_access,
            "avg_importance": sum(e.importance for e in self._entries) / len(self._entries) if self._entries else 0,
        }


class MemorySystem:
    """Unified memory system combining short and long-term memory.
    
    This provides a single interface for all memory operations.
    """
    
    def __init__(
        self,
        short_term_max_turns: int = 20,
        long_term_storage_path: str = "data/logs/long_term_memory.jsonl",
        logger: Optional[JSONLLogger] = None,
    ):
        """Initialize Memory System.
        
        Args:
            short_term_max_turns: Max STM turns.
            long_term_storage_path: LTM storage path.
            logger: Optional JSONL logger.
        """
        self.short_term = ShortTermMemory(max_turns=short_term_max_turns)
        self.long_term = LongTermMemory(storage_path=long_term_storage_path)
        self.logger = logger
    
    def add_conversation(
        self,
        role: str,
        content: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """Add a conversation turn to short-term memory.
        
        Args:
            role: Role (user/assistant/system).
            content: Message content.
            metadata: Optional metadata.
        """
        self.short_term.add_turn(role, content, metadata or {})
        
        if self.logger:
            self.logger.log({
                "type": "memory_add_conversation",
                "role": role,
                "content_preview": content[:100],
            })
    
    def add_experience(
        self,
        content: str,
        importance: float = 0.5,
        metadata: Optional[dict[str, Any]] = None,
    ) -> MemoryEntry:
        """Add an experience to long-term memory.
        
        Args:
            content: Experience content.
            importance: Importance score.
            metadata: Optional metadata.
            
        Returns:
            Created MemoryEntry.
        """
        entry = self.long_term.add_entry(
            content=content,
            entry_type="experience",
            metadata=metadata or {},
            importance=importance,
        )
        
        if self.logger:
            self.logger.log({
                "type": "memory_add_experience",
                "content_preview": content[:100],
                "importance": importance,
            })
        
        return entry
    
    def add_lesson(
        self,
        content: str,
        importance: float = 0.8,
        metadata: Optional[dict[str, Any]] = None,
    ) -> MemoryEntry:
        """Add a lesson learned to long-term memory.
        
        Args:
            content: Lesson content.
            importance: Importance score (default high).
            metadata: Optional metadata.
            
        Returns:
            Created MemoryEntry.
        """
        entry = self.long_term.add_entry(
            content=content,
            entry_type="lesson",
            metadata=metadata or {},
            importance=importance,
        )
        
        if self.logger:
            self.logger.log({
                "type": "memory_add_lesson",
                "content_preview": content[:100],
                "importance": importance,
            })
        
        return entry
    
    def search_relevant_memories(
        self,
        query: str,
        limit: int = 5,
    ) -> list[MemoryEntry]:
        """Search for relevant memories.
        
        Args:
            query: Search query.
            limit: Maximum results.
            
        Returns:
            List of relevant memories.
        """
        results = self.long_term.search(query, limit=limit)
        
        if self.logger and results:
            self.logger.log({
                "type": "memory_search",
                "query": query,
                "results_count": len(results),
            })
        
        return results
    
    def get_context_for_llm(self) -> str:
        """Get formatted context for LLM.
        
        Returns:
            Context string combining STM and relevant LTM.
        """
        parts = []
        
        # Add short-term context
        stm_messages = self.short_term.get_messages_for_llm()
        if stm_messages:
            parts.append("=== Recent Conversation ===")
            for msg in stm_messages:
                parts.append(f"{msg['role']}: {msg['content'][:200]}")
        
        return "\n\n".join(parts)
    
    def get_stats(self) -> dict[str, Any]:
        """Get memory system statistics.
        
        Returns:
            Statistics dictionary.
        """
        ltm_stats = self.long_term.get_stats()
        return {
            "short_term_turns": len(self.short_term.turns),
            "short_term_summary_length": len(self.short_term.summary),
            **ltm_stats,
        }
    
    def clear(self) -> None:
        """Clear short-term memory only."""
        self.short_term.clear()