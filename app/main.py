"""HaqDar AI — FastAPI application factory."""

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.routes import router as v1_router
from app.core.ai_client import warm_up
from app.core.config import get_settings
from app.core.vector_store import init_store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("haqdar")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if get_settings().gemini_api_key:
        init_store()  # index verified law provisions into Chroma (idempotent)
        warm_up()
    else:
        logger.warning(
            "GEMINI_API_KEY not set — AI + vector store disabled; "
            "inclusion fallback and demo cache remain available"
        )
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="HaqDar AI — حق دار",
        description="Pakistan's first AI legal rights assistant. Speak your complaint. "
        "Know your rights. Get your letter.",
        version="1.0.0",
        lifespan=lifespan,
    )

    # 🌟 Flawless CORS configuration for production and local testing
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.origins_list,
        allow_origin_regex=r"https://.*\.vercel\.app",  # Safely allow dynamic frontend preview URLs
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],       # Allows required preflight handshakes
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_meta(request: Request, call_next):
        request_id = str(uuid.uuid4())[:8]
        start = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{(time.perf_counter() - start) * 1000:.0f}ms"
        return response

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        logger.exception("unhandled error on %s", request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "اندرونی خرابی۔ براہ کرم دوبارہ کوشش کریں۔"},
        )

    app.include_router(v1_router, prefix=settings.api_prefix)

    @app.get("/", tags=["ops"])
    def root() -> dict:
        return {"service": "HaqDar AI — حق دار", "docs": "/docs", "api": settings.api_prefix}

    return app


app = create_app()