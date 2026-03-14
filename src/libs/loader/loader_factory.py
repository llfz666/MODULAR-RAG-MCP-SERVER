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

logger = logging.getLogger(__name__)


# File extension to loader class mapping
LOADER_REGISTRY: Dict[str, Type[BaseLoader]] = {
    '.pdf': PdfLoader,
    '.docx': DocxLoader,
    '.doc': DocxLoader,  # Note: .doc may need different handling
    '.pptx': PptxLoader,
    '.xlsx': XlsxLoader,
    '.xlsm': XlsxLoader,
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
        **loader_kwargs
    ) -> BaseLoader:
        """Create a loader for the given file type.
        
        Args:
            file_path: Path to document file.
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
        
        # Get loader class
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
    **kwargs
) -> Document:
    """Load a PDF file with optional OCR.
    
    Args:
        file_path: Path to PDF file.
        extract_images: Whether to extract images.
        enable_ocr: Whether to enable OCR for scanned PDFs.
        ocr_backend: OCR backend ('paddle', 'rapid', 'tesseract').
        **kwargs: Additional arguments for PdfLoader.
        
    Returns:
        Parsed Document object.
    """
    loader = PdfLoader(
        extract_images=extract_images,
        enable_ocr=enable_ocr,
        ocr_backend=ocr_backend,
        **kwargs
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
    'load_pdf',
    'load_docx',
    'load_pptx',
    'load_xlsx',
]