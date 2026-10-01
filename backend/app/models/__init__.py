"""Pydantic schemas shared across STT / Chat / TTS endpoints."""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------
# Generic envelope
# ---------------------------------------------------------------------
class ErrorResponse(BaseModel):
    """Standard error envelope returned by every failing endpoint."""

    success: Literal[False] = False
    error: str = Field(..., description="Human-readable error message.")
    error_code: str = Field(
        ..., description="Stable machine code, e.g. 'stt_no_api_key'."
    )


# ---------------------------------------------------------------------
# /api/stt
# ---------------------------------------------------------------------
class STTResponse(BaseModel):
    success: bool = True
    text: str = Field(..., description="Transcribed user speech.")
    language: Optional[str] = Field(
        None,
        description=(
            "ISO-639-1 code detected from the audio (e.g. 'en', 'hi', 'te'). "
            "May be None if the provider could not detect a language."
        ),
    )
    language_confidence: Optional[float] = None


# ---------------------------------------------------------------------
# /api/chat
# ---------------------------------------------------------------------
class ChatMessage(BaseModel):
    """A single previous turn in the conversation history."""

    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=8000)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)
    language: str = Field(
        "en",
        description="ISO-639-1 code (or short code) of the user's language.",
    )
    conversation_history: List[ChatMessage] = Field(default_factory=list)


class ChatResponse(BaseModel):
    success: bool = True
    response: str = Field(..., description="Generated AI reply.")
    language: str = Field(..., description="Language code echoed back.")


# ---------------------------------------------------------------------
# /api/tts
# ---------------------------------------------------------------------
class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)
    language: str = Field(
        "en",
        description="ISO-639-1 code of the language being spoken (for logging only).",
    )


class TTSResponse(BaseModel):
    success: bool = True
    language: str
    audio_base64: str = Field(
        ..., description="Base64-encoded MP3 audio (browser-playable)."
    )
    mime_type: str = "audio/mpeg"


# ---------------------------------------------------------------------
# /api/health
# ---------------------------------------------------------------------
class HealthResponse(BaseModel):
    status: str = "ok"
    services: dict
