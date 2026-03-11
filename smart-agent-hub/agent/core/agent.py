"""Agent Pipeline for Smart Agent Hub - Main agent orchestration."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any, AsyncGenerator, Optional

from agent.core.executor import Action as ExecutorAction
from agent.core.executor import Executor, Observation as ExecutorObservation
from agent.core.executor import SafetyGate
from agent.core.planner import ReActPlanner, ReActResult, ReActStep
from agent.core.state_manager import StateManager
from agent.llm.client import BaseLLMClient, LLMClient
from agent.mcp.client import MCPClient
from agent.mcp.tool_registry import ToolRegistry
from agent.storage.jsonl_logger import JSONLLogger


class Agent:
    """Main Agent for Smart Agent Hub.
    
    This agent orchestrates the full pipeline:
    1. Connect to MCP servers
    2. Initialize LLM client
    3. Execute ReAct planning loop
    4. Persist state and logs
    """
    
    def __init__(
        self,
        llm_provider: str = "qwen",
        llm_settings: Optional[dict[str, Any]] = None,
        mcp_server_configs: Optional[dict[str, dict[str, Any]]] = None,
        state_db_path: str = "data/db/agent_sessions.db",
        log_path: str = "data/logs/agent_traces.jsonl",
        max_iterations: int = 10,
        enable_reflection: bool = True,
        safety_approval: bool = False,
    ):
        """Initialize Agent.
        
        Args:
            llm_provider: LLM provider name.
            llm_settings: LLM configuration settings.
            mcp_server_configs: MCP server configurations.
            state_db_path: Path to state database.
            log_path: Path to JSONL log file.
            max_iterations: Maximum ReAct iterations.
            enable_reflection: Enable self-reflection.
            safety_approval: Require approval for dangerous tools.
        """
        self.llm_provider = llm_provider
        self.llm_settings = llm_settings or {}
        self.mcp_server_configs = mcp_server_configs or {}
        self.state_db_path = state_db_path
        self.log_path = log_path
        self.max_iterations = max_iterations
        self.enable_reflection = enable_reflection
        self.safety_approval = safety_approval
        
        # Components (initialized on connect)
        self.llm_client: Optional[BaseLLMClient] = None
        self.tool_registry: Optional[ToolRegistry] = None
        self.executor: Optional[Executor] = None
        self.planner: Optional[ReActPlanner] = None
        self.state_manager: Optional[StateManager] = None
        self.logger: Optional[JSONLLogger] = None
        self.mcp_clients: dict[str, MCPClient] = {}
        
        # Session state
        self.session_id: Optional[str] = None
        self.task_id: Optional[str] = None
        self._connected = False
    
    async def connect(self) -> None:
        """Connect to MCP servers and initialize components."""
        if self._connected:
            return
        
        # Initialize LLM client
        self.llm_client = LLMClient.create(
            provider=self.llm_provider,
            api_key=self.llm_settings.get("api_key"),
        )
        
        # Initialize tool registry
        self.tool_registry = ToolRegistry()
        
        # Connect to MCP servers and register tools
        for server_name, config in self.mcp_server_configs.items():
            client = MCPClient(config)
            await client.connect()
            self.mcp_clients[server_name] = client
            self.tool_registry.register_mcp_client(server_name, client)
        
        # Initialize executor
        safety_gate = SafetyGate(require_approval=self.safety_approval)
        self.executor = Executor(
            tool_registry=self.tool_registry,
            safety_gate=safety_gate,
        )
        
        # Initialize planner
        self.planner = ReActPlanner(
            llm_client=self.llm_client,
            tool_registry=self.tool_registry,
            max_iterations=self.max_iterations,
            enable_reflection=self.enable_reflection,
        )
        
        # Initialize state manager and logger
        self.state_manager = StateManager(db_path=self.state_db_path)
        self.logger = JSONLLogger(log_path=self.log_path)
        
        self._connected = True
    
    async def disconnect(self) -> None:
        """Disconnect from MCP servers and cleanup."""
        if not self._connected:
            return
        
        # Disconnect all MCP clients
        for client in self.mcp_clients.values():
            await client.disconnect()
        
        self.mcp_clients.clear()
        self._connected = False
    
    async def run(
        self,
        query: str,
        session_id: Optional[str] = None,
        context: Optional[str] = None,
    ) -> ReActResult:
        """Run the agent with a query.
        
        Args:
            query: User query to process.
            session_id: Optional session ID to continue.
            context: Optional context string.
            
        Returns:
            ReActResult with the final answer.
        """
        if not self._connected:
            await self.connect()
        
        # Create or load session
        self.session_id = session_id or str(uuid.uuid4())
        self.task_id = str(uuid.uuid4())
        
        # Save session
        self.state_manager.save_session(
            self.session_id,
            metadata={"query": query, "context": context},
        )
        
        # Save task
        self.state_manager.save_task(
            self.task_id,
            self.session_id,
            query,
            status="running",
        )
        
        # Log start
        self.logger.log({
            "type": "task_start",
            "session_id": self.session_id,
            "task_id": self.task_id,
            "query": query,
        })
        
        try:
            # Execute planning
            result = await self.planner.execute(query, context=context)
            
            # Update task status
            status = "completed" if result.success else "failed"
            self.state_manager.update_task_status(
                self.task_id,
                status,
                final_result=result.final_answer,
            )
            
            # Save steps to state manager
            for i, step in enumerate(result.steps):
                self.state_manager.save_step(
                    self.session_id,
                    self.task_id,
                    i,
                    thought=step.thought,
                    action=step.action,
                    action_input=step.action_input,
                    observation=step.observation,
                    error=step.error,
                    is_final=step.is_final,
                    final_answer=step.final_answer,
                )
                
                # Log each step
                if step.thought:
                    self.logger.log_thought(
                        self.session_id,
                        self.task_id,
                        step.thought,
                        i,
                    )
                if step.action:
                    self.logger.log_action(
                        self.session_id,
                        self.task_id,
                        step.action,
                        step.action_input or {},
                        i,
                    )
                if step.observation or step.error:
                    self.logger.log_observation(
                        self.session_id,
                        self.task_id,
                        step.observation or step.error,
                        0,
                        i,
                        error=step.error,
                    )
            
            # Log final answer
            self.logger.log_final_answer(
                self.session_id,
                self.task_id,
                result.final_answer,
                result.success,
            )
            
            return result
            
        except Exception as e:
            # Log error
            self.logger.log_error(
                self.session_id,
                self.task_id,
                str(e),
                error_type=type(e).__name__,
            )
            
            # Update task status
            self.state_manager.update_task_status(
                self.task_id,
                "failed",
                final_result=f"Error: {e}",
            )
            
            raise
    
    async def run_streaming(
        self,
        query: str,
        session_id: Optional[str] = None,
        context: Optional[str] = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Run the agent with streaming events.
        
        Args:
            query: User query to process.
            session_id: Optional session ID.
            context: Optional context string.
            
        Yields:
            Event dictionaries with type and content.
        """
        if not self._connected:
            await self.connect()
        
        # Create or load session
        self.session_id = session_id or str(uuid.uuid4())
        self.task_id = str(uuid.uuid4())
        
        # Save session
        self.state_manager.save_session(
            self.session_id,
            metadata={"query": query, "context": context},
        )
        
        # Save task
        self.state_manager.save_task(
            self.task_id,
            self.session_id,
            query,
            status="running",
        )
        
        # Log start
        self.logger.log({
            "type": "task_start",
            "session_id": self.session_id,
            "task_id": self.task_id,
            "query": query,
        })
        
        try:
            # Execute planning with streaming
            steps: list[ReActStep] = []
            total_tokens = 0
            
            # Build messages for ReAct loop
            tools_description = self.tool_registry.get_all_tools_description()
            from agent.llm.prompts import PromptTemplates
            system_prompt = PromptTemplates.format_react_system(tools_description)
            
            from agent.llm.client import LLMMessage
            messages = [
                LLMMessage(role="system", content=system_prompt),
                LLMMessage(role="user", content=f"Question: {query}"),
            ]
            
            if context:
                messages.insert(1, LLMMessage(role="user", content=f"Context: {context}"))
            
            retry_count = 0
            
            for iteration in range(self.max_iterations):
                # Get LLM response
                response = await self.llm_client.chat(messages)
                total_tokens += response.usage.get("total_tokens", 0)
                
                # Parse response
                try:
                    parsed = response.parse_json()
                except:
                    parsed = self.planner._extract_json(response.content)
                    if parsed is None:
                        retry_count += 1
                        if retry_count >= 3:
                            yield {
                                "type": "error",
                                "content": "Failed to parse LLM response",
                            }
                            break
                        continue
                
                step = ReActStep(
                    thought=parsed.get("thought", ""),
                    action=parsed.get("action"),
                    action_input=parsed.get("action_input"),
                    is_final=parsed.get("is_final", False),
                    final_answer=parsed.get("final_answer"),
                )
                
                # Yield thought
                if step.thought:
                    yield {"type": "thought", "content": step.thought}
                    self.logger.log_thought(
                        self.session_id,
                        self.task_id,
                        step.thought,
                        iteration,
                    )
                
                # Check if final
                if step.is_final:
                    steps.append(step)
                    yield {
                        "type": "final_answer",
                        "content": step.final_answer,
                    }
                    self.logger.log_final_answer(
                        self.session_id,
                        self.task_id,
                        step.final_answer,
                        True,
                    )
                    
                    # Save final state
                    self.state_manager.save_step(
                        self.session_id,
                        self.task_id,
                        iteration,
                        thought=step.thought,
                        is_final=True,
                        final_answer=step.final_answer,
                    )
                    self.state_manager.update_task_status(
                        self.task_id,
                        "completed",
                        final_result=step.final_answer,
                    )
                    return
                
                # Execute action
                if step.action:
                    yield {
                        "type": "action",
                        "tool": step.action,
                        "input": step.action_input or {},
                    }
                    self.logger.log_action(
                        self.session_id,
                        self.task_id,
                        step.action,
                        step.action_input or {},
                        iteration,
                    )
                    
                    # Execute tool
                    obs = await self.executor.execute(
                        ExecutorAction(
                            tool_name=step.action,
                            tool_input=step.action_input or {},
                        )
                    )
                    
                    step.observation = obs.result if obs.success else None
                    step.error = obs.error
                    
                    if obs.success:
                        yield {"type": "observation", "result": obs.result}
                        self.logger.log_observation(
                            self.session_id,
                            self.task_id,
                            obs.result,
                            obs.latency_ms,
                            iteration,
                        )
                    else:
                        yield {"type": "error", "error": obs.error}
                        self.logger.log_observation(
                            self.session_id,
                            self.task_id,
                            obs.error,
                            obs.latency_ms,
                            iteration,
                            error=obs.error,
                        )
                        retry_count += 1
                        
                        if retry_count >= 3:
                            yield {
                                "type": "error",
                                "content": f"Failed after {retry_count} retries",
                            }
                            break
                    
                    # Add to messages
                    from agent.llm.client import LLMMessage
                    messages.append(LLMMessage(
                        role="assistant",
                        content=str(parsed),
                    ))
                    messages.append(LLMMessage(
                        role="user",
                        content=f"Observation: {step.observation or step.error}",
                    ))
                
                steps.append(step)
                
                # Save step
                self.state_manager.save_step(
                    self.session_id,
                    self.task_id,
                    iteration,
                    thought=step.thought,
                    action=step.action,
                    action_input=step.action_input,
                    observation=step.observation,
                    error=step.error,
                )
            
            # Max iterations reached
            yield {
                "type": "error",
                "content": "Max iterations reached",
            }
            self.state_manager.update_task_status(
                self.task_id,
                "failed",
                final_result="Max iterations reached",
            )
            
        except Exception as e:
            yield {"type": "error", "error": str(e)}
            self.logger.log_error(
                self.session_id,
                self.task_id,
                str(e),
                error_type=type(e).__name__,
            )
            self.state_manager.update_task_status(
                self.task_id,
                "failed",
                final_result=f"Error: {e}",
            )
            raise
    
    def get_session_history(self, session_id: str) -> list[dict[str, Any]]:
        """Get session history.
        
        Args:
            session_id: Session ID.
            
        Returns:
            List of events.
        """
        return self.logger.get_session_events(session_id)
    
    def list_sessions(self) -> list[dict[str, Any]]:
        """List recent sessions.
        
        Returns:
            List of session summaries.
        """
        return self.state_manager.list_sessions()