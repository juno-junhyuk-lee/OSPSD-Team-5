"""Bounded request metrics and one sanitized outcome log per HTTP request."""

import json
import logging
import os
import re
from dataclasses import dataclass
from time import perf_counter
from uuid import uuid4

from calendar_contract import ErrorCode
from opentelemetry import metrics
from opentelemetry.metrics import Meter
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger("calendar_service")
logger.setLevel(logging.INFO)
if not logger.handlers:
    logger.addHandler(logging.StreamHandler())

SERVICE = "calendar-team-5"
STATE_KEY = "calendar_request_outcome"
OPERATIONS = {
    "create_event": "create",
    "get_event": "get",
    "replace_event": "replace",
    "delete_event": "delete",
    "update_event": "patch",
    "get_calendar": "get_calendar",
    "health": "health",
    "ready": "ready",
}


@dataclass
class RequestOutcome:
    error: ErrorCode | None = None
    provider: bool = False


def record_failure(scope: Scope, code: ErrorCode, provider: bool) -> bool:
    """Pass safe error context to the middleware without logging twice."""
    outcome = scope.get("state", {}).get(STATE_KEY)
    if not isinstance(outcome, RequestOutcome):
        return False
    outcome.error = code
    outcome.provider = provider
    return True


def request_operation(scope: Scope) -> tuple[str, str]:
    name = getattr(scope.get("route"), "name", "")
    if name in OPERATIONS:
        return name, OPERATIONS[name]
    # Authentication can reject a request before routing has selected a handler.
    path = scope["path"]
    method = scope["method"]
    if path == "/events" and method == "POST":
        return "create_event", "create"
    if path.startswith("/events/") and path.count("/") == 2 and path[8:]:
        handlers = {
            "GET": "get_event",
            "PUT": "replace_event",
            "PATCH": "update_event",
            "DELETE": "delete_event",
        }
        if method in handlers:
            handler = handlers[method]
            return handler, OPERATIONS[handler]
    if (
        path.startswith("/calendars/")
        and path.count("/") == 2
        and path[11:]
        and method == "GET"
    ):
        return "get_calendar", "get_calendar"
    return "http_other", "http_other"


def request_result(
    outcome: RequestOutcome, status: int, unexpected: bool
) -> tuple[str, str]:
    if unexpected:
        return "internal_error", "service"
    if outcome.error is not None:
        code = outcome.error.value
    elif status == 401 or status == 403:
        code = "access_denied"
    elif status == 404:
        code = "not_found"
    elif status >= 500:
        return "internal_error", "service"
    elif status >= 400:
        return "http_error", "caller"
    else:
        return "success", "none"
    if code in {"invalid_input", "not_found"}:
        return code, "caller"
    if code == "access_denied" and not outcome.provider:
        return code, "caller"
    return code, "provider" if outcome.provider else "service"


class RequestMetrics:
    """Use fixed labels and SDK aggregation, never keep individual requests."""

    def __init__(self, meter: Meter | None = None) -> None:
        meter = meter if meter is not None else metrics.get_meter("calendar.requests")
        self.requests = meter.create_counter(
            "calendar.requests", unit="{request}", description="Completed HTTP requests"
        )
        self.errors = meter.create_counter(
            "calendar.request.errors",
            unit="{request}",
            description="Failed HTTP requests by outcome and failure source",
        )
        self.duration = meter.create_histogram(
            "calendar.request.duration",
            unit="s",
            description="Request duration, separated by success and failure outcome",
            explicit_bucket_boundaries_advisory=(
                0.005,
                0.01,
                0.025,
                0.05,
                0.1,
                0.25,
                0.5,
                1,
                2.5,
                5,
                10,
                30,
                90,
            ),
        )

    def record(
        self, operation: str, outcome: str, source: str, status: int, duration: float
    ) -> None:
        attributes = {
            "operation": operation,
            "outcome": outcome,
            "failure_source": source,
            "http.response.status_code": status,
        }
        self.requests.add(1, attributes)
        self.duration.record(duration, attributes)
        if outcome != "success":
            self.errors.add(1, attributes)


class RequestTelemetryMiddleware:
    def __init__(
        self, app: ASGIApp, request_metrics: RequestMetrics | None = None
    ) -> None:
        self.app = app
        self.metrics = (
            request_metrics if request_metrics is not None else RequestMetrics()
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        outcome = RequestOutcome()
        scope.setdefault("state", {})[STATE_KEY] = outcome
        request_id = uuid4().hex
        started = perf_counter()
        status = 500
        unexpected = False

        async def send_response(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                message = {
                    **message,
                    "headers": [
                        (key, value)
                        for key, value in message.get("headers", [])
                        if key.lower() != b"x-request-id"
                    ]
                    + [(b"x-request-id", request_id.encode("ascii"))],
                }
            await send(message)

        try:
            await self.app(scope, receive, send_response)
        except Exception:
            unexpected = True
            raise
        finally:
            duration = max(0.0, perf_counter() - started)
            handler, operation = request_operation(scope)
            result, source = request_result(outcome, status, unexpected)
            release = os.getenv("CALENDAR_RELEASE", "")
            if not re.fullmatch(r"[0-9a-f]{40}", release):
                release = "local"
            # Telemetry must never change the HTTP result or retry provider work.
            try:
                self.metrics.record(operation, result, source, status, duration)
            except Exception:
                pass
            try:
                level = (
                    logging.ERROR
                    if source == "service" or status >= 500
                    else logging.WARNING
                    if status >= 400
                    else logging.INFO
                )
                logger.log(
                    level,
                    json.dumps(
                        {
                            "service": SERVICE,
                            "release": release,
                            "operation": handler,
                            "contract_operation": operation,
                            "outcome": result,
                            "error": result if result != "success" else None,
                            "failure_source": source,
                            "provider": (
                                outcome.provider if outcome.error is not None else None
                            ),
                            "status": status,
                            "duration_ms": round(duration * 1000, 3),
                            "request_id": request_id,
                        }
                    ),
                )
            except Exception:
                pass
