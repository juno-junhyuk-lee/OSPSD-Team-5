"""Bounded request metrics and one sanitized outcome log per HTTP request."""

import json
import logging
import os
import re
from dataclasses import dataclass
from threading import Lock
from time import perf_counter
from uuid import uuid4

from calendar_contract import ErrorCode
from opentelemetry import metrics
from opentelemetry.metrics import Meter
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.tracing import (
    SERVICE,
    finish_request_span,
    release_identity,
    request_span,
    span_identity,
)

logger = logging.getLogger("calendar_service")
logger.setLevel(logging.INFO)
if not logger.handlers:
    logger.addHandler(logging.StreamHandler())

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

    def __init__(self, meter: Meter | None = None, *, cloud: bool = False) -> None:
        meter = meter if meter is not None else metrics.get_meter("calendar.requests")
        self.common: dict[str, str] = {}
        if cloud:
            environment = os.getenv("CALENDAR_ENV", "local")
            self.common = {
                "release": release_identity(),
                "environment": environment
                if environment in {"demo", "verify"}
                else "local",
            }
        self.active = 0
        self.lock = Lock()
        self.saturation = meter.create_histogram(
            "calendar.request.saturation",
            unit="1",
            description="Active shared-operation requests / configured concurrency (1)",
            explicit_bucket_boundaries_advisory=(0, 0.25, 0.5, 0.75, 1, 2, 4),
        )
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
            **self.common,
            "operation": operation,
            "outcome": outcome,
            "failure_source": source,
            "http.response.status_code": status,
        }
        self.requests.add(1, attributes)
        self.duration.record(duration, attributes)
        if outcome != "success":
            self.errors.add(1, attributes)

    def enter(self, operation: str) -> bool:
        if operation not in {"create", "get", "replace", "delete"}:
            return False
        with self.lock:
            self.active += 1
            active = self.active
        try:
            self.saturation.record(active / 1, {**self.common, "operation": operation})
        except Exception:
            pass
        return True

    def leave(self) -> None:
        with self.lock:
            self.active -= 1


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
        state = getattr(scope.get("app"), "state", None)
        request_metrics = getattr(state, "request_metrics", None) or self.metrics
        entered = False
        try:
            entered = request_metrics.enter(request_operation(scope)[1])
        except Exception:
            pass
        with request_span(scope, request_id) as span:
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
                            if key.lower() not in {b"x-request-id", b"x-trace-id"}
                        ]
                        + [(b"x-request-id", request_id.encode("ascii"))],
                    }
                    trace_id = span_identity(span)["trace_id"]
                    if trace_id is not None:
                        message["headers"].append(
                            (b"x-trace-id", trace_id.encode("ascii"))
                        )
                await send(message)

            try:
                await self.app(scope, receive, send_response)
            except Exception:
                unexpected = True
                raise
            finally:
                if entered:
                    try:
                        request_metrics.leave()
                    except Exception:
                        pass
                duration = max(0.0, perf_counter() - started)
                handler, operation = request_operation(scope)
                result, source = request_result(outcome, status, unexpected)
                finish_request_span(span, operation, result, source, status)
                # Telemetry must never change the HTTP result or retry provider work.
                try:
                    request_metrics.record(operation, result, source, status, duration)
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
                                "release": release_identity(),
                                "operation": handler,
                                "contract_operation": operation,
                                "outcome": result,
                                "error": result if result != "success" else None,
                                "failure_source": source,
                                "provider": (
                                    outcome.provider
                                    if outcome.error is not None
                                    else None
                                ),
                                "status": status,
                                "duration_ms": round(duration * 1000, 3),
                                "severity": logging.getLevelName(level),
                                "request_id": request_id,
                                **span_identity(span),
                                **cloud_log_correlation(span_identity(span)),
                            }
                        ),
                    )
                except Exception:
                    pass


def cloud_log_correlation(identity: dict[str, str | None]) -> dict[str, str | bool]:
    project = os.getenv("CALENDAR_TELEMETRY_PROJECT", "")
    if (
        not re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]", project)
        or not identity["trace_id"]
        or not identity["span_id"]
    ):
        return {}
    return {
        "logging.googleapis.com/trace": f"projects/{project}/traces/{identity['trace_id']}",
        "logging.googleapis.com/spanId": identity["span_id"],
        "logging.googleapis.com/trace_sampled": True,
    }
