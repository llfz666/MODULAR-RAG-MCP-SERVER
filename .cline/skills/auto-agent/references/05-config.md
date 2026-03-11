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
