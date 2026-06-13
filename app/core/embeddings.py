"""Embedding wrapper around gemini-embedding-001 (new google-genai SDK)."""

import logging

from google import genai

from app.core.config import get_settings

logger = logging.getLogger("haqdar.embeddings")

_client: genai.Client | None = None


def _client_get() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=get_settings().gemini_api_key)
    return _client


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts. Raises on failure so callers can fall back."""
    settings = get_settings()
    result = _client_get().models.embed_content(
        model=settings.embedding_model,
        contents=texts,
    )
    return [e.values for e in result.embeddings]


def embed_one(text: str) -> list[float]:
    return embed_texts([text])[0]
