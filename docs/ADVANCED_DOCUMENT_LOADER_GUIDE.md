# 高级文档加载器使用指南

本指南介绍 Modular RAG MCP Server 新增的高级文档加载器功能，专门针对金融保险行业文档的特殊需求进行了优化。

## 目录

1. [功能概述](#功能概述)
2. [安装依赖](#安装依赖)
3. [核心功能](#核心功能)
4. [使用示例](#使用示例)
5. [金融保险测试数据生成](#金融保险测试数据生成)
6. [真实数据源获取](#真实数据源获取)
7. [常见问题](#常见问题)

---

## 功能概述

### 新增加载器

| 加载器 | 功能 | 适用场景 |
|--------|------|----------|
| `AdvancedPdfLoader` | PDF 布局分析 + 表格识别 + 多栏排版 | 金融报告、学术论文、保险条款 |
| `EnhancedPptxLoader` | PPT 图片 OCR + 演讲者备注提取 | 培训材料、产品演示、会议记录 |
| `VideoSubtitleLoader` | 视频字幕提取 + 音频转录 | 培训视频、产品介绍、会议录像 |

### 核心特性对比

| 特性 | 标准加载器 | 高级加载器 |
|------|-----------|-----------|
| PDF 多栏分析 | ❌ | ✅ PP-Structure 布局分析 |
| 表格识别 | 基础文本 | ✅ HTML/Markdown 转换 |
| PPT 图片 OCR | ❌ | ✅ PaddleOCR 集成 |
| 演讲者备注 | ✅ | ✅ (增强) |
| 视频字幕 | ❌ | ✅ SRT/VTT/ASS + Whisper |
| 代码块检测 | ❌ | ✅ 自动识别格式化 |

---

## 安装依赖

### 基础依赖

```bash
# 核心依赖
pip install pymupdf pillow

# PPTX 处理
pip install python-pptx

# DOCX 处理
pip install python-docx

# XLSX 处理
pip install openpyxl
```

### 高级功能依赖（可选）

```bash
# PaddleOCR - 用于布局分析和图片 OCR
pip install paddlepaddle
pip install paddleocr

# Whisper - 用于音频转录
pip install openai-whisper

# 测试数据生成
pip install reportlab
```

### 完整安装命令

```bash
# 安装所有可选依赖
pip install paddlepaddle paddleocr openai-whisper reportlab
```

---

## 核心功能

### 1. AdvancedPdfLoader - 高级 PDF 加载器

#### 特性
- **布局分析 (Layout Analysis)**: 检测多栏、表格、图表、公式
- **表格识别 (Table Recognition)**: 将表格转换为 Markdown/HTML
- **OCR 融合**: PaddleOCR 支持扫描件
- **代码块检测**: 自动识别并格式化代码

#### 使用示例

```python
from src.libs.loader.loader_factory import load_pdf_advanced

# 基础使用 - 自动检测布局
doc = load_pdf_advanced(
    "financial_report.pdf",
    use_layout_analysis=True,  # 启用布局分析
    use_table_recognition=True,  # 启用表格识别
    use_ocr=True,  # 启用 OCR
    ocr_lang='ch',  # 中文识别
    use_gpu=False,  # 不使用 GPU
    detect_code_blocks=True,  # 检测代码块
)

print(f"文档 ID: {doc.id}")
print(f"内容长度：{len(doc.text)}")
print(f"元数据：{doc.metadata}")
```

#### 输出示例

```markdown
# 金融保险行业报告

## 第一章：市场概况

市场规模持续扩大，2024 年原保险保费收入同比增长 8.5%...

| 指标 | 2023 年 | 2024 年 | 增长率 |
|------|--------|--------|--------|
| 保费收入 | 500 亿 | 550 亿 | 10% |
| 净利润 | 80 亿 | 95 亿 | 18.75% |

[FIGURE: Page 3]

```
def calculate_premium(base_rate, age_factor):
    return base_rate * age_factor
```
```

### 2. EnhancedPptxLoader - 增强 PPT 加载器

#### 特性
- **演讲者备注提取**: 优先提取演讲者备注（通常包含关键信息）
- **图片 OCR**: 对幻灯片中的图片进行 OCR 识别
- **图表文本提取**: 提取图表中的文字信息
- **完整结构保留**: 保留幻灯片层级结构

#### 使用示例

```python
from src.libs.loader.loader_factory import load_pptx_enhanced

# 加载 PPT 并提取图片 OCR
doc = load_pptx_enhanced(
    "insurance_training.pptx",
    extract_notes=True,      # 提取演讲者备注
    extract_images=True,     # 提取图片
    ocr_images=True,         # 对图片进行 OCR
    ocr_lang='ch',           # 中文识别
    use_gpu=False,
)

print(f"幻灯片数量：{doc.metadata.get('total_slides')}")
print(f"有备注的幻灯片：{doc.metadata.get('slides_with_notes')}")
print(f"图片 OCR 结果：{doc.metadata.get('ocr_results')}")
```

#### 输出示例

```markdown
# 2024 年保险业务发展报告

## 幻灯片 1

### 市场概况

- 市场规模持续扩大
- 健康险增速显著

**【演讲者备注】**:
> 介绍保险行业的整体发展情况
> 关键点说明：需要重点强调数据背后的意义

[IMAGE: abc123_s1_img_0]

## 【图片 OCR 识别结果】

### 幻灯片 1 - 图片 0
```
2024 年保费收入增长率：8.5%
人身险占比：65%
财产险占比：35%
```
```

### 3. VideoSubtitleLoader - 视频字幕加载器

#### 特性
- **字幕提取**: 支持 SRT、VTT、ASS 格式
- **音频转录**: Whisper 语音转文字（无字幕时）
- **语义分段**: 按语义自动分段

#### 使用示例

```python
from src.libs.loader.loader_factory import load_video

# 加载视频并提取字幕
result = load_video(
    "training_video.mp4",
    extract_subtitles=True,    # 提取字幕
    transcribe_audio=True,     # 无字幕时转录音频
    whisper_model='base',      # Whisper 模型大小
    language='zh',             # 中文
    semantic_segmentation=True, # 语义分段
)

print(f"字幕数量：{result['metadata']['subtitle_count']}")
print(f"分段数量：{result['metadata']['segment_count']}")
print(f"完整文本：{result['full_text'][:500]}...")
```

#### 输出示例

```json
{
  "id": "doc_abc123",
  "full_text": "欢迎观看保险产品介绍视频。首先，我们来了解一下什么是人寿保险...",
  "subtitles": [
    {
      "index": 1,
      "start_time": "00:00:01,000",
      "end_time": "00:00:04,000",
      "text": "欢迎观看保险产品介绍视频"
    }
  ],
  "segments": [
    {
      "text": "欢迎观看保险产品介绍视频。首先，我们来了解一下什么是人寿保险...",
      "start_seconds": 0,
      "end_seconds": 30
    }
  ],
  "metadata": {
    "subtitle_count": 10,
    "segment_count": 5,
    "extraction_method": "subtitle"
  }
}
```

---

## 使用示例

### 场景 1: 处理金融报告 PDF

```python
from src.libs.loader.loader_factory import DocumentLoaderFactory

# 使用高级加载器处理多栏 PDF
loader = DocumentLoaderFactory.create_loader(
    "annual_report.pdf",
    use_advanced=True,  # 使用高级加载器
    use_layout_analysis=True,
    use_table_recognition=True,
)

doc = loader.load("annual_report.pdf")

# 检查是否检测到表格
if 'table' in str(doc.metadata.get('region_types', [])):
    print("检测到表格内容")
```

### 场景 2: 处理保险培训 PPT

```python
from src.libs.loader.loader_factory import load_pptx_enhanced

# 加载培训 PPT，提取演讲者备注和图片 OCR
doc = load_pptx_enhanced(
    "agent_training.pptx",
    extract_notes=True,
    ocr_images=True,
    ocr_lang='ch',
)

# 查找包含关键信息的备注
for slide in doc.metadata.get('slides', []):
    if slide.get('has_notes'):
        print(f"幻灯片 {slide['slide_number']} 备注：{slide.get('notes_preview')}")
```

### 场景 3: 批量处理文档

```python
from pathlib import Path
from src.libs.loader.loader_factory import DocumentLoaderFactory

def batch_process_documents(input_dir: str, output_dir: str):
    """批量处理文档目录"""
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    for file_path in input_path.glob("*"):
        try:
            # 自动检测文件类型并使用适当加载器
            loader = DocumentLoaderFactory.create_loader(
                file_path,
                use_advanced=file_path.suffix.lower() in ['.pdf', '.pptx'],
            )
            doc = loader.load(file_path)
            
            # 保存为 Markdown
            output_file = output_path / f"{file_path.stem}.md"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(doc.text)
            
            print(f"✓ 处理完成：{file_path.name}")
            
        except Exception as e:
            print(f"✗ 处理失败：{file_path.name} - {e}")

# 使用示例
batch_process_documents("input_docs", "output_md")
```

---

## 金融保险测试数据生成

### 生成测试数据

```bash
# 运行测试数据生成脚本
python tests/fixtures/generate_financial_insurance_test_data.py --output-dir tests/fixtures/financial_insurance_data
```

### 生成的文件类型

| 文件 | 描述 | 测试功能 |
|------|------|----------|
| `insurance_report_multicolumn.pdf` | 多栏金融报告 PDF | 布局分析、表格识别 |
| `insurance_presentation.pptx` | 保险业务 PPT | 演讲者备注、图片 OCR |
| `insurance_policy.docx` | 保险合同文档 | 复杂格式处理 |
| `financial_data.xlsx` | 财务数据表格 | 公式和数据提取 |
| `sample_video_subtitles.srt` | 示例字幕文件 | 字幕解析 |

### 依赖安装

```bash
pip install reportlab python-pptx python-docx openpyxl
```

---

## 真实数据源获取

### 公开金融保险数据源

1. **SEC EDGAR 数据库** (美国)
   - 网址：https://www.sec.gov/edgar
   - 内容：上市公司财报、保险行业文件

2. **NAIC** (美国保险监管协会)
   - 网址：https://www.naic.org
   - 内容：保险行业报告、统计数据

3. **中国银保监会**
   - 网址：http://www.cbirc.gov.cn
   - 内容：监管文件、行业数据

4. **保险公司年报**
   - 中国人寿、中国平安等公司官网
   - 内容：年度报告、社会责任报告

5. **Kaggle 数据集**
   - 搜索 "insurance", "financial"
   - 网址：https://www.kaggle.com/datasets

### 使用真实数据的注意事项

1. **版权合规**: 确保有使用权限
2. **数据脱敏**: 移除敏感客户信息
3. **引用来源**: 在研究/文档中注明数据来源
4. **使用限制**: 遵守数据提供方的使用条款

---

## 常见问题

### Q1: 安装 PaddleOCR 后环境冲突怎么办？

**解决方案**:
```bash
# 1. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 2. 先安装基础依赖
pip install numpy==1.24.3

# 3. 安装 PaddleOCR
pip install paddlepaddle paddleocr

# 4. 如有冲突，使用 --force-reinstall
pip install --force-reinstall paddlepaddle
```

### Q2: 布局分析检测不到表格？

**可能原因**:
- PDF 是扫描件而非文本 PDF
- 表格格式复杂

**解决方案**:
```python
# 启用 OCR 辅助
doc = load_pdf_advanced(
    "document.pdf",
    use_layout_analysis=True,
    use_table_recognition=True,
    use_ocr=True,  # 启用 OCR
    ocr_dpi=300,   # 提高 DPI
)
```

### Q3: PPT 图片 OCR 识别率低？

**优化建议**:
```python
# 使用 GPU 加速和更高分辨率
doc = load_pptx_enhanced(
    "presentation.pptx",
    ocr_images=True,
    use_gpu=True,      # 使用 GPU
    ocr_lang='ch',     # 确保语言正确
)
```

### Q4: 视频字幕提取失败？

**检查事项**:
1. 确认 ffmpeg 已安装：`ffmpeg -version`
2. 视频是否包含内嵌字幕
3. 尝试音频转录作为备选

```python
result = load_video(
    "video.mp4",
    extract_subtitles=True,
    transcribe_audio=True,  # 备选方案
    whisper_model='medium',  # 使用更大模型提高准确率
)
```

### Q5: 如何处理超大 PDF 文件？

```python
import fitz  # PyMuPDF

def process_large_pdf(pdf_path: str, max_pages: int = 100):
    """分批处理大 PDF"""
    doc = fitz.open(pdf_path)
    
    # 只处理前 N 页
    for page_num in range(min(max_pages, len(doc))):
        page = doc[page_num]
        # 处理每页...
    
    doc.close()
```

---

## API 参考

### DocumentLoaderFactory

```python
from src.libs.loader.loader_factory import DocumentLoaderFactory

# 创建加载器
loader = DocumentLoaderFactory.create_loader(
    "document.pdf",
    use_advanced=False,  # 使用标准或高级加载器
    **kwargs
)

# 直接加载
doc = DocumentLoaderFactory.load("document.pdf")

# 获取支持的文件类型
extensions = DocumentLoaderFactory.get_supported_extensions()
```

### 高级加载器参数

```python
# AdvancedPdfLoader
AdvancedPdfLoader(
    use_layout_analysis=True,    # 布局分析
    use_table_recognition=True,  # 表格识别
    use_ocr=True,                # OCR 支持
    ocr_lang='ch',               # OCR 语言
    use_gpu=False,               # GPU 加速
    detect_code_blocks=True,     # 代码块检测
    ocr_dpi=300,                 # OCR DPI
)

# EnhancedPptxLoader
EnhancedPptxLoader(
    extract_notes=True,          # 演讲者备注
    extract_images=True,         # 图片提取
    ocr_images=True,             # 图片 OCR
    ocr_lang='ch',
    use_gpu=False,
    image_storage_dir="data/images",
)

# VideoSubtitleLoader
VideoSubtitleLoader(
    extract_subtitles=True,      # 字幕提取
    transcribe_audio=True,       # 音频转录
    whisper_model='base',        # 模型大小
    language='zh',
    semantic_segmentation=True,  # 语义分段
)
```

---

## 更新日志

### v1.0.0 (2024)
- ✅ 新增 `AdvancedPdfLoader` 支持布局分析和表格识别
- ✅ 新增 `EnhancedPptxLoader` 支持图片 OCR
- ✅ 新增 `VideoSubtitleLoader` 支持字幕提取和音频转录
- ✅ 更新 `DocumentLoaderFactory` 支持高级加载器
- ✅ 新增金融保险测试数据生成器

---

## 联系与支持

如有问题或建议，请提交 Issue 或联系开发团队。