# 模拟面试报告

**项目**：Modular RAG MCP Server  
**面试时间**：2026-03-13 20:41  
**面试官风格**：🔬 深挖发散型 (DEEP)  
**掷骰结果**：5  
**评分**：7/10

---

## 一、面试记录

> ✅ 答对核心要点 | ⚠️ 方向正确但细节缺失 | ❌ 未能答出或方向错误

### 方向 1：项目综述

| 轮次 | 问题 | 候选人回答摘要 | 评估 | 参考答案 |
|-----|------|-------------|------|---------|
| Q1 | 从用户发起一次查询，到拿到结果，整个链路经过哪些组件？ | 最初只说出组件名称列表，经提示后能描述基本流程 | ⚠️ | [→ 查看](#a-查询链路) |
| Q1-追问 1 | 这些组件之间的数据流是怎么打通的？Query Embedding 是怎么调用的？Hybrid Retriever 是怎么同时调用 Dense 和 Sparse 两路的？ | 描述了通用 RAG 管道流程，但未能说明本项目实际实现 | ⚠️ | [→ 查看](#a-查询链路) |
| Q1-追问 2 | Embedding 是同步还是异步？Dense 和 Sparse 是并行还是串行？Reranker 失败有什么降级策略？ | 正确区分离线/在线 Embedding，理解 I/O 密集型操作，能解释 Fallback 逻辑 | ✅ | [→ 查看](#a-查询链路) |

### 方向 2：简历深挖

| 轮次 | 问题 | 候选人回答摘要 | 评估 | 露馅 | 参考答案 |
|-----|------|-------------|------|-----|---------|
| Q2 | HitRate@10 达到 92%，MRR 为 0.85，测试集是怎么建立的？有多少条测试用例？ | 能完整描述测试集构建流程、计算逻辑、可复现性，说出 50-100 条规模 | ✅ | 否 | [→ 查看](#a-评估指标) |
| Q2-追问 1 | 用什么脚本从文档中抽取关键段落？人工标注一个 query 一般标注几个 golden_chunk_ids？集成测试和 E2E 测试有什么区别？ | 能清晰解释半自动生成流程，用表格对比集成测试和 E2E 测试的区别 | ✅ | 否 | [→ 查看](#a-评估指标) |

### 方向 3：技术深挖

| 轮次 | 问题 | 候选人回答摘要 | 评估 | 参考答案 |
|-----|------|-------------|------|---------|
| Q3 | 新增一个 Embedding Provider 需要改哪些文件？每一步具体做什么？ | 能描述 Factory Pattern + 注册表模式，说出 4 步流程 | ✅ | [→ 查看](#a-可插拔架构) |
| Q3-追问 1 | TraceContext 是怎么工作的？每个阶段写入的数据结构是什么样的？Dashboard 是怎么读取并展示的？ | 描述了通用 Trace 系统设计思路，但 5 阶段命名与本项目有差异 | ⚠️ | [→ 查看](#a-可观测性) |
| Q3-追问 2 | 本项目中 Ingestion Pipeline 的实际 5 阶段命名是什么？Trace 用什么存储？Dashboard 用什么技术栈？ | 能够识别自己回答中的模糊之处，给出对比表格进行自我纠正 | ✅ | [→ 查看](#a-可观测性) |

---

## 二、参考答案

### <a id="a-查询链路"></a>Q: 从用户发起一次查询，到拿到结果，整个链路经过哪些组件？

**参考答案**：

用户查询链路共 5 个阶段：

1. **QueryProcess**：用户通过 MCP Client 发起请求 → MCP Server 接收 JSON-RPC 消息 → 调用 `query_knowledge_hub` 工具
2. **DenseRecall**：Query Embedding 模型将查询文本向量化 → Chroma 向量库中 Cosine Similarity 检索 → Top-N 语义候选
3. **SparseRecall**：BM25 倒排索引进行关键词检索 → Top-N 关键词候选
4. **Fusion**：RRF 融合算法将两路召回结果按排名融合 → 生成统一排序列表
5. **Rerank**：Cross-Encoder 或 LLM Rerank 对候选集精排 → 返回最终 Top-K 结果，带 Citation 结构化引用

**关键组件**：
- MCP Server（`src/mcp_server/server.py`）
- Query Engine（`src/core/query_engine/`）
  - `hybrid_search.py` — Hybrid Search 混合检索主入口
  - `dense_retriever.py` — Dense 向量检索
  - `sparse_retriever.py` — Sparse BM25 检索
  - `fusion.py` — RRF 融合算法
  - `reranker.py` — 精排模块
- Reranker（`src/libs/reranker/`）
  - `cross_encoder_reranker.py` — Cross-Encoder 精排
  - `llm_reranker.py` — LLM Rerank
- Vector Store（Chroma）+ BM25 Index
  - `src/libs/vector_store/chroma_store.py`
  - BM25 索引存储在 `data/db/bm25/`

**本项目实际实现**：
- Hybrid Retriever 使用 `asyncio.gather()` **并行执行** Dense 和 Sparse 两路召回
- Reranker 降级策略：超时/失败时直接返回 RRF 融合后的 Top-K，跳过精排

---

### <a id="a-评估指标"></a>Q: Hit Rate@K 和 MRR 是怎么计算的？测试集怎么建立？

**参考答案**：

**Hit Rate@K**：

$$HitRate@K = \frac{\text{Top-K 结果中至少命中一条 Golden Answer 的查询数}}{\text{总查询数}}$$

对 Golden Test Set 中每条 `(query, expected_chunks)`，取 Top-K 检索结果，至少一条匹配则 hit=1，否则 hit=0。

**MRR（Mean Reciprocal Rank）**：

$$MRR = \frac{1}{|Q|} \sum_{i=1}^{|Q|} \frac{1}{rank_i}$$

$rank_i$ 是第 $i$ 条查询中第一条正确结果的排名。第一条命中得 1 分，第 2 位得 0.5 分，衡量**头部排序质量**。

**测试集建立方法**：
1. 建立 50-100 条问答对的 Golden Test Set（`tests/fixtures/golden_test_set.json`）
2. 每条包含 query 和对应的 golden_chunk_ids
3. 半自动生成：从已摄入文档抽取关键段落作为候选答案，人工标注每个 query 应命中的 chunk
4. 一个 query 一般标注 1-3 个 golden_chunk_ids（唯一答案型 1 个，分散答案型 2-3 个）

**集成测试 vs E2E 测试**：
| 维度 | 集成测试 | E2E 测试 |
|------|---------|---------|
| 测试范围 | 局部流程：Query → 检索结果 | 全流程：Query → 最终 Answer |
| 测试指标 | Hit Rate@K、MRR、NDCG@K | Answer Relevance、Faithfulness |
| 数据依赖 | Golden Test Set（Query + Chunk IDs） | Golden Q&A Pairs（Query + Ideal Answer） |
| 执行频率 | 每次代码变更都可跑 | 较慢，nightly build 或 Release 前跑 |

---

### <a id="a-可插拔架构"></a>Q: 新增一个 Embedding Provider 需要改哪些文件？

**参考答案**：
只需改 **3 处**，已有代码零修改（开闭原则）：

1. **新建** `src/libs/embedding/your_provider.py`：继承 `BaseEmbedding`，实现 `embed_texts()` 等接口方法
2. **修改** `src/libs/embedding/factory.py`：在 `provider_map` 中注册 `"your_provider": YourProviderClass`
3. **修改** `config/settings.yaml`：将 `embedding.provider` 改为 `"your_provider"`

其他组件（LLM / Reranker / VectorStore / Loader / Splitter）遵循同一套三步流程。

---

### <a id="a-可观测性"></a>Q: Trace 是怎么实现的？Ingestion 的 5 个阶段各是什么？

**参考答案**：

**Trace 实现**：显式调用模式（非 AOP 拦截），各阶段手动向 TraceContext 写入耗时、数量、分数分布，存为 **JSON Lines 结构化日志**，零外部依赖（无需 LangSmith/LangFuse）。

**Ingestion 5 阶段**：
1. **Load**：MarkItDown 将 PDF 转为 Markdown，前置 SHA256 文件哈希去重
2. **Split**：LangChain `RecursiveCharacterTextSplitter` 按 Markdown 结构语义切分
3. **Transform**：3 个 LLM 增强步骤（ChunkRefiner / MetadataEnricher / ImageCaptioner）
4. **Embed**：BM25 + Dense Embedding 双路向量化，差量计算
5. **Upsert**：幂等写入 Chroma 向量库 + BM25 倒排索引

**Dashboard**：Streamlit + Plotly 实现，6 个页面（系统总览、数据浏览器、Ingestion 管理、Ingestion 追踪、Query 追踪、评估面板）。动态渲染设计，基于 Trace 中的 `method`/`provider` 字段自动适配。

---

## 三、简历包装点评

### 包装合理 ✅
- **"采用 Factory Pattern + YAML 配置实现多模型快速切换"**：能够描述 Factory Pattern + 注册表模式，说出新增 Provider 的基本流程
- **"建立自动化评估与测试体系"**：能清晰解释测试集构建流程，用表格对比集成测试和 E2E 测试，展现扎实理解
- **"失败时自动回退保障可用性"**：能解释 Reranker 降级策略和 Fallback 逻辑
- **自我纠正能力**：Q3-追问 2 中能够识别自己回答中的模糊之处，主动给出对比表格进行自我纠正，这是优秀工程师的特质

### 露馅点 ⚠️
- **"五阶段智能数据摄取流水线：Load→Split→Transform→Embed→Upsert"** → 最初回答时使用了 "Loader → Chunker → Embedding → Indexing → Validation" 的通用命名，而非本项目实际命名。**严重性：低**（后续能够自我纠正）
- **"集成 MCP 协议标准"** → Q1 中对数据流、并行机制等细节未能第一时间说出本项目实际实现（如 `asyncio.gather()` 并行）。**严重性：中**（经提示后能理解，但缺乏对本项目实现的精准掌握）
- **"Streamlit + Plotly"** → Dashboard 技术栈在追问前描述为 "Grafana 或自研 UI"，存在模糊空间。**严重性：低**（后续能够纠正）

### 改进建议
1. **精准掌握项目实现细节**：作为"独立开发者"，应该对本项目的实际实现（如具体函数名、配置路径、技术选型）了如指掌，而非通用描述
2. **面试前过一遍代码**：确保能说出关键文件路径（如 `src/mcp_server/server.py`、`src/core/query_engine/`）
3. **保持诚实但也要准备充分**：能够承认"这个我需要确认一下"是好的，但核心技术点应该能够脱口而出

---

## 四、综合评价

**优势**：
- 对 RAG 系统整体架构有清晰理解，能够描述查询链路、测试体系、可插拔架构等核心概念
- Q2 对评估指标和测试体系的理解非常到位，表格对比清晰专业
- Q3-追问 2 展现出优秀的自我反思和纠正能力，这是高级工程师的重要特质
- 对 I/O 密集型操作、离线/在线 Embedding 区分等概念理解正确

**薄弱点**：
- 对本项目**实际实现细节**掌握不够精准（如 5 阶段命名、Trace 存储方式、Dashboard 技术栈）
- Q1 初始回答较为笼统，需要多轮追问才能触及本项目具体实现
- 部分回答使用"通用框架"而非"本项目实现"，存在用通用知识覆盖具体实现的风险

**面试官建议**：
1. **深入阅读项目代码**：作为"独立开发者"，应该能说出每个核心模块的具体文件路径和实现细节
2. **准备"本项目实际实现"类问题**：每个技术点都要能说出"本项目是怎么做的"，而非只说"一般系统会怎么做"
3. **继续保持自我纠正的习惯**：Q3-追问 2 的表现非常好，能够识别模糊之处并主动纠正，这是面试中的加分项

---

## 五、评分

| 维度 | 分数（满分 10）| 评分依据 |
|-----|--------------|---------|
| 项目架构掌握 | 7 | 整体架构理解清晰，但对本项目实际实现细节（5 阶段命名、Trace 存储）掌握不够精准 |
| 简历真实性 | 7 | 大部分技术点能自圆其说，但部分描述（如 Dashboard 技术栈）存在模糊空间，后续能自我纠正 |
| 算法理论深度 | 7 | 对 RRF、Hybrid Search、评估指标等有基本理解，但未能深入公式层面 |
| 实现细节掌握 | 6 | 对通用实现有较好理解，但对本项目具体实现（如 asyncio.gather 并行、JSON Lines 存储）需要提示 |
| 表达清晰度 | 8 | 回答结构化好，能用表格对比，自我纠正能力强 |
| **综合** | **7** | 技术底子扎实，对 RAG 系统有整体理解，自我纠正能力突出。但作为"独立开发者"，对本项目实际实现细节掌握不够精准，需要加强代码熟悉度。建议面试前深入阅读项目代码，确保能说出关键文件路径和实现细节。 |

---

**报告生成时间**：2026-03-13 20:41  
**面试官**：模拟面试官 Agent（interview-prep skill）  
**本场风格**：🔬 深挖发散型 (DEEP) — 每方向多轮追问，形成发散式对话  
**掷骰结果**：5 — 决定开场题池第 9 题、P3 技术词汇池、D 组第 5 题

**与上一场面试对比**：
| 维度 | 上一场 (FAST) | 本场 (DEEP) | 变化 |
|------|-------------|-----------|------|
| 风格 | 速攻广度型 | 深挖发散型 | - |
| 题目数 | 5 题 | 3 方向 7 轮 | 深度增加 |
| 评分 | 6/10 | 7/10 | +1 |
| 表现 | Q3-Q5 好，Q1/Q2 露馅 | 自我纠正能力强，实现细节仍需加强 | 表达能力提升 |