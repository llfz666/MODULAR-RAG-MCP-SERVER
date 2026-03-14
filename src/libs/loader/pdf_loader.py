"""PDF Loader implementation with OCR support.

This module implements PDF parsing with image extraction and OCR support,
converting PDFs to standardized Markdown format with image placeholders.

Features:
- Text extraction and Markdown conversion via MarkItDown
- Image extraction and storage
- OCR support for scanned PDFs (PaddleOCR, RapidOCR, Tesseract)
- Hybrid mode: prefer text layer, fallback to OCR
- Image placeholder insertion with metadata tracking
- Graceful degradation if image extraction fails
"""

from __future__ import annotations

import hashlib
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from markitdown import MarkItDown
    MARKITDOWN_AVAILABLE = True
except ImportError:
    MARKITDOWN_AVAILABLE = False

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

from PIL import Image
import io

from src.core.types import Document
from src.libs.loader.base_loader import BaseLoader
from src.libs.loader.ocr_engine import (
    BaseOCREngine,
    PaddleOCREngine,
    RapidOCREngine,
    TesseractOCREngine,
    create_ocr_engine,
)

logger = logging.getLogger(__name__)


class PdfLoader(BaseLoader):
    """PDF Loader using MarkItDown for text extraction and OCR for scanned PDFs.
    
    This loader:
    1. Extracts text from PDF and converts to Markdown
    2. Extracts images and saves to data/images/{doc_hash}/
    3. Inserts image placeholders in the format [IMAGE: {image_id}]
    4. Records image metadata in Document.metadata.images
    5. Supports OCR for scanned PDFs with multiple backends
    
    Configuration:
        extract_images: Enable/disable image extraction (default: True)
        image_storage_dir: Base directory for image storage (default: data/images)
        enable_ocr: Enable OCR for scanned PDFs (default: True)
        ocr_backend: OCR backend to use ('paddle', 'rapid', 'tesseract')
        ocr_lang: OCR language ('ch' for Chinese, 'en' for English)
        ocr_threshold: Text length threshold to trigger OCR (default: 100)
        ocr_dpi: DPI for rendering PDF pages during OCR (default: 200)
    
    Graceful Degradation:
        If image extraction fails, logs warning and continues with text-only parsing.
        If OCR fails, falls back to text-only extraction.
    """
    
    def __init__(
        self,
        extract_images: bool = True,
        image_storage_dir: str | Path = "data/images",
        enable_ocr: bool = True,
        ocr_backend: str = 'paddle',
        ocr_lang: str = 'ch',
        ocr_threshold: int = 100,
        ocr_dpi: int = 200,
        ocr_use_gpu: bool = False,
    ):
        """Initialize PDF Loader.
        
        Args:
            extract_images: Whether to extract images from PDFs.
            image_storage_dir: Base directory for storing extracted images.
            enable_ocr: Whether to enable OCR for scanned PDFs.
            ocr_backend: OCR backend to use ('paddle', 'rapid', 'tesseract').
            ocr_lang: OCR language code.
            ocr_threshold: Minimum text length to consider PDF as having text layer.
            ocr_dpi: DPI for rendering PDF pages during OCR.
            ocr_use_gpu: Whether to use GPU for OCR (only for PaddleOCR).
        """
        if not MARKITDOWN_AVAILABLE:
            raise ImportError(
                "MarkItDown is required for PdfLoader. "
                "Install with: pip install markitdown"
            )
        
        self.extract_images = extract_images
        self.image_storage_dir = Path(image_storage_dir)
        self._markitdown = MarkItDown()
        
        # OCR configuration
        self.enable_ocr = enable_ocr
        self.ocr_threshold = ocr_threshold
        self.ocr_dpi = ocr_dpi
        self._ocr_engine: Optional[BaseOCREngine] = None
        
        if enable_ocr:
            self._init_ocr_engine(ocr_backend, ocr_lang, ocr_use_gpu)
    
    def _init_ocr_engine(
        self, 
        backend: str, 
        lang: str, 
        use_gpu: bool
    ) -> None:
        """Initialize OCR engine with fallback logic.
        
        Args:
            backend: Preferred OCR backend.
            lang: Language code.
            use_gpu: Whether to use GPU.
        """
        # Try preferred backend first
        try:
            self._ocr_engine = create_ocr_engine(
                backend=backend,
                lang=lang if backend == 'paddle' else None,
                use_gpu=use_gpu if backend == 'paddle' else False,
            )
            if self._ocr_engine and self._ocr_engine.available:
                logger.info(f"Initialized OCR engine: {backend}")
                return
        except Exception as e:
            logger.warning(f"Failed to initialize {backend} OCR: {e}")
        
        # Fallback chain
        fallback_order = ['paddle', 'rapid', 'tesseract']
        for fallback_backend in fallback_order:
            if fallback_backend == backend:
                continue
            try:
                if fallback_backend == 'paddle':
                    self._ocr_engine = create_ocr_engine(
                        backend=fallback_backend,
                        lang=lang,
                        use_gpu=use_gpu,
                    )
                elif fallback_backend == 'rapid':
                    self._ocr_engine = create_ocr_engine(
                        backend=fallback_backend,
                        use_cuda=use_gpu,
                    )
                else:
                    self._ocr_engine = create_ocr_engine(
                        backend=fallback_backend,
                        lang='chi_sim+eng' if 'ch' in lang else 'eng',
                    )
                
                if self._ocr_engine and self._ocr_engine.available:
                    logger.info(f"Initialized fallback OCR engine: {fallback_backend}")
                    return
            except Exception as e:
                logger.debug(f"Fallback {fallback_backend} OCR not available: {e}")
        
        logger.warning("No OCR engine available, OCR will be disabled")
        self._ocr_engine = None
        self.enable_ocr = False
    
    def load(self, file_path: str | Path) -> Document:
        """Load and parse a PDF file.
        
        Args:
            file_path: Path to the PDF file.
            
        Returns:
            Document with Markdown text and metadata.
            
        Raises:
            FileNotFoundError: If the PDF file doesn't exist.
            ValueError: If the file is not a valid PDF.
            RuntimeError: If parsing fails critically.
        """
        # Validate file
        path = self._validate_file(file_path)
        if path.suffix.lower() != '.pdf':
            raise ValueError(f"File is not a PDF: {path}")
        
        # Compute document hash for unique ID and image directory
        doc_hash = self._compute_file_hash(path)
        doc_id = f"doc_{doc_hash[:16]}"
        
        # First, extract images using PyMuPDF (before MarkItDown parsing)
        images_metadata = []
        if self.extract_images and PYMUPDF_AVAILABLE:
            try:
                images_metadata = self._extract_images_with_pymupdf(path, doc_hash)
                logger.info(f"Extracted {len(images_metadata)} images from {path}")
            except Exception as e:
                logger.warning(f"PyMuPDF image extraction failed: {e}")
        
        # Check if PDF has a text layer by extracting text with PyMuPDF
        has_text_layer = self._check_text_layer(path)
        
        # Parse PDF with MarkItDown
        text_content = ""
        use_ocr = False
        
        if has_text_layer:
            try:
                result = self._markitdown.convert(str(path))
                text_content = result.text_content if hasattr(result, 'text_content') else str(result)
            except Exception as e:
                logger.warning(f"MarkItDown parsing failed: {e}")
        
        # Determine if OCR is needed
        if not has_text_layer or len(text_content.strip()) < self.ocr_threshold:
            if self.enable_ocr and self._ocr_engine:
                logger.info(
                    f"OCR triggered for {path}: "
                    f"has_text_layer={has_text_layer}, text_len={len(text_content.strip())}"
                )
                use_ocr = True
        
        # Perform OCR if needed
        if use_ocr:
            try:
                ocr_text = self._ocr_engine.recognize_pdf(path, dpi=self.ocr_dpi)
                if ocr_text:
                    # Combine OCR text with any MarkItDown text
                    if text_content:
                        text_content = f"{text_content}\n\n=== OCR Content ===\n{ocr_text}"
                    else:
                        text_content = ocr_text
                    logger.info(f"OCR extracted {len(ocr_text)} characters from {path}")
            except Exception as e:
                logger.error(f"OCR failed: {e}")
                # If we have no text at all, raise error
                if not text_content.strip():
                    raise RuntimeError(f"Both MarkItDown and OCR failed for {path}") from e
        
        # Initialize metadata
        metadata: Dict[str, Any] = {
            "source_path": str(path),
            "doc_type": "pdf",
            "doc_hash": doc_hash,
            "has_text_layer": has_text_layer,
            "ocr_used": use_ocr,
            "ocr_backend": self._ocr_engine.__class__.__name__ if use_ocr and self._ocr_engine else None,
        }
        
        # Extract title from first heading if available
        title = self._extract_title(text_content)
        if title:
            metadata["title"] = title
        
        # Add image metadata
        if images_metadata:
            metadata["images"] = images_metadata
            # Insert image placeholders into text if not already present
            text_content = self._insert_image_placeholders(text_content, images_metadata)
        
        return Document(
            id=doc_id,
            text=text_content,
            metadata=metadata
        )
    
    def _check_text_layer(self, pdf_path: Path) -> bool:
        """Check if PDF has an embedded text layer.
        
        Args:
            pdf_path: Path to PDF file.
            
        Returns:
            True if PDF has a text layer, False otherwise.
        """
        if not PYMUPDF_AVAILABLE:
            return False
        
        try:
            doc = fitz.open(pdf_path)
            total_text_len = 0
            
            # Check first few pages for text content
            for page_num in range(min(3, len(doc))):
                page = doc[page_num]
                text = page.get_text()
                total_text_len += len(text.strip())
                
                # Early exit if we found enough text
                if total_text_len >= self.ocr_threshold:
                    doc.close()
                    return True
            
            doc.close()
            return total_text_len >= self.ocr_threshold
            
        except Exception as e:
            logger.warning(f"Failed to check text layer: {e}")
            return False
    
    def _compute_file_hash(self, file_path: Path) -> str:
        """Compute SHA256 hash of file content.
        
        Args:
            file_path: Path to file.
            
        Returns:
            Hex string of SHA256 hash.
        """
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    def _extract_title(self, text: str) -> Optional[str]:
        """Extract title from first Markdown heading or first non-empty line.
        
        Args:
            text: Markdown text content.
            
        Returns:
            Title string if found, None otherwise.
        """
        lines = text.split('\n')
        
        # First try to find a markdown heading
        for line in lines[:20]:  # Check first 20 lines
            line = line.strip()
            if line.startswith('# '):
                return line[2:].strip()
        
        # Fallback: use first non-empty line as title
        for line in lines[:10]:
            line = line.strip()
            if line and len(line) > 0:
                return line
        
        return None
    
    def _extract_images_with_pymupdf(
        self,
        pdf_path: Path,
        doc_hash: str
    ) -> List[Dict[str, Any]]:
        """Extract images from PDF using PyMuPDF directly.
        
        This method extracts all images from the PDF and saves them
        to the designated storage directory.
        
        Args:
            pdf_path: Path to PDF file.
            doc_hash: Document hash for image directory.
            
        Returns:
            List of image metadata dictionaries.
        """
        if not PYMUPDF_AVAILABLE:
            logger.warning(f"PyMuPDF not available for image extraction")
            return []
        
        images_metadata = []
        
        try:
            # Create image storage directory
            image_dir = self.image_storage_dir / doc_hash
            image_dir.mkdir(parents=True, exist_ok=True)
            
            # Open PDF with PyMuPDF
            doc = fitz.open(pdf_path)
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                image_list = page.get_images(full=True)
                
                for img_index, img_info in enumerate(image_list):
                    try:
                        # Extract image
                        xref = img_info[0]
                        base_image = doc.extract_image(xref)
                        image_bytes = base_image["image"]
                        image_ext = base_image["ext"]
                        
                        # Generate image ID and filename
                        image_id = self._generate_image_id(doc_hash, page_num + 1, img_index + 1)
                        image_filename = f"{image_id}.{image_ext}"
                        image_path = image_dir / image_filename
                        
                        # Save image
                        with open(image_path, "wb") as img_file:
                            img_file.write(image_bytes)
                        
                        # Get image dimensions
                        try:
                            img = Image.open(io.BytesIO(image_bytes))
                            width, height = img.size
                        except Exception:
                            width, height = 0, 0
                        
                        # Convert path to be relative to project root or absolute
                        try:
                            relative_path = image_path.relative_to(Path.cwd())
                        except ValueError:
                            relative_path = image_path.absolute()
                        
                        # Record metadata
                        image_metadata = {
                            "id": image_id,
                            "path": str(relative_path),
                            "page": page_num + 1,
                            "position": {
                                "width": width,
                                "height": height,
                                "page": page_num + 1,
                                "index": img_index
                            }
                        }
                        images_metadata.append(image_metadata)
                        
                        logger.debug(f"Extracted image {image_id} from page {page_num + 1}")
                        
                    except Exception as e:
                        logger.warning(f"Failed to extract image {img_index} from page {page_num + 1}: {e}")
                        continue
            
            doc.close()
            
        except Exception as e:
            logger.warning(f"Image extraction failed: {e}")
        
        return images_metadata
    
    def _insert_image_placeholders(
        self,
        text_content: str,
        images_metadata: List[Dict[str, Any]]
    ) -> str:
        """Insert image placeholders into text content.
        
        Args:
            text_content: Original text content from MarkItDown.
            images_metadata: List of image metadata.
            
        Returns:
            Text content with image placeholders inserted.
        """
        modified_text = text_content
        
        # Check if MarkItDown already inserted placeholders
        existing_placeholders = set()
        for img in images_metadata:
            img_id = img["id"]
            if f"[IMAGE: {img_id}]" in text_content or f"![image]" in text_content.lower():
                existing_placeholders.add(img_id)
        
        # Insert placeholders for images not already in text
        for img in images_metadata:
            img_id = img["id"]
            if img_id not in existing_placeholders:
                placeholder = f"\n\n[IMAGE: {img_id}]\n\n"
                modified_text += placeholder
        
        return modified_text
    
    @staticmethod
    def _generate_image_id(doc_hash: str, page: int, sequence: int) -> str:
        """Generate unique image ID.
        
        Args:
            doc_hash: Document hash.
            page: Page number (0-based).
            sequence: Image sequence on page (0-based).
            
        Returns:
            Unique image ID string.
        """
        return f"{doc_hash[:8]}_{page}_{sequence}"