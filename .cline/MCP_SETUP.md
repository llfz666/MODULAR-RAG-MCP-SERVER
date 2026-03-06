# Modular RAG MCP Server - Cline 配置说明

## 问题根源

错误 "Unexpected token 'M', 'Modular RA'... is not valid JSON" 是因为 `src/observability/logger.py` 中的 `get_logger()` 函数调用了 `logging.basicConfig()`，这会在 MCP stdio 传输启动前向 stdout 写入内容，破坏了 JSON-RPC 协议流。

## 已修复的文件

### 1. `src/observability/logger.py`
- 添加 `use_basic_config` 参数（默认 `True` 保持向后兼容）
- 当 `use_basic_config=False` 时，不调用 `logging.basicConfig()`

### 2. `src/mcp_server/server.py`
- 重定向 `sys.stdout` 到 `sys.stderr`
- 手动配置 logger，不使用 `basicConfig()`
- 添加 `_suppress_all_stdout()` 和 `_redirect_all_loggers_to_stderr()` 函数

### 3. `src/mcp_server/protocol_handler.py`
- 在 `__post_init__` 中手动创建 logger
- 不使用 `get_logger()` 避免 `basicConfig()` 调用
- 清除现有 handler 避免重复日志

### 4. `.cline/mcp_server_wrapper.py`
- 启动时立即重定向 `sys.stdout` 和 `sys.__stdout__` 到 `sys.stderr`
- 使用 `os.dup2(2, 1)` 重定向文件描述符
- 设置环境变量 `PYTHONUNBUFFERED=1` 和 `PYTHONIOENCODING=utf-8`

## Cline 配置

### 方式一：使用 MCP 设置文件（推荐）

Cline 会自动读取 `.cline/mcp_settings.json` 文件。当前配置：

```json
{
  "mcpServers": {
    "modular-rag-mcp-server": {
      "command": "python",
      "args": [
        "-u",
        "e:/code/MODULAR-RAG-MCP-SERVER/.cline/mcp_server_wrapper.py"
      ],
      "cwd": "e:/code/MODULAR-RAG-MCP-SERVER",
      "env": {
        "PYTHONUNBUFFERED": "1",
        "PYTHONIOENCODING": "utf-8"
      },
      "disabled": false,
      "autoApprove": false,
      "timeout": 120
    }
  }
}
```

### 方式二：手动配置

在 Cline 的 MCP Servers 管理面板中，添加以下配置：

- **Server Name**: `modular-rag-mcp-server`
- **Command**: `python`
- **Args**: `-u e:/code/MODULAR-RAG-MCP-SERVER/.cline/mcp_server_wrapper.py`
- **Working Directory**: `e:/code/MODULAR-RAG-MCP-SERVER`
- **Environment**:
  - `PYTHONUNBUFFERED=1`
  - `PYTHONIOENCODING=utf-8`
- **Timeout**: `120`

## 可用工具

连接成功后，Cline 将可以使用以下三个 MCP 工具：

| 工具名称 | 描述 |
|---------|------|
| `list_collections` | 列出知识库集合 |
| `get_document_summary` | 获取文档摘要 |
| `query_knowledge_hub` | 查询知识库 |

## 验证步骤

1. 在 Cline 中打开 MCP Servers 管理面板（点击侧边栏的 🔌 图标）
2. 找到 `modular-rag-mcp-server`
3. 点击刷新/重新连接按钮
4. 服务器启动可能需要 10-30 秒（用于加载 chromadb 等重型依赖）
5. 连接成功后，工具列表将显示三个可用工具

## 故障排除

### 问题：连接后立即断开

**原因**：可能有其他代码向 stdout 写入了内容。

**解决**：
1. 检查是否有其他 `print()` 语句未被重定向
2. 查看日志文件 `logs/` 目录中的错误信息

### 问题：工具调用超时

**原因**：首次加载 chromadb 等重型依赖需要时间。

**解决**：
1. 增加 `timeout` 值到 180 或更高
2. 首次连接后，后续启动会更快（模块已缓存）

### 问题：找不到 Python

**解决**：确保 `command` 使用完整路径，例如：
```
C:/Users/<用户名>/AppData/Local/Programs/Python/Python310/python.exe