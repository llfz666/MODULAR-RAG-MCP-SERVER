## 4. 核心模块实现

### 4.1 MCP Client 模块

```python
# agent/mcp/client.py
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from typing import Any

class MCPClient:
    """MCP 客户端 - 连接外部 MCP Server"""
    
    def __init__(self, server_config: dict):
        self.server_config = server_config
        self.session: Optional[ClientSession] = None
        self._stdio_context = None
        self._tools_cache: list[dict] = []
    
    async def connect(self):
        """连接到 MCP Server"""
        server_params = StdioServerParameters(
            command=self.server_config["command"],
            args=self.server_config.get("args", []),
            cwd=self.server_config.get("cwd", ".")
        )
        
        self._stdio_context = stdio_client(server_params)
        read, write = await self._stdio_context.__aenter__()
        
        self.session = ClientSession(read, write)
        await self.session.initialize()
        
        # 获取可用工具列表
        tools_response = await self.session.list_tools()
        self._tools_cache = [
            {"name": t.name, "description": t.description, "schema": t.inputSchema}
            for t in tools_response.tools
        ]
    
    async def disconnect(self):
        """断开连接"""
        if self.session:
            await self.session.close()
            self.session = None
        if self._stdio_context:
            await self._stdio_context.__aexit__(None, None, None)
    
    def get_available_tools(self) -> list[dict]:
        """获取可用工具列表"""
        return self._tools_cache
    
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """调用工具"""
        if not self.session:
            raise RuntimeError("Not connected to MCP Server")
        
        result = await self.session.call_tool(name, arguments)
        return result
```

### 4.2 工具注册表

```python
# agent/mcp/tool_registry.py
from typing import Callable, Any, Optional
import asyncio

class ToolRegistry:
    """工具注册表 - 管理所有可用工具"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tools = {}
            cls._instance._mcp_clients = {}
        return cls._instance
    
    def register_mcp_client(self, server_name: str, client: "MCPClient"):
        """注册 MCP Client"""
        self._mcp_clients[server_name] = client
    
    def get_tool_schema(self, tool_name: str) -> Optional[dict]:
        """获取工具 Schema"""
        for client in self._mcp_clients.values():
            for tool in client.get_available_tools():
                if tool["name"] == tool_name:
                    return tool
        return None
    
    def get_all_tools_description(self) -> str:
        """获取所有工具的描述（用于 Prompt）"""
        descriptions = []
        for client in self._mcp_clients.values():
            for tool in client.get_available_tools():
                desc = f"- {tool['name']}: {tool['description']}"
                descriptions.append(desc)
        return "\n".join(descriptions)
    
    async def execute_tool(self, tool_name: str, arguments: dict) -> Any:
        """执行工具调用"""
        for client in self._mcp_clients.values():
            for tool in client.get_available_tools():
                if tool["name"] == tool_name:
                    return await client.call_tool(tool_name, arguments)
        raise ValueError(f"Unknown tool: {tool_name}")
```

### 4.3 ReAct 规划器

```python
# agent/core/planner.py
from typing import Optional, AsyncGenerator
import json

class ReActPlanner:
    """ReAct 规划器 - 任务拆解和多步推理"""
    
    def __init__(self, llm_client, tool_registry: ToolRegistry):
        self.llm = llm_client
        self.tool_registry = tool_registry
        self.max_iterations = 10
    
    async def plan_and_execute(
        self, 
        query: str, 
        context: Optional[dict] = None
    ) -> AsyncGenerator[dict, None]:
        """
        执行 ReAct 循环
        
        产出:
        - {"type": "thought", "content": "..."}
        - {"type": "action", "tool": "...", "input": {...}}
        - {"type": "observation", "result": "..."}
        - {"type": "final_answer", "content": "..."}
        """
        # 构建系统 Prompt
        system_prompt = self._build_system_prompt()
        
        # 初始化对话历史
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query}
        ]
        
        for iteration in range(self.max_iterations):
            # Step 1: LLM 思考
            response = await self.llm.generate(messages, stream=False)
            thought = self._parse_thought(response)
            
            # 产出思考
            yield {"type": "thought", "content": thought.content}
            
            # 检查是否是最终答案
            if thought.is_final:
                yield {"type": "final_answer", "content": thought.final_answer}
                return
            
            # Step 2: 执行工具调用
            if thought.action:
                # 产出动作
                yield {
                    "type": "action", 
                    "tool": thought.action.tool_name,
                    "input": thought.action.tool_input
                }
                
                # 执行工具
                try:
                    result = await self.tool_registry.execute_tool(
                        thought.action.tool_name,
                        thought.action.tool_input
                    )
                    observation = Observation(
                        success=True,
                        result=result,
                        latency_ms=0
                    )
                except Exception as e:
                    observation = Observation(
                        success=False,
                        error=str(e),
                        latency_ms=0
                    )
                
                # 产出观察结果
                yield {"type": "observation", "result": observation.result}
                
                # 将结果添加到历史
                messages.append({
                    "role": "assistant",
                    "content": f"Thought: {thought.content}\nAction: {thought.action.tool_name}\nObservation: {observation.result}"
                })
    
    def _build_system_prompt(self) -> str:
        """构建系统 Prompt"""
        tools_desc = self.tool_registry.get_all_tools_description()
        
        return f"""你是一个智能助手，通过调用工具来帮助用户解决问题。

## 可用工具
{tools_desc}

## 输出格式
请按照以下格式思考和行动：

Thought: 你当前的思考过程
Action: 要调用的工具名称
Action Input: 工具的输入参数（JSON 格式）

或者，如果你已经有最终答案：

Thought: 我已经有了最终答案
Final Answer: 你的最终回答

## 注意事项
1. 每次只执行一个动作
2. 确保 Action Input 是有效的 JSON 格式
3. 如果工具返回错误，分析错误原因并尝试修正
4. 最多执行 10 轮思考 - 行动循环
"""
    
    def _parse_thought(self, response: str) -> Thought:
        """解析 LLM 响应"""
        # 检查是否是最终答案
        if "Final Answer:" in response:
            parts = response.split("Final Answer:")
            return Thought(
                content=parts[0].replace("Thought:", "").strip(),
                is_final=True,
                final_answer=parts[1].strip()
            )
        
        # 解析工具调用
        if "Action:" in response and "Action Input:" in response:
            thought_part = response.split("Action:")[0].replace("Thought:", "").strip()
            action_part = response.split("Action:")[1].split("Action Input:")[0].strip()
            input_part = response.split("Action Input:")[1].strip()
            
            try:
                input_json = json.loads(input_part)
            except:
                input_json = {"raw": input_part}
            
            return Thought(
                content=thought_part,
                action=Action(
                    tool_name=action_part,
                    tool_input=input_json
                )
            )
        
        # 默认情况
        return Thought(content=response)
```

### 4.4 执行器

```python
# agent/core/executor.py
import time
from typing import Any

class Executor:
    """执行器 - 工具调用分发器"""
    
    def __init__(self, tool_registry: ToolRegistry, safety_gate: "SafetyGate"):
        self.tool_registry = tool_registry
        self.safety_gate = safety_gate
    
    async def execute(self, action: Action) -> Observation:
        """执行工具调用"""
        start_time = time.time()
        
        # 安全检查
        if self.safety_gate.requires_approval(action.tool_name):
            # 等待用户批准
            approved = await self.safety_gate.wait_for_approval(action)
            if not approved:
                return Observation(
                    success=False,
                    error="User denied the action",
                    latency_ms=(time.time() - start_time) * 1000
                )
        
        # 执行工具
        try:
            result = await self.tool_registry.execute_tool(
                action.tool_name,
                action.tool_input
            )
            return Observation(
                success=True,
                result=result,
                latency_ms=(time.time() - start_time) * 1000
            )
        except Exception as e:
            return Observation(
                success=False,
                error=str(e),
                latency_ms=(time.time() - start_time) * 1000
            )

class SafetyGate:
    """安全门控 - 需要用户批准的危险操作"""
    
    DESTRUCTIVE_TOOLS = {"delete_file", "execute_code", "write_file"}
    
    def requires_approval(self, tool_name: str) -> bool:
        """检查是否需要批准"""
        return tool_name in self.DESTRUCTIVE_TOOLS
    
    async def wait_for_approval(self, action: Action) -> bool:
        """等待用户批准"""
        # 这里可以实现 CLI 确认或 Web 面板批准
        print(f"\n⚠️ 危险操作确认：{action.tool_name}")
        print(f"参数：{action.tool_input}")
        response = input("是否继续？(y/n): ")
        return response.lower() == "y"
```

### 4.5 状态管理器

```python
# agent/core/state_manager.py
import sqlite3
import json
from datetime import datetime
from typing import Optional

class StateManager:
    """状态管理器 - SQLite 持久化"""
    
    def __init__(self, db_path: str = "data/db/agent_sessions.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                task_id TEXT,
                step_index INTEGER,
                thought TEXT,
                action TEXT,
                observation TEXT,
                latency_ms REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def save_session(self, session_id: str, metadata: dict):
        """保存会话"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO sessions (session_id, updated_at, metadata)
            VALUES (?, CURRENT_TIMESTAMP, ?)
        """, (session_id, json.dumps(metadata)))
        
        conn.commit()
        conn.close()
    
    def save_step(self, session_id: str, task_id: str, step: dict):
        """保存步骤"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO steps (session_id, task_id, step_index, thought, action, observation, latency_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id,
            task_id,
            step.get("index", 0),
            json.dumps(step.get("thought", {})),
            json.dumps(step.get("action", {})),
            json.dumps(step.get("observation", {})),
            step.get("latency_ms", 0)
        ))
        
        conn.commit()
        conn.close()
    
    def load_session(self, session_id: str) -> Optional[dict]:
        """加载会话"""
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
    
    def get_session_steps(self, session_id: str) -> list[dict]:
        """获取会话步骤"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT thought, action, observation, latency_ms FROM steps
            WHERE session_id = ?
            ORDER BY step_index
        """, (session_id,))
        
        steps = []
        for row in cursor.fetchall():
            steps.append({
                "thought": json.loads(row[0]),
                "action": json.loads(row[1]),
                "observation": json.loads(row[2]),
                "latency_ms": row[3]
            })
        
        conn.close()
        return steps
```

### 4.6 JSONL 轨迹记录

```python
# agent/storage/jsonl_logger.py
import json
from datetime import datetime
from pathlib import Path

class JSONLLogger:
    """JSONL 轨迹记录器"""
    
    def __init__(self, log_path: str = "data/logs/agent_traces.jsonl"):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
    
    def log(self, event: dict):
        """记录事件"""
        event["timestamp"] = datetime.now().isoformat()
        
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    
    def log_thought(self, session_id: str, task_id: str, content: str):
        """记录思考"""
        self.log({
            "type": "thought",
            "session_id": session_id,
            "task_id": task_id,
            "content": content
        })
    
    def log_action(self, session_id: str, task_id: str, tool: str, input: dict):
        """记录动作"""
        self.log({
            "type": "action",
            "session_id": session_id,
            "task_id": task_id,
            "tool": tool,
            "input": input
        })
    
    def log_observation(self, session_id: str, task_id: str, result: any, latency_ms: float):
        """记录观察"""
        self.log({
            "type": "observation",
            "session_id": session_id,
            "task_id": task_id,
            "result": result,
            "latency_ms": latency_ms
        })
```

---
