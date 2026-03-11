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
