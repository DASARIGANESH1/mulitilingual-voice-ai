"""
Text-to-Speech service backed by ElevenLabs.

This service converts AI response text into natural-sounding speech.

Configuration comes from backend/.env:
    ELEVENLABS_API_KEY
    ELEVENLABS_VOICE_ID
    ELEVENLABS_MODEL_ID
    ELEVENLABS_STABILITY
    ELEVENLABS_SIMILARITY_BOOST
    ELEVENLABS_STYLE
    ELEVENLABS_SPEAKER_BOOST
    ELEVENLABS_SPEED
"""

from __future__ import annotations

import logging
import os

from elevenlabs import VoiceSettings
from elevenlabs.client import ElevenLabs

from app.config import settings
from app.utils import normalise_language


logger = logging.getLogger("uvicorn.error")


class TTSError(Exception):
    """Custom exception used by the TTS service."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class TTSService:
    """
    ElevenLabs Text-to-Speech service.

    The service:
        1. Checks the API configuration.
        2. Sends text to ElevenLabs.
        3. Receives MP3 chunks.
        4. Combines the chunks.
        5. Returns MP3 bytes to the API route.
    """

    def __init__(self, client: ElevenLabs | None = None) -> None:
        self._client = client

    # =========================================================
    # Create ElevenLabs client
    # =========================================================

    def _ensure_client(self) -> ElevenLabs:
        """Create the ElevenLabs client when needed."""

        if not settings.has_elevenlabs:
            raise TTSError(
                "tts_no_api_key",
                (
                    "ElevenLabs is not configured. "
                    "Set ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID "
                    "in backend/.env."
                ),
            )

        if self._client is None:
            self._client = ElevenLabs(
                api_key=settings.elevenlabs_api_key
            )

        return self._client

    # =========================================================
    # Read floating-point environment setting
    # =========================================================

    @staticmethod
    def _get_float_env(
        name: str,
        default: float,
        minimum: float,
        maximum: float,
    ) -> float:
        """
        Read a floating-point setting from environment variables.

        Invalid values automatically fall back to the default.
        """

        value = os.getenv(name, str(default)).strip()

        try:
            number = float(value)
        except ValueError:
            logger.warning(
                "Invalid %s=%r. Using default %.2f.",
                name,
                value,
                default,
            )
            return default

        if number < minimum or number > maximum:
            logger.warning(
                "%s=%s is outside the allowed range %.2f-%.2f. "
                "Using default %.2f.",
                name,
                number,
                minimum,
                maximum,
                default,
            )
            return default

        return number

    # =========================================================
    # Read boolean environment setting
    # =========================================================

    @staticmethod
    def _get_bool_env(name: str, default: bool) -> bool:
        """Read a boolean setting from environment variables."""

        value = os.getenv(name, str(default)).strip().lower()

        if value in {"true", "1", "yes", "on"}:
            return True

        if value in {"false", "0", "no", "off"}:
            return False

        logger.warning(
            "Invalid %s=%r. Using default %s.",
            name,
            value,
            default,
        )

        return default

    # =========================================================
    # Text to Speech
    # =========================================================

    def synthesise(
        self,
        text: str,
        language_code: str,
    ) -> bytes:
        """
        Convert text into MP3 audio.

        ElevenLabs automatically detects the language from the
        supplied text when using a multilingual model such as
        eleven_multilingual_v2.
        """

        # -----------------------------------------------------
        # Validate text
        # -----------------------------------------------------

        if not text or not text.strip():
            raise TTSError(
                "tts_empty_text",
                "Nothing to synthesise.",
            )

        text = text.strip()

        # -----------------------------------------------------
        # Get ElevenLabs client
        # -----------------------------------------------------

        client = self._ensure_client()

        # -----------------------------------------------------
        # Get configuration
        # -----------------------------------------------------

        voice_id = settings.elevenlabs_voice_id
        model_id = settings.elevenlabs_model_id

        if not voice_id:
            raise TTSError(
                "tts_voice_not_found",
                (
                    "ELEVENLABS_VOICE_ID is missing. "
                    "Add your ElevenLabs voice ID to backend/.env."
                ),
            )

        if not model_id:
            model_id = "eleven_multilingual_v2"

        # -----------------------------------------------------
        # Normalise language
        # -----------------------------------------------------

        language = normalise_language(language_code) or "en"

        logger.info(
            "ElevenLabs TTS: language=%s model=%s voice=%s",
            language,
            model_id,
            voice_id,
        )

        # -----------------------------------------------------
        # Voice settings
        # -----------------------------------------------------

        stability = self._get_float_env(
            "ELEVENLABS_STABILITY",
            0.40,
            0.0,
            1.0,
        )

        similarity_boost = self._get_float_env(
            "ELEVENLABS_SIMILARITY_BOOST",
            0.75,
            0.0,
            1.0,
        )

        style = self._get_float_env(
            "ELEVENLABS_STYLE",
            0.20,
            0.0,
            1.0,
        )

        speed = self._get_float_env(
            "ELEVENLABS_SPEED",
            0.98,
            0.70,
            1.20,
        )

        speaker_boost = self._get_bool_env(
            "ELEVENLABS_SPEAKER_BOOST",
            True,
        )

        voice_settings = VoiceSettings(
            stability=stability,
            similarity_boost=similarity_boost,
            style=style,
            use_speaker_boost=speaker_boost,
            speed=speed,
        )

        # -----------------------------------------------------
        # Generate speech
        # -----------------------------------------------------

        audio_chunks: list[bytes] = []

        try:
            response = client.text_to_speech.convert(
                voice_id=voice_id,
                model_id=model_id,
                text=text,
                output_format="mp3_44100_128",
                voice_settings=voice_settings,
            )

            # ElevenLabs returns audio as chunks.
            for chunk in response:
                if not chunk:
                    continue

                if isinstance(chunk, bytes):
                    audio_chunks.append(chunk)

                elif isinstance(chunk, bytearray):
                    audio_chunks.append(bytes(chunk))

            logger.info(
                "ElevenLabs TTS generated %d audio chunks.",
                len(audio_chunks),
            )

        except Exception as exc:
            logger.exception(
                "ElevenLabs TTS request failed."
            )

            self._map_api_error(exc)

        # -----------------------------------------------------
        # Combine MP3 chunks
        # -----------------------------------------------------

        audio_bytes = b"".join(audio_chunks)

        if not audio_bytes:
            raise TTSError(
                "tts_empty_audio",
                "The voice service returned no audio.",
            )

        logger.info(
            "ElevenLabs TTS completed successfully. Audio size=%d bytes.",
            len(audio_bytes),
        )

        return audio_bytes

    # =========================================================
    # ElevenLabs error handling
    # =========================================================

    @staticmethod
    def _map_api_error(exc: Exception) -> None:
        """
        Convert ElevenLabs exceptions into application-level
        TTSError codes.

        IMPORTANT:
        ElevenLabs may return HTTP 401 for quota_exceeded.
        Therefore quota detection MUST happen before the
        generic 401/API-key detection.
        """

        # -----------------------------------------------------
        # HTTP status
        # -----------------------------------------------------

        status = getattr(exc, "status_code", None)

        if status is not None:
            try:
                status = int(status)
            except (TypeError, ValueError):
                status = None

        # -----------------------------------------------------
        # Extract complete error information
        # -----------------------------------------------------

        error_text = str(exc).lower()

        body = getattr(exc, "body", None)

        if body:
            body_text = str(body).lower()
        else:
            body_text = ""

        # Combine both sources.
        detail_lower = f"{error_text} {body_text}"

        logger.error(
            "ElevenLabs error details: status=%s error=%s",
            status,
            detail_lower,
        )

        # =====================================================
        # 1. QUOTA EXCEEDED
        # =====================================================
        #
        # IMPORTANT:
        # ElevenLabs can return status 401 for quota_exceeded.
        # Therefore this MUST be checked BEFORE the 401 check.
        # =====================================================

        if (
            "quota_exceeded" in detail_lower
            or "quota exceeded" in detail_lower
            or "exceeds your quota" in detail_lower
            or "credits remaining" in detail_lower
        ):
            raise TTSError(
                "tts_rate_limit",
                (
                    "ElevenLabs quota has been exceeded. "
                    "Your account does not have enough credits "
                    "for this request."
                ),
            )

        # =====================================================
        # 2. INVALID API KEY
        # =====================================================

        if (
            status == 401
            and (
                "invalid_api_key" in detail_lower
                or "invalid api key" in detail_lower
                or "unauthorized" in detail_lower
            )
        ):
            raise TTSError(
                "tts_invalid_api_key",
                (
                    "ElevenLabs API key is invalid. "
                    "Check ELEVENLABS_API_KEY in backend/.env."
                ),
            )

        # =====================================================
        # 3. RATE LIMIT
        # =====================================================

        if (
            status == 429
            or "rate limit" in detail_lower
            or "rate_limit" in detail_lower
            or "too many requests" in detail_lower
        ):
            raise TTSError(
                "tts_rate_limit",
                (
                    "ElevenLabs rate limit reached. "
                    "Please try again later."
                ),
            )

        # =====================================================
        # 4. VOICE / MODEL NOT FOUND
        # =====================================================

        if (
            status == 404
            or "voice_not_found" in detail_lower
            or "voice id" in detail_lower
            or "voice_id" in detail_lower
            or "model not found" in detail_lower
            or "model_not_found" in detail_lower
        ):
            raise TTSError(
                "tts_voice_not_found",
                (
                    "The ElevenLabs voice or model was not found. "
                    "Check ELEVENLABS_VOICE_ID and "
                    "ELEVENLABS_MODEL_ID in backend/.env."
                ),
            )

        # =====================================================
        # 5. BAD REQUEST
        # =====================================================

        if status == 400 or status == 422:
            raise TTSError(
                "tts_provider_error",
                (
                    "ElevenLabs rejected the text-to-speech request. "
                    "Check your voice ID, model ID and voice settings."
                ),
            )

        # =====================================================
        # 6. SERVER / PROVIDER ERROR
        # =====================================================

        if status is not None and 500 <= status <= 599:
            raise TTSError(
                "tts_provider_unavailable",
                (
                    "ElevenLabs is temporarily unavailable. "
                    "Please try again shortly."
                ),
            )

        # =====================================================
        # 7. UNKNOWN ERROR
        # =====================================================

        raise TTSError(
            "tts_provider_error",
            "Voice generation failed. Please try again.",
        )


# =============================================================
# Single shared service instance
# =============================================================

tts_service = TTSService()