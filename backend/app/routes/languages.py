"""GET /api/languages — returns the catalogue of supported languages so
the frontend can render a picker without duplicating the list."""

from __future__ import annotations

from fastapi import APIRouter

from app.services.language_service import get_supported

router = APIRouter()


@router.get("/languages")
async def list_languages():
    return {"success": True, "languages": get_supported()}
