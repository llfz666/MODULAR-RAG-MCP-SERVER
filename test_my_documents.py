#!/usr/bin/env python
"""
简单测试脚本 - 测试您自己的文档

使用方法:
    python test_my_documents.py

这个脚本会：
1. 测试 PDF 加载器读取生成的测试文档
2. 显示文档内容和元数据
3. 测试 PPTX、DOCX、XLSX 加载器
"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from src.libs.loader.pdf_loader import PdfLoader

# 检查依赖 - 使用导入测试（最可靠的方式）
def try_import_module(module_name, import_statement):
    """尝试导入模块来检查是否可用"""
    try:
        exec(import_statement)
        print(f"[DEBUG] {module_name}: ✅ 可导入")
        return True
    except Exception as e:
        print(f"[DEBUG] {module_name}: ❌ 不可用 - {e}")
        return False

# 检查各个依赖
print("\n[DEBUG] 检查依赖包状态...")
PPTX_AVAILABLE = try_import_module("python-pptx", "from pptx import Presentation")
DOCX_AVAILABLE = try_import_module("python-docx", "from docx import Document")
XLSX_AVAILABLE = try_import_module("openpyxl", "import openpyxl")
print("[DEBUG] 依赖检查完成\n")

# 现在导入加载器 - 使用 try/except 直接捕获
PptxLoader = None
DocxLoader = None
XlsxLoader = None

if PPTX_AVAILABLE:
    try:
        from src.libs.loader.pptx_loader import PptxLoader
    except Exception as e:
        print(f"[DEBUG] PptxLoader 导入失败：{e}")
        PPTX_AVAILABLE = False

if DOCX_AVAILABLE:
    try:
        from src.libs.loader.docx_loader import DocxLoader
    except Exception as e:
        print(f"[DEBUG] DocxLoader 导入失败：{e}")
        DOCX_AVAILABLE = False

if XLSX_AVAILABLE:
    try:
        from src.libs.loader.xlsx_loader import XlsxLoader
    except Exception as e:
        print(f"[DEBUG] XlsxLoader 导入失败：{e}")
        XLSX_AVAILABLE = False


def test_pdf_loader():
    """测试 PDF 加载器"""
    print("=" * 60)
    print("测试 PDF 加载器")
    print("=" * 60)
    
    pdf_path = "tests/fixtures/financial_insurance_data/insurance_report_multicolumn.pdf"
    
    if not Path(pdf_path).exists():
        print(f"❌ 文件不存在：{pdf_path}")
        return
    
    # 初始化加载器
    loader = PdfLoader(
        extract_images=False,  # 暂时不提取图片
        enable_ocr=False,      # 暂时不启用 OCR（加速测试）
    )
    
    # 加载文档
    print(f"📄 正在加载：{pdf_path}")
    doc = loader.load(pdf_path)
    
    # 显示结果
    print(f"✅ 加载成功!")
    print(f"   文档 ID: {doc.id}")
    print(f"   文档类型：{doc.metadata['doc_type']}")
    print(f"   是否有文字层：{doc.metadata['has_text_layer']}")
    print(f"   内容长度：{len(doc.text)} 字符")
    print(f"\n📝 内容预览 (前 300 字):")
    print("-" * 40)
    print(doc.text[:300])
    print("-" * 40)


def test_pptx_loader():
    """测试 PPTX 加载器"""
    print("\n" + "=" * 60)
    print("测试 PPTX 加载器")
    print("=" * 60)
    
    if not PPTX_AVAILABLE:
        print("⚠️  跳过：缺少 python-pptx 依赖")
        print("   安装：pip install python-pptx")
        return
    
    pptx_path = "tests/fixtures/financial_insurance_data/insurance_presentation.pptx"
    
    if not Path(pptx_path).exists():
        print(f"❌ 文件不存在：{pptx_path}")
        return
    
    try:
        loader = PptxLoader()
    except Exception as e:
        print(f"⚠️  跳过：初始化失败 - {e}")
        return
    
    print(f"📄 正在加载：{pptx_path}")
    doc = loader.load(pptx_path)
    
    print(f"✅ 加载成功!")
    print(f"   文档 ID: {doc.id}")
    print(f"   幻灯片数量：{doc.metadata.get('slide_count', 'N/A')}")
    print(f"\n📝 内容预览 (前 300 字):")
    print("-" * 40)
    print(doc.text[:300])
    print("-" * 40)


def test_docx_loader():
    """测试 DOCX 加载器"""
    print("\n" + "=" * 60)
    print("测试 DOCX 加载器")
    print("=" * 60)
    
    if not DOCX_AVAILABLE:
        print("⚠️  跳过：缺少 python-docx 依赖")
        print("   安装：pip install python-docx")
        return
    
    docx_path = "tests/fixtures/financial_insurance_data/insurance_policy.docx"
    
    if not Path(docx_path).exists():
        print(f"❌ 文件不存在：{docx_path}")
        return
    
    try:
        loader = DocxLoader()
    except Exception as e:
        print(f"⚠️  跳过：初始化失败 - {e}")
        return
    
    print(f"📄 正在加载：{docx_path}")
    doc = loader.load(docx_path)
    
    print(f"✅ 加载成功!")
    print(f"   文档 ID: {doc.id}")
    print(f"   段落数量：{doc.metadata.get('paragraph_count', 'N/A')}")
    print(f"\n📝 内容预览 (前 300 字):")
    print("-" * 40)
    print(doc.text[:300])
    print("-" * 40)


def test_xlsx_loader():
    """测试 XLSX 加载器"""
    print("\n" + "=" * 60)
    print("测试 XLSX 加载器")
    print("=" * 60)
    
    if not XLSX_AVAILABLE:
        print("⚠️  跳过：缺少 openpyxl 依赖")
        print("   安装：pip install openpyxl")
        return
    
    xlsx_path = "tests/fixtures/financial_insurance_data/financial_data.xlsx"
    
    if not Path(xlsx_path).exists():
        print(f"❌ 文件不存在：{xlsx_path}")
        return
    
    try:
        loader = XlsxLoader()
        print(f"📄 正在加载：{xlsx_path}")
        doc = loader.load(xlsx_path)
    except Exception as e:
        print(f"⚠️  跳过：加载失败 - {e}")
        return
    
    print(f"✅ 加载成功!")
    print(f"   文档 ID: {doc.id}")
    print(f"   工作表数量：{doc.metadata.get('sheet_count', 'N/A')}")
    print(f"\n📝 内容预览 (前 300 字):")
    print("-" * 40)
    print(doc.text[:300])
    print("-" * 40)


def main():
    """主函数"""
    print("\n🚀 文档加载器测试套件\n")
    
    try:
        # 测试各个加载器
        test_pdf_loader()
        test_pptx_loader()
        test_docx_loader()
        test_xlsx_loader()
        
        print("\n" + "=" * 60)
        print("✅ 所有测试完成!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 测试失败：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()