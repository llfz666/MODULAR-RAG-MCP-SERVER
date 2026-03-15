"""Unified document loader factory.

This module provides a factory for creating document loaders
based on file type, with support for:
- PDF (with OCR)
- DOCX (with comments, revisions)
- PPTX (with speaker notes)
- XLSX (with formulas)
- Auto-detection of file types

Usage:
    from src.libs.loader.loader_factory import DocumentLoaderFactory
    
    # Auto-detect and load
    loader = DocumentLoaderFactory.create_loader("document.pdf")
    doc = loader.load("document.pdf")
    
    # Or use convenience method
    doc = DocumentLoaderFactory.load("document.docx")
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional, Type

from src.core.types import Document
from src.libs.loader.base_loader import BaseLoader
from src.libs.loader.pdf_loader import PdfLoader
from src.libs.loader.docx_loader import DocxLoader
from src.libs.loader.pptx_loader import PptxLoader
from src.libs.loader.xlsx_loader import XlsxLoader
from src.libs.loader.advanced_pdf_loader import AdvancedPdfLoader
from src.libs.loader.enhanced_pptx_loader import EnhancedPptxLoader
from src.libs.loader.video_subtitle_loader import VideoSubtitleLoader

logger = logging.getLogger(__name__)


# File extension to loader class mapping
LOADER_REGISTRY: Dict[str, Type[BaseLoader]] = {
    '.pdf': PdfLoader,
    '.docx': DocxLoader,
    '.doc': DocxLoader,  # Note: .doc may need different loader
    '.pptx': PptxLoader,
    '.xlsx': XlsxLoader,
    '.xlsm': XlsxLoader,
    # Video/Audio files
    '.mp4': VideoSubtitleLoader,
    '.avi': VideoSubtitleLoader,
    '.mkv': VideoSubtitleLoader,
    '.mov': VideoSubtitleLoader,
    '.mp3': VideoSubtitleLoader,
    '.wav': VideoSubtitleLoader,
}

# Advanced loaders with enhanced features (Layout Analysis, Image OCR, etc.)
ADVANCED_LOADER_REGISTRY: Dict[str, Type] = {
    '.pdf': AdvancedPdfLoader,  # With layout analysis and table recognition
    '.pptx': EnhancedPptxLoader,  # With image OCR support
}


class DocumentLoaderFactory:
    """Factory for creating document loaders.
    
    This factory:
    1. Auto-detects file type from extension
    2. Creates appropriate loader instance
    3. Provides unified load() interface
    4. Supports custom loader registration
    """
    
    @classmethod
    def create_loader(
        cls,
        file_path: str | Path,
        use_advanced: bool = False,
        **loader_kwargs
    ) -> BaseLoader:
        """Create a loader for the given file type.
        
        Args:
            file_path: Path to document file.
            use_advanced: Use advanced loader with enhanced features
                         (Layout Analysis, Table Recognition, Image OCR).
            **loader_kwargs: Keyword arguments passed to loader constructor.
            
        Returns:
            Appropriate loader instance for the file type.
            
        Raises:
            ValueError: If file type is not supported.
            ImportError: If required loader dependency is missing.
        """
        path = Path(file_path)
        ext = path.suffix.lower()
        
        # Handle .doc files (may need different loader)
        if ext == '.doc':
            logger.warning(
                f".doc format (binary Word document) may have limited support. "
                f"Consider converting to .docx for better results."
            )
        
        # Check for advanced loader
        if use_advanced and ext in ADVANCED_LOADER_REGISTRY:
            loader_class = ADVANCED_LOADER_REGISTRY[ext]
            logger.info(f"Using advanced loader: {loader_class.__name__}")
        else:
            loader_class = LOADER_REGISTRY.get(ext)
        
        if loader_class is None:
            supported = ', '.join(LOADER_REGISTRY.keys())
            raise ValueError(
                f"Unsupported file type: {ext}. "
                f"Supported types: {supported}"
            )
        
        # Create loader instance
        try:
            return loader_class(**loader_kwargs)
        except ImportError as e:
            raise ImportError(
                f"Failed to create {loader_class.__name__}: {e}. "
                f"Please install required dependencies."
            )
    
    @classmethod
    def load(
        cls,
        file_path: str | Path,
        **loader_kwargs
    ) -> Document:
        """Convenience method to create loader and load document.
        
        Args:
            file_path: Path to document file.
            **loader_kwargs: Keyword arguments passed to loader constructor.
            
        Returns:
            Parsed Document object.
            
        Raises:
            ValueError: If file type is not supported.
            FileNotFoundError: If file doesn't exist.
            RuntimeError: If parsing fails.
        """
        loader = cls.create_loader(file_path, **loader_kwargs)
        return loader.load(file_path)
    
    @classmethod
    def register_loader(
        cls,
        extension: str,
        loader_class: Type[BaseLoader],
        overwrite: bool = False
    ) -> None:
        """Register a custom loader for a file extension.
        
        Args:
            extension: File extension (e.g., '.txt').
            loader_class: Loader class (must extend BaseLoader).
            overwrite: Whether to overwrite existing registration.
            
        Raises:
            ValueError: If extension already registered and overwrite=False.
            TypeError: If loader_class doesn't extend BaseLoader.
        """
        extension = extension.lower()
        
        if not extension.startswith('.'):
            extension = f'.{extension}'
        
        if extension in LOADER_REGISTRY and not overwrite:
            raise ValueError(
                f"Extension {extension} already registered. "
                f"Set overwrite=True to override."
            )
        
        if not issubclass(loader_class, BaseLoader):
            raise TypeError(
                f"loader_class must extend BaseLoader, got {loader_class.__name__}"
            )
        
        LOADER_REGISTRY[extension] = loader_class
        logger.info(f"Registered loader {loader_class.__name__} for extension {extension}")
    
    @classmethod
    def get_supported_extensions(cls) -> list[str]:
        """Get list of supported file extensions.
        
        Returns:
            List of supported file extensions.
        """
        return list(LOADER_REGISTRY.keys())
    
    @classmethod
    def detect_file_type(cls, file_path: str | Path) -> Optional[str]:
        """Detect file type from path.
        
        Args:
            file_path: Path to file.
            
        Returns:
            File extension (lowercase) or None if unknown.
        """
        path = Path(file_path)
        ext = path.suffix.lower()
        return ext if ext in LOADER_REGISTRY else None
    
    @classmethod
    def is_supported(cls, file_path: str | Path) -> bool:
        """Check if file type is supported.
        
        Args:
            file_path: Path to file.
            
        Returns:
            True if file type is supported.
        """
        return cls.detect_file_type(file_path) is not None


# Convenience functions for common use cases

def load_pdf(
    file_path: str | Path,
    extract_images: bool = True,
    enable_ocr: bool = True,
    ocr_backend: str = 'rapid',
    use_advanced: bool = False,
    **kwargs
) -> Document:
    """Load a PDF file with optional OCR.
    
    Args:
        file_path: Path to PDF file.
        extract_images: Whether to extract images.
        enable_ocr: Whether to enable OCR for scanned PDFs.
        ocr_backend: OCR backend ('paddle', 'rapid', 'tesseract').
        use_advanced: Use AdvancedPdfLoader with Layout Analysis.
        **kwargs: Additional arguments for loader.
        
    Returns:
        Parsed Document object.
    """
    if use_advanced:
        loader = AdvancedPdfLoader(
            use_ocr=enable_ocr,
            ocr_lang='ch' if ocr_backend == 'paddle' else 'en',
            **kwargs
        )
    else:
        loader = PdfLoader(
            extract_images=extract_images,
            enable_ocr=enable_ocr,
            ocr_backend=ocr_backend,
            **kwargs
        )
    return loader.load(file_path)


def load_pdf_advanced(
    file_path: str | Path,
    use_layout_analysis: bool = True,
    use_table_recognition: bool = True,
    use_ocr: bool = True,
    ocr_lang: str = 'ch',
    use_gpu: bool = False,
    detect_code_blocks: bool = True,
    **kwargs
) -> Document:
    """Load a PDF file with advanced features.
    
    This uses AdvancedPdfLoader with:
    - Layout Analysis (布局分析) for multi-column detection
    - Table Recognition (表格识别) for structured data
    - OCR Fusion with PaddleOCR
    - Code Block Detection
    
    Args:
        file_path: Path to PDF file.
        use_layout_analysis: Enable layout analysis.
        use_table_recognition: Enable table recognition.
        use_ocr: Enable OCR support.
        ocr_lang: OCR language ('ch' or 'en').
        use_gpu: Use GPU acceleration.
        detect_code_blocks: Auto-detect code blocks.
        **kwargs: Additional arguments.
        
    Returns:
        Parsed Document object with structured content.
    """
    loader = AdvancedPdfLoader(
        use_layout_analysis=use_layout_analysis,
        use_table_recognition=use_table_recognition,
        use_ocr=use_ocr,
        ocr_lang=ocr_lang,
        use_gpu=use_gpu,
        detect_code_blocks=detect_code_blocks,
        **kwargs
    )
    return loader.load(file_path)


def load_pptx(
    file_path: str | Path,
    extract_notes: bool = True,
    use_advanced: bool = False,
    **kwargs
) -> Document:
    """Load a PPTX file with speaker notes.
    
    Args:
        file_path: Path to PPTX file.
        extract_notes: Whether to extract speaker notes (CRITICAL).
        use_advanced: Use EnhancedPptxLoader with image OCR.
        **kwargs: Additional arguments for loader.
        
    Returns:
        Parsed Document object.
    """
    if use_advanced:
        loader = EnhancedPptxLoader(
            extract_notes=extract_notes,
            ocr_images=True,
            **kwargs
        )
    else:
        loader = PptxLoader(
            extract_notes=extract_notes,
            **kwargs
        )
    return loader.load(file_path)


def load_pptx_enhanced(
    file_path: str | Path,
    extract_notes: bool = True,
    extract_images: bool = True,
    ocr_images: bool = True,
    ocr_lang: str = 'ch',
    use_gpu: bool = False,
    **kwargs
) -> Document:
    """Load a PPTX file with enhanced image OCR.
    
    This uses EnhancedPptxLoader with:
    - Speaker Notes extraction (演讲者备注)
    - Image extraction from slides
    - OCR on all images to extract embedded text
    - Chart and diagram text extraction
    
    Args:
        file_path: Path to PPTX file.
        extract_notes: Extract speaker notes.
        extract_images: Extract embedded images.
        ocr_images: Perform OCR on images.
        ocr_lang: OCR language.
        use_gpu: Use GPU for OCR.
        **kwargs: Additional arguments.
        
    Returns:
        Parsed Document object with OCR results.
    """
    loader = EnhancedPptxLoader(
        extract_notes=extract_notes,
        extract_images=extract_images,
        ocr_images=ocr_images,
        ocr_lang=ocr_lang,
        use_gpu=use_gpu,
        **kwargs
    )
    return loader.load(file_path)


def load_video(
    file_path: str | Path,
    extract_subtitles: bool = True,
    transcribe_audio: bool = True,
    whisper_model: str = 'base',
    language: str = 'zh',
    semantic_segmentation: bool = True,
) -> Dict[str, Any]:
    """Load a video/audio file and extract subtitles or transcribe.
    
    This uses VideoSubtitleLoader with:
    - Subtitle extraction (SRT, VTT, ASS formats)
    - Whisper audio transcription (fallback)
    - Semantic segmentation of transcript
    
    Args:
        file_path: Path to video/audio file.
        extract_subtitles: Extract embedded subtitles.
        transcribe_audio: Transcribe audio if no subtitles.
        whisper_model: Whisper model size.
        language: Language code.
        semantic_segmentation: Apply semantic segmentation.
        
    Returns:
        Dict with full_text, subtitles, segments, and metadata.
    """
    loader = VideoSubtitleLoader(
        extract_subtitles=extract_subtitles,
        transcribe_audio=transcribe_audio,
        whisper_model=whisper_model,
        language=language,
        semantic_segmentation=semantic_segmentation,
    )
    return loader.load(file_path)


def load_docx(
    file_path: str | Path,
    extract_comments: bool = True,
    extract_revisions: bool = True,
    **kwargs
) -> Document:
    """Load a DOCX file with comments and revisions.
    
    Args:
        file_path: Path to DOCX file.
        extract_comments: Whether to extract comments.
        extract_revisions: Whether to extract tracked changes.
        **kwargs: Additional arguments for DocxLoader.
        
    Returns:
        Parsed Document object.
    """
    loader = DocxLoader(
        extract_comments=extract_comments,
        extract_revisions=extract_revisions,
        **kwargs
    )
    return loader.load(file_path)


def load_pptx(
    file_path: str | Path,
    extract_notes: bool = True,
    **kwargs
) -> Document:
    """Load a PPTX file with speaker notes.
    
    Args:
        file_path: Path to PPTX file.
        extract_notes: Whether to extract speaker notes (CRITICAL).
        **kwargs: Additional arguments for PptxLoader.
        
    Returns:
        Parsed Document object.
    """
    loader = PptxLoader(
        extract_notes=extract_notes,
        **kwargs
    )
    return loader.load(file_path)


def load_xlsx(
    file_path: str | Path,
    extract_formulas: bool = True,
    **kwargs
) -> Document:
    """Load an XLSX file with formulas.
    
    Args:
        file_path: Path to XLSX file.
        extract_formulas: Whether to extract formulas.
        **kwargs: Additional arguments for XlsxLoader.
        
    Returns:
        Parsed Document object.
    """
    loader = XlsxLoader(
        extract_formulas=extract_formulas,
        **kwargs
    )
    return loader.load(file_path)


# Export public API
__all__ = [
    'DocumentLoaderFactory',
    'BaseLoader',
    'PdfLoader',
    'DocxLoader',
    'PptxLoader',
    'XlsxLoader',
    'AdvancedPdfLoader',
    'EnhancedPptxLoader',
    'VideoSubtitleLoader',
    'load_pdf',
    'load_pdf_advanced',
    'load_docx',
    'load_pptx',
    'load_pptx_enhanced',
    'load_xlsx',
    'load_video',
]
