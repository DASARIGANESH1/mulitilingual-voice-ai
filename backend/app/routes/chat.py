"""POST /api/chat — LLM / NLG route handler."""

from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.config import settings
from app.models import ChatRequest, ChatResponse, ErrorResponse
from app.services.language_service import is_supported
from app.services.llm_service import LLMError, llm_service
from app.utils import normalise_language, sanitise_error

router = APIRouter()
logger = logging.getLogger("uvicorn.error")


def _error(code: str, message: str, status_code: int = 500) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(error=sanitise_error(message), error_code=code).model_dump(),
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Generate a human-like reply using Gemini."""
    language_code = normalise_language(request.language) or "en"

    # Defensive: if the STT-detected code isn't in our catalogue we still
    # answer — the model can usually figure out the language from the
    # input text — but we log it so the operator can extend the catalogue.
    if not is_supported(language_code):
        logger.info(
            "Language '%s' not in SUPPORTED_LANGUAGES — relying on Gemini's "
            "own language detection.",
            request.language,
        )

    # Trim conversation history to the configured limit. We keep the most
    # recent N turns because the user's question is more likely to refer to
    # recent context than to ancient turns.
    history_pairs = [
        (msg.role, msg.content) for msg in request.conversation_history
    ]
    if len(history_pairs) > settings.backend_max_history:
        history_pairs = history_pairs[-settings.backend_max_history :]

    try:
        response_text = llm_service.generate(
            user_message=request.message,
            language_code=language_code,
            history=history_pairs,
        )
    except LLMError as exc:
        logger.warning("LLM failure: code=%s message=%s", exc.code, exc.message)
        return _error(exc.code, exc.message)
    except Exception:  # noqa: BLE001 - safety net
        logger.exception("Unexpected LLM failure")
        return _error(
            "llm_internal_error",
            "I couldn't think of a reply right now. Please try again.",
        )

    return ChatResponse(
        success=True,
        response=response_text,
        language=language_code,
    )
