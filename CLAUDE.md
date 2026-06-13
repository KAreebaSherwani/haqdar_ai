# HaqDar AI — Backend (Hackathon: Code for Pakistan, deadline June 13)

FastAPI backend for a Pakistani legal rights assistant. Citizens submit complaints
in Urdu; we return the violated law, responsible authority, and a formal Urdu
complaint letter.

## Stack — non-negotiable
- Python 3.12+, managed with **uv** (never raw pip)
- FastAPI + Pydantic v2, async endpoints, versioned under /api/v1
- AI: **google-genai** SDK (NEVER google-generativeai — deprecated)
- Primary model: gemini-3-flash · Fallback: gemini-3.1-flash-lite
- Structured output via response_schema (Pydantic), never prompt-only JSON

## Architecture rules
- Layers: api/ -> services/ -> core/ai_client.py -> knowledge/
- AI may cite ONLY laws from knowledge/pakistan_laws.py (anti-hallucination)
- Three-tier fallback: 3 Flash -> 3.1 Flash-Lite -> resilience/demo_cache.py
- All errors return clean JSON in Urdu, never stack traces
- CORS locked to the Vercel frontend domain + localhost

## Commands
- Run: uv run uvicorn app.main:app --reload
- Lint: uv run ruff check . --fix
