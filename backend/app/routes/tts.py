"""POST /api/tts — Text-to-Speech route handler."""

from __future__ import annotations

import base64
import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.models import ErrorResponse, TTSRequest, TTSResponse
from app.services.tts_service import TTSError, tts_service
from app.utils import normalise_language, sanitise_error

router = APIRouter()
logger = logging.getLogger("uvicorn.error")


def _error(code: str, message: str, status_code: int = 500) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(error=sanitise_error(message), error_code=code).model_dump(),
    )


@router.post("/tts", response_model=TTSResponse)
async def synthesise_speech(request: TTSRequest):
    """Generate spoken audio for a piece of text using ElevenLabs."""
    language_code = normalise_language(request.language) or "en"

    try:
        audio_bytes = tts_service.synthesise(
            text=request.text,
            language_code=language_code,
        )
    except TTSError as exc:
        logger.warning("TTS failure: code=%s message=%s", exc.code, exc.message)
        return _error(exc.code, exc.message)
    except Exception:  # noqa: BLE001 - safety net
        logger.exception("Unexpected TTS failure")
        return _error(
            "tts_internal_error",
            "Voice generation failed. Please try again.",
        )

    audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
    return TTSResponse(
        success=True,
        language=language_code,
        audio_base64=audio_b64,
        mime_type="audio/mpeg",
    )
