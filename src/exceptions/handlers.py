from __future__ import annotations

from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse


def register_exception_handlers(app: FastAPI):

    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        request: Request,
        exc: HTTPException,
    ):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "message": exc.detail if isinstance(exc.detail, str) else "Request error.",
                "detail": exc.detail,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            headers=exc.headers,
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(
        request: Request,
        exc: Exception,
    ):
        print(f"Unhandled Exception on {request.url.path}: {type(exc).__name__}: {exc}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": "Internal server error occurred.",
                "error": str(exc),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )