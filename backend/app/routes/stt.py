"""POST /api/stt — Speech-to-Text route handler."""

from __future__ import annotations

import logging

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import JSONResponse

from app.models import ErrorResponse, STTResponse
from app.services.stt_service import STTError, stt_service
from app.utils import sanitise_error

router = APIRouter()
logger = logging.getLogger("uvicorn.error")


def _error(code: str, message: str, status_code: int = 400) -> JSONResponse:
    """Return a uniform error envelope with the given HTTP status code."""
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(error=sanitise_error(message), error_code=code).model_dump(),
    )


@router.post("/stt", response_model=STTResponse)
async def transcribe_audio(request: Request, file: UploadFile = File(...)):
    """Transcribe an uploaded audio blob using Groq Whisper.

    Expects multipart form data with a single field ``file`` containing
    the recorded audio bytes (webm/opus from MediaRecorder is the common
    case but mp3/wav/m4a are also accepted).
    """
    try:
        audio_bytes = await file.read()
    except Exception:  # noqa: BLE001
        logger.exception("Failed to read uploaded audio")
        return _error("stt_read_failed", "Could not read the uploaded audio file.")

    try:
        text, language_code, confidence = stt_service.transcribe(
            audio_bytes=audio_bytes,
            filename=file.filename,
            mime_type=file.content_type,
        )
    except STTError as exc:
        logger.warning("STT failure: code=%s message=%s", exc.code, exc.message)
        return _error(exc.code, exc.message)
    except Exception:  # noqa: BLE001 - safety net
        logger.exception("Unexpected STT failure")
        return _error(
            "stt_internal_error",
            "Speech recognition failed. Please try recording again.",
            status_code=500,
        )

    return STTResponse(
        success=True,
        text=text,
        language=language_code,
        language_confidence=confidence,
    )
