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
