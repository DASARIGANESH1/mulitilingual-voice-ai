"""Configuration loader.

Reads environment variables from `backend/.env` (or process environment),
applies sensible defaults, and exposes a single typed `settings` object to
the rest of the backend. **No API key is ever returned by any API response**;
they live only in this in-memory object on the server.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import List

from dotenv import load_dotenv

# Load variables from backend/.env into os.environ if the file exists.
# We look for it relative to this file so the server can be started from any CWD.
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ENV_PATH = os.path.join(_BASE_DIR, ".env")
if os.path.exists(_ENV_PATH):
    load_dotenv(_ENV_PATH)


def _parse_csv(value: str) -> List[str]:
    """Split a comma-separated env value and trim whitespace."""
    return [item.strip() for item in value.split(",") if item.strip()]


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


class Settings:
    """Typed view of all backend configuration."""

    # ---- Groq (STT) ----
    groq_api_key: str = os.getenv("GROQ_API_KEY", "").strip()
    groq_stt_model: str = os.getenv("GROQ_STT_MODEL", "whisper-large-v3-turbo").strip()

    # ---- Gemini (LLM/NLG) ----
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "").strip()
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash").strip()

    # ---- ElevenLabs (TTS) ----
    elevenlabs_api_key: str = os.getenv("ELEVENLABS_API_KEY", "").strip()
    elevenlabs_voice_id: str = os.getenv("ELEVENLABS_VOICE_ID", "").strip()
    elevenlabs_model_id: str = os.getenv(
        "ELEVENLABS_MODEL_ID", "eleven_multilingual_v2"
    ).strip()

    # ---- Server / security ----
    backend_port: int = _get_int("BACKEND_PORT", 8000)
    backend_max_audio_mb: int = _get_int("BACKEND_MAX_AUDIO_MB", 25)
    backend_max_history: int = _get_int("BACKEND_MAX_HISTORY", 10)
    cors_origins: List[str] = _parse_csv(
        os.getenv("BACKEND_CORS_ORIGINS", "http://localhost:3000")
    )

    # ---- Convenience flags ----
    @property
    def has_groq(self) -> bool:
        return bool(self.groq_api_key)

    @property
    def has_gemini(self) -> bool:
        return bool(self.gemini_api_key)

    @property
    def has_elevenlabs(self) -> bool:
        return bool(self.elevenlabs_api_key and self.elevenlabs_voice_id)

    @property
    def max_audio_bytes(self) -> int:
        return self.backend_max_audio_mb * 1024 * 1024


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a singleton Settings object. Cached for the process lifetime."""
    return Settings()


settings = get_settings()
