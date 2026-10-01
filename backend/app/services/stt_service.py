"""
Speech-to-Text service backed by Groq Whisper Large V3.

The service receives audio from the browser microphone,
sends it to Groq Whisper, and returns the transcription.

IMPORTANT — Whisper hallucination protection:
--------------------------------------------
Whisper is known to hallucinate common phrases such as "you", "thank you",
"thanks for watching", "please subscribe", "music", "[BLANK_AUDIO]" when fed
near-silent audio, very short clips, or background noise.  We defensively
reject all of these patterns and surface a clear STT error to the caller.
"""

from __future__ import annotations

import io
import logging
import os
import re
from typing import Optional, Tuple

from groq import APIStatusError, Groq

from app.config import settings
from app.utils import normalise_language


logger = logging.getLogger("uvicorn.error")


class STTError(Exception):
    """Application-level Speech-to-Text error."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# ---------------------------------------------------------------------------
# Supported audio MIME types
# ---------------------------------------------------------------------------

_ALLOWED_MIME_TYPES = {
    "audio/wav",
    "audio/x-wav",
    "audio/mpeg",
    "audio/mp3",
    "audio/mp4",
    "audio/m4a",
    "audio/x-m4a",
    "audio/aac",
    "audio/ogg",
    "audio/oga",
    "audio/webm",
    "audio/x-matroska",
    "audio/flac",
    "audio/x-flac",
    "application/octet-stream",
}


# ---------------------------------------------------------------------------
# MIME type -> extension
# ---------------------------------------------------------------------------

_MIME_TO_EXT = {
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/mp4": ".mp4",
    "audio/m4a": ".m4a",
    "audio/x-m4a": ".m4a",
    "audio/aac": ".aac",
    "audio/ogg": ".ogg",
    "audio/oga": ".ogg",
    "audio/webm": ".webm",
    "audio/x-matroska": ".webm",
    "audio/flac": ".flac",
    "audio/x-flac": ".flac",
    "application/octet-stream": ".webm",
}


# ---------------------------------------------------------------------------
# Extension -> MIME type
# ---------------------------------------------------------------------------

_EXT_TO_MIME = {
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".mp4": "audio/mp4",
    ".aac": "audio/aac",
    ".ogg": "audio/ogg",
    ".oga": "audio/ogg",
    ".webm": "audio/webm",
    ".mkv": "audio/webm",
    ".flac": "audio/flac",
}


def _guess_mime(
    filename: Optional[str],
    fallback: Optional[str],
) -> str:
    """Determine the most likely MIME type for uploaded audio."""

    if fallback:
        fallback = fallback.split(";")[0].strip().lower()

        if fallback in _ALLOWED_MIME_TYPES:
            return fallback

    if filename:
        _, extension = os.path.splitext(filename.lower())

        if extension in _EXT_TO_MIME:
            return _EXT_TO_MIME[extension]

    # Chrome/Edge MediaRecorder normally produces WebM/Opus.
    return "audio/webm"


def _extension_for_mime(mime_type: str) -> str:
    """Return the appropriate file extension."""

    return _MIME_TO_EXT.get(mime_type, ".webm")


def _safe_float(value: object) -> Optional[float]:
    """Safely convert a value to float."""

    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None

    return None


# ---------------------------------------------------------------------------
# Whisper hallucination guard
# ---------------------------------------------------------------------------

# Known Whisper hallucination outputs when fed silence, near-silence, or
# background noise.  These appear in Whisper's training data as common
# phrases from YouTube subtitling.  When the audio contains no real speech,
# the model often falls back to one of these phrases instead of returning
# an empty string.
_PLACEHOLDER_PATTERNS = {
    # Single-word hallucinations
    "you",
    "user",
    "so",
    "uh",
    "ah",
    "oh",
    "bye",
    "hi",
    "hey",
    "ok",
    "okay",
    "music",
    "applause",
    "laughter",
    "noise",

    # Multi-word hallucinations
    "thank you",
    "thanks for watching",
    "thank you for watching",
    "please subscribe",
    "please like and subscribe",
    "thanks for listening",
    "thank you for listening",
    "bye bye",
    "goodbye",
    "see you next time",
    "see you later",
    "have a nice day",
    "have a good day",
    "you too",
    "same to you",
    "take care",
    "be right back",
    "coming up next",
    "stay tuned",
    "subscribe",
    "like and subscribe",

    # Audio-tag hallucinations.  Whisper sometimes emits these as
    # literal "[BLANK_AUDIO]" / "[music]" / "[noise]" tokens.
    "[blank_audio]",
    "[silence]",
    "[music]",
    "[noise]",
    "[applause]",
    # The same tokens without brackets, in case our punctuation
    # stripper removed them before we get here.
    "blank_audio",
    "silence",
}


def _looks_like_placeholder_transcript(value: str) -> bool:
    """Return True if ``value`` looks like a Whisper hallucination.

    A hallucinated transcript is one that consists entirely of one of the
    known placeholder phrases (possibly repeated, e.g. ``"you you you"``)
    after stripping punctuation and whitespace.

    This guard is intentionally strict: we prefer to surface an STT error
    rather than let a hallucinated "you" leak into the conversation UI.
    """

    if not value:
        return False

    normalised = re.sub(r"[\s\u00A0]+", " ", value).strip()

    if not normalised:
        return False

    # Strip all punctuation so "you." / "You!" / "thank you." all match.
    simplified = re.sub(r"[.?!,;:()\[\]\"'\-]+", "", normalised).strip().lower()

    if not simplified:
        return False

    # Exact single-phrase match.
    if simplified in _PLACEHOLDER_PATTERNS:
        return True

    # Repeated single-token hallucination, e.g. "you you you" or "you, you".
    tokens = simplified.split()
    if tokens:
        unique = set(tokens)
        if len(unique) == 1 and next(iter(unique)) in _PLACEHOLDER_PATTERNS:
            return True

    # Repeated multi-word hallucination, e.g. "thank you thank you".
    if len(tokens) >= 4 and len(tokens) % 2 == 0:
        half = len(tokens) // 2
        if tokens[:half] == tokens[half:]:
            joined_first_half = " ".join(tokens[:half])
            if joined_first_half in _PLACEHOLDER_PATTERNS:
                return True

    return False


class STTService:
    """Groq Whisper Large V3 transcription service."""

    def __init__(self, client: Optional[Groq] = None) -> None:
        # Lazy initialization allows the application to start
        # even when the API key is missing.
        self._client = client

    # -----------------------------------------------------------------------
    # Groq client
    # -----------------------------------------------------------------------

    def _ensure_client(self) -> Groq:
        """Create the Groq client when required."""

        if not settings.has_groq:
            raise STTError(
                "stt_no_api_key",
                "Groq API key is not configured on the server.",
            )

        if self._client is None:
            self._client = Groq(
                api_key=settings.groq_api_key
            )

        return self._client

    # -----------------------------------------------------------------------
    # Main transcription method
    # -----------------------------------------------------------------------

    def transcribe(
        self,
        audio_bytes: bytes,
        filename: Optional[str],
        mime_type: Optional[str],
        language_code: Optional[str] = None,
    ) -> Tuple[str, Optional[str], Optional[float]]:
        """
        Transcribe uploaded audio using Groq Whisper.

        If language_code is not provided, Whisper automatically detects
        the spoken language.
        """

        # -------------------------------------------------------------------
        # 1. Validate audio
        # -------------------------------------------------------------------

        if not audio_bytes:
            raise STTError(
                "stt_empty_audio",
                "Empty audio upload.",
            )

        if len(audio_bytes) > settings.max_audio_bytes:
            raise STTError(
                "stt_file_too_large",
                (
                    f"Audio file exceeds "
                    f"{settings.backend_max_audio_mb} MB limit."
                ),
            )

        logger.info(
            "STT request received: filename=%s mime=%s bytes=%d",
            filename,
            mime_type,
            len(audio_bytes),
        )

        # -------------------------------------------------------------------
        # 2. Detect MIME type
        # -------------------------------------------------------------------

        guessed_mime = _guess_mime(
            filename=filename,
            fallback=mime_type,
        )

        logger.info(
            "STT detected MIME type: %s",
            guessed_mime,
        )

        if guessed_mime not in _ALLOWED_MIME_TYPES:
            raise STTError(
                "stt_unsupported_format",
                f"Unsupported audio format: {guessed_mime}",
            )

        # -------------------------------------------------------------------
        # 3. Get Groq client
        # -------------------------------------------------------------------

        client = self._ensure_client()

        # -------------------------------------------------------------------
        # 4. Prepare uploaded audio file
        # -------------------------------------------------------------------

        extension = _extension_for_mime(guessed_mime)

        sent_filename = filename or f"recording{extension}"

        # Make sure the filename has the correct extension so that the
        # Groq / OpenAI-compatible SDK can sniff the audio container format
        # correctly.  If the user-supplied filename lacks an extension we
        # fall back to the guessed one.
        base_name, ext = os.path.splitext(sent_filename)
        if not ext:
            sent_filename = f"{base_name}{extension}"
        elif ext.lower() not in _EXT_TO_MIME:
            # Replace unknown extension with one Whisper accepts.
            sent_filename = f"{base_name}{extension}"

        file_obj = io.BytesIO(audio_bytes)

        # Groq/OpenAI-compatible SDK uses the filename
        # to determine the uploaded file format.
        file_obj.name = sent_filename

        # -------------------------------------------------------------------
        # 5. Normalize optional language
        # -------------------------------------------------------------------

        requested_language = None

        if language_code:
            requested_language = normalise_language(
                language_code
            )

        # -------------------------------------------------------------------
        # 6. Select Whisper model
        # -------------------------------------------------------------------

        model_name = getattr(
            settings,
            "groq_stt_model",
            None,
        ) or "whisper-large-v3"

        logger.info(
            "STT model selected: %s",
            model_name,
        )

        # -------------------------------------------------------------------
        # 7. Call Groq Whisper
        # -------------------------------------------------------------------

        try:
            request_args = {
                "model": model_name,
                "file": file_obj,
                "response_format": "verbose_json",
                "temperature": 0.0,
                "timestamp_granularities": ["segment"],
            }

            # Only send language when we actually know it.
            # Otherwise Whisper automatically detects it.

            if requested_language:
                request_args["language"] = requested_language

                logger.info(
                    "STT language mode: forced=%s",
                    requested_language,
                )
            else:
                logger.info(
                    "STT language mode: automatic detection"
                )

            logger.info(
                "Groq STT request started: model=%s filename=%s mime=%s bytes=%d",
                model_name,
                sent_filename,
                guessed_mime,
                len(audio_bytes),
            )

            response = client.audio.transcriptions.create(
                **request_args
            )

        except APIStatusError as exc:

            status = getattr(exc, "status_code", 0) or 0

            logger.error(
                "Groq STT API error: status=%s error=%s",
                status,
                str(exc),
            )

            if status == 400:
                raise STTError(
                    "stt_bad_request",
                    (
                        "Groq could not process the audio. "
                        "Please record again using the microphone."
                    ),
                ) from exc

            if status == 401:
                raise STTError(
                    "stt_invalid_api_key",
                    "Groq API key is invalid or unauthorised.",
                ) from exc

            if status == 413:
                raise STTError(
                    "stt_file_too_large",
                    "Audio file is too large for Groq.",
                ) from exc

            if status == 429:
                raise STTError(
                    "stt_rate_limit",
                    (
                        "Groq rate limit reached. "
                        "Please wait a moment and try again."
                    ),
                ) from exc

            if status and 500 <= status < 600:
                raise STTError(
                    "stt_provider_unavailable",
                    (
                        "Groq is temporarily unavailable. "
                        "Please try again shortly."
                    ),
                ) from exc

            raise STTError(
                "stt_provider_error",
                "Speech recognition failed at the Groq service.",
            ) from exc

        except Exception as exc:

            logger.exception(
                "Groq STT unexpected failure"
            )

            raise STTError(
                "stt_internal_error",
                (
                    "Speech recognition failed unexpectedly. "
                    "Please try again."
                ),
            ) from exc

        # -------------------------------------------------------------------
        # 8. Extract transcript
        # -------------------------------------------------------------------

        text = (
            getattr(response, "text", "") or ""
        ).strip()

        logger.info(
            "Groq STT response received: language=%s transcript=%r",
            getattr(response, "language", None),
            text,
        )

        # Reject known Whisper hallucinations such as "you", "thank you",
        # "thanks for watching", etc.  These appear when Whisper is fed
        # near-silent audio and would otherwise leak into the conversation
        # UI as if the user actually said them.
        if text and _looks_like_placeholder_transcript(text):
            logger.warning(
                "STT rejected probable hallucination: %r",
                text,
            )
            raise STTError(
                "stt_no_speech",
                (
                    "I could not clearly detect speech. "
                    "Please speak closer to the microphone "
                    "and try again."
                ),
            )

        # -------------------------------------------------------------------
        # 9. Extract detected language
        # -------------------------------------------------------------------

        detected_language = getattr(
            response,
            "language",
            None,
        )

        detected_language = (
            str(detected_language).strip()
            if detected_language
            else None
        )

        language_result = (
            normalise_language(detected_language)
            if detected_language
            else None
        )

        if not language_result and requested_language:
            language_result = requested_language

        # -------------------------------------------------------------------
        # 10. Extract verbose metadata
        # -------------------------------------------------------------------

        segments = getattr(
            response,
            "segments",
            None,
        )

        if segments:

            avg_logprobs = []
            no_speech_probs = []
            compression_ratios = []

            for segment in segments:

                avg_logprob = _safe_float(
                    getattr(
                        segment,
                        "avg_logprob",
                        None,
                    )
                )

                no_speech_prob = _safe_float(
                    getattr(
                        segment,
                        "no_speech_prob",
                        None,
                    )
                )

                compression_ratio = _safe_float(
                    getattr(
                        segment,
                        "compression_ratio",
                        None,
                    )
                )

                if avg_logprob is not None:
                    avg_logprobs.append(avg_logprob)

                if no_speech_prob is not None:
                    no_speech_probs.append(no_speech_prob)

                if compression_ratio is not None:
                    compression_ratios.append(
                        compression_ratio
                    )

            mean_logprob = (
                sum(avg_logprobs) / len(avg_logprobs)
                if avg_logprobs
                else None
            )

            max_no_speech_prob = (
                max(no_speech_probs)
                if no_speech_probs
                else None
            )

            max_compression_ratio = (
                max(compression_ratios)
                if compression_ratios
                else None
            )

            logger.info(
                (
                    "STT result: language=%s text=%r "
                    "avg_logprob=%s no_speech_prob=%s "
                    "compression_ratio=%s"
                ),
                language_result,
                text,
                (
                    f"{mean_logprob:.3f}"
                    if mean_logprob is not None
                    else "n/a"
                ),
                (
                    f"{max_no_speech_prob:.3f}"
                    if max_no_speech_prob is not None
                    else "n/a"
                ),
                (
                    f"{max_compression_ratio:.3f}"
                    if max_compression_ratio is not None
                    else "n/a"
                ),
            )

        else:

            logger.info(
                "STT result: language=%s text=%r",
                language_result,
                text,
            )

        # -------------------------------------------------------------------
        # 11. Empty transcription protection
        # -------------------------------------------------------------------

        if not text:
            raise STTError(
                "stt_empty_result",
                (
                    "I couldn't clearly hear anything in that recording. "
                    "Please speak again."
                ),
            )

        # -------------------------------------------------------------------
        # 12. No-speech protection (lower threshold than 0.98 because
        #     Whisper's no_speech_prob is a useful signal even below that).
        # -------------------------------------------------------------------

        if segments:

            no_speech_values = []

            for segment in segments:

                value = _safe_float(
                    getattr(
                        segment,
                        "no_speech_prob",
                        None,
                    )
                )

                if value is not None:
                    no_speech_values.append(value)

            if no_speech_values:

                max_no_speech = max(
                    no_speech_values
                )

                # Reject strong silence predictions.
                # 0.85 is a more aggressive threshold than the previous 0.98
                # and catches more of Whisper's hallucination-prone cases.
                if max_no_speech >= 0.85:

                    logger.warning(
                        (
                            "STT rejected probable silence: "
                            "no_speech_prob=%.3f text=%r"
                        ),
                        max_no_speech,
                        text,
                    )

                    raise STTError(
                        "stt_no_speech",
                        (
                            "I could not clearly detect speech. "
                            "Please speak closer to the microphone "
                            "and try again."
                        ),
                    )

        # -------------------------------------------------------------------
        # 13. Final diagnostic log
        # -------------------------------------------------------------------

        logger.info(
            (
                "STT SUCCESS | model=%s | "
                "requested_language=%s | "
                "detected_language=%s | "
                "transcript=%r"
            ),
            model_name,
            requested_language or "auto",
            language_result or "unknown",
            text,
        )

        # -------------------------------------------------------------------
        # 14. Return
        # -------------------------------------------------------------------

        return (
            text,
            language_result,
            None,
        )


# ---------------------------------------------------------------------------
# Single shared service instance
# ---------------------------------------------------------------------------

stt_service = STTService()
