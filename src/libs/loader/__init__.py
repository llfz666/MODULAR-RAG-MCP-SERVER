"""
Loader Module.

This package contains document loader components:
- Base loader class
- PDF loader with OCR support
- DOCX loader with comments/revisions
- PPTX loader with speaker notes
- XLSX loader with formulas
- File integrity checker
- OCR engines (PaddleOCR, RapidOCR, Tesseract)
- Unified loader factory
"""

from src.libs.loader.base_loader import BaseLoader
from src.libs.loader.pdf_loader import PdfLoader
from src.libs.loader.docx_loader import DocxLoader
from src.libs.loader.pptx_loader import PptxLoader
from src.libs.loader.xlsx_loader import XlsxLoader
from src.libs.loader.file_integrity import FileIntegrityChecker, SQLiteIntegrityChecker
from src.libs.loader.ocr_engine import (
    BaseOCREngine,
    PaddleOCREngine,
    RapidOCREngine,
    TesseractOCREngine,
    create_ocr_engine,
)
from src.libs.loader.loader_factory import (
    DocumentLoaderFactory,
    load_pdf,
    load_docx,
    load_pptx,
    load_xlsx,
)

__all__ = [
    # Base
    "BaseLoader",
    
    # Loaders
    "PdfLoader",
    "DocxLoader",
    "PptxLoader",
    "XlsxLoader",
    
    # Factory
    "DocumentLoaderFactory",
    "load_pdf",
    "load_docx",
    "load_pptx",
    "load_xlsx",
    
    # Integrity
    "FileIntegrityChecker",
    "SQLiteIntegrityChecker",
    
    # OCR
    "BaseOCREngine",
    "PaddleOCREngine",
    "RapidOCREngine",
    "TesseractOCREngine",
    "create_ocr_engine",
]
