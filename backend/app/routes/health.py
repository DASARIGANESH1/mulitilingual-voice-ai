"""GET /api/health — quick way to verify the backend is reachable and to
let the frontend show which providers are currently configured (without
exposing keys)."""

from __future__ import annotations

from fastapi import APIRouter

from app.config import settings

router = APIRouter()


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "services": {
            "stt": {
                "provider": "groq",
                "model": settings.groq_stt_model,
                "configured": settings.has_groq,
            },
            "llm": {
                "provider": "gemini",
                "model": settings.gemini_model,
                "configured": settings.has_gemini,
            },
            "tts": {
                "provider": "elevenlabs",
                "model": settings.elevenlabs_model_id,
                "voice_id_set": bool(settings.elevenlabs_voice_id),
                "configured": settings.has_elevenlabs,
            },
        },
        # Surface the catalogue of supported languages so the frontend can
        # render language pickers without duplicating the list.
        "supported_languages_url": "/api/languages",
    }
