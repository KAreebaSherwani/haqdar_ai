# HaqDar AI — حق دار (Backend)

Pakistan's first AI legal rights assistant. Speak your complaint. Know your rights. Get your letter.

## Quick start

```bash
# 1. Install uv (once):  https://docs.astral.sh/uv/
# 2. Setup
uv sync
cp .env.example .env   # paste your Gemini API key from aistudio.google.com

# 3. Run
uv run uvicorn app.main:app --reload

# 4. Open the auto docs
# http://localhost:8000/docs
```

## Test

```bash
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{"complaint": "Police ne mujhe bina wajah fine diya aur receipt nahi di"}'
```

## Endpoints
| Endpoint | Method | Purpose |
|---|---|---|
| /api/v1/analyze | POST | Complaint -> full legal package |
| /api/v1/rights | POST | Scenario -> rights education |
| /api/v1/stats | GET | Civic stats (demo data) |
| /api/v1/health | GET | Liveness + keep-alive target |

## Architecture
- **Schema-constrained output** — Gemini cannot return malformed JSON
- **Grounded law base** — AI cites only `app/knowledge/pakistan_laws.py`
- **3-tier fallback** — gemini-3-flash -> gemini-3.1-flash-lite -> demo cache

## Deploy (Render free tier)
1. Push to GitHub, create a Render Web Service from the repo (render.yaml is auto-detected)
2. Set GEMINI_API_KEY and ALLOWED_ORIGINS in the Render dashboard
3. Add a cron-job.org ping to /api/v1/health every 10 minutes (kills cold starts)
