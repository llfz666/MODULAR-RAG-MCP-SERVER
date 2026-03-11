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
