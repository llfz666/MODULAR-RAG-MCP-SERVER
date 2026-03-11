智能代理框架深度设计版本 0.2 (Inspired by OpenClaw)

# 目录

1. 项目概述
2. 设计理念
3. 核心特点
4. 技术选型
5. 测试方案
6. 系统架构与模块设计
7. 项目排期
8. 可扩展性与未来展望

---

## 1. 项目概述

本项目是一个基于任务编排（Orchestration）与模型上下文协议（MCP）设计的自主智能体（Autonomous Agent）框架。其核心目标是搭建一个能够自主理解复杂指令、拆解任务、并调用外部工具（特别是集成之前的 RAG 知识库）来解决问题的智能中枢。

### 设计理念

**核心定位：从"检索"迈向"执行"（From Retrieval to Action）**

本项目是 RAG 知识库项目的进阶版。如果说 RAG 是让 AI 拥有"记忆"，那么本项目就是让 AI 拥有"双手"。通过仿照 OpenClaw 的轻量化、模块化设计，我们将探索 Agent 开发中最核心的三个命题：如何规划路径、如何使用工具、如何管理长期状态。

---

## 2. 核心特点 (Core Features)

本框架在设计上拒绝"黑盒调用"，强调逻辑的透明性与执行的鲁棒性。以下是四大核心模块的详细技术实现方案：

### 2.1 智能规划与多模式执行 (Advanced Planning & Execution)

Agent 的大脑不仅需要"思考"，更需要根据任务难度选择合适的"思维模式"。

**动态任务拆解（Hierarchical Task Decomposition）：**
- **方法**：采用 Planner-Executor 二元架构。
- **实现**：当接收到复杂指令时，Planner 利用 LLM Reasoning 将其拆解为有序的 DAG 任务流。
- **支持版本**：支持线性执行和并行执行两种模式。
- **核心逻辑**：每一轮循环都强制包含 Thought（当前心理状态）、Action（决定调用的工具）、Observation（工具返回的结果）。

**反思机制（Reflexion）：** 引入"自我修正"环节。若工具调用返回错误，Agent 会在 Observation 后进行 Self-Correction，尝试更换参数或寻找备选路径。

**思维链模式（CoT & ToT Support）：** 针对逻辑严密任务，强制开启 Step-by-Step 验证。支持 ToT 实验性功能，对于关键决策生成多个分支并评估最优解。

### 2.2 深度 MCP 工具集成 (Enterprise-Grade MCP Tooling)

本项目作为标准的 MCP Client，通过统一协议打通物理世界的边界。

- **原生支持 MCP 协议**：
  - 实现方法：集成 mcp-python-sdk（v1.0+）
  - 传输支持：支持通过 Stdio 或 HTTP 传输协议连接外部 Server
  - 即插即用：支持动态扫描，只需配置 config/mcp_servers.yaml 中的启动路径

- **RAG 联动工具**：
  - 专用连接器：默认预置连接到 Smart Knowledge Hub 的工具
  - 方法：通过调用 query_knowledge_hub 工具，Agent 可以获取经过 Rerank 优化后的私有文档上下文

- **工具契约与校验**：
  - 技术选型：使用 Pydantic v2 进行强类型校验
  - 自动翻译：系统自动将 Python 函数类型提示转换为 LLM 识别的 JSON Schema

### 2.3 白盒化追踪与可观测性 (Full-Stack Observability)

Agent 的执行过程往往是不可测的，本项目通过"全链路白盒化"解决这一难题。

**思维轨迹可视化（Thought Trace）：**
- 记录内容：详细记录 LLM 每一轮的 Prompt、Raw Output 以及解析后的 Action
- 存储格式：采用 JSON Lines 实时追加，确保在长任务中即使程序中断也能保留完整日志

**执行瀑布流（Execution Waterfall）：**
- 功能：在控制台或 Dashboard 中展示任务耗时
- 方法：通过装饰器自动统计 LLM 推理耗时、工具调用耗时及网络开销

**人工介入检查点（HITL）：**
- 安全分级：Read-Only 工具自动执行；Destructive 工具强制触发 Wait-for-Approval 状态
- 交互方式：支持通过终端 CLI 确认或可视化面板点击"批准/修改/拒绝"

### 2.4 混合记忆与上下文管理 (Hybrid Memory & Context)

解决 Agent"转头就忘"和"上下文爆炸"的平衡问题。

- **短期工作记忆**：
  - 存储：内存存储当前任务的所有步骤
  - 管理：支持滑动窗口或基于摘要的截断，防止 Token 溢出

- **长期状态存储**：
  - 数据库：采用 SQLite（wal 模式）
  - 内容：记录会话 ID、用户偏好、已完成的任务里程碑

- **经验检索增强**：
  - 方法：Agent 完成复杂任务后，可选择将"成功路径"存储回 RAG 向量库
  - 复用：下次遇到类似任务时，优先检索历史成功的思考链路

---

## 3. 技术选型 (Tech Stack)

### 3.1 LLM 策略：分层推理架构

| 层级 | 选型 | 用途 | 要求 |
|------|------|------|------|
| **决策层** | GPT-4o, Claude 3.5 Sonnet 或 DeepSeek-V3 | 负责复杂的任务拆解、ReAct 循环中的 Thought 生成、以及对工具返回结果的深度总结 | 具备极强的指令遵循能力和逻辑推理能力 |
| **执行层** | GPT-4o-mini, Llama-3.1-8B 或 DeepSeek-Chat | 负责简单的格式转换、从 Observation 中提取关键词、以及生成非关键性的 UI 文案 | 低延迟、低成本 |

**统一调用协议**：采用 OpenAI-Compatible API，通过配置 base_url 即可无缝切换国内外不同厂商的后端。

### 3.2 核心中间件与通信协议

**工具协议：Model Context Protocol（MCP）：**
- SDK 选型：mcp-python-sdk
- 传输层：默认采用 Stdio Transport，支持 HTTP SSE Transport
- 动态性：利用 SDK 的 list_tools 能力实现工具的自发现

**并发控制：Python Asyncio：**
- 应用场景：Agent 在执行并行任务时，通过 asyncio.gather 同时调用多个 MCP 工具
- 流式处理：全链路支持 AsyncGenerator，确保 Agent 的思考过程和执行状态能以流式反馈给前端

### 3.3 状态管理与数据持久化

**工作流状态机：Pydantic v2：**
- 作用：定义 Task、Action、Observation 和 AgentState 的强类型模型
- 优势：利用 Pydantic 的序列化能力，将当前内存中的所有变量快照化

**持久化存储：SQLite（WAL Mode）：**
- 位置：data/db/agent_sessions.db
- 表结构设计：
  - sessions：记录会话元数据
  - steps：记录每一轮 ReAct 的 trace_id、输入、输出、耗时和状态
  - checkpoints：存储序列化后的状态快照，支持任务回滚
- 优势：本地文件存储，无需配置数据库服务，且 WAL 模式支持高性能的并发读写

### 3.4 可观测性与日志体系

**轨迹记录：JSON Lines：**
- 方案：所有 Thought-Action-Observation 链条实时追加写入 logs/agent_traces.jsonl
- 理由：结构化程度高，方便 Dashboard 进行实时解析和瀑布流渲染

**可视化面板：Streamlit：**
- 功能：构建本地 Web UI，用于监控 Agent 的思考过程、手动审批高风险操作、查看工具调用统计
- 理由：开发效率极高，内置对多模态内容的优秀支持

### 3.5 辅助工具与库

| 类别 | 库名 | 具体用途 |
|------|------|----------|
| 数据校验 | pydantic | 确保 LLM 返回的 Tool Call 参数符合预期 |
| 异步工具 | httpx | 处理所有非 MCP 协议的外部 API 请求 |
| 日期处理 | pendulum | 处理跨时区的任务排期与时间感知 |
| 图标/UI | lucide-react | 在 Dashboard 中用于区分不同类型的工具 |
| 环境管理 | python-dotenv | 管理 API Key 及敏感配置 |

---

## 4. 测试方案 (Testing Strategy)

Agent 系统的测试极具挑战性，因为它涉及非确定性的推理过程。本方案采用"分层自动化测试 + 确定性 Mock + 轨迹回归"的组合策略。

### 4.1 单元测试：核心组件的"白盒"校验

- **协议解析器测试**：
  - 验证解析器是否能准确从 LLM 的 Raw Text 中提取 Thought、Action 和 Action Input
  - 测试包含异常换行、缺失括号、多余 Markdown 标记的非法字符串

- **状态机转移测试**：
  - 验证任务从 Created -> Running -> WaitingForApproval -> Completed 的流转逻辑
  - 模拟工具执行超时或被用户拒绝的情况

- **Prompt 模板测试**：
  - 检查变量注入后，最终生成的 Prompt 是否符合 Token 长度限制和语法规范

### 4.2 集成测试：工具调用的"闭环"验证

- **MCP 工具自发现测试**：
  - 使用 pytest-asyncio 启动一个 Mock MCP Server
  - 验证 Agent 能否通过 list_tools 自动识别出工具名及参数 Schema

- **并发工具调用测试**：
  - 给出一个需要同时查询天气和日程的任务
  - 验证 asyncio.gather 是否被正确触发，且多个工具返回的结果能被正确汇聚

- **持久化回归测试**：
  - 执行一半任务时强行关闭进程
  - 验证从 SQLite 读取 Checkpoint 后，Agent 能否恢复到之前的 Thought 阶段继续执行

### 4.3 Agent 特有测试：确定性与鲁棒性

- **金点路径回归**：
  - 使用 Mock LLM，预设一系列 LLM 的响应，模拟完整的"成功推理序列"
  - 确保在代码重构后，Agent 依然能按照预期的逻辑步骤完成任务

- **异常恢复测试**：
  - 模拟工具返回 Permission Denied 或 Invalid Argument
  - 期望 Agent 的下一轮 Thought 应包含对错误的分析，并尝试修改参数再次调用

- **人机交互门控测试**：
  - 触发 Destructive 类工具
  - 验证 Agent 必须进入挂起状态，直到收到 Mock 的 Approve 信号后才执行物理动作

### 4.4 评估指标：量化 Agent 的"聪明程度"

- **任务成功率**：针对一组标准测试集，统计 Agent 成功达到目标状态的比例
- **推理步骤效率**：完成同一任务所需的平均 ReAct 轮数
- **Token 成本监控**：记录单次任务消耗的 Input/Output Token

### 4.5 测试工具链与环境

| 工具 | 用途 | 备注 |
|------|------|------|
| Pytest | 基础测试框架 | 支持异步测试插件 pytest-asyncio |
| VCR.py | 录制并回放 HTTP 请求 | 用于锁定 LLM 的响应 |
| Pydantic Validation | 运行时参数校验 | 在测试中强制检查 Tool Call 的参数格式 |
| SQLite (In-Memory) | 临时存储测试 | 测试运行完即销毁，保持环境纯净 |

---

## 5. 系统架构与模块设计 (Architecture & Module Design)

### 5.1 整体架构图

```
Smart Agent Hub (Core)
├── Input Handler (Preprocessing)
├── Planner (CoT/ReAct Loop)
├── Memory (Short/Long)
├── State Manager (SQLite/Context)
├── Executor (Tool Dispatcher)
├── Trace Logger (JSONL Logs)
└── Tool Integration Layer
    ├── Local Toolset (File/Script/Search/Python)
    ├── External MCP Servers (RAG Hub/Browser/Database)
    ├── Tool Routing & HITL Gate
    └── MCP Protocol Client (Stdio/HTTP)
```

### 5.2 目录结构

```
.
├── agent/
│   ├── core/
│   │   ├── planner.py          # ReAct 循环逻辑
│   │   ├── executor.py          # 工具执行分发器
│   │   ├── state_manager.py     # 状态管理
│   │   └── memory.py            # 记忆模块
│   ├── llm/
│   │   ├── client.py            # 统一 LLM 客户端
│   │   └── prompts.py           # Prompt 模板引擎
│   ├── mcp/
│   │   ├── client.py            # MCP 协议客户端
│   │   └── dispatcher.py        # 工具参数映射器
│   ├── tools/
│   │   ├── local/               # 本地内置工具库
│   │   └── safety_gate.py       # 安全门控
│   ├── storage/
│   │   ├── sqlite_store.py      # 会话状态存储
│   │   └── jsonl_logger.py      # JSONL 轨迹记录
│   └── utils/
│       └── common.py            # 通用工具
├── dashboard/
│   └── app.py                   # Streamlit 监控面板
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── data/
│   ├── db/
│   └── logs/
├── config/
│   ├── settings.yaml
│   └── mcp_servers.yaml
├── cli.py                       # CLI 入口脚本
├── pyproject.toml               # 项目依赖配置
└── README.md
```

### 5.3 核心模块功能详述

#### 5.3.1 规划器 (Planner & Loop Manager)
- **功能**：这是 Agent 的"思考"中枢。核心方法为 step()，每一轮 step 会将当前的 State 和 History 喂给决策 LLM。
- **版本支持**：
  - Simple-ReAct：标准的单步思考 - 行动循环
  - Sub-task DAG：支持在第一步将复杂任务拆解为子任务图，然后逐个执行
- **职责**：负责动态生成系统提示词，注入可用的 Tools Description。

#### 5.3.2 执行器与工具管理器 (Executor & Tool Manager)
- **功能**：负责将 Planner 产出的 Action 转化为具体的函数调用。
- **实现机制**：
  - MCP Dispatcher：通过 JSON-RPC 调用远程 MCP 服务器工具
  - Safety Gate：检查工具是否属于 Destructive 类型，如果是，则挂起执行并等待 Human-in-the-Loop 信号
- **方法**：execute(action: Action) -> Observation

#### 5.3.3 状态管理器 (State Manager)
- **功能**：维护 Agent 的短期记忆和任务进度。
- **持久化方案**：使用 SQLite WAL 模式。
- **Checkpoint 机制**：每一轮推理结束后自动保存状态，支持 Undo 操作，防止因外部 API 失败导致的进度丢失。

#### 5.3.4 记忆模块 (Memory Module)
- **工作记忆**：存储当前 ReAct 步骤的细节
- **检索增强记忆**：当检测到相似任务时，通过 RAG 接口从 ChromaDB 检索历史成功的思考链路

### 5.4 典型数据流

1. **输入阶段**：Input Handler 接收用户指令，从 Storage 加载会话上下文
2. **规划阶段**：Planner 结合角色定义和当前上下文，调用决策 LLM 生成 Thought 和 Action
3. **决策解析**：Loop Manager 解析 LLM 输出。如果是 Final Answer 则结束；如果是 Tool Call 则进入下一步
4. **执行阶段**：Executor 调用工具（本地或 MCP），获得 Observation
5. **记录阶段**：Trace Logger 将全过程写入 JSONL，State Manager 更新 SQLite
6. **反馈阶段**：Observation 被喂回 Planner，开始下一轮循环

---

## 6. 项目排期 (Project Schedule)

### 排期原则
- **最小可行性**：优先打通"思考 - 行动 - 观察"的闭环
- **契约先行**：先定义 Pydantic 数据模型
- **安全第一**：高风险工具的门控逻辑需在执行器早期阶段实现

### 进度计划表

| 阶段 | 任务编号 | 任务名称 | 验收标准 | 备注 |
|------|----------|----------|----------|------|
| **阶段 A：工程骨架** | A1 | 目录结构与依赖初始化 | 完成 pyproject.toml，支持 pytest 运行 | 参照 5.2 节目录结构 |
| | A2 | 定义核心 Data Schemas | Task、Action、Observation 模型通过 Pydantic v2 验证 | |
| | A3 | 配置系统 | 支持读取环境变量及 settings.yaml | 包含 LLM 密钥校验 |
| **阶段 B：LLM 抽象层** | B1 | 统一 LLM Client 封装 | 实现支持流式输出的 llm.generate() | 适配 OpenAI 协议 |
| | B2 | Prompt 模板引擎 | 支持动态注入 tool_list 和 history | 解决提示词拼接问题 |
| **阶段 C：MCP 客户端** | C1 | MCP Stdio Transport | 成功启动外部 RAG Server 并获取工具列表 | 进程间通信逻辑 |
| | C2 | 工具参数映射器 | 自动将 MCP JSON Schema 转为 Python 类型 | 确保调用参数准确 |
| **阶段 D：规划引擎** | D1 | ReAct 循环逻辑实现 | Agent 能在控制台完成"思考 - 行动 - 观察"一次循环 | 核心逻辑 loop.py |
| | D2 | 异常反思机制 | 当工具返回 Error 时，Agent 尝试修正参数重试 | 提高逻辑鲁棒性 |
| **阶段 E：工具执行** | E1 | 工具执行分发器 | 支持异步调用多个工具并收集结果 | asyncio.gather |
| | E2 | 人工介入门控 | 危险动作触发挂起，等待 CLI/VUI 确认 | Safety Gate 实现 |
| **阶段 F：状态持久化** | F1 | SQLite 状态存储 | 会话结束后，重启能加载历史 steps 数据 | 采用 WAL 模式 |
| | F2 | 上下文窗口动态裁剪 | 在长任务中通过摘要自动压缩历史 Token | 解决 Context 溢出 |
| **阶段 G：可观测性** | G1 | JSONL 轨迹记录器 | 实时记录每一步的思维轨迹到本地文件 | 结构化日志写入 |
| | G2 | Streamlit Dashboard | 网页端展示执行瀑布图与思维链回放 | 参照 5.3.4 节设计 |
| **阶段 H：质量评估** | H1 | 任务成功率 Benchmark | 运行 20 组标准任务，成功率>85% | 建立基准测试 |
| | H2 | Token 成本与耗时优化 | 记录每步开销，优化重复生成的冗余提示 | 性能调优 |
| **阶段 I：文档发布** | I1 | 完善 README 与注释 | 外部开发者可根据文档 5 分钟启动项目 | 编写用户手册 |
| | I2 | 制作教学视频与 Demo | 演示 Agent 调用 RAG 知识库解决复杂问题 | 录制全链路演示 |

---

## 7. 可扩展性与未来展望

本项目的设计初衷不仅是建立一个工具调用器，而是构建一个具备"进化能力"的智能中枢。

### 7.1 自主进化与反思机制

- **强化学习反馈**：
  - 记录用户对 Agent 最终执行结果的满意度评价
  - 通过微调或 DPO 策略，让 Agent 逐渐掌握特定用户的偏好

- **思维轨迹回溯**：
  - 引入"全局观察者"模块，当检测到重复动作超过 3 次时强制中断
  - 触发 Self-Correction 逻辑，要求 LLM 重新审视初始任务目标

- **自动工具合成**：
  - 当现有工具库无法解决问题时，Agent 可自主编写 Python 代码
  - 通过本地沙箱运行，封装成临时的新工具供后续步骤调用

### 7.2 多智能体协同作战

- **角色化分工**：
  - **Researcher**：专精于通过 MCP 调用 RAG 搜索深度知识
  - **Writer**：专精于内容编排与文案润色
  - **Reviewer**：负责根据预设的安全规则对输出进行审查

- **SOP 数字化协议**：
  - 将企业内部标准的作业程序转化为 Agent 群组的通讯契约
  - 通过状态共享总线，实现不同 Agent 之间的无缝上下文传递

- **动态组队机制**：
  - 根据用户指令，系统自动唤醒最合适的 2-3 个 Agent
  - 例如：处理报销单时，唤醒"OCR Agent"与"财务合规 Agent"

### 7.3 迈向自主智能：Agentic RAG 的演进路径

当前的 RAG 架构主要遵循"一次检索 - 一次生成"的固有范式，但在面对极其复杂的问题（如跨文档对比、多步推理、时序分析）时，单一的线性流程往往力不从心。本项目作为标准的 MCP Server，天然具备向 **Agentic RAG（代理式 RAG）** 演进的潜力。这不需要重写现有代码，而是通过在 Server 端提供更细粒度的工具，赋能 Client 端的 Agent 具备更强的自主性。

#### 7.3.1 演进路线图

```
┌─────────────────────────────────────────────────────────────────┐
│                    Agentic RAG 演进路线                          │
├─────────────────────────────────────────────────────────────────┤
│  Phase 1: 单步检索 → Phase 2: 多步决策 → Phase 3: 自主反思      │
│     [search]         [decompose + search]     [self_check]      │
│                          ↓                        ↓              │
│                    [list_docs]              [verify_fact]       │
│                    [preview_doc]            [re_search]         │
└─────────────────────────────────────────────────────────────────┘
```

#### 7.3.2 核心能力升级

**能力一：从"单步检索"到"多步决策"**

| 工具名 | 功能描述 | 输入参数 | 返回结果 |
|--------|----------|----------|----------|
| `list_collections` | 查看知识库目录结构 | `collection_pattern: str` | 匹配的知识库列表 |
| `preview_document` | 预览文档摘要/元数据 | `doc_id: str`, `top_k: int` | 文档摘要、标签、页数 |
| `search_explorer` | 探索式检索，返回相关关键词 | `query: str`, `top_k: int` | 相关关键词列表 + 初步结果 |
| `verify_fact` | 事实核查，验证检索结果是否支撑论点 | `claim: str`, `evidence_ids: list` | 支撑度评分 (0-1) |
| `compare_documents` | 跨文档对比分析 | `doc_ids: list[str]`, `aspect: str` | 对比表格 + 差异分析 |

**Agent 工作流示例**（解决"对比 A 公司和 B 公司的技术路线差异"）：

```
1. Agent 调用 list_collections() → 发现"行业报告"知识库
2. Agent 调用 search_explorer("A 公司 技术路线") → 获取相关文档 ID 列表
3. Agent 调用 preview_document(doc_id) → 快速筛选高相关文档
4. Agent 并行调用 search(文档 A) 和 search(文档 B) → 获取双方信息
5. Agent 调用 compare_documents([doc_a, doc_b], "技术路线") → 生成对比分析
6. Agent 输出最终答案，附带引用来源
```

**能力二：让 Agent 具备"反思"能力**

```python
# 伪代码示例：Agentic RAG 的反思循环
def agentic_search_with_reflection(query: str, max_iterations: int = 3):
    for iteration in range(max_iterations):
        # Step 1: 检索
        results = hybrid_search(query, top_k=10)
        
        # Step 2: 生成初步答案
        answer = generate_answer(query, results)
        
        # Step 3: 自我检查（调用 Evaluation 模块）
        check_result = self_check(
            query=query,
            answer=answer,
            context=results
        )
        
        # Step 4: 根据检查结果决定下一步
        if check_result["hallucination_score"] < 0.3:
            return answer  # 质量合格，返回答案
        else:
            # 质量不足，进行更深度的搜索
            new_query = refine_query(query, check_result["missing_info"])
            results = dense_search(new_query, top_k=5)  # 追加检索
```

**Self-Check 接口设计**：

| 检查项 | 评估方法 | 阈值 |
|--------|----------|------|
| 幻觉检测 | 答案中的关键实体是否出现在检索结果中 | > 80% 实体需有来源 |
| 支撑度评估 | 检索结果是否充分支撑答案论点 | 支撑度 > 0.7 |
| 完整性检查 | 是否覆盖了问题的所有子问题 | 子问题覆盖率 > 90% |

**能力三：动态策略选择**

```yaml
# MCP Server 暴露的独立检索工具
tools:
  - name: keyword_search
    description: 精确匹配关键词，适合搜索人名、专有名词、型号等
    parameters:
      query: str
      field: str  # 可选：title, content, tags
      
  - name: semantic_search
    description: 语义相似度检索，适合搜索概念、定义、开放式问题
    parameters:
      query: str
      similarity_threshold: float
      
  - name: hybrid_search
    description: 混合检索（默认），结合关键词和语义匹配
    parameters:
      query: str
      rrf_k: int  # RRF 融合参数
      
  - name: filtered_search
    description: 带元数据过滤的检索
    parameters:
      query: str
      filters: dict  # 如 {"tags": ["RAG", "面试"]}
```

#### 7.3.3 实现计划（分阶段落地）

| 阶段 | 目标 | 预计工作量 | 依赖 |
|------|------|------------|------|
| **Phase 1** | 暴露原子化工具（list_docs, preview_doc） | 2 天 | 无 |
| **Phase 2** | 实现 self_check 接口，集成 Evaluation 模块 | 3 天 | Evaluation Panel 完成 |
| **Phase 3** | 拆分检索策略为独立工具 | 2 天 | 无 |
| **Phase 4** | 实现 Agentic 工作流编排器 | 5 天 | Phase 1-3 完成 |
| **Phase 5** | 多 Agent 协同（Researcher + Writer + Reviewer） | 7 天 | Phase 4 完成 |

#### 7.3.4 预期收益

通过上述演进，本项目将从一个**"智能搜索引擎"**升级为一个**"智能研究助理"**的基础设施底座：

| 维度 | 当前能力 | 演进后能力 |
|------|----------|------------|
| 问题复杂度 | 单跳问答（What is X?） | 多跳推理（Compare X and Y, analyze Z） |
| 答案质量 | 依赖单次检索 | 自我反思 + 多轮验证 |
| 用户交互 | 被动响应 | 主动探索 + 澄清追问 |
| 可扩展性 | 固定检索逻辑 | Agent 自主编排工作流 |

这种演进方向不仅提升了 RAG 系统的实用性，更为构建真正的**个人知识助理**奠定了技术基础。

### 7.4 隐私保护与本地化智能

- **端侧模型驱动**：
  - 利用 llama.cpp 或 MLC LLM，在用户本地电脑运行 7B 或更小的模型
  - 简单的日常任务完全由本地小模型处理，复杂逻辑加密上传至云端

- **MCP 生态的"万能插座"**：
  - 随着越来越多的软件支持 MCP，SAH 框架将成为用户的个人"数字管家"
  - 所有对物理世界的操作均保留在 Human-in-the-Loop 的安全门控内

### 7.5 持续学习的学习笔记

作为开发者，本项目也是理解"通用人工智能"的一块试验田。每一个版本的更新都会同步记录在 docs/learning_path 中，包括：

- 为什么从 LangChain 的复杂链式结构转向了更灵活的 OpenClaw 模式
- 在处理长上下文时，如何通过"滑动窗口"和"动态压缩"保持逻辑连贯性