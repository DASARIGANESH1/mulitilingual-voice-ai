"""LLM / NLG service backed by Google Gemini (free tier).

We use the official ``google-genai`` SDK (``from google import genai``)
because it supports all current free-tier models, including the recommended
``gemini-2.0-flash``. The model name is fully configurable through env.

The system prompt for human-like, multilingual, conversational responses
is built by :mod:`app.services.language_service` and never changes inside
this file — keeping prompt authoring in one place.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from google import genai
from google.genai import errors as genai_errors
from google.genai.types import (
    Content,
    GenerateContentConfig,
    HttpOptions,
    Part,
    SafetySetting,
)

from app.config import settings
from app.services.language_service import build_system_prompt
from app.utils import normalise_language

logger = logging.getLogger("uvicorn.error")


class LLMError(Exception):
    """Raised for any Gemini failure. `code` is a stable machine label."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# Gemini safety settings. For a conversational assistant the defaults are
# too aggressive and routinely block benign content. We loosen them so the
# model doesn't refuse to answer friendly questions.
_DEFAULT_SAFETY = [
    SafetySetting(
        category="HARM_CATEGORY_HARASSMENT",
        threshold="BLOCK_ONLY_HIGH",
    ),
    SafetySetting(
        category="HARM_CATEGORY_HATE_SPEECH",
        threshold="BLOCK_ONLY_HIGH",
    ),
    SafetySetting(
        category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
        threshold="BLOCK_ONLY_HIGH",
    ),
    SafetySetting(
        category="HARM_CATEGORY_DANGEROUS_CONTENT",
        threshold="BLOCK_ONLY_HIGH",
    ),
    SafetySetting(
        category="HARM_CATEGORY_CIVIC_INTEGRITY",
        threshold="BLOCK_ONLY_HIGH",
    ),
]


class LLMService:
    """Wraps the Gemini generate-content call."""

    def __init__(self, client: Optional[genai.Client] = None) -> None:
        self._client = client

    def _ensure_client(self) -> genai.Client:
        if not settings.has_gemini:
            raise LLMError(
                code="llm_no_api_key",
                message="Gemini API key is not configured on the server.",
            )
        if self._client is None:
            # ``http_options`` lets us bump the timeout so we don't trip
            # on slow first-call latency on free tier.
            self._client = genai.Client(
                api_key=settings.gemini_api_key,
                http_options=HttpOptions(timeout=30_000),
            )
        return self._client

    def generate(
        self,
        user_message: str,
        language_code: str,
        history: List[Tuple[str, str]],
    ) -> str:
        """Generate a human-like reply.

        Parameters
        ----------
        user_message
            The latest user turn (already transcribed).
        language_code
            ISO-639-1 code used to build the system prompt.
        history
            List of ``(role, content)`` tuples, oldest first. Already
            truncated to ``settings.backend_max_history`` by the route.
        """
        client = self._ensure_client()
        system_prompt = build_system_prompt(language_code)

        # Build Gemini-style Contents from history + new user message.
        #
        # Gemini's API only accepts the roles "user" and "model".  Our
        # conversation history uses the OpenAI-style pair "user" /
        # "assistant", so we translate "assistant" -> "model" here.
        # Sending "assistant" verbatim triggers a 400 INVALID_ARGUMENT
        # from Gemini.
        contents: List[Content] = []
        for role, content in history:
            if role == "user":
                gemini_role = "user"
            elif role == "assistant":
                gemini_role = "model"
            else:
                # Skip anything we don't recognise so the request still
                # succeeds when the frontend forwards a malformed turn.
                continue
            contents.append(
                Content(
                    role=gemini_role,
                    parts=[Part(text=content)],
                )
            )
        contents.append(
            Content(
                role="user",
                parts=[Part(text=user_message)],
            )
        )

        try:
            response = client.models.generate_content(
                model=settings.gemini_model,
                contents=contents,
                config=GenerateContentConfig(
                    system_instruction=system_prompt,
                    safety_settings=_DEFAULT_SAFETY,
                    temperature=0.7,        # natural variation
                    top_p=0.95,
                    top_k=40,
                    max_output_tokens=400,  # keep spoken responses short
                ),
            )
        except genai_errors.ClientError as exc:
            self._map_client_error(exc)
        except genai_errors.ServerError as exc:
            raise LLMError(
                code="llm_provider_unavailable",
                message="Gemini is temporarily unavailable. Try again shortly.",
            ) from exc
        except Exception as exc:  # noqa: BLE001 - intentional broad catch
            logger.exception("Gemini unexpected failure")
            raise LLMError(
                code="llm_internal_error",
                message="I couldn't think of a reply right now. Try again.",
            ) from exc

        # Extract text. The SDK exposes it as `.text` (a convenience) that
        # raises if no candidate was returned, so we guard with candidates.
        text = ""
        if response and getattr(response, "candidates", None):
            cand = response.candidates[0]
            if cand and getattr(cand, "content", None):
                parts = getattr(cand.content, "parts", None) or []
                text = "".join(getattr(p, "text", "") or "" for p in parts).strip()

        # Surface a friendly message when the model returned nothing —
        # usually a safety filter blocked the reply.
        if not text:
            # Inspect prompt_feedback for a hint about why it was blocked.
            feedback = getattr(response, "prompt_feedback", None)
            block_reason = getattr(feedback, "block_reason", None) if feedback else None
            if block_reason:
                raise LLMError(
                    code="llm_blocked",
                    message="I'm not able to answer that. Could you rephrase?",
                )
            raise LLMError(
                code="llm_empty_response",
                message="The model returned an empty reply. Please try again.",
            )

        return text

    @staticmethod
    def _map_client_error(exc: genai_errors.ClientError) -> None:
        """Translate a Gemini ClientError into a stable LLMError code."""
        status = getattr(exc, "status", 0) or 0
        message = str(exc)
        if status == 401 or "API_KEY_INVALID" in message.upper():
            raise LLMError(
                code="llm_invalid_api_key",
                message="Gemini API key is invalid.",
            )
        if status == 429 or "RESOURCE_EXHAUSTED" in message.upper():
            raise LLMError(
                code="llm_rate_limit",
                message="Gemini rate limit reached on the free tier. Wait a moment.",
            )
        if status == 404 or "NOT_FOUND" in message.upper():
            raise LLMError(
                code="llm_model_not_found",
                message=(
                    f"The Gemini model '{settings.gemini_model}' was not found. "
                    "Update GEMINI_MODEL in backend/.env to a valid free-tier model."
                ),
            )
        raise LLMError(
            code="llm_provider_error",
            message="The model couldn't produce a reply. Please try again.",
        )


# Single shared instance for the app
llm_service = LLMService()


# Re-export normalise_language so callers don't have to import from utils
__all__ = ["llm_service", "LLMError", "normalise_language"]
