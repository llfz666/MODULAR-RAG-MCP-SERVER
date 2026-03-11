# Smart Agent Hub - 模式 1 实现规范

## 与 RAG-MCP-SERVER 集成的 MCP Client Agent

版本：1.0 (模式 1 - Agent 作为 RAG Client)

---

## 1. 项目概述

### 1.1 项目定位

本项目是一个**基于 MCP 协议的自主智能体框架**，作为 RAG-MCP-SERVER 的 Client 端，通过调用 RAG Server 暴露的工具来完成复杂的多步推理任务。

**核心关系**：
```
┌─────────────────────┐         MCP 协议          ┌─────────────────────────┐
│   Smart Agent Hub   │ ◄──────────────────────►  │  RAG-MCP-SERVER         │
│   (本项目的 Agent)   │                           │  (已存在的 RAG 系统)     │
│                     │                           │                         │
│  • Planner (规划器)  │  调用工具：                │  暴露工具：              │
│  • Executor (执行器) │  • search()               │  • search()             │
│  • Memory (记忆)     │  • list_collections()     │  • list_collections()   │
│  • State (状态)      │  • preview_document()     │  • preview_document()   │
│                      │  • compare_documents()    │  • compare_documents()  │
└─────────────────────┘                           └─────────────────────────┘
```

### 1.2 模式 1 架构说明

**模式 1 = Agent Client + RAG MCP Server（独立进程）**

- Agent 和 RAG 是两个独立的进程
- 通过 MCP 协议进行通信
- Agent 负责任务规划和多步推理
- RAG 负责知识检索和生成

### 1.3 核心功能

| 功能模块 | 描述 | 优先级 |
|----------|------|--------|
| **MCP Client** | 连接 RAG-MCP-SERVER，自动发现工具 | P0 |
| **ReAct 规划器** | 任务拆解、多步推理、反思循环 | P0 |
| **工具执行器** | 调用 MCP 工具、处理结果、错误恢复 | P0 |
| **状态管理** | SQLite 持久化、任务进度保存/恢复 | P1 |
| **记忆系统** | 短期工作记忆 + 长期经验检索 | P1 |
| **可观测性** | JSONL 轨迹记录 + Streamlit Dashboard | P2 |

---

## 2. 系统架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Smart Agent Hub                               │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                      CLI / API Input                          │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                              │                                        │
│                              ▼                                        │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                       Input Handler                           │   │
│  │  • 解析用户输入                                                │   │
│  │  • 加载会话上下文                                              │   │
│  │  • 复杂度判断（简单/复杂）                                      │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                              │                                        │
│                              ▼                                        │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                        Planner                                │   │
│  │  ┌─────────────────┐  ┌─────────────────┐                    │   │
│  │  │  Task Decomposer │  │  ReAct Loop     │                    │   │
│  │  │  任务拆解         │  │  思考 - 行动循环   │                    │   │
│  │  └─────────────────┘  └─────────────────┘                    │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                              │                                        │
│                              ▼                                        │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                       Executor                                │   │
│  │  ┌─────────────────┐  ┌─────────────────┐                    │   │
│  │  │  MCP Dispatcher │  │  Safety Gate    │                    │   │
│  │  │  工具调用        │  │  安全门控        │                    │   │
│  │  └─────────────────┘  └─────────────────┘                    │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                              │                                        │
│                              ▼                                        │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    MCP Protocol Layer                         │   │
│  │  • mcp-python-sdk                                             │   │
│  │  • Stdio Transport                                            │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                               │
                               │ MCP JSON-RPC
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        RAG-MCP-SERVER                                │
│  (已存在的项目，无需修改核心逻辑)                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 项目目录关系

采用**两个独立仓库**的方案：

```
parent-folder/
├── MODULAR-RAG-MCP-SERVER/    # RAG Server 项目（已存在）
│   ├── src/
│   ├── config/
│   ├── tests/
│   ├── main.py                # MCP Server 入口
│   └── ...
│
└── smart-agent-hub/           # Agent Client 项目（新建）
    ├── agent/
    │   ├── core/
    │   │   ├── __init__.py
    │   │   ├── planner.py           # ReAct 规划器
    │   │   ├── executor.py          # 工具执行器
    │   │   ├── state_manager.py     # 状态管理
    │   │   └── memory.py            # 记忆模块
    │   ├── mcp/
    │   │   ├── __init__.py
    │   │   ├── client.py            # MCP Client
    │   │   └── tool_registry.py     # 工具注册表
    │   ├── llm/
    │   │   ├── __init__.py
    │   │   ├── client.py            # LLM 客户端
    │   │   └── prompts.py           # Prompt 模板
    │   ├── storage/
    │   │   ├── __init__.py
    │   │   ├── sqlite_store.py      # SQLite 存储
    │   │   └── jsonl_logger.py      # JSONL 日志
    │   └── utils/
    │       ├── __init__.py
    │       └── helpers.py           # 辅助函数
    ├── dashboard/
    │   ├── __init__.py
    │   └── app.py                   # Streamlit 监控面板
    ├── config/
    │   ├── settings.yaml            # 主配置
    │   └── mcp_servers.yaml         # MCP Server 配置
    ├── tests/
    │   ├── unit/
    │   ├── integration/
    │   └── fixtures/
    ├── data/
    │   ├── db/
    │   │   └── agent_sessions.db    # SQLite 数据库
    │   └── logs/
    │       └── agent_traces.jsonl   # 轨迹日志
    ├── cli.py                       # CLI 入口
    ├── main.py                      # 主入口
    ├── pyproject.toml
    └── README.md
```

**优点**：
- 职责分离清晰：RAG Server 专注于知识检索，Agent Client 负责任务规划
- 可独立部署和扩展：两个项目可以独立开发、测试和部署
- Agent 可连接多个 MCP Server：未来可以扩展连接浏览器自动化工具、代码执行器等
- 符合 MCP 协议的客户端 - 服务器架构设计

**配置关联**：
Agent 项目通过 `config/mcp_servers.yaml` 配置 RAG Server 的路径：
```yaml
servers:
  rag_server:
    command: "python"
    args:
      - "main.py"
    cwd: "../MODULAR-RAG-MCP-SERVER"  # 相对路径指向 RAG 项目
```

---

## 3. 核心数据模型

### 3.1 Pydantic 模型定义

```python
# agent/core/models.py
from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime
from enum import Enum

class TaskStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class Action(BaseModel):
    """工具调用动作"""
    tool_name: str = Field(..., description="工具名称")
    tool_input: dict[str, Any] = Field(..., description="工具输入参数")
    
class Observation(BaseModel):
    """工具执行结果"""
    success: bool = Field(..., description="是否成功")
    result: Any = Field(None, description="工具返回结果")
    error: Optional[str] = Field(None, description="错误信息")
    latency_ms: float = Field(..., description="耗时 (毫秒)")

class Thought(BaseModel):
    """思考过程"""
    content: str = Field(..., description="思考内容")
    action: Optional[Action] = Field(None, description="决定的动作")
    is_final: bool = Field(False, description="是否是最终答案")
    final_answer: Optional[str] = Field(None, description="最终答案")

class TaskStep(BaseModel):
    """任务步骤"""
    step_id: str = Field(..., description="步骤 ID")
    thought: Thought = Field(..., description="思考")
    observation: Optional[Observation] = Field(None, description="观察结果")
    created_at: datetime = Field(default_factory=datetime.now)

class Task(BaseModel):
    """任务"""
    task_id: str = Field(..., description="任务 ID")
    session_id: str = Field(..., description="会话 ID")
    user_query: str = Field(..., description="用户查询")
    status: TaskStatus = Field(TaskStatus.CREATED, description="状态")
    steps: list[TaskStep] = Field(default_factory=list, description="步骤列表")
    final_result: Optional[str] = Field(None, description="最终结果")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

class AgentState(BaseModel):
    """Agent 状态"""
    session_id: str
    current_task: Optional[Task] = None
    conversation_history: list[dict] = Field(default_factory=list)
    short_term_memory: list[str] = Field(default_factory=list)
```

---

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

## 5. 配置文件

### 5.1 主配置 (config/settings.yaml)

```yaml
# Smart Agent Hub 配置

llm:
  provider: "qwen"  # openai, azure, ollama, deepseek, qwen
  model: "qwen3.5-plus"
  base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1"
  api_key: "${QWEN_API_KEY}"  # 支持环境变量
  temperature: 0.0
  max_tokens: 4096

agent:
  max_iterations: 10
  enable_reflection: true
  enable_memory: true

storage:
  db_path: "data/db/agent_sessions.db"
  log_path: "data/logs/agent_traces.jsonl"

dashboard:
  enabled: true
  port: 8502
```

### 5.2 MCP Server 配置 (config/mcp_servers.yaml)

```yaml
# MCP Server 配置

servers:
  # RAG-MCP-SERVER 配置
  rag_server:
    enabled: true
    command: "python"
    args:
      - "main.py"
    cwd: "../MODULAR-RAG-MCP-SERVER"  # RAG 项目路径
    timeout: 60
    tools:
      - search
      - list_collections
      - preview_document
      - compare_documents

  # 其他 MCP Server（可选）
  # browser_server:
  #   enabled: false
  #   command: "npx"
  #   args:
  #     - "-y"
  #     - "@modelcontextprotocol/server-puppeteer"
```

---

## 6. 使用示例

### 6.1 CLI 使用

```bash
# 启动 Agent
python cli.py "帮我对比一下 A 公司和 B 公司在 AI 战略上的差异"

# 指定会话继续
python cli.py --session-id abc123 "继续上一个问题"
```

### 6.2 Python API 使用

```python
from agent.core.planner import ReActPlanner
from agent.mcp.client import MCPClient
from agent.mcp.tool_registry import ToolRegistry

async def main():
    # 初始化 MCP Client
    rag_client = MCPClient({
        "command": "python",
        "args": ["main.py"],
        "cwd": "../MODULAR-RAG-MCP-SERVER"
    })
    await rag_client.connect()
    
    # 注册工具
    registry = ToolRegistry()
    registry.register_mcp_client("rag", rag_client)
    
    # 初始化规划器
    planner = ReActPlanner(llm_client, registry)
    
    # 执行任务
    async for event in planner.plan_and_execute("帮我查找关于 RAG 的资料"):
        if event["type"] == "thought":
            print(f"🤔 思考：{event['content']}")
        elif event["type"] == "action":
            print(f"🔧 调用 {event['tool']}: {event['input']}")
        elif event["type"] == "observation":
            print(f"📦 结果：{event['result']}")
        elif event["type"] == "final_answer":
            print(f"✅ 答案：{event['content']}")
    
    await rag_client.disconnect()
```

### 6.3 典型执行流程

```
用户查询："对比 A 公司和 B 公司在 AI 战略上的差异"

Agent 执行流程:
┌─────────────────────────────────────────────────────────────┐
│ Step 1: Thought                                             │
│ "我需要先查找 A 公司和 B 公司的 AI 战略信息"                      │
├─────────────────────────────────────────────────────────────┤
│ Step 2: Action → search("A 公司 AI 战略")                      │
│ Step 2: Observation → [doc_a1, doc_a2, ...]                 │
├─────────────────────────────────────────────────────────────┤
│ Step 3: Action → search("B 公司 AI 战略")                      │
│ Step 3: Observation → [doc_b1, doc_b2, ...]                 │
├─────────────────────────────────────────────────────────────┤
│ Step 4: Thought                                             │
│ "我已经获取了双方的信息，现在需要对比"                          │
├─────────────────────────────────────────────────────────────┤
│ Step 5: Action → compare_documents(                          │
│   doc_ids=[doc_a1, doc_b1],                                  │
│   aspect="AI 战略"                                            │
│ )                                                            │
│ Step 5: Observation → "对比结果..."                          │
├─────────────────────────────────────────────────────────────┤
│ Step 6: Final Answer                                        │
│ "A 公司和 B 公司在 AI 战略上的主要差异如下：..."                  │
└─────────────────────────────────────────────────────────────┘
```

---

## 7. 与 RAG-MCP-SERVER 的集成

### 7.1 RAG Server 需要暴露的工具

| 工具名 | 描述 | 输入参数 | 返回结果 |
|--------|------|----------|----------|
| `search` | 检索知识库 | `query: str, top_k: int, collection: str` | `list[Chunk]` |
| `list_collections` | 查看知识库列表 | `pattern: str` | `list[str]` |
| `preview_document` | 预览文档 | `doc_id: str` | `DocumentPreview` |
| `compare_documents` | 对比文档 | `doc_ids: list[str], aspect: str` | `ComparisonResult` |

### 7.2 RAG Server 配置要求

确保 RAG-MCP-SERVER 的 `main.py` 可以作为独立进程启动：

```python
# RAG-MCP-SERVER/main.py
import asyncio
from src.mcp_server.server import create_server

async def main():
    server = create_server()
    
    # 注册工具
    @server.tool(name="search")
    async def search(query: str, top_k: int = 10) -> list:
        ...
    
    @server.tool(name="list_collections")
    async def list_collections(pattern: str = ".*") -> list[str]:
        ...
    
    await server.run()

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 8. 测试方案

### 8.1 单元测试

```python
# tests/unit/test_planner.py
import pytest
from agent.core.planner import ReActPlanner

@pytest.mark.asyncio
async def test_parse_thought_final_answer():
    planner = ReActPlanner(None, None)
    response = """Thought: 我已经有了最终答案
Final Answer: 这是答案内容"""
    
    thought = planner._parse_thought(response)
    assert thought.is_final == True
    assert thought.final_answer == "这是答案内容"

@pytest.mark.asyncio
async def test_parse_thought_action():
    planner = ReActPlanner(None, None)
    response = """Thought: 我需要搜索
Action: search
Action Input: {"query": "RAG", "top_k": 5}"""
    
    thought = planner._parse_thought(response)
    assert thought.action.tool_name == "search"
    assert thought.action.tool_input == {"query": "RAG", "top_k": 5}
```

### 8.2 集成测试

```python
# tests/integration/test_mcp_rag.py
import pytest
from agent.mcp.client import MCPClient

@pytest.mark.asyncio
async def test_connect_to_rag_server():
    client = MCPClient({
        "command": "python",
        "args": ["main.py"],
        "cwd": "../MODULAR-RAG-MCP-SERVER"
    })
    
    await client.connect()
    
    tools = client.get_available_tools()
    assert len(tools) > 0
    assert any(t["name"] == "search" for t in tools)
    
    await client.disconnect()
```

---

## 9. 项目排期

> **排期原则**
> 
> - **1 小时一个可验收增量**：每个小阶段（≈1h）都必须同时给出"验收标准 + 测试方法"。
> - **先打通主闭环，再完善细节**：优先实现"可运行的端到端路径"，再逐步优化。
> - **TDD 开发**：每个模块实现的同时编写对应的单元测试。

### 阶段总览（大阶段 → 目的）

| 阶段 | 名称 | 目的 | 预计时间 |
|------|------|------|----------|
| **阶段 A** | 工程骨架与测试基座 | 建立可运行、可配置、可测试的工程骨架 | 1 天 |
| **阶段 B** | MCP Client 层 | 实现 MCP 协议客户端，连接 RAG Server | 2 天 |
| **阶段 C** | ReAct Planner | 实现任务拆解和多步推理能力 | 3 天 |
| **阶段 D** | 状态管理与持久化 | SQLite 存储、断点恢复 | 2 天 |
| **阶段 E** | Dashboard 可视化 | Streamlit 监控面板 | 2 天 |
| **阶段 F** | 端到端验收 | 完整测试与文档收口 | 2 天 |

---

### 📊 进度跟踪表

> **状态说明**：`[ ]` 未开始 | `[~]` 进行中 | `[x]` 已完成
> 
> **更新时间**：每完成一个子任务后更新对应状态

#### 阶段 A：工程骨架与测试基座

| 任务编号 | 任务名称 | 状态 | 完成日期 | 备注 |
|---------|---------|------|---------|------|
| A1 | 初始化目录树与最小可运行入口 | [ ] | - | 目录结构、配置文件、main.py |
| A2 | 引入 pytest 并建立测试目录约定 | [ ] | - | pytest 配置、tests/目录结构 |
| A3 | 配置加载与校验（Settings） | [ ] | - | 配置加载、校验与单元测试 |

#### 阶段 B：MCP Client 层

| 任务编号 | 任务名称 | 状态 | 完成日期 | 备注 |
|---------|---------|------|---------|------|
| B1 | MCP Client 基础实现 | [ ] | - | Stdio Transport 连接 |
| B2 | Tool Registry 工具注册表 | [ ] | - | 工具发现与路由 |
| B3 | MCP Client 单元测试 | [ ] | - | Mock 测试、连接测试 |

#### 阶段 C：ReAct Planner

| 任务编号 | 任务名称 | 状态 | 完成日期 | 备注 |
|---------|---------|------|---------|------|
| C1 | LLM Client 抽象 | [ ] | - | 支持多 LLM Provider |
| C2 | ReAct 循环实现 | [ ] | - | Thought-Action-Observation |
| C3 | Prompt 模板系统 | [ ] | - | 系统 Prompt、工具描述注入 |
| C4 | 错误处理与重试 | [ ] | - | 工具调用失败恢复 |

#### 阶段 D：状态管理与持久化

| 任务编号 | 任务名称 | 状态 | 完成日期 | 备注 |
|---------|---------|------|---------|------|
| D1 | SQLite 存储层 | [ ] | - | 会话表、步骤表 |
| D2 | State Manager | [ ] | - | 保存/恢复会话 |
| D3 | JSONL Logger | [ ] | - | 轨迹记录 |

#### 阶段 E：Dashboard 可视化

| 任务编号 | 任务名称 | 状态 | 完成日期 | 备注 |
|---------|---------|------|---------|------|
| E1 | Streamlit 基础架构 | [ ] | - | 多页面应用 |
| E2 | 会话历史页面 | [ ] | - | 查看历史会话 |
| E3 | 执行追踪页面 | [ ] | - | Thought-Action 可视化 |

#### 阶段 F：端到端验收

| 任务编号 | 任务名称 | 状态 | 完成日期 | 备注 |
|---------|---------|------|---------|------|
| F1 | 集成测试 | [ ] | - | 连接 RAG Server 测试 |
| F2 | CLI 入口 | [ ] | - | 命令行工具 |
| F3 | README 文档 | [ ] | - | 使用指南 |

---

## 10. 总结

本规范定义了**模式 1（Agent Client + RAG MCP Server）**的完整实现方案：

1. **架构清晰**：Agent 和 RAG 是独立进程，通过 MCP 协议通信
2. **接口明确**：定义了 MCP Client、Planner、Executor 等核心模块的接口
3. **数据模型**：使用 Pydantic 定义强类型的数据模型
4. **持久化**：SQLite 存储状态，JSONL 记录轨迹
5. **可扩展**：支持添加更多 MCP Server 和工具

按照此规范实现后，Agent 能够：
- 自主拆解复杂任务
- 调用 RAG 工具进行多步检索
- 保存和恢复任务进度
- 可视化执行过程

---

## 附录 A：快速开始

```bash
# 1. 克隆项目
git clone https://github.com/your-repo/smart-agent-hub.git
cd smart-agent-hub

# 2. 安装依赖
pip install -e .

# 3. 配置环境变量
export QWEN_API_KEY=your_api_key

# 4. 启动 Agent
python cli.py "帮我查找 RAG 相关资料"
```

## 附录 B：常见问题

**Q: 如何添加新的 MCP Server？**
A: 在 `config/mcp_servers.yaml` 中添加新配置，ToolRegistry 会自动发现。

**Q: 如何调试 Agent 执行过程？**
A: 查看 `data/logs/agent_traces.jsonl` 或使用 Dashboard 可视化查看。

**Q: 如何限制 Agent 的最大执行轮数？**
A: 在 `config/settings.yaml` 中设置 `agent.max_iterations`。