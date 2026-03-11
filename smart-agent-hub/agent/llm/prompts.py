"""Prompt templates for ReAct agent."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class PromptTemplates:
    """Prompt templates for ReAct agent."""

    # ReAct system prompt
    REACT_SYSTEM: str = """You are a helpful AI assistant that uses ReAct (Reasoning + Acting) to solve tasks.

You have access to the following tools:

{tools_description}

To answer the user's question, you need to use the tools above. For each step:
1. Think about what needs to be done
2. Choose the appropriate tool
3. Provide the tool input
4. Observe the result
5. Repeat until you have enough information to answer

Format your response as JSON with the following structure:
{{
    "thought": "Your reasoning about what to do next",
    "action": "tool_name",
    "action_input": {{"param1": "value1", ...}},
    "is_final": false
}}

When you have enough information to provide a final answer:
{{
    "thought": "Your final reasoning",
    "action": null,
    "action_input": null,
    "is_final": true,
    "final_answer": "Your comprehensive answer"
}}

IMPORTANT RULES:
- Always respond with valid JSON
- Only use tools that are available
- If you don't need any tools, set is_final to true
- Explain your reasoning clearly in the "thought" field
"""

    # Reflection prompt for self-correction
    REFLECTION_PROMPT: str = """Review your previous actions and consider:

1. Have you gathered enough information to answer the question?
2. Are there any other tools you should try?
3. Is there a more efficient approach?

Previous actions:
{previous_actions}

Current question: {question}

Based on your reflection, what should you do next?"""

    # Error recovery prompt
    ERROR_RECOVERY_PROMPT: str = """An error occurred while executing the tool:

Tool: {tool_name}
Error: {error_message}

Please try a different approach or fix the tool input.

Current question: {question}
What you've tried so far: {previous_actions}

What should you do next?"""

    # Summary prompt for final answer
    SUMMARY_PROMPT: str = """Based on all the information gathered, provide a comprehensive answer.

Question: {question}

Information gathered:
{information}

Please provide a clear, well-structured answer."""

    @classmethod
    def format_react_system(cls, tools_description: str) -> str:
        """Format the ReAct system prompt with tools description."""
        return cls.REACT_SYSTEM.format(tools_description=tools_description)

    @classmethod
    def format_reflection(
        cls,
        previous_actions: str,
        question: str,
    ) -> str:
        """Format the reflection prompt."""
        return cls.REFLECTION_PROMPT.format(
            previous_actions=previous_actions,
            question=question,
        )

    @classmethod
    def format_error_recovery(
        cls,
        tool_name: str,
        error_message: str,
        question: str,
        previous_actions: str,
    ) -> str:
        """Format the error recovery prompt."""
        return cls.ERROR_RECOVERY_PROMPT.format(
            tool_name=tool_name,
            error_message=error_message,
            question=question,
            previous_actions=previous_actions,
        )

    @classmethod
    def format_summary(
        cls,
        question: str,
        information: str,
    ) -> str:
        """Format the summary prompt."""
        return cls.SUMMARY_PROMPT.format(
            question=question,
            information=information,
        )