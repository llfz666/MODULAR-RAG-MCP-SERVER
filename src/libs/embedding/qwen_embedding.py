"""Qwen (DashScope) Embedding implementation.

This module provides a Qwen Embedding implementation that works with
Alibaba Cloud's DashScope API using OpenAI-compatible protocol.
"""

from __future__ import annotations

import os
from typing import Any, List, Optional

from src.libs.embedding.base_embedding import BaseEmbedding


class QwenEmbeddingError(RuntimeError):
    """Raised when Qwen Embedding API call fails."""


class QwenEmbedding(BaseEmbedding):
    """Qwen Embedding provider implementation.
    
    This class implements the BaseEmbedding interface for Qwen's Embeddings API
    via Alibaba Cloud DashScope. It uses the OpenAI-compatible protocol.
    
    Attributes:
        api_key: The API key for authentication.
        model: The model identifier to use.
        base_url: The base URL for the API (DashScope endpoint).
    
    Example:
        >>> from src.core.settings import load_settings
        >>> settings = load_settings('config/settings.yaml')
        >>> embedding = QwenEmbedding(settings)
        >>> vectors = embedding.embed(["hello world", "test"])
    """
    
    DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    
    def __init__(
        self,
        settings: Any,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the Qwen Embedding provider.
        
        Args:
            settings: Application settings containing Embedding configuration.
            api_key: Optional API key override.
            base_url: Optional base URL override.
            **kwargs: Additional configuration overrides.
        
        Raises:
            ValueError: If API key is not provided.
        """
        self.model = settings.embedding.model
        
        # Extract optional dimensions setting
        self.dimensions = getattr(settings.embedding, 'dimensions', None)
        
        # API key: explicit > settings > env var
        self.api_key = (
            api_key
            or getattr(settings.embedding, 'api_key', None)
            or os.environ.get("DASHSCOPE_API_KEY")
            or os.environ.get("QWEN_API_KEY")
        )
        if not self.api_key:
            raise ValueError(
                "Qwen API key not provided. Set in settings.yaml (embedding.api_key), "
                "DASHSCOPE_API_KEY or QWEN_API_KEY environment variable, "
                "or pass api_key parameter."
            )
        
        # Base URL: override > settings > default
        if base_url:
            self.base_url = base_url
        else:
            settings_base_url = getattr(settings.embedding, 'base_url', None)
            self.base_url = settings_base_url if settings_base_url else self.DEFAULT_BASE_URL
        
        self._extra_config = kwargs
    
    def embed(
        self,
        texts: List[str],
        trace: Optional[Any] = None,
        **kwargs: Any,
    ) -> List[List[float]]:
        """Generate embeddings for a batch of texts using Qwen API.
        
        Args:
            texts: List of text strings to embed.
            trace: Optional TraceContext for observability.
            **kwargs: Override parameters.
        
        Returns:
            List of embedding vectors.
        
        Raises:
            ValueError: If texts list is empty.
            QwenEmbeddingError: If API call fails.
        """
        self.validate_texts(texts)
        
        import httpx
        
        url = f"{self.base_url.rstrip('/')}/embeddings"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": self.model,
            "input": texts,
        }
        
        # Add dimensions if specified
        dimensions = kwargs.get("dimensions", self.dimensions)
        if dimensions is not None:
            payload["dimensions"] = dimensions
        
        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(url, json=payload, headers=headers)
                
                if response.status_code != 200:
                    error_detail = self._parse_error_response(response)
                    raise QwenEmbeddingError(
                        f"[Qwen] API error (HTTP {response.status_code}): {error_detail}"
                    )
                
                response_data = response.json()
                
                # Parse response
                try:
                    embeddings = []
                    for item in response_data.get("data", []):
                        if isinstance(item, dict) and "embedding" in item:
                            embeddings.append(item["embedding"])
                        elif isinstance(item, (list, tuple)):
                            embeddings.append(list(item))
                    
                    if len(embeddings) != len(texts):
                        raise QwenEmbeddingError(
                            f"Output length mismatch: expected {len(texts)}, got {len(embeddings)}"
                        )
                    
                    return embeddings
                except (KeyError, TypeError) as e:
                    raise QwenEmbeddingError(
                        f"[Qwen] Failed to parse response: {e}"
                    ) from e
        except httpx.TimeoutException as e:
            raise QwenEmbeddingError(
                f"[Qwen] Request timed out after 60 seconds"
            ) from e
        except httpx.RequestError as e:
            raise QwenEmbeddingError(
                f"[Qwen] Connection failed: {type(e).__name__}: {e}"
            ) from e
    
    def _parse_error_response(self, response: Any) -> str:
        """Parse error details from API response."""
        try:
            error_data = response.json()
            if "error" in error_data:
                error = error_data["error"]
                if isinstance(error, dict):
                    return error.get("message", str(error))
                return str(error)
            return response.text
        except Exception:
            return response.text or "Unknown error"
    
    def get_dimension(self) -> Optional[int]:
        """Get the embedding dimension for the configured model.
        
        Returns:
            The embedding dimension, or None if not deterministic.
        """
        if self.dimensions is not None:
            return self.dimensions
        
        # Model-specific defaults for Qwen embedding models
        model_dimensions = {
            "text-embedding-v1": 1536,
            "text-embedding-v2": 1536,
            "text-embedding-v3": 1024,
        }
        
        return model_dimensions.get(self.model)