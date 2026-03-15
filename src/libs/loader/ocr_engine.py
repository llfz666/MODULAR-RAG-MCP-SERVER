"""OCR Engine module for PDF text extraction.

This module provides OCR capabilities using PaddleOCR or RapidOCR
for processing scanned PDFs and images that don't have a text layer.

Supported backends:
- paddle: PaddleOCR (best for Chinese, high accuracy)
- rapid: RapidOCR (faster, ONNX-based)
- tesseract: Tesseract OCR (fallback, requires system install)
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class BaseOCREngine(ABC):
    """Abstract base class for OCR engines."""
    
    @abstractmethod
    def recognize(self, image_path: str | Path) -> str:
        """Recognize text from an image.
        
        Args:
            image_path: Path to the image file.
            
        Returns:
            Recognized text string.
        """
        pass
    
    @abstractmethod
    def recognize_with_boxes(
        self, 
        image_path: str | Path
    ) -> List[Dict[str, Any]]:
        """Recognize text with bounding box information.
        
        Args:
            image_path: Path to the image file.
            
        Returns:
            List of dicts with 'text', 'bbox', 'confidence' keys.
        """
        pass


class PaddleOCREngine(BaseOCREngine):
    """PaddleOCR engine implementation.
    
    PaddleOCR provides excellent Chinese and English recognition
    with support for multiple languages and text angle detection.
    """
    
    def __init__(
        self,
        lang: str = 'ch',
        use_angle_cls: bool = True,
        use_gpu: bool = False,
        show_log: bool = False,
        det_model_dir: Optional[str] = None,
        rec_model_dir: Optional[str] = None,
    ):
        """Initialize PaddleOCR engine.
        
        Args:
            lang: Language code ('ch' for Chinese, 'en' for English, etc.)
            use_angle_cls: Whether to use angle classification for rotated text.
            use_gpu: Whether to use GPU acceleration.
            show_log: Whether to show OCR logs.
            det_model_dir: Custom detection model directory.
            rec_model_dir: Custom recognition model directory.
        """
        # Lazy import to avoid PaddleX initialization conflicts
        self._ocr = None
        self._available = False
        self._lang = lang
        self._use_angle_cls = use_angle_cls
        self._use_gpu = use_gpu
        self._show_log = show_log
        self._det_model_dir = det_model_dir
        self._rec_model_dir = rec_model_dir
        
        # Try to initialize lazily
        self._lazy_init()
    
    def _lazy_init(self):
        """Lazy initialize PaddleOCR."""
        if self._ocr is not None:
            return
        
        try:
            from paddleocr import PaddleOCR
            self._ocr = PaddleOCR(
                use_angle_cls=self._use_angle_cls,
                lang=self._lang,
                use_gpu=self._use_gpu,
                show_log=self._show_log,
                det_model_dir=self._det_model_dir,
                rec_model_dir=self._rec_model_dir,
            )
            self._available = True
        except Exception as e:
            logger.warning(f"PaddleOCR not available: {e}")
            self._available = False
            self._ocr = None
    
    @property
    def available(self) -> bool:
        """Check if PaddleOCR is available."""
        return self._available
    
    def recognize(self, image_path: str | Path) -> str:
        """Recognize text from an image.
        
        Args:
            image_path: Path to the image file.
            
        Returns:
            Recognized text string.
        """
        if not self._available:
            raise RuntimeError("PaddleOCR is not available")
        
        result = self._ocr.ocr(str(image_path), cls=False)
        
        # Flatten result and extract text
        texts = []
        if result and result[0]:
            for line in result[0]:
                if line and len(line) >= 2:
                    text = line[1][0]
                    confidence = line[1][1]
                    if confidence > 0.5:  # Filter low confidence results
                        texts.append(text)
        
        return '\n'.join(texts)
    
    def recognize_with_boxes(
        self, 
        image_path: str | Path
    ) -> List[Dict[str, Any]]:
        """Recognize text with bounding box information.
        
        Args:
            image_path: Path to the image file.
            
        Returns:
            List of dicts with 'text', 'bbox', 'confidence' keys.
        """
        if not self._available:
            raise RuntimeError("PaddleOCR is not available")
        
        result = self._ocr.ocr(str(image_path), cls=False)
        
        boxes = []
        if result and result[0]:
            for line in result[0]:
                if line and len(line) >= 2:
                    bbox = line[0]  # Four corner points
                    text, confidence = line[1]
                    if confidence > 0.5:
                        boxes.append({
                            'text': text,
                            'bbox': bbox,
                            'confidence': confidence,
                        })
        
        return boxes
    
    def recognize_pdf(
        self, 
        pdf_path: str | Path, 
        dpi: int = 200
    ) -> str:
        """Recognize text from a PDF file.
        
        Converts each PDF page to image and performs OCR.
        
        Args:
            pdf_path: Path to the PDF file.
            dpi: DPI for rendering PDF pages.
            
        Returns:
            Combined recognized text from all pages.
        """
        if not self._available:
            raise RuntimeError("PaddleOCR is not available")
        
        try:
            import fitz  # PyMuPDF
            from PIL import Image
            import io
            
            doc = fitz.open(pdf_path)
            all_texts = []
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                # Render page to image
                mat = fitz.Matrix(dpi / 72, dpi / 72)
                pix = page.get_pixmap(matrix=mat)
                
                # Convert to PIL Image
                img_data = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_data))
                
                # Save to temp file for OCR
                import tempfile
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                    img.save(f.name)
                    temp_path = f.name
                
                try:
                    page_text = self.recognize(temp_path)
                    if page_text:
                        all_texts.append(f"=== Page {page_num + 1} ===\n{page_text}")
                finally:
                    import os
                    os.unlink(temp_path)
            
            doc.close()
            return '\n\n'.join(all_texts)
            
        except Exception as e:
            logger.error(f"PDF OCR failed: {e}")
            raise


class RapidOCREngine(BaseOCREngine):
    """RapidOCR engine implementation (ONNX-based, faster).
    
    RapidOCR is a lightweight OCR solution based on PaddleOCR
    but using ONNX runtime for faster inference.
    """
    
    def __init__(self, use_cuda: bool = False):
        """Initialize RapidOCR engine.
        
        Args:
            use_cuda: Whether to use CUDA acceleration.
        """
        try:
            from rapidocr_onnxruntime import RapidOCR
            self._ocr = RapidOCR(text_score=0.5, use_cuda=use_cuda)
            self._available = True
        except ImportError as e:
            logger.warning(f"RapidOCR not available: {e}")
            self._available = False
            self._ocr = None
    
    @property
    def available(self) -> bool:
        """Check if RapidOCR is available."""
        return self._available
    
    def recognize(self, image_path: str | Path) -> str:
        """Recognize text from an image.
        
        Args:
            image_path: Path to the image file.
            
        Returns:
            Recognized text string.
        """
        if not self._available:
            raise RuntimeError("RapidOCR is not available")
        
        result, _ = self._ocr(str(image_path))
        
        if result is None:
            return ""
        
        texts = []
        for box in result:
            text = box[1]
            confidence = box[2]
            if confidence > 0.5:
                texts.append(text)
        
        return '\n'.join(texts)
    
    def recognize_with_boxes(
        self, 
        image_path: str | Path
    ) -> List[Dict[str, Any]]:
        """Recognize text with bounding box information.
        
        Args:
            image_path: Path to the image file.
            
        Returns:
            List of dicts with 'text', 'bbox', 'confidence' keys.
        """
        if not self._available:
            raise RuntimeError("RapidOCR is not available")
        
        result, _ = self._ocr(str(image_path))
        
        if result is None:
            return []
        
        boxes = []
        for box in result:
            bbox = box[0]  # Four corner points
            text = box[1]
            confidence = box[2]
            boxes.append({
                'text': text,
                'bbox': bbox,
                'confidence': confidence,
            })
        
        return boxes
    
    def recognize_pdf(
        self, 
        pdf_path: str | Path, 
        dpi: int = 200
    ) -> str:
        """Recognize text from a PDF file.
        
        Converts each PDF page to image and performs OCR.
        
        Args:
            pdf_path: Path to the PDF file.
            dpi: DPI for rendering PDF pages.
            
        Returns:
            Combined recognized text from all pages.
        """
        if not self._available:
            raise RuntimeError("RapidOCR is not available")
        
        try:
            import fitz  # PyMuPDF
            from PIL import Image
            import io
            
            doc = fitz.open(pdf_path)
            all_texts = []
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                # Render page to image
                mat = fitz.Matrix(dpi / 72, dpi / 72)
                pix = page.get_pixmap(matrix=mat)
                
                # Convert to PIL Image
                img_data = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_data))
                
                # Save to temp file for OCR
                import tempfile
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                    img.save(f.name)
                    temp_path = f.name
                
                try:
                    page_text = self.recognize(temp_path)
                    if page_text:
                        all_texts.append(f"=== Page {page_num + 1} ===\n{page_text}")
                finally:
                    import os
                    os.unlink(temp_path)
            
            doc.close()
            return '\n\n'.join(all_texts)
            
        except Exception as e:
            logger.error(f"PDF OCR failed: {e}")
            raise


class TesseractOCREngine(BaseOCREngine):
    """Tesseract OCR engine implementation.
    
    Tesseract is a mature OCR engine with good language support
    but generally lower accuracy for Chinese compared to PaddleOCR.
    """
    
    def __init__(
        self,
        lang: str = 'chi_sim+eng',
        oem: int = 3,
        psm: int = 3,
    ):
        """Initialize Tesseract OCR engine.
        
        Args:
            lang: Language code(s) (e.g., 'chi_sim+eng' for Chinese+English)
            oem: OCR Engine Mode (3 = Default, based on trained data + LSTM)
            psm: Page Segmentation Mode (3 = Fully automatic)
        """
        try:
            import pytesseract
            from PIL import Image
            
            self._pytesseract = pytesseract
            self._lang = lang
            self._oem = oem
            self._psm = psm
            self._available = True
            
            # Verify tesseract is installed
            try:
                self._pytesseract.get_tesseract_version()
            except Exception:
                logger.warning("Tesseract not found in PATH")
                self._available = False
                
        except ImportError as e:
            logger.warning(f"pytesseract not available: {e}")
            self._available = False
    
    @property
    def available(self) -> bool:
        """Check if Tesseract OCR is available."""
        return self._available
    
    def recognize(self, image_path: str | Path) -> str:
        """Recognize text from an image.
        
        Args:
            image_path: Path to the image file.
            
        Returns:
            Recognized text string.
        """
        if not self._available:
            raise RuntimeError("Tesseract OCR is not available")
        
        from PIL import Image
        img = Image.open(image_path)
        
        config = f'--oem {self._oem} --psm {self._psm}'
        text = self._pytesseract.image_to_string(
            img, 
            lang=self._lang, 
            config=config
        )
        
        return text.strip()
    
    def recognize_with_boxes(
        self, 
        image_path: str | Path
    ) -> List[Dict[str, Any]]:
        """Recognize text with bounding box information.
        
        Args:
            image_path: Path to the image file.
            
        Returns:
            List of dicts with 'text', 'bbox', 'confidence' keys.
        """
        if not self._available:
            raise RuntimeError("Tesseract OCR is not available")
        
        from PIL import Image
        img = Image.open(image_path)
        
        # Get data with bounding boxes
        data = self._pytesseract.image_to_data(
            img, 
            lang=self._lang,
            output_type=self._pytesseract.Output.DICT
        )
        
        boxes = []
        n_boxes = len(data['level'])
        
        for i in range(n_boxes):
            text = data['text'][i].strip()
            if text and data['conf'][i] > 0:
                boxes.append({
                    'text': text,
                    'bbox': [
                        data['left'][i],
                        data['top'][i],
                        data['width'][i],
                        data['height'][i],
                    ],
                    'confidence': data['conf'][i] / 100.0,
                })
        
        return boxes
    
    def recognize_pdf(
        self, 
        pdf_path: str | Path, 
        dpi: int = 200
    ) -> str:
        """Recognize text from a PDF file.
        
        Args:
            pdf_path: Path to the PDF file.
            dpi: DPI for rendering PDF pages.
            
        Returns:
            Combined recognized text from all pages.
        """
        if not self._available:
            raise RuntimeError("Tesseract OCR is not available")
        
        try:
            import fitz  # PyMuPDF
            from PIL import Image
            import io
            
            doc = fitz.open(pdf_path)
            all_texts = []
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                # Render page to image
                mat = fitz.Matrix(dpi / 72, dpi / 72)
                pix = page.get_pixmap(matrix=mat)
                
                # Convert to PIL Image
                img_data = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_data))
                
                config = f'--oem {self._oem} --psm {self._psm}'
                page_text = self._pytesseract.image_to_string(
                    img, 
                    lang=self._lang, 
                    config=config
                )
                
                if page_text:
                    all_texts.append(f"=== Page {page_num + 1} ===\n{page_text}")
            
            doc.close()
            return '\n\n'.join(all_texts)
            
        except Exception as e:
            logger.error(f"PDF OCR failed: {e}")
            raise


def create_ocr_engine(
    backend: str = 'paddle',
    **kwargs
) -> BaseOCREngine:
    """Factory function to create OCR engine.
    
    Args:
        backend: OCR backend to use ('paddle', 'rapid', 'tesseract')
        **kwargs: Additional arguments for the specific engine.
        
    Returns:
        OCR engine instance.
        
    Raises:
        ValueError: If backend is not supported.
    """
    engines = {
        'paddle': PaddleOCREngine,
        'rapid': RapidOCREngine,
        'tesseract': TesseractOCREngine,
    }
    
    if backend not in engines:
        raise ValueError(
            f"Unknown OCR backend: {backend}. "
            f"Available backends: {list(engines.keys())}"
        )
    
    engine = engines[backend](**kwargs)
    
    if not engine.available:
        logger.warning(f"OCR engine '{backend}' is not available")
    
    return engine