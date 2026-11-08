"""Trace requests and Google calls without recording payloads or exceptions."""

import os
import re
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Literal

from opentelemetry import trace
from opentelemetry.context import Context
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import SpanLimits, TracerProvider
from opentelemetry.sdk.trace.sampling import ALWAYS_ON
from opentelemetry.trace import (
    INVALID_SPAN_CONTEXT,
    NonRecordingSpan,
    Span,
    SpanKind,
    StatusCode,
    Tracer,
)
from opentelemetry.util.types import Attributes
from starlette.types import Scope

SERVICE = "calendar-team-5"
GoogleMethod = Literal[
    "events.insert",
    "events.get",
    "events.patch",
    "events.delete",
    "calendars.get",
    "oauth.refresh",
]
_request_tracer: ContextVar[Tracer | None] = ContextVar(
    "calendar_request_tracer", default=None
)


def release_identity() -> str:
    value = os.getenv("CALENDAR_RELEASE", "")
    return value if re.fullmatch(r"[0-9a-f]{40}", value) else "local"


def create_tracer_provider() -> TracerProvider:
    """Create an app-owned SDK provider; attach exporters during startup."""
    resource: dict[str, str] = {
        "service.name": SERVICE,
        "service.version": release_identity(),
    }
    project = os.getenv("CALENDAR_TELEMETRY_PROJECT", "")
    if re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]", project):
        resource["gcp.project_id"] = project
    return TracerProvider(
        resource=Resource(resource),
        sampler=ALWAYS_ON,
        span_limits=SpanLimits(
            max_attributes=16, max_events=0, max_links=0, max_attribute_length=128
        ),
        shutdown_on_exit=False,
    )


def mark_error(span: Span) -> None:
    try:
        span.set_status(StatusCode.ERROR)
    except Exception:
        pass


@contextmanager
def safe_span(
    tracer: Tracer,
    name: str,
    kind: SpanKind,
    attributes: Attributes,
    *,
    root: bool = False,
) -> Iterator[Span]:
    try:
        span = tracer.start_span(
            name,
            context=Context() if root else None,
            kind=kind,
            attributes=attributes,
            record_exception=False,
            set_status_on_exception=False,
        )
    except Exception:
        span = NonRecordingSpan(INVALID_SPAN_CONTEXT)
    with trace.use_span(span, record_exception=False, set_status_on_exception=False):
        try:
            yield span
        except BaseException:
            mark_error(span)
            raise
        finally:
            try:
                span.end()
            except Exception:
                pass


@contextmanager
def request_span(scope: Scope, request_id: str) -> Iterator[Span]:
    application = scope.get("app")
    state = getattr(application, "state", None)
    tracer = getattr(state, "request_tracer", None)
    if tracer is None:
        tracer = trace.NoOpTracer()
    token = _request_tracer.set(tracer)
    try:
        with safe_span(
            tracer,
            "calendar.request",
            SpanKind.SERVER,
            {"request.id": request_id},
            root=True,
        ) as span:
            yield span
    finally:
        _request_tracer.reset(token)


def finish_request_span(
    span: Span,
    operation: str,
    outcome: str,
    source: str,
    status: int,
) -> None:
    try:
        span.update_name(f"calendar.{operation}")
        span.set_attributes(
            {
                "operation": operation,
                "outcome": outcome,
                "failure_source": source,
                "http.response.status_code": status,
            }
        )
        if status >= 500 or outcome == "internal_error":
            mark_error(span)
    except Exception:
        pass


def span_identity(span: Span) -> dict[str, str | None]:
    try:
        context = span.get_span_context()
        if context.is_valid:
            return {
                "trace_id": trace.format_trace_id(context.trace_id),
                "span_id": trace.format_span_id(context.span_id),
            }
    except Exception:
        pass
    return {"trace_id": None, "span_id": None}


@contextmanager
def google_call(method: GoogleMethod) -> Iterator[None]:
    """Time exactly one SDK call, preserving its return value and exception."""
    tracer = _request_tracer.get()
    if tracer is None:
        yield
        return
    with safe_span(
        tracer,
        f"google.calendar.{method}",
        SpanKind.CLIENT,
        {"rpc.system": "google_calendar", "rpc.method": method},
    ):
        yield
