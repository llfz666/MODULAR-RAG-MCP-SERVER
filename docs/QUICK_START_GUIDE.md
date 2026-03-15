# 快速开始指南 - Modular RAG MCP Server

本指南将带您完成从数据准备到功能测试的完整流程。

---

## 📋 目录

1. [项目结构概览](#1-项目结构概览)
2. [环境准备](#2-环境准备)
3. [数据集准备](#3-数据集准备)
4. [测试文档加载器功能](#4-测试文档加载器功能)
5. [测试 MCP 服务](#5-测试 MCP 服务)
6. [运行 Dashboard](#6-运行 Dashboard)

---

## 1. 项目结构概览

```
MODULAR-RAG-MCP-SERVER/
├── scripts/                    # 脚本工具
│   ├── ingest.py              # 数据导入脚本
│   ├── query.py               # 查询测试脚本
│   └── demo_evaluation.py     # 演示评估脚本
├── tests/
│   ├── fixtures/              # 测试数据生成器
│   │   ├── generate_blogger_intro_pdf.py
│   │   ├── generate_complex_pdf.py
│   │   └── generate_financial_insurance_test_data.py
│   └── integration/           # 集成测试
├── src/libs/loader/           # 文档加载器
│   ├── pdf_loader.py          # PDF 加载器
│   ├── advanced_pdf_loader.py # 高级 PDF 加载器
│   ├── pptx_loader.py         # PPTX 加载器
│   └── docx_loader.py         # Word 加载器
├── data/                       # 数据存储目录
│   └── images/                # 提取的图片
└── config/
    └── settings.yaml          # 配置文件
```

---

## 2. 环境准备

### 2.1 检查 Python 版本

```bash
python --version  # 需要 Python 3.10+
```

### 2.2 安装依赖

```bash
pip install -e .
```

### 2.3 验证安装

```bash
pytest tests/unit/test_smoke_imports.py -v
```

---

## 3. 数据集准备

### 方法一：使用测试数据生成器（推荐）

项目内置了多个测试数据生成脚本：

#### 3.1 生成金融/保险测试数据

```bash
# 生成 5 个金融/保险领域的 PDF 文档
python tests/fixtures/generate_financial_insurance_test_data.py
```

生成的文件位置：`tests/fixtures/financial_insurance_data/`

#### 3.2 生成简单 PDF

```bash
# 生成一个简单的介绍性 PDF
python tests/fixtures/generate_blogger_intro_pdf.py
```

生成的文件位置：`tests/fixtures/sample_documents/blogger_intro.pdf`

#### 3.3 生成复杂 PDF（包含多栏、表格等）

```bash
# 生成一个复杂的 PDF 文档
python tests/fixtures/generate_complex_pdf.py
```

生成的文件位置：`tests/fixtures/sample_documents/complex_document.pdf`

### 方法二：使用自己的 PDF 文件

将您的 PDF 文件放到 `tests/fixtures/sample_documents/` 目录：

```bash
# 创建目录（如果不存在）
mkdir -p tests/fixtures/sample_documents

# 复制您的 PDF 文件
copy path\to\your\document.pdf tests/fixtures/sample_documents/
```

---

## 4. 测试文档加载器功能

### 4.1 测试基础 PDF 加载器

创建一个测试脚本 `test_loader.py`：

```python
from src.libs.loader.pdf_loader import PdfLoader

# 初始化加载器
loader = PdfLoader(
    extract_images=True,      # 提取图片
    enable_ocr=True,          # 启用 OCR
    ocr_backend='paddle',     # 使用 PaddleOCR
)

# 加载 PDF
doc = loader.load("tests/fixtures/sample_documents/blogger_intro.pdf")

# 查看结果
print(f"文档 ID: {doc.id}")
print(f"文档类型：{doc.metadata['doc_type']}")
print(f"是否有文字层：{doc.metadata['has_text_layer']}")
print(f"\n内容预览 (前 500 字):")
print(doc.text[:500])
```

运行测试：

```bash
python test_loader.py
```

### 4.2 测试高级 PDF 加载器（带布局分析）

```python
from src.libs.loader.advanced_pdf_loader import AdvancedPdfLoader

# 初始化高级加载器
loader = AdvancedPdfLoader(
    use_layout_analysis=True,      # 启用布局分析
    use_table_recognition=True,    # 启用表格识别
    ocr_lang='ch',                 # 中文 OCR
)

# 加载 PDF
doc = loader.load("tests/fixtures/sample_documents/complex_document.pdf")

print(f"检测到的区域类型：{doc.metadata.get('page_metadata', [])}")
print(f"\n内容预览:")
print(doc.text[:1000])
```

### 4.3 测试 PPTX 加载器

```python
from src.libs.loader.enhanced_pptx_loader import EnhancedPptxLoader

# 初始化 PPTX 加载器
loader = EnhancedPptxLoader(
    extract_notes=True,       # 提取演讲者备注
    ocr_images=True,          # 对图片进行 OCR
    ocr_lang='ch',
)

# 加载 PPTX
doc = loader.load("path/to/your/presentation.pptx")

print(f"幻灯片数量：{doc.metadata['slide_count']}")
print(doc.text[:500])
```

### 4.4 运行集成测试

```bash
# 测试 PDF 加载器
pytest tests/integration/test_pdf_loader_integration.py -v

# 测试 OCR 功能
pytest tests/integration/test_pdf_ocr_integration.py -v

# 测试所有加载器
pytest tests/unit/test_loader_pdf_contract.py -v
```

---

## 5. 测试 MCP 服务

### 5.1 启动 MCP 服务器

```bash
python -m src.mcp_server.server
```

### 5.2 使用 MCP 工具

在另一个终端中，使用 MCP 客户端测试：

```python
# 测试查询知识库
from src.mcp_server.server import query_knowledge_hub

results = query_knowledge_hub(
    query="保险理赔流程是什么？",
    top_k=3
)

for result in results:
    print(f"来源：{result.get('source')}")
    print(f"内容：{result.get('content')[:200]}")
    print("---")
```

### 5.3 运行 MCP 集成测试

```bash
pytest tests/integration/test_mcp_server.py -v
```

---

## 6. 运行 Dashboard

### 6.1 启动 Streamlit Dashboard

```bash
# 方式一：使用脚本
python scripts/start_dashboard.py

# 方式二：直接运行
streamlit run src/observability/dashboard/app.py
```

### 6.2 访问 Dashboard

打开浏览器访问：`http://localhost:8501`

### 6.3 Dashboard 功能

- 📊 数据导入监控
- 🔍 查询测试面板
- 📈 评估指标可视化
- 📝 文档浏览

---

## 7. 完整测试流程示例

### 步骤 1：生成测试数据

```bash
python tests/fixtures/generate_financial_insurance_test_data.py
```

### 步骤 2：运行数据导入

```bash
python scripts/ingest.py --input-dir tests/fixtures/financial_insurance_data/
```

### 步骤 3：执行查询测试

```bash
python scripts/query.py "保险理赔需要哪些材料？"
```

### 步骤 4：运行评估

```bash
python scripts/demo_evaluation.py
```

### 步骤 5：查看 Dashboard

```bash
python scripts/start_dashboard.py
```

---

## 常见问题

### Q1: OCR 不可用怎么办？

确保已安装 PaddleOCR：

```bash
pip install paddleocr paddlepaddle
```

### Q2: 测试失败怎么办？

运行单元测试检查基本功能：

```bash
pytest tests/unit/ -v --tb=short
```

### Q3: 如何查看详细的错误日志？

```bash
# 启用调试日志
pytest tests/integration/test_pdf_ocr_integration.py -v -s
```

---

## 下一步

- 阅读 `docs/ADVANCED_DOCUMENT_LOADER_GUIDE.md` 了解更多加载器功能
- 阅读 `docs/EVALUATION_MODULES_GUIDE.md` 了解评估模块
- 查看 `README.md` 了解项目完整文档