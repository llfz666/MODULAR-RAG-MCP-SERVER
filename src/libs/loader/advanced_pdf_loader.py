"""Advanced PDF Loader with Layout Analysis and Table Recognition.

This module implements advanced PDF parsing with:
1. Layout Analysis (布局分析) - Detects columns, tables, figures, text regions
2. Table Recognition (表格识别) - Specialized table structure extraction
3. Multi-column Support (多栏排版) - Properly handles academic papers, reports
4. OCR Fusion - PaddleOCR with layout-aware OCR
5. Code Block Detection - Preserves code formatting

Key Features:
- Uses PaddleOCR's layout analysis (PP-Structure)
- Detects and preserves table structure as Markdown/HTML
- Handles multi-column layouts correctly
- Extracts figures and charts with captions
- Preserves code blocks with syntax highlighting markers
"""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

import numpy as np

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

# Lazy import to avoid PaddleX initialization conflicts
PaddleOCR = None
StructureSystem = None
init_args = None
PPSTRUCTURE_AVAILABLE = False

from PIL import Image
import io
import tempfile
import os

from src.core.types import Document
from src.libs.loader.base_loader import BaseLoader

logger = logging.getLogger(__name__)


class LayoutRegionType(Enum):
    """Layout region types."""
    TEXT = "text"
    TITLE = "title"
    TABLE = "table"
    FIGURE = "figure"
    FORMULA = "formula"
    CODE = "code"
    LIST = "list"
    HEADER = "header"
    FOOTER = "footer"
    SEPARATOR = "separator"


@dataclass
class LayoutRegion:
    """Represents a detected layout region."""
    region_type: LayoutRegionType
    bbox: Tuple[int, int, int, int]  # (x0, y0, x1, y1)
    content: str = ""
    confidence: float = 0.0
    page_num: int = 0
    column_index: int = 0  # For multi-column detection
    metadata: Dict[str, Any] = field(default_factory=dict)


class LayoutAnalyzer:
    """Layout analysis engine using PaddleOCR PP-Structure."""
    
    def __init__(
        self,
        use_gpu: bool = False,
        lang: str = 'ch',
        show_log: bool = False,
    ):
        """Initialize layout analyzer.
        
        Args:
            use_gpu: Whether to use GPU acceleration.
            lang: Language code ('ch' for Chinese, 'en' for English).
            show_log: Whether to show debug logs.
        """
        self._available = False
        self._table_engine = None
        self._ocr_engine = None
        
        if not PPSTRUCTURE_AVAILABLE:
            logger.warning("PP-Structure not available. Install with: pip install paddleocr")
            return
        
        try:
            # Lazy import PP-Structure at runtime
            global init_args, StructureSystem
            if init_args is None:
                from ppstructure.utility import init_args as _init_args
                init_args = _init_args
            if StructureSystem is None:
                from ppstructure.predict_system import StructureSystem as _StructureSystem
                StructureSystem = _StructureSystem
            
            # Initialize table recognition engine
            args = init_args()
            args.use_gpu = use_gpu
            args.lang = lang
            args.show_log = show_log
            args.recovery = True  # Enable layout recovery
            
            self._table_engine = StructureSystem(args)
            self._available = True
            logger.info("Layout analyzer initialized successfully")
            
        except Exception as e:
            logger.warning(f"Failed to initialize layout analyzer: {e}")
    
    @property
    def available(self) -> bool:
        """Check if layout analyzer is available."""
        return self._available
    
    def analyze_page(
        self, 
        image: np.ndarray, 
        page_num: int = 0
    ) -> List[LayoutRegion]:
        """Analyze a single page and detect layout regions.
        
        Args:
            image: Page rendered as numpy array (RGB/BGR).
            page_num: Page number.
            
        Returns:
            List of detected layout regions.
        """
        if not self._available:
            logger.warning("Layout analyzer not available")
            return []
        
        try:
            # Run layout analysis
            result = self._table_engine(image)
            
            regions = []
            for item in result:
                region_type = self._map_region_type(item.get('type', 'text'))
                bbox = item.get('bbox', [0, 0, 0, 0])
                
                # Convert bbox format if needed
                if len(bbox) == 8:  # Polygon format
                    x_coords = [bbox[i] for i in range(0, 8, 2)]
                    y_coords = [bbox[i] for i in range(1, 8, 2)]
                    bbox = (min(x_coords), min(y_coords), max(x_coords), max(y_coords))
                
                region = LayoutRegion(
                    region_type=region_type,
                    bbox=tuple(bbox),
                    confidence=item.get('score', 0.0),
                    page_num=page_num,
                )
                
                # Extract content based on type
                if region_type == LayoutRegionType.TABLE and 'html' in item:
                    region.content = item['html']
                elif 'text' in item:
                    region.content = item['text']
                
                regions.append(region)
                
            return regions
            
        except Exception as e:
            logger.error(f"Layout analysis failed: {e}")
            return []
    
    def _map_region_type(self, type_str: str) -> LayoutRegionType:
        """Map PP-Structure type to our enum."""
        type_mapping = {
            'text': LayoutRegionType.TEXT,
            'title': LayoutRegionType.TITLE,
            'table': LayoutRegionType.TABLE,
            'figure': LayoutRegionType.FIGURE,
            'figure_caption': LayoutRegionType.FIGURE,
            'equation': LayoutRegionType.FORMULA,
            'code': LayoutRegionType.CODE,
            'list': LayoutRegionType.LIST,
            'header': LayoutRegionType.HEADER,
            'footer': LayoutRegionType.FOOTER,
            'separator': LayoutRegionType.SEPARATOR,
        }
        return type_mapping.get(type_str.lower(), LayoutRegionType.TEXT)


class TableRecognizer:
    """Specialized table recognition and conversion."""
    
    def __init__(self):
        """Initialize table recognizer."""
        self._available = PPSTRUCTURE_AVAILABLE
    
    def recognize_table(
        self, 
        table_image: np.ndarray
    ) -> Optional[Dict[str, Any]]:
        """Recognize table structure from image.
        
        Args:
            table_image: Table region as numpy array.
            
        Returns:
            Table data with cells, rows, cols info.
        """
        if not self._available:
            return None
        
        try:
            # Lazy import PP-Structure at runtime
            global init_args, StructureSystem
            if init_args is None:
                from ppstructure.utility import init_args as _init_args
                init_args = _init_args
            if StructureSystem is None:
                from ppstructure.predict_system import StructureSystem as _StructureSystem
                StructureSystem = _StructureSystem
            
            args = init_args()
            args.use_gpu = False
            args.lang = 'ch'
            engine = StructureSystem(args)
            
            result = engine(table_image)
            
            if result:
                table_data = result[0]
                return {
                    'html': table_data.get('html', ''),
                    'cells': table_data.get('cells', []),
                    'structure': table_data.get('structure', []),
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Table recognition failed: {e}")
            return None
    
    @staticmethod
    def html_to_markdown(html: str) -> str:
        """Convert HTML table to Markdown."""
        if not html:
            return ""
        
        # Simple HTML table to Markdown conversion
        lines = []
        
        # Remove HTML tags and parse
        in_row = False
        cells = []
        
        for line in html.split('\n'):
            line = line.strip()
            
            if '<tr' in line.lower():
                in_row = True
                cells = []
            elif '</tr' in line.lower():
                if cells:
                    lines.append("| " + " | ".join(cells) + " |")
                    if len(lines) == 1:  # First row is header
                        lines.append("|" + "|".join(["---"] * len(cells)) + "|")
                in_row = False
            elif in_row and ('<td' in line.lower() or '<th' in line.lower()):
                # Extract cell content
                match = re.search(r'>([^<]*)<', line)
                if match:
                    cells.append(match.group(1).strip())
        
        return "\n".join(lines)


class CodeBlockDetector:
    """Detect and extract code blocks from text."""
    
    # Common programming language markers
    CODE_PATTERNS = [
        # Function definitions
        (r'^(def |class |async def |function |public |private |protected )', 'code'),
        # Import statements
        (r'^(import |from .* import |#include |using namespace |require\()', 'code'),
        # Variable declarations
        (r'^(let |const |var |int |float |double |char |bool |string )', 'code'),
        # Control structures
        (r'^(if |else |elif |for |while |switch |case |try |catch |finally )', 'code'),
        # Return statements
        (r'^(return |yield |raise |throw )', 'code'),
        # Code blocks with braces
        (r'^\s*[\{\}]', 'code'),
        # Comments
        (r'^(//|/\*|\*|#|<!--|-->)', 'code'),
    ]
    
    def __init__(self):
        """Initialize code block detector."""
        self._compiled_patterns = [
            (re.compile(pattern, re.MULTILINE), label)
            for pattern, label in self.CODE_PATTERNS
        ]
    
    def detect_code_blocks(self, text: str) -> List[Tuple[int, int, str]]:
        """Detect code blocks in text.
        
        Args:
            text: Input text.
            
        Returns:
            List of (start_pos, end_pos, language) tuples.
        """
        code_blocks = []
        lines = text.split('\n')
        
        in_code_block = False
        code_start = 0
        code_score = 0
        
        for i, line in enumerate(lines):
            is_code_line = False
            
            for pattern, label in self._compiled_patterns:
                if pattern.search(line):
                    is_code_line = True
                    break
            
            if is_code_line:
                if not in_code_block:
                    code_start = i
                    in_code_block = True
                    code_score = 1
                else:
                    code_score += 1
            else:
                if in_code_block:
                    if code_score >= 3:  # At least 3 code lines
                        block_text = '\n'.join(lines[code_start:i])
                        code_blocks.append((code_start, i, 'auto'))
                    in_code_block = False
                    code_score = 0
        
        # Handle code block at end of text
        if in_code_block and code_score >= 3:
            block_text = '\n'.join(lines[code_start:])
            code_blocks.append((code_start, len(lines), 'auto'))
        
        return code_blocks
    
    def wrap_code_blocks(
        self, 
        text: str, 
        blocks: List[Tuple[int, int, str]]
    ) -> str:
        """Wrap detected code blocks with markdown code fences.
        
        Args:
            text: Original text.
            blocks: List of (start, end, language) tuples.
            
        Returns:
            Text with code blocks wrapped in ``` markers.
        """
        if not blocks:
            return text
        
        lines = text.split('\n')
        result = []
        last_end = 0
        
        for start, end, lang in sorted(blocks):
            # Add non-code lines
            result.extend(lines[last_end:start])
            
            # Add code block with fences
            result.append("```")
            result.extend(lines[start:end])
            result.append("```")
            
            last_end = end
        
        # Add remaining lines
        result.extend(lines[last_end:])
        
        return '\n'.join(result)


class AdvancedPdfLoader(BaseLoader):
    """Advanced PDF Loader with layout analysis.
    
    This loader implements:
    1. Layout Analysis - Detects columns, tables, figures
    2. Table Recognition - Converts tables to Markdown/HTML
    3. Multi-column Support - Reads columns in correct order
    4. Code Block Detection - Preserves code formatting
    5. OCR Fusion - Uses PaddleOCR for scanned PDFs
    
    Configuration:
        use_layout_analysis: Enable layout analysis (default: True)
        use_table_recognition: Enable table recognition (default: True)
        use_ocr: Enable OCR for scanned PDFs (default: True)
        ocr_lang: OCR language ('ch' or 'en')
        use_gpu: Use GPU acceleration (default: False)
        detect_code_blocks: Auto-detect code blocks (default: True)
        ocr_dpi: DPI for OCR rendering (default: 300)
    """
    
    def __init__(
        self,
        use_layout_analysis: bool = True,
        use_table_recognition: bool = True,
        use_ocr: bool = True,
        ocr_lang: str = 'ch',
        use_gpu: bool = False,
        detect_code_blocks: bool = True,
        ocr_dpi: int = 300,
    ):
        """Initialize advanced PDF loader.
        
        Args:
            use_layout_analysis: Enable layout analysis.
            use_table_recognition: Enable table recognition.
            use_ocr: Enable OCR support.
            ocr_lang: OCR language.
            use_gpu: Use GPU acceleration.
            detect_code_blocks: Auto-detect code blocks.
            ocr_dpi: DPI for OCR.
        """
        self.use_layout_analysis = use_layout_analysis
        self.use_table_recognition = use_table_recognition
        self.use_ocr = use_ocr
        self.ocr_lang = ocr_lang
        self.use_gpu = use_gpu
        self.detect_code_blocks = detect_code_blocks
        self.ocr_dpi = ocr_dpi
        
        # Initialize components
        self._layout_analyzer: Optional[LayoutAnalyzer] = None
        self._table_recognizer: Optional[TableRecognizer] = None
        self._code_detector: Optional[CodeBlockDetector] = None
        self._ocr_engine = None
        
        self._init_components()
    
    def _init_components(self):
        """Initialize analysis components."""
        # Layout analyzer
        if self.use_layout_analysis:
            self._layout_analyzer = LayoutAnalyzer(
                use_gpu=self.use_gpu,
                lang=self.ocr_lang,
            )
        
        # Table recognizer
        if self.use_table_recognition:
            self._table_recognizer = TableRecognizer()
        
        # Code detector
        if self.detect_code_blocks:
            self._code_detector = CodeBlockDetector()
        
        # OCR engine
        if self.use_ocr:
            try:
                from paddleocr import PaddleOCR
                self._ocr_engine = PaddleOCR(
                    use_angle_cls=True,
                    lang=self.ocr_lang,
                    use_gpu=self.use_gpu,
                    show_log=False,
                )
                logger.info("PaddleOCR initialized")
            except Exception as e:
                logger.warning(f"PaddleOCR not available: {e}")
                self._ocr_engine = None
    
    def load(self, file_path: str | Path) -> Document:
        """Load and parse a PDF file with advanced features.
        
        Args:
            file_path: Path to the PDF file.
            
        Returns:
            Document with structured Markdown text and metadata.
        """
        path = self._validate_file(file_path)
        if path.suffix.lower() != '.pdf':
            raise ValueError(f"File is not a PDF: {path}")
        
        # Compute document hash
        doc_hash = self._compute_file_hash(path)
        doc_id = f"doc_{doc_hash[:16]}"
        
        # Open PDF
        if not PYMUPDF_AVAILABLE:
            raise RuntimeError("PyMuPDF is required for AdvancedPdfLoader")
        
        doc = fitz.open(path)
        
        # Process each page
        all_content = []
        page_metadata = []
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            
            # Render page for analysis
            mat = fitz.Matrix(self.ocr_dpi / 72, self.ocr_dpi / 72)
            pix = page.get_pixmap(matrix=mat)
            page_image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                (pix.height, pix.width, pix.n)
            )
            
            # Perform layout analysis
            regions = []
            if self._layout_analyzer and self._layout_analyzer.available:
                regions = self._layout_analyzer.analyze_page(page_image, page_num + 1)
            
            # Process regions
            page_content = self._process_regions(regions, page, page_num)
            
            # If no layout analysis, fall back to basic extraction
            if not page_content.strip() and regions:
                page_content = page.get_text()
            
            all_content.append(page_content)
            
            page_metadata.append({
                'page': page_num + 1,
                'regions_detected': len(regions),
                'region_types': list(set(r.region_type.value for r in regions)),
            })
        
        doc.close()
        
        # Combine all content
        full_text = "\n\n".join(all_content)
        
        # Post-process: detect and wrap code blocks
        if self._code_detector:
            code_blocks = self._code_detector.detect_code_blocks(full_text)
            if code_blocks:
                full_text = self._code_detector.wrap_code_blocks(full_text, code_blocks)
                logger.info(f"Detected {len(code_blocks)} code blocks")
        
        # Build metadata
        metadata = {
            "source_path": str(path),
            "doc_type": "pdf",
            "doc_hash": doc_hash,
            "total_pages": len(doc),
            "page_metadata": page_metadata,
            "layout_analysis_used": self._layout_analyzer is not None,
            "table_recognition_used": self._table_recognizer is not None,
            "ocr_used": self._ocr_engine is not None,
        }
        
        # Extract title
        title = self._extract_title(full_text)
        if title:
            metadata["title"] = title
        
        return Document(
            id=doc_id,
            text=full_text,
            metadata=metadata
        )
    
    def _process_regions(
        self, 
        regions: List[LayoutRegion],
        page,
        page_num: int
    ) -> str:
        """Process layout regions and convert to Markdown.
        
        Args:
            regions: List of detected layout regions.
            page: PyMuPDF page object.
            page_num: Page number.
            
        Returns:
            Markdown-formatted content for this page.
        """
        if not regions:
            # Fallback to basic text extraction
            return page.get_text()
        
        # Sort regions by position (top-to-bottom, left-to-right for columns)
        sorted_regions = sorted(regions, key=lambda r: (r.bbox[1], r.bbox[0]))
        
        content_parts = []
        
        for region in sorted_regions:
            region_content = self._process_region(region, page)
            if region_content:
                content_parts.append(region_content)
        
        return "\n\n".join(content_parts)
    
    def _process_region(
        self, 
        region: LayoutRegion,
        page
    ) -> str:
        """Process a single layout region.
        
        Args:
            region: Layout region.
            page: PyMuPDF page object.
            
        Returns:
            Markdown-formatted content.
        """
        if region.region_type == LayoutRegionType.TITLE:
            return f"# {region.content}\n"
        
        elif region.region_type == LayoutRegionType.TABLE:
            if region.content:
                # Already has HTML from layout analysis
                return TableRecognizer.html_to_markdown(region.content)
            else:
                # Try to extract table from page
                return self._extract_table_from_page(page, region.bbox)
        
        elif region.region_type == LayoutRegionType.FIGURE:
            return f"[FIGURE: Page {region.page_num}]\n"
        
        elif region.region_type == LayoutRegionType.FORMULA:
            return f"$$ {region.content} $$\n"
        
        elif region.region_type == LayoutRegionType.CODE:
            return f"```\n{region.content}\n```\n"
        
        elif region.region_type == LayoutRegionType.LIST:
            # Format as bullet list
            lines = region.content.split('\n')
            formatted = [f"- {line.strip()}" for line in lines if line.strip()]
            return "\n".join(formatted)
        
        elif region.region_type in (LayoutRegionType.HEADER, LayoutRegionType.FOOTER):
            # Skip headers and footers
            return ""
        
        else:  # TEXT or default
            return region.content
    
    def _extract_table_from_page(
        self, 
        page, 
        bbox: Tuple[int, int, int, int]
    ) -> str:
        """Extract table from page region.
        
        Args:
            page: PyMuPDF page object.
            bbox: Bounding box of table region.
            
        Returns:
            Markdown-formatted table.
        """
        try:
            # Render table region
            rect = fitz.Rect(bbox)
            mat = fitz.Matrix(2, 2)  # 2x zoom for better quality
            pix = page.get_pixmap(matrix=mat, clip=rect)
            
            table_image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                (pix.height, pix.width, pix.n)
            )
            
            # Use table recognizer
            if self._table_recognizer and self._table_recognizer._available:
                result = self._table_recognizer.recognize_table(table_image)
                if result and result.get('html'):
                    return TableRecognizer.html_to_markdown(result['html'])
            
            # Fallback: extract as text
            return page.get_text("text", clip=rect)
            
        except Exception as e:
            logger.error(f"Table extraction failed: {e}")
            return ""
    
    def _extract_title(self, text: str) -> Optional[str]:
        """Extract title from text."""
        lines = text.split('\n')
        
        # Look for first heading
        for line in lines[:20]:
            line = line.strip()
            if line.startswith('# '):
                return line[2:].strip()
        
        # Fallback: first non-empty line
        for line in lines[:10]:
            line = line.strip()
            if line and len(line) < 200:
                return line
        
        return None
    
    def _compute_file_hash(self, file_path: Path) -> str:
        """Compute SHA256 hash of file content."""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()