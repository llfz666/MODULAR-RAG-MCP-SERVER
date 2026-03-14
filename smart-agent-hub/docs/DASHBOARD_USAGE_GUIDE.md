# Dashboard 使用指南 - 避免端口冲突

## 📊 两个 Dashboard 对比

| 项目 | RAG Dashboard | Agent Dashboard |
|------|---------------|-----------------|
| **路径** | `src/observability/dashboard/app.py` | `smart-agent-hub/dashboard/app.py` |
| **功能** | RAG 评估、数据浏览、Ingestion 管理 | Agent 会话、记忆管理、执行追踪 |
| **默认端口** | 8501 | 8502 (建议) |
| **数据存储** | `data/db/` | `smart-agent-hub/data/db/` |

---

## 🚀 启动命令

### 1️⃣ RAG Dashboard (端口 8501)

```bash
# 在项目根目录 (e:\code\MODULAR-RAG-MCP-SERVER)
cd e:\code\MODULAR-RAG-MCP-SERVER

# 安装依赖 (如果还没安装)
pip install streamlit pandas

# 启动 Dashboard (默认端口 8501)
streamlit run src/observability/dashboard/app.py

# 或者明确指定端口
streamlit run src/observability/dashboard/app.py --server.port 8501
```

**访问地址**: http://localhost:8501

**页面功能**:
- 📊 Overview: 项目总览
- 🔍 Data Browser: 数据浏览
- 📥 Ingestion Manager: 数据导入管理
- 🔬 Ingestion Traces: 导入追踪
- 🔎 Query Traces: 查询追踪
- 📏 Evaluation Panel: 评估面板

---

### 2️⃣ Agent Dashboard (端口 8502)

```bash
# 在 smart-agent-hub 子目录
cd e:\code\MODULAR-RAG-MCP-SERVER\smart-agent-hub

# 安装依赖 (如果还没安装)
pip install -e ".[dashboard]"

# 启动 Dashboard (使用 8502 端口避免冲突)
streamlit run dashboard/app.py --server.port 8502
```

**访问地址**: http://localhost:8502

**页面功能**:
- 📊 Overview: Agent 会话统计
- 📜 Session History: 会话历史浏览
- 🔍 Execution Trace: 执行流程可视化
- 🧠 Memory View: 长期记忆管理
- ⚙️ Settings: 设置

---

## ⚠️ 端口冲突说明

### 问题

Streamlit 默认使用 **8501** 端口。如果两个 Dashboard 都使用默认端口，后启动的会报错：

```
ERROR: Port 8501 is already in use
```

### 解决方案

**方案 A**: 只启动一个 Dashboard
- 需要 RAG 功能 → 启动 RAG Dashboard (8501)
- 需要 Agent 功能 → 启动 Agent Dashboard (8501 默认)

**方案 B**: 同时启动两个 Dashboard (推荐)
- RAG Dashboard → 端口 8501
- Agent Dashboard → 端口 8502

```bash
# 终端 1: 启动 RAG Dashboard
cd e:\code\MODULAR-RAG-MCP-SERVER
streamlit run src/observability/dashboard/app.py --server.port 8501

# 终端 2: 启动 Agent Dashboard
cd e:\code\MODULAR-RAG-MCP-SERVER\smart-agent-hub
streamlit run dashboard/app.py --server.port 8502
```

---

## 📋 快速启动脚本

### Windows Batch 脚本

创建 `start_dashboards.bat`:

```batch
@echo off
echo Starting RAG Dashboard on port 8501...
start cmd /k "cd /d e:\code\MODULAR-RAG-MCP-SERVER && streamlit run src/observability/dashboard/app.py --server.port 8501"

timeout /t 2 /nobreak >nul

echo Starting Agent Dashboard on port 8502...
start cmd /k "cd /d e:\code\MODULAR-RAG-MCP-SERVER\smart-agent-hub && streamlit run dashboard/app.py --server.port 8502"

echo Both dashboards are starting...
```

双击运行即可同时启动两个 Dashboard。

---

## 🔧 配置选项

### 自定义端口

```bash
# 任意端口都可以
streamlit run dashboard/app.py --server.port 850X
```

### 其他配置

```bash
# 指定浏览器
streamlit run dashboard/app.py --server.port 8502 --browser.serverAddress localhost

# 关闭自动重新加载
streamlit run dashboard/app.py --server.port 8502 --server.headless true
```

---

## 📝 总结

| 场景 | 命令 | 访问地址 |
|------|------|----------|
| 仅 RAG Dashboard | `streamlit run src/observability/dashboard/app.py` | http://localhost:8501 |
| 仅 Agent Dashboard | `streamlit run smart-agent-hub/dashboard/app.py` | http://localhost:8501 |
| 同时运行 (推荐) | RAG: `--server.port 8501`<br>Agent: `--server.port 8502` | 8501 + 8502 |

**注意**: 两个 Dashboard 数据存储路径独立，不会互相干扰。