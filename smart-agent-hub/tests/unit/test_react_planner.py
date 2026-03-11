"""Unit tests for ReAct Planner."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.core.planner import ReActPlanner, ReActResult, ReActStep
from agent.llm.client import LLMMessage, LLMResponse
from agent.mcp.tool_registry import ToolRegistry


class TestReActStep:
    """Tests for ReActStep dataclass."""

    def test_default_values(self):
        """Test default values."""
        step = ReActStep(thought="Thinking...")

        assert step.thought == "Thinking..."
        assert step.action is None
        assert step.action_input is None
        assert step.observation is None
        assert step.error is None
        assert step.is_final is False
        assert step.final_answer is None

    def test_final_step(self):
        """Test final step."""
        step = ReActStep(
            thought="I have enough information.",
            is_final=True,
            final_answer="The answer is 42.",
        )

        assert step.is_final is True
        assert step.final_answer == "The answer is 42."


class TestReActResult:
    """Tests for ReActResult dataclass."""

    def test_default_values(self):
        """Test default values."""
        result = ReActResult(final_answer="Answer")

        assert result.final_answer == "Answer"
        assert result.steps == []
        assert result.total_tokens == 0
        assert result.success is True
        assert result.error_message is None

    def test_error_result(self):
        """Test error result."""
        result = ReActResult(
            final_answer="Failed",
            success=False,
            error_message="Something went wrong",
        )

        assert result.success is False
        assert result.error_message == "Something went wrong"


class TestReActPlannerInitialization:
    """Tests for ReActPlanner initialization."""

    def test_default_initialization(self):
        """Test default initialization."""
        planner = ReActPlanner()

        assert planner.llm_client is None
        assert isinstance(planner.tool_registry, ToolRegistry)
        assert planner.max_iterations == 10
        assert planner.enable_reflection is True
        assert planner.max_retries == 3

    def test_custom_initialization(self):
        """Test custom initialization."""
        mock_llm = MagicMock()
        mock_registry = MagicMock()

        planner = ReActPlanner(
            llm_client=mock_llm,
            tool_registry=mock_registry,
            max_iterations=5,
            enable_reflection=False,
            max_retries=2,
        )

        assert planner.llm_client is mock_llm
        assert planner.tool_registry is mock_registry
        assert planner.max_iterations == 5
        assert planner.enable_reflection is False
        assert planner.max_retries == 2


class TestReActPlannerExecute:
    """Tests for ReActPlanner execute method."""

    @pytest.mark.asyncio
    async def test_no_llm_client(self):
        """Test execution without LLM client."""
        planner = ReActPlanner(llm_client=None)

        result = await planner.execute("What is 2+2?")

        assert result.success is False
        assert "LLM client not configured" in result.final_answer

    @pytest.mark.asyncio
    async def test_immediate_final_answer(self):
        """Test when LLM returns immediate final answer."""
        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(return_value=LLMResponse(
            content=json.dumps({
                "thought": "I know this!",
                "action": None,
                "action_input": None,
                "is_final": True,
                "final_answer": "The answer is 42.",
            }),
            usage={"total_tokens": 10},
        ))

        planner = ReActPlanner(llm_client=mock_llm)
        result = await planner.execute("What is 2+2?")

        assert result.success is True
        assert result.final_answer == "The answer is 42."
        assert result.total_tokens == 10
        assert len(result.steps) == 1

    @pytest.mark.asyncio
    async def test_single_tool_execution(self):
        """Test single tool execution."""
        mock_llm = AsyncMock()
        mock_registry = MagicMock()

        # First call: execute tool
        # Second call: return final answer
        mock_llm.chat = AsyncMock(side_effect=[
            LLMResponse(
                content=json.dumps({
                    "thought": "I need to search for this.",
                    "action": "search",
                    "action_input": {"query": "test"},
                    "is_final": False,
                }),
                usage={"total_tokens": 10},
            ),
            LLMResponse(
                content=json.dumps({
                    "thought": "I found the answer.",
                    "action": None,
                    "action_input": None,
                    "is_final": True,
                    "final_answer": "The answer is in the search results.",
                }),
                usage={"total_tokens": 15},
            ),
        ])

        mock_registry.execute_tool = AsyncMock(return_value=("Search results", None))

        planner = ReActPlanner(
            llm_client=mock_llm,
            tool_registry=mock_registry,
        )
        result = await planner.execute("What is test?")

        assert result.success is True
        assert "answer is in the search results" in result.final_answer
        assert result.total_tokens == 25
        assert len(result.steps) == 2

    @pytest.mark.asyncio
    async def test_tool_execution_error(self):
        """Test tool execution error with retries."""
        mock_llm = AsyncMock()
        mock_registry = MagicMock()

        # LLM always returns same action, tool always fails
        # This will run until max_iterations is reached
        mock_llm.chat = AsyncMock(return_value=LLMResponse(
            content=json.dumps({
                "thought": "Trying search.",
                "action": "search",
                "action_input": {"query": "test"},
                "is_final": False,
            }),
            usage={"total_tokens": 10},
        ))

        mock_registry.execute_tool = AsyncMock(
            return_value=(None, "Tool execution failed")
        )

        planner = ReActPlanner(
            llm_client=mock_llm,
            tool_registry=mock_registry,
            max_retries=3,  # Default
            max_iterations=5,  # Limit iterations for test
        )
        result = await planner.execute("What is test?")

        # Should fail due to max iterations reached
        assert result.success is False
        assert "Max iterations" in result.error_message

    @pytest.mark.asyncio
    async def test_json_parse_error(self):
        """Test JSON parse error handling."""
        mock_llm = AsyncMock()

        # Return invalid JSON
        mock_llm.chat = AsyncMock(return_value=LLMResponse(
            content="This is not valid JSON",
            usage={"total_tokens": 5},
        ))

        planner = ReActPlanner(
            llm_client=mock_llm,
            max_retries=2,
        )
        result = await planner.execute("What is test?")

        assert result.success is False
        assert "Failed to parse" in result.final_answer

    @pytest.mark.asyncio
    async def test_json_extraction(self):
        """Test JSON extraction from invalid response."""
        mock_llm = AsyncMock()

        # Return JSON embedded in text
        valid_json = json.dumps({
            "thought": "Found it!",
            "action": None,
            "action_input": None,
            "is_final": True,
            "final_answer": "The answer is 42.",
        })
        mock_llm.chat = AsyncMock(return_value=LLMResponse(
            content=f"Let me think...\n{valid_json}\nHope this works!",
            usage={"total_tokens": 10},
        ))

        planner = ReActPlanner(llm_client=mock_llm)
        result = await planner.execute("What is 2+2?")

        assert result.success is True
        assert result.final_answer == "The answer is 42."

    @pytest.mark.asyncio
    async def test_max_iterations(self):
        """Test max iterations reached."""
        mock_llm = AsyncMock()
        mock_registry = MagicMock()

        # Always return non-final actions
        mock_llm.chat = AsyncMock(return_value=LLMResponse(
            content=json.dumps({
                "thought": "Still working...",
                "action": "search",
                "action_input": {"query": "test"},
                "is_final": False,
            }),
            usage={"total_tokens": 10},
        ))

        mock_registry.execute_tool = AsyncMock(return_value=("Result", None))

        planner = ReActPlanner(
            llm_client=mock_llm,
            tool_registry=mock_registry,
            max_iterations=3,
        )
        result = await planner.execute("What is test?")

        assert result.success is False
        assert "Max iterations" in result.error_message
        assert len(result.steps) == 3

    @pytest.mark.asyncio
    async def test_with_context(self):
        """Test execution with additional context."""
        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(return_value=LLMResponse(
            content=json.dumps({
                "thought": "I know this!",
                "action": None,
                "action_input": None,
                "is_final": True,
                "final_answer": "The answer is 42.",
            }),
            usage={"total_tokens": 10},
        ))

        planner = ReActPlanner(llm_client=mock_llm)
        result = await planner.execute(
            "What is 2+2?",
            context="This is a math question.",
        )

        assert result.success is True
        # Verify context was included in messages
        call_args = mock_llm.chat.call_args[0][0]
        assert any("This is a math question." in msg.content for msg in call_args)


class TestReActPlannerHelpers:
    """Tests for ReActPlanner helper methods."""

    def test_format_previous_actions(self):
        """Test formatting previous actions."""
        planner = ReActPlanner()

        steps = [
            ReActStep(
                thought="First thought",
                action="search",
                action_input={"query": "test"},
                observation="Search results",
            ),
            ReActStep(
                thought="Second thought",
                action="read",
                action_input={"id": "1"},
                error="Not found",
            ),
        ]

        formatted = planner._format_previous_actions(steps)

        assert "Step 1:" in formatted
        assert "First thought" in formatted
        assert "search" in formatted
        assert "Step 2:" in formatted
        assert "Second thought" in formatted
        assert "Not found" in formatted

    def test_extract_json_valid(self):
        """Test JSON extraction from valid string."""
        planner = ReActPlanner()

        valid_json = json.dumps({"key": "value"})
        result = planner._extract_json(valid_json)

        assert result == {"key": "value"}

    def test_extract_json_embedded(self):
        """Test JSON extraction from embedded string."""
        planner = ReActPlanner()

        content = "Some text before {\"key\": \"value\"} and after"
        result = planner._extract_json(content)

        assert result == {"key": "value"}

    def test_extract_json_invalid(self):
        """Test JSON extraction from invalid string."""
        planner = ReActPlanner()

        result = planner._extract_json("This is not JSON")

        assert result is None

    def test_extract_json_empty(self):
        """Test JSON extraction from empty string."""
        planner = ReActPlanner()

        result = planner._extract_json("")

        assert result is None

    def test_generate_summary_with_info(self):
        """Test summary generation with information."""
        planner = ReActPlanner()

        steps = [
            ReActStep(
                thought="Searching...",
                action="search",
                observation="Result 1",
            ),
            ReActStep(
                thought="Reading...",
                action="read",
                observation="Result 2",
            ),
        ]

        summary = planner._generate_summary("What is test?", steps)

        assert "Result 1" in summary
        assert "Result 2" in summary
        assert "iteration limit" in summary

    def test_generate_summary_no_info(self):
        """Test summary generation without information."""
        planner = ReActPlanner()

        steps = [
            ReActStep(thought="Thinking..."),
            ReActStep(thought="Still thinking..."),
        ]

        summary = planner._generate_summary("What is test?", steps)

        assert "wasn't able to gather enough information" in summary


class TestReActPlannerReflection:
    """Tests for ReActPlanner reflection feature."""

    @pytest.mark.asyncio
    async def test_reflection_triggered(self):
        """Test that reflection is triggered every 3 iterations."""
        mock_llm = AsyncMock()
        mock_registry = MagicMock()

        # Return non-final actions for 5 iterations
        responses = []
        for i in range(5):
            responses.append(LLMResponse(
                content=json.dumps({
                    "thought": f"Iteration {i}",
                    "action": "search",
                    "action_input": {"query": "test"},
                    "is_final": False,
                }),
                usage={"total_tokens": 10},
            ))

        mock_llm.chat = AsyncMock(side_effect=responses)
        mock_registry.execute_tool = AsyncMock(return_value=("Result", None))

        planner = ReActPlanner(
            llm_client=mock_llm,
            tool_registry=mock_registry,
            max_iterations=5,
            enable_reflection=True,
        )
        result = await planner.execute("What is test?")

        # Verify reflection was attempted (iteration 3)
        # Check that messages include reflection prompt
        all_messages = []
        for call in mock_llm.chat.call_args_list:
            all_messages.extend(call[0][0])

        reflection_found = any(
            "Review your previous actions" in msg.content
            for msg in all_messages
            if hasattr(msg, "content")
        )
        assert reflection_found

    @pytest.mark.asyncio
    async def test_reflection_disabled(self):
        """Test with reflection disabled."""
        mock_llm = AsyncMock()
        mock_registry = MagicMock()

        responses = []
        for i in range(4):
            responses.append(LLMResponse(
                content=json.dumps({
                    "thought": f"Iteration {i}",
                    "action": "search",
                    "action_input": {"query": "test"},
                    "is_final": False,
                }),
                usage={"total_tokens": 10},
            ))

        mock_llm.chat = AsyncMock(side_effect=responses)
        mock_registry.execute_tool = AsyncMock(return_value=("Result", None))

        planner = ReActPlanner(
            llm_client=mock_llm,
            tool_registry=mock_registry,
            max_iterations=4,
            enable_reflection=False,
        )
        result = await planner.execute("What is test?")

        # Verify no reflection prompts
        all_messages = []
        for call in mock_llm.chat.call_args_list:
            all_messages.extend(call[0][0])

        reflection_found = any(
            "Review your previous actions" in msg.content
            for msg in all_messages
            if hasattr(msg, "content")
        )
        assert not reflection_found