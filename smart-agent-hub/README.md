# Smart Agent Hub

基于 MCP 协议的自主智能体框架，作为 RAG-MCP-SERVER 的 Client 端，通过调用 RAG Server 暴露的工具来完成复杂的多步推理任务。

## 快速开始

### 安装

```bash
# 安装基础依赖
pip install -e .

# 安装完整依赖（包含 MCP 和 Dashboard）
pip install -e ".[all]"
```

### 配置

1. 复制配置文件模板：
```bash
cp config/settings.yaml.example config/settings.yaml
```

2. 设置环境变量：
```bash
export QWEN_API_KEY=your_api_key
```

### 运行

```bash
# CLI 模式 - 基础用法
python cli.py "帮我查找关于 RAG 的资料"

# CLI 模式 - 流式输出
python cli.py --stream "帮我查找关于 RAG 的资料"

# CLI 模式 - 详细输出
python cli.py -v --stream "帮我查找关于 RAG 的资料"

# 继续之前的会话
python cli.py --session-id <session_id> "继续上一个问题"
```

## 项目结构

```
smart-agent-hub/
├── agent/
│   ├── core/
│   │   ├── __init__.py
│   │   ├── agent.py         # Agent Pipeline
│   │   ├── models.py        # Pydantic 数据模型
│   │   ├── settings.py      # 配置管理
│   │   ├── planner.py       # ReAct 规划器
│   │   ├── executor.py      # 工具执行器
│   │   └── state_manager.py # 状态管理
│   ├── mcp/
│   │   ├── __init__.py
│   │   ├── client.py        # MCP Client
│   │   └── tool_registry.py # 工具注册表
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── client.py        # LLM 客户端
│   │   └── prompts.py       # Prompt 模板
│   └── storage/
│       ├── __init__.py
│       └── jsonl_logger.py  # JSONL 日志
├── config/
│   └── settings.yaml        # 主配置
├── tests/
│   ├── unit/
│   └── integration/
├── data/
│   ├── db/
│   └── logs/
├── cli.py                   # CLI 入口
├── main.py                  # 主入口
├── pyproject.toml
└── README.md
```

## 核心功能

| 模块 | 描述 | 状态 |
|------|------|------|
| MCP Client | 连接 RAG-MCP-SERVER，自动发现工具 | ✅ 完成 |
| Tool Registry | 工具注册表，统一管理 MCP 工具 | ✅ 完成 |
| ReAct 规划器 | 任务拆解、多步推理、反思循环 | ✅ 完成 |
| 工具执行器 | 调用 MCP 工具、处理结果、错误恢复 | ✅ 完成 |
| SafetyGate | 安全门控，危险操作需用户确认 | ✅ 完成 |
| State Manager | SQLite 持久化、任务进度保存/恢复 | ✅ 完成 |
| JSONL Logger | 执行轨迹记录，支持回放分析 | ✅ 完成 |
| Agent Pipeline | 完整 ReAct 循环，支持流式输出 | ✅ 完成 |
| CLI 入口 | 命令行交互界面 | ✅ 完成 |
| 记忆系统 | 短期工作记忆 + 长期经验检索 | ⬜ 待开发 |
| Dashboard | Streamlit 可视化界面 | ⬜ 待开发 |

## 开发进度

### 阶段 A：工程骨架与测试基座 ✅

- [x] A1: 初始化目录树与最小可运行入口
- [x] A2: 引入 pytest 并建立测试目录约定
- [x] A3: 配置加载与校验（Settings）

### 阶段 B：MCP Client 层 ✅

- [x] B1: MCP Client 基础实现
- [x] B2: Tool Registry 工具注册表
- [x] B3: MCP Client 单元测试

### 阶段 C：ReAct Planner ✅

- [x] C1: LLM Client 抽象
- [x] C2: ReAct 循环实现
- [x] C3: Prompt 模板系统
- [x] C4: 错误处理与重试

### 阶段 D：状态管理与持久化 ✅

- [x] D1: SQLite 存储层
- [x] D2: State Manager
- [x] D3: JSONL Logger

### 阶段 E：Agent Pipeline ✅

- [x] E1: Agent 主流程实现
- [x] E2: 流式输出支持
- [x] E3: CLI 入口完善

### 阶段 F：测试覆盖 ✅

- [x] F1: Settings 测试 (16 个通过)
- [x] F2: MCP Client 测试 (24 个通过)
- [x] F3: ReAct Planner 测试 (23 个通过)
- [x] F4: Executor 测试 (14 个通过)
- [x] F5: State Manager & Logger 测试 (22 个通过)
- [x] F6: 总计 99 个单元测试通过

### 阶段 G：Dashboard 可视化 ⬜

- [ ] G1: Streamlit 基础架构
- [ ] G2: 会话历史页面
- [ ] G3: 执行追踪页面

## 测试

```bash
# 运行单元测试
pytest tests/unit/ -v

# 运行特定测试模块
pytest tests/unit/test_settings.py -v
pytest tests/unit/test_mcp_client.py -v
pytest tests/unit/test_react_planner.py -v
pytest tests/unit/test_executor.py -v
pytest tests/unit/test_state_manager.py -v

# 运行集成测试
pytest tests/integration/ -v

# 运行所有测试
pytest tests/ -v

# 生成覆盖率报告
pytest tests/ --cov=agent --cov-report=html
```

### 测试结果

```
============================ 99 passed, 1 warning in 1.20s =============================
```

## 配置文件

### config/settings.yaml

```yaml
settings:
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

  dashboard:
    enabled: true
    port: 8502

  mcp_servers:
    rag_server:
      enabled: true
      command: "python"
      args:
        - "main.py"
      cwd: "../MODULAR-RAG-MCP-SERVER"
      timeout: 60
      tools:
        - search
        - list_collections
        - preview_document
        - compare_documents
```

## CLI 使用示例

```bash
# 基础查询
python cli.py "帮我查找关于 RAG 的资料"

# 流式输出（实时显示思考过程）
python cli.py --stream "帮我对比两个文档"

# 详细模式（显示完整执行过程）
python cli.py -v --stream "帮我查找关于 RAG 的资料"

# 继续之前的会话
python cli.py --session-id abc123 "继续上一个问题"

# 指定配置文件
python cli.py -c config/custom.yaml "查询"
```

### 输出示例

```
🤔 思考中：帮我查找关于 RAG 的资料
📋 Session ID: new
⚙️  LLM Provider: qwen/qwen3.5-plus
🔧 MCP Servers: ['rag_server']

⏳ 处理中...

==================================================
✅ 答案：RAG (Retrieval-Augmented Generation) 是一种...
==================================================
```

## 与 RAG-MCP-SERVER 集成

Smart Agent Hub 通过 MCP 协议与 RAG-MCP-SERVER 通信：

```
┌─────────────────────┐         MCP 协议          ┌─────────────────────────┐
│   Smart Agent Hub   │ ◄──────────────────────►  │  RAG-MCP-SERVER         │
│   (本项目的 Agent)   │                           │  (已存在的 RAG 系统)     │
└────────────────────┘                           └─────────────────────────┘
```

确保 RAG-MCP-SERVER 的 `main.py` 可以作为独立进程启动。

## 数据持久化

### SQLite 数据库

存储会话、任务和执行步骤：

```sql
-- 会话表
sessions (session_id, metadata, created_at)

-- 任务表
tasks (task_id, session_id, user_query, status, final_result, created_at)

-- 步骤表
steps (step_id, session_id, task_id, step_index, thought, action, action_input, observation, error, is_final)
```

### JSONL 日志

记录完整的执行轨迹，支持事件回放：

```json
{"timestamp": "2024-01-01T00:00:00", "type": "thought", "session_id": "...", "task_id": "...", "content": "..."}
{"timestamp": "2024-01-01T00:00:01", "type": "action", "session_id": "...", "task_id": "...", "tool": "search", "input": {...}}
{"timestamp": "2024-01-01T00:00:02", "type": "observation", "session_id": "...", "task_id": "...", "result": "...", "latency_ms": 100}
```

## 许可证

MIT License