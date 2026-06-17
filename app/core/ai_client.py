"""Gemini client wrapper.

- Uses the NEW unified google-genai SDK (the old google-generativeai is deprecated).
- Output is schema-constrained: Gemini is forced to emit JSON matching our
  Pydantic model, so malformed responses are impossible by design.
- Two-model fallback: gemini-3-flash -> gemini-3.1-flash-lite.
  (Tier 3 — the demo cache — lives in the service layer.)
"""

import asyncio
import logging

from google import genai
from google.genai import types
from pydantic import BaseModel

from app.core.config import get_settings

logger = logging.getLogger("haqdar.ai")

_client: genai.Client | None = None


def get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=get_settings().gemini_api_key)
    return _client


class AIUnavailableError(Exception):
    """Raised when all model tiers fail."""


async def generate_structured(prompt: str, schema: type[BaseModel]) -> tuple[BaseModel, str]:
    """Run the prompt against the model chain; return (parsed_object, model_used).

    Raises AIUnavailableError if every tier fails — the caller decides whether
    the demo cache can answer instead.
    """
    settings = get_settings()
    if not settings.gemini_api_key:
        raise AIUnavailableError("GEMINI_API_KEY not configured")

    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=schema,
        temperature=0.4,
    )

    last_error: Exception | None = None
    for model_name in (settings.primary_model, settings.fallback_model):
        try:
            client = get_client()
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    client.models.generate_content,
                    model=model_name,
                    contents=prompt,
                    config=config,
                ),
                timeout=30,
            )
            parsed = response.parsed
            if parsed is None:
                parsed = schema.model_validate_json(response.text)
            logger.info("model=%s ok", model_name)
            return parsed, model_name
        except Exception as exc:  # noqa: BLE001 — any failure moves us down the chain
            last_error = exc
            logger.warning("model=%s failed: %s — trying next tier", model_name, exc)

    raise AIUnavailableError(str(last_error))


async def transcribe_audio(audio_bytes: bytes, mime_type: str = "audio/ogg") -> str:
    """Transcribe a voice note to text using Gemini audio understanding.

    Shared by the website audio feature and WhatsApp voice notes. Returns the
    transcribed text in the spoken language (Urdu or English). Raises
    AIUnavailableError on total failure so the caller can ask the user to type.
    """
    settings = get_settings()
    if not settings.gemini_api_key:
        raise AIUnavailableError("GEMINI_API_KEY not configured")

    instruction = (
        "Transcribe this audio to text exactly as spoken. The speaker may be using "
        "Urdu, English, Punjabi, Sindhi, or Pashto. Output ONLY the transcribed words in the original language "
        "and script, with no translation, no labels, and no extra commentary."
    )

    last_error = None
    for model_name in (settings.primary_model, settings.fallback_model):
        try:
            client = get_client()
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    client.models.generate_content,
                    model=model_name,
                    contents=[
                        types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
                        instruction,
                    ],
                ),
                timeout=40,
            )
            text = (response.text or "").strip()
            if text:
                logger.info("transcription model=%s ok (%d chars)", model_name, len(text))
                return text
        except Exception as exc:
            last_error = exc
            logger.warning("transcription model=%s failed: %s", model_name, exc)

    raise AIUnavailableError("transcription failed: %s" % last_error)


def warm_up() -> None:
    """Tiny call at startup so the first real request isn't also the first handshake."""
    try:
        get_client().models.generate_content(
            model=get_settings().fallback_model,
            contents="ok",
            config=types.GenerateContentConfig(max_output_tokens=5),
        )
        logger.info("warm-up complete")
    except Exception as exc:  # noqa: BLE001
        logger.warning("warm-up skipped: %s", exc)
