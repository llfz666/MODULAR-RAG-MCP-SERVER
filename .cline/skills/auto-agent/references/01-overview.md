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
