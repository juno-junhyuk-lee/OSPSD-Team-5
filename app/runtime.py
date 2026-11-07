"""Hosted startup configuration and caller access."""

import hmac
import os
import re
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from app.errors import ErrorCode
from app.event_provider import CalendarAuthenticationError
from app.google_auth import hosted, hosted_authorization
from app.tracing import create_tracer_provider


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    mode = os.getenv("CALENDAR_MODE", "local")
    if mode not in {"local", "hosted"}:
        raise RuntimeError("CALENDAR_MODE must be local or hosted.")
    app.state.demo_bearer = None
    app.state.request_tracer = None
    provider = None
    try:
        try:
            provider = create_tracer_provider()
            app.state.request_tracer = provider.get_tracer("calendar.requests")
        except Exception:
            pass
        if hosted():
            app.state.demo_bearer = validate_hosted_config()
        yield
    finally:
        app.state.demo_bearer = None
        app.state.request_tracer = None
        if provider is not None:
            try:
                provider.shutdown()
            except Exception:
                pass
        hosted_authorization.cache_clear()


def validate_hosted_config() -> bytes:
    if not re.fullmatch(r"[0-9a-f]{40}", os.getenv("CALENDAR_RELEASE", "")):
        raise RuntimeError("CALENDAR_RELEASE must be a full Git commit SHA.")
    try:
        hosted_authorization()
    except CalendarAuthenticationError:
        raise RuntimeError(
            "Provide usable Google authorization in CALENDAR_TOKEN_FILE."
        ) from None
    try:
        bearer = Path(os.environ["CALENDAR_BEARER_FILE"]).read_text().strip()
    except KeyError, OSError, ValueError:
        raise RuntimeError("Provide a readable CALENDAR_BEARER_FILE.") from None
    if not re.fullmatch(r"[A-Za-z0-9_-]{32,}", bearer):
        raise RuntimeError("CALENDAR_BEARER_FILE must contain a URL-safe secret.")
    return bearer.encode("ascii")


async def require_hosted_access(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    if hosted() and request.url.path not in {"/health", "/ready"}:
        expected = getattr(request.app.state, "demo_bearer", None)
        headers = request.headers.getlist("authorization")
        if expected is not None and len(headers) == 1:
            scheme, _, supplied = headers[0].partition(" ")
            if scheme.lower() == "bearer" and hmac.compare_digest(
                supplied.encode("latin-1"), expected
            ):
                return await call_next(request)
        return JSONResponse(
            status_code=401,
            headers={"WWW-Authenticate": "Bearer"},
            content={
                "error": {
                    "code": ErrorCode.ACCESS_DENIED.value,
                    "message": "A valid API bearer token is required.",
                    "retryable": False,
                }
            },
        )
    return await call_next(request)
