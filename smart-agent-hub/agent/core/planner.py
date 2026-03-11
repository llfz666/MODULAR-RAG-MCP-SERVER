"""ReAct Planner for Smart Agent Hub."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional

from agent.llm.client import BaseLLMClient, LLMClient, LLMMessage, LLMResponse
from agent.llm.prompts import PromptTemplates
from agent.mcp.tool_registry import ToolRegistry


@dataclass
class ReActStep:
    """A single step in the ReAct loop."""
    thought: str
    action: Optional[str] = None
    action_input: Optional[dict] = None
    observation: Optional[str] = None
    error: Optional[str] = None
    is_final: bool = False
    final_answer: Optional[str] = None


@dataclass
class ReActResult:
    """Result of the ReAct planning process."""
    final_answer: str
    steps: list[ReActStep] = field(default_factory=list)
    total_tokens: int = 0
    success: bool = True
    error_message: Optional[str] = None


class ReActPlanner:
    """ReAct Planner - Implements Reasoning + Acting loop.

    This planner uses LLM to:
    1. Reason about the task
    2. Select and execute tools
    3. Observe results
    4. Iterate until completion
    """

    def __init__(
        self,
        llm_client: Optional[BaseLLMClient] = None,
        tool_registry: Optional[ToolRegistry] = None,
        max_iterations: int = 10,
        enable_reflection: bool = True,
        max_retries: int = 3,
    ):
        """Initialize ReAct Planner.

        Args:
            llm_client: LLM client for reasoning.
            tool_registry: Tool registry for tool execution.
            max_iterations: Maximum iterations before giving up.
            enable_reflection: Enable self-reflection for improvement.
            max_retries: Maximum retries for error recovery.
        """
        self.llm_client = llm_client
        self.tool_registry = tool_registry or ToolRegistry()
        self.max_iterations = max_iterations
        self.enable_reflection = enable_reflection
        self.max_retries = max_retries

    async def execute(
        self,
        question: str,
        context: Optional[str] = None,
    ) -> ReActResult:
        """Execute the ReAct loop to answer a question.

        Args:
            question: The user's question to answer.
            context: Optional additional context.

        Returns:
            ReActResult with the final answer and execution trace.
        """
        if not self.llm_client:
            return ReActResult(
                final_answer="LLM client not configured.",
                success=False,
                error_message="LLM client not configured.",
            )

        steps: list[ReActStep] = []
        total_tokens = 0
        retry_count = 0

        # Build system prompt with tools description
        tools_description = self.tool_registry.get_all_tools_description()
        system_prompt = PromptTemplates.format_react_system(tools_description)

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=f"Question: {question}"),
        ]

        if context:
            messages.insert(1, LLMMessage(role="user", content=f"Context: {context}"))

        for iteration in range(self.max_iterations):
            # Get LLM response
            response = await self.llm_client.chat(messages)
            total_tokens += response.usage.get("total_tokens", 0)

            try:
                parsed = json.loads(response.content)
            except json.JSONDecodeError as e:
                # Try to extract JSON from response
                parsed = self._extract_json(response.content)
                if parsed is None:
                    steps.append(ReActStep(
                        thought="Failed to parse LLM response as JSON.",
                        error=str(e),
                    ))
                    retry_count += 1
                    if retry_count >= self.max_retries:
                        return ReActResult(
                            final_answer="Failed to parse LLM responses.",
                            steps=steps,
                            total_tokens=total_tokens,
                            success=False,
                            error_message=f"JSON parse error: {e}",
                        )
                    continue

            step = ReActStep(
                thought=parsed.get("thought", ""),
                action=parsed.get("action"),
                action_input=parsed.get("action_input"),
                is_final=parsed.get("is_final", False),
                final_answer=parsed.get("final_answer"),
            )

            # Check if this is the final answer
            if step.is_final:
                steps.append(step)
                return ReActResult(
                    final_answer=step.final_answer or "No answer provided.",
                    steps=steps,
                    total_tokens=total_tokens,
                    success=True,
                )

            # Execute the action
            if step.action:
                observation, error = await self._execute_action(
                    step.action,
                    step.action_input or {},
                )

                if error:
                    step.error = error
                    retry_count += 1

                    # Error recovery
                    if retry_count >= self.max_retries:
                        steps.append(step)
                        return ReActResult(
                            final_answer=f"Failed after {retry_count} retries. Last error: {error}",
                            steps=steps,
                            total_tokens=total_tokens,
                            success=False,
                            error_message=error,
                        )

                    # Add error recovery prompt
                    previous_actions = self._format_previous_actions(steps)
                    recovery_prompt = PromptTemplates.format_error_recovery(
                        tool_name=step.action,
                        error_message=error,
                        question=question,
                        previous_actions=previous_actions,
                    )
                    messages.append(LLMMessage(role="user", content=recovery_prompt))
                else:
                    retry_count = 0  # Reset retry count on success

                step.observation = observation
                messages.append(LLMMessage(
                    role="assistant",
                    content=json.dumps(parsed),
                ))
                messages.append(LLMMessage(
                    role="user",
                    content=f"Observation: {observation}",
                ))

            steps.append(step)

            # Optional reflection
            if self.enable_reflection and iteration > 0 and iteration % 3 == 0:
                previous_actions = self._format_previous_actions(steps)
                reflection_prompt = PromptTemplates.format_reflection(
                    previous_actions=previous_actions,
                    question=question,
                )
                messages.append(LLMMessage(role="user", content=reflection_prompt))

        # Max iterations reached
        return ReActResult(
            final_answer=self._generate_summary(question, steps),
            steps=steps,
            total_tokens=total_tokens,
            success=False,
            error_message=f"Max iterations ({self.max_iterations}) reached.",
        )

    async def _execute_action(
        self,
        action: str,
        action_input: dict,
    ) -> tuple[Optional[str], Optional[str]]:
        """Execute a tool action.

        Args:
            action: Tool name.
            action_input: Tool input arguments.

        Returns:
            Tuple of (observation, error).
        """
        try:
            result = await self.tool_registry.execute_tool(
                action,
                action_input,
            )
            # Convert result to string observation
            if isinstance(result, dict):
                observation = str(result)
            elif hasattr(result, "__dict__"):
                observation = str(result.__dict__)
            else:
                observation = str(result)
            return observation, None
        except Exception as e:
            return None, str(e)

    def _format_previous_actions(self, steps: list[ReActStep]) -> str:
        """Format previous actions for reflection/error recovery."""
        lines = []
        for i, step in enumerate(steps):
            line = f"Step {i + 1}:"
            line += f"\n  Thought: {step.thought}"
            if step.action:
                line += f"\n  Action: {step.action}"
                line += f"\n  Input: {step.action_input}"
            if step.observation:
                line += f"\n  Observation: {step.observation}"
            if step.error:
                line += f"\n  Error: {step.error}"
            lines.append(line)
        return "\n".join(lines)

    def _extract_json(self, content: str) -> Optional[dict]:
        """Try to extract JSON from a string."""
        # Try to find JSON in the content
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(content[start:end])
            except json.JSONDecodeError:
                pass
        return None

    def _generate_summary(
        self,
        question: str,
        steps: list[ReActStep],
    ) -> str:
        """Generate a summary from the execution trace."""
        information = []
        for step in steps:
            if step.observation:
                information.append(f"- {step.observation}")

        if information:
            info_text = "\n".join(information)
            return f"Based on the gathered information:\n{info_text}\n\nHowever, I couldn't reach a complete answer within the iteration limit."
        else:
            return f"I wasn't able to gather enough information to answer: {question}"