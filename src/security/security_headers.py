from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware that adds OWASP recommended security headers to all HTTP responses.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking in iframes
        response.headers["X-Frame-Options"] = "DENY"

        # Enable XSS filtering in legacy browsers
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Enforce HTTPS transport
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        # Control referrer information
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Restrict browser features and sensors
        response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"

        return response
