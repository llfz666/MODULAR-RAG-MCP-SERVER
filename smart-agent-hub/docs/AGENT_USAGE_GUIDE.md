# Smart Agent Hub - 完整使用指南

## 📖 目录

1. [Agent 是什么？](#1-agent-是什么)
2. [核心功能模块](#2-核心功能模块)
3. [与 RAG 系统的联动](#3-与-rag-系统的联动)
4. [快速开始](#4-快速开始)
5. [使用示例](#5-使用示例)
6. [Dashboard 使用说明](#6-dashboard-使用说明)

---

## 1. Agent 是什么？

### 1.1 定位

**Smart Agent Hub** 是一个基于 **MCP 协议** 的自主智能体，它作为 RAG-MCP-SERVER 的客户端，通过调用 RAG Server 暴露的工具来完成复杂的多步推理任务。

### 1.2 核心能力

| 能力 | 描述 | 类比 |
|------|------|------|
| **任务拆解** | 将复杂问题分解为多个子任务 | 像人类把大问题拆成小步骤 |
| **多步推理** | 执行 Thought-Action-Observation 循环 | 思考→行动→观察→再思考 |
| **工具调用** | 自动发现并调用 MCP 工具 | 像使用手机 App 完成任务 |
| **记忆持久化** | 保存会话历史和长期经验 | 短期工作记忆 + 长期知识库 |
| **可观测性** | 完整记录执行过程 | 可追溯、可调试、可分析 |

### 1.3 架构关系

```
┌─────────────────────┐         MCP 协议          ┌─────────────────────────┐
│   Smart Agent Hub   │ ◄──────────────────────►  │  RAG-MCP-SERVER         │
│   (本项目的 Agent)   │                           │  (已存在的 RAG 系统)     │
│                     │                           │                         │
│  • Planner (规划器) │  调用工具：                │  暴露工具：              │
│  • Executor (执行器) │  • search()               │  • search()             │
│  • Memory (记忆)    │  • list_collections()     │  • list_collections()   │
│  • State (状态)     │  • preview_document()     │  • preview_document()   │
│                     │                           │  • compare_documents()  │
└─────────────────────┘                           └─────────────────────────┘
```

---

## 2. 核心功能模块

### 2.1 模块总览

```
smart-agent-hub/
├── agent/
│   ├── core/              # 核心逻辑
│   │   ├── planner.py     # ReAct 规划器
│   │   ├── executor.py    # 工具执行器
│   │   ├── state_manager.py # 状态管理
│   │   └── memory.py      # 记忆系统
│   ├── mcp/               # MCP 协议层
│   │   ├── client.py      # MCP 客户端
│   │   └── tool_registry.py # 工具注册表
│   ├── llm/               # LLM 接入
│   │   ├── client.py      # LLM 客户端
│   │   └── prompts.py     # Prompt 模板
│   └── storage/           # 存储层
│       ├── jsonl_logger.py # JSONL 轨迹
│       └── sqlite_store.py # SQLite 存储
└── dashboard/             # 可视化面板
    └── app.py             # Streamlit 应用
```

### 2.2 各模块详解

#### 🔷 Planner（规划器）

**职责**: 任务拆解和多步推理

**工作流程**:
```
用户查询 → 分析任务 → 生成思考 → 决定行动 → 执行工具 → 观察结果 → 循环...
```

**ReAct 循环**:
```
Thought: 我需要先查找 A 公司的信息
Action: search(query="A 公司", top_k=5)
Observation: [文档 1, 文档 2, ...]

Thought: 现在我需要查找 B 公司的信息
Action: search(query="B 公司", top_k=5)
Observation: [文档 3, 文档 4, ...]

Thought: 我已经有了双方信息，可以进行对比
Final Answer: A 公司和 B 公司的差异如下...
```

---

#### 🔷 Executor（执行器）

**职责**: 工具调用分发器

**功能**:
- 接收 Planner 的 Action 指令
- 调用对应的 MCP 工具
- 处理执行结果和错误
- 安全门控（危险操作需用户确认）

**安全门控示例**:
```python
# 危险操作需要用户确认
DESTRUCTIVE_TOOLS = {"delete_file", "execute_code", "write_file"}

⚠️ 危险操作确认：delete_file
参数：{"path": "data/important.txt"}
是否继续？(y/n): _
```

---

#### 🔷 MCP Client（MCP 客户端）

**职责**: 连接外部 MCP Server

**功能**:
- 通过 Stdio Transport 连接 MCP Server
- 自动发现可用工具列表
- 工具调用和结果返回

**连接流程**:
```python
# 1. 配置 Server
server_config = {
    "command": "python",
    "args": ["main.py"],
    "cwd": "../MODULAR-RAG-MCP-SERVER"
}

# 2. 建立连接
client = MCPClient(server_config)
await client.connect()

# 3. 获取工具列表
tools = client.get_available_tools()
# → [{"name": "search", "description": "...", "schema": {...}}, ...]

# 4. 调用工具
result = await client.call_tool("search", {"query": "RAG", "top_k": 5})
```

---

#### 🔷 Memory（记忆系统）

**双系统架构**:

| 类型 | 功能 | 存储方式 | 用途 |
|------|------|----------|------|
| **短期工作记忆** | 对话历史、当前上下文 | 内存/SQLite | 保持对话连贯性 |
| **长期经验记忆** | 历史任务、经验知识 | JSONL 文件 | 经验检索和复用 |

**记忆类型**:
- 📝 Conversation: 对话记录
- 💡 Experience: 经验知识
- 📚 Knowledge: 学到的知识

---

#### 🔷 State Manager（状态管理）

**职责**: SQLite 持久化

**数据库表结构**:
```sql
-- 会话表
sessions (
    session_id TEXT PRIMARY KEY,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    metadata TEXT
)

-- 任务表
tasks (
    task_id TEXT PRIMARY KEY,
    session_id TEXT,
    user_query TEXT,
    status TEXT,
    final_result TEXT
)

-- 步骤表
steps (
    step_index INTEGER,
    task_id TEXT,
    thought TEXT,
    action TEXT,
    observation TEXT,
    latency_ms REAL
)
```

**功能**:
- 保存会话进度
- 断点恢复
- 历史查询

---

#### 🔷 JSONL Logger（轨迹记录）

**职责**: 记录完整执行轨迹

**日志格式**:
```json
{"type": "thought", "session_id": "abc123", "content": "我需要搜索..."}
{"type": "action", "session_id": "abc123", "tool": "search", "input": {"query": "RAG"}}
{"type": "observation", "session_id": "abc123", "result": [...], "latency_ms": 123.45}
```

**用途**:
- 调试分析
- Dashboard 可视化
- 审计追溯

---

## 3. 与 RAG 系统的联动

### 3.1 联动架构

```
用户问题
    ↓
┌─────────────────────────────────────────┐
│         Smart Agent Hub                  │
│  ┌─────────────────────────────────┐    │
│  │  Planner: 分析任务，决定行动     │    │
│  └─────────────────────────────────┘    │
│              ↓                          │
│  ┌─────────────────────────────────┐    │
│  │  Executor: 调用 MCP 工具         │    │
│  └─────────────────────────────────┘    │
└─────────────┬───────────────────────────┘
              │ MCP JSON-RPC
              ↓
┌─────────────────────────────────────────┐
│         RAG-MCP-SERVER                   │
│  ┌─────────────────────────────────┐    │
│  │  search() - 检索知识库          │    │
│  │  list_collections() - 查看库列表 │    │
│  │  preview_document() - 预览文档   │    │
│  │  compare_documents() - 对比文档  │    │
│  └─────────────────────────────────┘    │
│              ↓                          │
│  ┌─────────────────────────────────┐    │
│  │  向量数据库 (ChromaDB)           │    │
│  │  BM25 索引                       │    │
│  └─────────────────────────────────┘    │
└─────────────────────────────────────────┘
```

### 3.2 工具调用流程

**示例场景**: "帮我对比一下 A 公司和 B 公司在 AI 战略上的差异"

```
Step 1: Agent 分析任务
┌─────────────────────────────────────┐
│ Thought: 用户想对比两家公司的 AI 战略  │
│ 我需要先查找 A 公司的相关信息         │
└─────────────────────────────────────┘
              ↓
Step 2: 调用 RAG search 工具
┌─────────────────────────────────────┐
│ Action: search(                      │
│   query="A 公司 AI 战略",              │
│   top_k=5                            │
│ )                                    │
└─────────────────────────────────────┘
              ↓ (MCP 协议)
┌─────────────────────────────────────┐
│ RAG Server 执行:                     │
│ 1. 语义检索 (Dense Retrieval)       │
│ 2. 关键词检索 (BM25)                │
│ 3. 混合排序 (RRF Fusion)            │
│ 4. 返回 Top 5 文档片段                │
└─────────────────────────────────────┘
              ↓
Step 3: Agent 接收结果
┌─────────────────────────────────────┐
│ Observation: [doc_a1, doc_a2, ...]  │
│ 获取了 A 公司的信息，现在查找 B 公司    │
└─────────────────────────────────────┘
              ↓
Step 4: 再次调用 search
┌─────────────────────────────────────┐
│ Action: search(                      │
│   query="B 公司 AI 战略",              │
│   top_k=5                            │
│ )                                    │
└─────────────────────────────────────┘
              ↓
Step 5: 调用 compare_documents
┌─────────────────────────────────────┐
│ Action: compare_documents(           │
│   doc_ids=[doc_a1, doc_b1],         │
│   aspect="AI 战略"                   │
│ )                                    │
└─────────────────────────────────────┘
              ↓
Step 6: 生成最终答案
┌─────────────────────────────────────┐
│ Final Answer:                        │
│ A 公司和 B 公司在 AI 战略上的主要差异... │
└─────────────────────────────────────┘
```

### 3.3 RAG 工具接口

| 工具名 | 描述 | 输入参数 | 返回结果 |
|--------|------|----------|----------|
| `search` | 检索知识库 | `query: str, top_k: int, collection: str` | `list[Chunk]` |
| `list_collections` | 查看知识库列表 | `pattern: str` | `list[str]` |
| `preview_document` | 预览文档 | `doc_id: str` | `DocumentPreview` |
| `compare_documents` | 对比文档 | `doc_ids: list[str], aspect: str` | `ComparisonResult` |

### 3.4 联动优势

| 优势 | 说明 |
|------|------|
| **解耦架构** | Agent 和 RAG 独立部署，互不影响 |
| **灵活扩展** | Agent 可连接多个 MCP Server |
| **标准化协议** | 基于 MCP 协议，兼容其他 MCP 工具 |
| **可观测性** | 完整记录每次工具调用 |

---

## 4. 快速开始

### 4.1 环境准备

```bash
# 1. 进入项目目录
cd smart-agent-hub

# 2. 安装依赖
pip install -e ".[dashboard]"

# 3. 配置 API Key
export QWEN_API_KEY=your_api_key
# 或编辑 config/settings.yaml
```

### 4.2 配置文件

**config/settings.yaml**:
```yaml
llm:
  provider: "qwen"
  model: "qwen3.5-plus"
  base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1"
  api_key: "${QWEN_API_KEY}"
  temperature: 0.0
  max_tokens: 4096

agent:
  max_iterations: 10
  enable_reflection: true
  enable_memory: true

storage:
  db_path: "data/db/agent_sessions.db"
  log_path: "data/logs/agent_traces.jsonl"
```

### 4.3 启动 Agent

```bash
# CLI 方式
python cli.py "帮我查找关于 RAG 的资料"

# 继续上一个会话
python cli.py --session-id abc123 "继续上一个问题"
```

### 4.4 启动 Dashboard

```bash
# 启动 Dashboard
streamlit run dashboard/app.py --server.port 8502

# 访问 http://localhost:8502
```

---

## 5. 使用示例

### 5.1 简单查询

```bash
# 单步检索
python cli.py "查找 RAG 相关的文档"
```

**执行流程**:
```
Thought: 用户想查找 RAG 相关文档
Action: search(query="RAG", top_k=5)
Observation: [chunk1, chunk2, chunk3, chunk4, chunk5]
Final Answer: 找到以下 RAG 相关文档：...
```

### 5.2 复杂任务

```bash
# 多步推理
python cli.py "对比 A 公司和 B 公司在 AI 战略上的差异"
```

**执行流程**:
```
Step 1: search("A 公司 AI 战略") → [doc_a1, doc_a2, ...]
Step 2: search("B 公司 AI 战略") → [doc_b1, doc_b2, ...]
Step 3: compare_documents([doc_a1, doc_b1], aspect="AI 战略")
Final Answer: A 公司和 B 公司的差异如下...
```

### 5.3 Python API

```python
import asyncio
from agent.core.planner import ReActPlanner
from agent.mcp.client import MCPClient
from agent.mcp.tool_registry import ToolRegistry
from agent.llm.client import LLMClient

async def main():
    # 1. 初始化 MCP Client
    rag_client = MCPClient({
        "command": "python",
        "args": ["main.py"],
        "cwd": "../MODULAR-RAG-MCP-SERVER"
    })
    await rag_client.connect()
    
    # 2. 注册工具
    registry = ToolRegistry()
    registry.register_mcp_client("rag", rag_client)
    
    # 3. 初始化 LLM
    llm = LLMClient.from_config()
    
    # 4. 初始化规划器
    planner = ReActPlanner(llm, registry)
    
    # 5. 执行任务
    query = "帮我查找关于 RAG 的资料"
    async for event in planner.plan_and_execute(query):
        if event["type"] == "thought":
            print(f"🤔 思考：{event['content']}")
        elif event["type"] == "action":
            print(f"🔧 调用 {event['tool']}: {event['input']}")
        elif event["type"] == "observation":
            print(f"📦 结果：{event['result']}")
        elif event["type"] == "final_answer":
            print(f"✅ 答案：{event['content']}")
    
    await rag_client.disconnect()

asyncio.run(main())
```

---

## 6. Dashboard 使用说明

### 6.1 页面总览

Dashboard 包含 5 个功能页面：

| 页面 | 功能 | 图标 |
|------|------|------|
| **Overview** | 总览统计 | 📊 |
| **Session History** | 会话历史浏览 | 📜 |
| **Execution Trace** | 执行流程可视化 | 🔍 |
| **Memory View** | 长期记忆管理 | 🧠 |
| **Settings** | 设置 | ⚙️ |

### 6.2 Overview 页面

**功能**:
- 总会话数、总任务数、已完成任务数、总步骤数
- 最近会话列表
- 快速操作（清除数据、刷新）

**指标说明**:
- **Total Sessions**: 创建的会话总数
- **Total Tasks**: 执行的任务总数
- **Completed**: 已完成的任务数
- **Total Steps**: 所有任务的步骤总数

### 6.3 Session History 页面

**功能**:
- 搜索会话（按查询内容）
- 查看会话详情
- 展开查看任务列表
- 可视化执行轨迹

**使用方式**:
1. 在搜索框输入关键词
2. 点击会话展开查看详情
3. 点击任务展开查看步骤
4. 点击 "Visualize Trace" 查看执行流程

### 6.4 Execution Trace 页面

**功能**:
- 选择会话和任务
- 查看完整执行流程
- 两种查看模式：
  - 📊 Visual Flow: 可视化流程图
  - 📋 Step List: 步骤列表

**Visual Flow 模式**:
```
🤔 Thought 1: 我需要先搜索...
└─ [思考内容]

🔧 Action 1: search
└─ {"query": "RAG", "top_k": 5}

📦 Observation 1:
└─ [检索结果]

...

✅ Final Answer:
└─ [最终答案]
```

### 6.5 Memory View 页面

**功能**:
- 查看长期记忆
- 按类型过滤（Conversation/Experience/Knowledge）
- 搜索记忆内容
- 查看重要性和访问次数

**记忆指标**:
- **Importance**: 重要性评分（0-1）
- **Access Count**: 被访问次数
- **Type**: 记忆类型

### 6.6 Settings 页面

**功能**:
- 查看数据路径配置
- 关于信息

---

## 7. 常见问题

### Q: 如何添加新的 MCP Server？

A: 在 `config/mcp_servers.yaml` 中添加新配置：

```yaml
servers:
  new_server:
    enabled: true
    command: "npx"
    args:
      - "-y"
      - "@mcp/new-server"
```

### Q: 如何调试 Agent 执行过程？

A: 有三种方式：
1. 查看 `data/logs/agent_traces.jsonl` 日志文件
2. 使用 Dashboard 的 Execution Trace 页面可视化查看
3. CLI 运行时添加 `--verbose` 参数

### Q: 如何限制 Agent 的最大执行轮数？

A: 在 `config/settings.yaml` 中设置：

```yaml
agent:
  max_iterations: 10  # 最多 10 轮思考 - 行动循环
```

### Q: Dashboard 和 RAG Dashboard 会冲突吗？

A: 不会。两个 Dashboard 使用不同端口：
- RAG Dashboard: 端口 8501
- Agent Dashboard: 端口 8502

同时启动时使用不同端口即可。

---

## 8. 总结

**Smart Agent Hub** 是一个强大的自主智能体框架，通过 MCP 协议与 RAG 系统联动，能够：

1. ✅ 自主拆解复杂任务
2. ✅ 调用 RAG 工具进行多步检索
3. ✅ 保存和恢复任务进度
4. ✅ 可视化执行过程

**核心价值**:
-  **智能规划**: ReAct 循环实现多步推理
- 🔗 **标准协议**: 基于 MCP 协议，易于扩展
- 💾 **持久化**: SQLite + JSONL 完整记录
- 📊 **可观测**: Dashboard 可视化监控

开始使用吧！🚀