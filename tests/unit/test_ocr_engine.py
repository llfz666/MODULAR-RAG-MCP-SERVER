"""Unit tests for OCR engine module.

Tests for PaddleOCR, RapidOCR, and Tesseract OCR engines.
These tests use proper mocking to work without actual OCR libraries installed.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, PropertyMock
import sys
import importlib

from src.libs.loader.ocr_engine import (
    BaseOCREngine,
    PaddleOCREngine,
    RapidOCREngine,
    TesseractOCREngine,
    create_ocr_engine,
)


@pytest.fixture
def mock_paddleocr():
    """Fixture to mock PaddleOCR module."""
    mock_module = MagicMock()
    mock_ocr_class = MagicMock()
    mock_ocr_instance = MagicMock()
    mock_ocr_instance.ocr.return_value = [
        [
            ([[10, 10], [100, 10], [100, 30], [10, 30]], ("Hello", 0.95)),
            ([[10, 40], [80, 40], [80, 60], [10, 60]], ("World", 0.90)),
        ]
    ]
    mock_ocr_class.return_value = mock_ocr_instance
    mock_module.PaddleOCR = mock_ocr_class
    return mock_module


@pytest.fixture
def mock_rapidocr():
    """Fixture to mock RapidOCR module."""
    mock_module = MagicMock()
    mock_ocr_class = MagicMock()
    mock_ocr_instance = MagicMock()
    mock_ocr_instance.return_value = (
        [
            ([[10, 10], [100, 10], [100, 30], [10, 30]], "Hello", 0.95),
            ([[10, 40], [80, 40], [80, 60], [10, 60]], "World", 0.90),
        ],
        None
    )
    mock_ocr_class.return_value = mock_ocr_instance
    mock_module.RapidOCR = mock_ocr_class
    return mock_module


@pytest.fixture
def mock_pytesseract():
    """Fixture to mock pytesseract module."""
    mock_module = MagicMock()
    mock_module.get_tesseract_version.return_value = "5.0.0"
    mock_module.image_to_string.return_value = "Hello World"
    
    class Output:
        DICT = 'dict'
    
    mock_module.Output = Output
    mock_module.image_to_data.return_value = {
        'level': [1, 2],
        'text': ['Hello', 'World'],
        'left': [10, 20],
        'top': [10, 20],
        'width': [50, 60],
        'height': [20, 20],
        'conf': [95, 90],
    }
    return mock_module


class TestPaddleOCREngine:
    """Tests for PaddleOCREngine."""
    
    def test_init_success(self, mock_paddleocr):
        """Test successful initialization."""
        with patch.dict('sys.modules', {'paddleocr': mock_paddleocr}):
            # Need to reload the module to pick up the mock
            import src.libs.loader.ocr_engine as ocr_module
            importlib.reload(ocr_module)
            
            engine = ocr_module.PaddleOCREngine(lang='ch', use_angle_cls=True)
            assert engine.available is True
            mock_paddleocr.PaddleOCR.assert_called_once()
    
    def test_init_failure(self):
        """Test initialization with ImportError."""
        with patch.dict('sys.modules', {'paddleocr': None}):
            import src.libs.loader.ocr_engine as ocr_module
            importlib.reload(ocr_module)
            
            engine = ocr_module.PaddleOCREngine(lang='ch')
            assert engine.available is False
    
    def test_recognize(self, mock_paddleocr):
        """Test text recognition from image."""
        with patch.dict('sys.modules', {'paddleocr': mock_paddleocr}):
            import src.libs.loader.ocr_engine as ocr_module
            importlib.reload(ocr_module)
            
            engine = ocr_module.PaddleOCREngine(lang='en')
            result = engine.recognize("test.png")
            
            assert "Hello" in result
            assert "World" in result
    
    def test_recognize_with_boxes(self, mock_paddleocr):
        """Test text recognition with bounding boxes."""
        with patch.dict('sys.modules', {'paddleocr': mock_paddleocr}):
            import src.libs.loader.ocr_engine as ocr_module
            importlib.reload(ocr_module)
            
            engine = ocr_module.PaddleOCREngine(lang='en')
            result = engine.recognize_with_boxes("test.png")
            
            assert len(result) == 1
            assert result[0]['text'] == "Hello"
            assert result[0]['confidence'] == 0.95
            assert result[0]['bbox'] == [[10, 10], [100, 10], [100, 30], [10, 30]]
    
    def test_recognize_filters_low_confidence(self, mock_paddleocr):
        """Test that low confidence results are filtered."""
        # Create mock with low confidence result
        mock_paddleocr.PaddleOCR.return_value.ocr.return_value = [
            [
                ([[10, 10], [100, 10], [100, 30], [10, 30]], ("Good", 0.95)),
                ([[10, 40], [80, 40], [80, 60], [10, 60]], ("Bad", 0.3)),
            ]
        ]
        
        with patch.dict('sys.modules', {'paddleocr': mock_paddleocr}):
            import src.libs.loader.ocr_engine as ocr_module
            importlib.reload(ocr_module)
            
            engine = ocr_module.PaddleOCREngine(lang='en')
            result = engine.recognize("test.png")
            
            assert "Good" in result
            assert "Bad" not in result


class TestRapidOCREngine:
    """Tests for RapidOCREngine."""
    
    def test_init_success(self, mock_rapidocr):
        """Test successful initialization."""
        with patch.dict('sys.modules', {'rapidocr_onnxruntime': mock_rapidocr}):
            import src.libs.loader.ocr_engine as ocr_module
            importlib.reload(ocr_module)
            
            engine = ocr_module.RapidOCREngine(use_cuda=False)
            assert engine.available is True
            mock_rapidocr.RapidOCR.assert_called_once()
    
    def test_init_failure(self):
        """Test initialization with ImportError."""
        with patch.dict('sys.modules', {'rapidocr_onnxruntime': None}):
            import src.libs.loader.ocr_engine as ocr_module
            importlib.reload(ocr_module)
            
            engine = ocr_module.RapidOCREngine()
            assert engine.available is False
    
    def test_recognize(self, mock_rapidocr):
        """Test text recognition from image."""
        with patch.dict('sys.modules', {'rapidocr_onnxruntime': mock_rapidocr}):
            import src.libs.loader.ocr_engine as ocr_module
            importlib.reload(ocr_module)
            
            engine = ocr_module.RapidOCREngine()
            result = engine.recognize("test.png")
            
            assert "Hello" in result
            assert "World" in result
    
    def test_recognize_with_boxes(self, mock_rapidocr):
        """Test text recognition with bounding boxes."""
        with patch.dict('sys.modules', {'rapidocr_onnxruntime': mock_rapidocr}):
            import src.libs.loader.ocr_engine as ocr_module
            importlib.reload(ocr_module)
            
            engine = ocr_module.RapidOCREngine()
            result = engine.recognize_with_boxes("test.png")
            
            assert len(result) == 1
            assert result[0]['text'] == "Hello"
            assert result[0]['confidence'] == 0.95


class TestTesseractOCREngine:
    """Tests for TesseractOCREngine."""
    
    def test_init_success(self, mock_pytesseract):
        """Test successful initialization."""
        with patch.dict('sys.modules', {'pytesseract': mock_pytesseract}):
            import src.libs.loader.ocr_engine as ocr_module
            importlib.reload(ocr_module)
            
            engine = ocr_module.TesseractOCREngine(lang='eng')
            assert engine.available is True
    
    def test_init_tesseract_not_found(self, mock_pytesseract):
        """Test initialization when Tesseract is not installed."""
        mock_pytesseract.get_tesseract_version.side_effect = Exception("Tesseract not found")
        
        with patch.dict('sys.modules', {'pytesseract': mock_pytesseract}):
            import src.libs.loader.ocr_engine as ocr_module
            importlib.reload(ocr_module)
            
            engine = ocr_module.TesseractOCREngine(lang='eng')
            assert engine.available is False
    
    def test_recognize(self, mock_pytesseract):
        """Test text recognition from image."""
        with patch.dict('sys.modules', {'pytesseract': mock_pytesseract}):
            with patch('PIL.Image.open'):
                import src.libs.loader.ocr_engine as ocr_module
                importlib.reload(ocr_module)
                
                engine = ocr_module.TesseractOCREngine(lang='eng')
                result = engine.recognize("test.png")
                
                assert result == "Hello World"
    
    def test_recognize_with_boxes(self, mock_pytesseract):
        """Test text recognition with bounding boxes."""
        with patch.dict('sys.modules', {'pytesseract': mock_pytesseract}):
            with patch('PIL.Image.open'):
                import src.libs.loader.ocr_engine as ocr_module
                importlib.reload(ocr_module)
                
                engine = ocr_module.TesseractOCREngine(lang='eng')
                result = engine.recognize_with_boxes("test.png")
                
                assert len(result) == 2
                assert result[0]['text'] == "Hello"
                assert result[0]['confidence'] == 0.95


class TestCreateOcrEngine:
    """Tests for create_ocr_engine factory function."""
    
    def test_create_paddle_engine(self, mock_paddleocr):
        """Test creating PaddleOCR engine."""
        with patch.dict('sys.modules', {'paddleocr': mock_paddleocr}):
            import src.libs.loader.ocr_engine as ocr_module
            importlib.reload(ocr_module)
            
            engine = ocr_module.create_ocr_engine(backend='paddle', lang='ch')
            assert isinstance(engine, ocr_module.PaddleOCREngine)
    
    def test_create_rapid_engine(self, mock_rapidocr):
        """Test creating RapidOCR engine."""
        with patch.dict('sys.modules', {'rapidocr_onnxruntime': mock_rapidocr}):
            import src.libs.loader.ocr_engine as ocr_module
            importlib.reload(ocr_module)
            
            engine = ocr_module.create_ocr_engine(backend='rapid')
            assert isinstance(engine, ocr_module.RapidOCREngine)
    
    def test_create_tesseract_engine(self, mock_pytesseract):
        """Test creating TesseractOCR engine."""
        with patch.dict('sys.modules', {'pytesseract': mock_pytesseract}):
            import src.libs.loader.ocr_engine as ocr_module
            importlib.reload(ocr_module)
            
            engine = ocr_module.create_ocr_engine(backend='tesseract', lang='eng')
            assert isinstance(engine, ocr_module.TesseractOCREngine)
    
    def test_create_unknown_backend(self):
        """Test creating engine with unknown backend."""
        # Reload with original module
        import src.libs.loader.ocr_engine as ocr_module
        importlib.reload(ocr_module)
        
        with pytest.raises(ValueError) as exc_info:
            ocr_module.create_ocr_engine(backend='unknown')
        
        assert "Unknown OCR backend" in str(exc_info.value)
        assert "paddle" in str(exc_info.value)
        assert "rapid" in str(exc_info.value)
        assert "tesseract" in str(exc_info.value)


class TestOcrEngineIntegration:
    """Integration tests for OCR engines."""
    
    @pytest.mark.slow
    def test_paddle_ocr_real_image(self, tmp_path):
        """Test PaddleOCR with a real image (slow)."""
        try:
            from paddleocr import PaddleOCR
        except ImportError:
            pytest.skip("PaddleOCR not installed")
        
        # Create a simple test image
        from PIL import Image, ImageDraw
        
        img = Image.new('RGB', (200, 50), color='white')
        draw = ImageDraw.Draw(img)
        draw.text((10, 10), "Hello OCR", fill='black')
        
        img_path = tmp_path / "test.png"
        img.save(img_path)
        
        from src.libs.loader.ocr_engine import PaddleOCREngine
        engine = PaddleOCREngine(lang='en', show_log=False)
        
        if engine.available:
            result = engine.recognize(img_path)
            assert len(result) > 0
        else:
            pytest.skip("PaddleOCR not available")
    
    @pytest.mark.slow
    def test_rapid_ocr_real_image(self, tmp_path):
        """Test RapidOCR with a real image (slow)."""
        try:
            from rapidocr_onnxruntime import RapidOCR
        except ImportError:
            pytest.skip("RapidOCR not installed")
        
        # Create a simple test image
        from PIL import Image, ImageDraw
        
        img = Image.new('RGB', (200, 50), color='white')
        draw = ImageDraw.Draw(img)
        draw.text((10, 10), "Hello OCR", fill='black')
        
        img_path = tmp_path / "test.png"
        img.save(img_path)
        
        from src.libs.loader.ocr_engine import RapidOCREngine
        engine = RapidOCREngine()
        
        if engine.available:
            result = engine.recognize(img_path)
            assert len(result) > 0
        else:
            pytest.skip("RapidOCR not available")