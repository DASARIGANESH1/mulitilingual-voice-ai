"""Convenience entrypoint so `python run.py` starts the FastAPI server
without needing to type the uvicorn command. Useful on Windows."""

from __future__ import annotations

import uvicorn

from app.config import settings


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.backend_port,
        reload=True,
        log_level="info",
    )
