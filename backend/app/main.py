"""FastAPI application entrypoint.

Wires up the route handlers, CORS, and a tiny in-process rate limiter
(defensive; the SDK itself is the real safety net on the free tier).

Run locally:
    cd backend
    uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from typing import Deque, Tuple

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.routes import chat, health, languages, stt, tts

logger = logging.getLogger("uvicorn.error")


# ---------------------------------------------------------------------
# Lightweight in-process rate limiter
# ---------------------------------------------------------------------
# Sliding-window per IP. 60 calls/minute per IP is more than enough for
# the MVP and well within the free-tier quotas of all three providers.
class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-IP sliding-window rate limiter."""

    WINDOW_SECONDS = 60
    MAX_REQUESTS = 60

    def __init__(self, app):  # type: ignore[no-untyped-def]
        super().__init__(app)
        self._hits: dict[str, Deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        # Skip rate-limiting the meta routes so the UI can poll freely.
        path = request.url.path
        if path in {"/api/health", "/api/languages", "/", "/docs", "/openapi.json"}:
            return await call_next(request)

        client = request.client.host if request.client else "unknown"
        now = time.time()
        bucket = self._hits[client]
        # drop entries outside the window
        while bucket and bucket[0] < now - self.WINDOW_SECONDS:
            bucket.popleft()
        if len(bucket) >= self.MAX_REQUESTS:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "success": False,
                    "error": "Too many requests. Please slow down and try again.",
                    "error_code": "rate_limited",
                },
            )
        bucket.append(now)
        return await call_next(request)


# ---------------------------------------------------------------------
# App
# ---------------------------------------------------------------------
app = FastAPI(
    title="Multilingual Voice AI",
    description=(
        "Real-time multilingual conversational voice assistant. Pipeline: "
        "Microphone -> Groq Whisper STT -> Gemini LLM/NLG -> ElevenLabs TTS."
    ),
    version="1.0.0",
)

# CORS — we accept the Next.js dev origin plus the sandbox preview origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"https://[a-zA-Z0-9\-]+\.space-z\.ai",
    allow_credentials=False,  # we don't use cookies — pure JSON API
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Add our tiny rate limiter AFTER CORS so OPTIONS preflight still works.
app.add_middleware(RateLimitMiddleware)


# ---------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------
# Health & metadata (the rate limiter skips these paths)
app.include_router(health.router, prefix="/api", tags=["meta"])
app.include_router(languages.router, prefix="/api", tags=["meta"])

# Core pipeline
app.include_router(stt.router, prefix="/api", tags=["pipeline"])
app.include_router(chat.router, prefix="/api", tags=["pipeline"])
app.include_router(tts.router, prefix="/api", tags=["pipeline"])


@app.get("/")
async def root():
    return {
        "name": "Multilingual Voice AI",
        "version": "1.0.0",
        "endpoints": {
            "POST /api/stt": "Speech-to-Text (multipart file upload)",
            "POST /api/chat": "LLM / NLG response generation",
            "POST /api/tts": "Text-to-Speech synthesis",
            "GET /api/health": "Backend health & provider config",
            "GET /api/languages": "Catalogue of supported languages",
            "Docs": "/docs",
        },
    }


@app.on_event("startup")
async def _log_startup() -> None:
    logger.info(
        "Backend starting. Configured providers: groq=%s gemini=%s elevenlabs=%s",
        settings.has_groq,
        settings.has_gemini,
        settings.has_elevenlabs,
    )
    if not (settings.has_groq and settings.has_gemini and settings.has_elevenlabs):
        logger.warning(
            "Some providers are not configured. Add the missing API keys to "
            "backend/.env before testing the full pipeline."
        )
