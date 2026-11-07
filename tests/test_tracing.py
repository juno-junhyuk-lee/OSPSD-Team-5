"""Inspect real SDK traces around the normal HTTP and Google adapter wiring."""

import json
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from typing import Any
from unittest.mock import MagicMock, Mock

import pytest
from fastapi.testclient import TestClient
from googleapiclient.errors import HttpError  # type: ignore[import-untyped]
from opentelemetry import trace
from opentelemetry.sdk.trace import ReadableSpan, SpanProcessor, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind, StatusCode, Tracer

from app import google_auth, google_create_events, runtime, tracing
from app.main import app

PAYLOAD = {
    "title": "private-title",
    "start": "2030-01-07T15:00:00Z",
    "end": "2030-01-07T15:30:00Z",
}
ROUTES = [
    ("POST", "/events", "create", 201, ["events.insert"]),
    ("GET", "/events/test-event", "get", 200, ["events.get"]),
    ("PUT", "/events/test-event", "replace", 200, ["events.get", "events.patch"]),
    ("DELETE", "/events/test-event", "delete", 204, ["events.delete"]),
    ("PATCH", "/events/test-event", "patch", 200, ["events.get", "events.patch"]),
]


@pytest.fixture
def exporter(monkeypatch: pytest.MonkeyPatch) -> InMemorySpanExporter:
    result = InMemorySpanExporter(max_spans=100)
    monkeypatch.setenv("CALENDAR_RELEASE", "a" * 40)

    def provider() -> TracerProvider:
        sdk = tracing.create_tracer_provider()
        sdk.add_span_processor(SimpleSpanProcessor(result))
        return sdk

    monkeypatch.setattr(runtime, "create_tracer_provider", provider)
    return result


@pytest.fixture
def traced_client(exporter: InMemorySpanExporter, client: TestClient) -> TestClient:
    return client


def request_log(caplog: pytest.LogCaptureFixture) -> dict[str, Any]:
    [record] = [r for r in caplog.records if r.name == "calendar_service"]
    assert record.exc_info is None
    return json.loads(record.getMessage())  # type: ignore[no-any-return]


def server_span(exporter: InMemorySpanExporter) -> ReadableSpan:
    [span] = [s for s in exporter.get_finished_spans() if s.kind == SpanKind.SERVER]
    assert span.parent is None
    return span


def provider_spans(exporter: InMemorySpanExporter) -> list[ReadableSpan]:
    return [s for s in exporter.get_finished_spans() if s.kind == SpanKind.CLIENT]


def assert_private_data_excluded(exporter: InMemorySpanExporter) -> None:
    for span in exporter.get_finished_spans():
        assert "private" not in span.to_json()
        assert span.events == ()
        assert span.links == ()
        assert span.status.description is None


@pytest.mark.parametrize("method,path,operation,status,calls", ROUTES)
def test_actual_adapters_have_separate_child_spans_and_correlated_logs(
    traced_client: TestClient,
    exporter: InMemorySpanExporter,
    caplog: pytest.LogCaptureFixture,
    method: str,
    path: str,
    operation: str,
    status: int,
    calls: list[str],
) -> None:
    response = traced_client.request(
        method,
        path,
        json=PAYLOAD if method in {"POST", "PUT", "PATCH"} else None,
        headers={
            "Authorization": "Bearer private-token",
            "traceparent": "00-" + "b" * 32 + "-" + "c" * 16 + "-01",
            "baggage": "secret=private-baggage",
        },
    )
    assert response.status_code == status
    parent = server_span(exporter)
    assert parent.name == f"calendar.{operation}"
    assert parent.context is not None
    expected_trace = trace.format_trace_id(parent.context.trace_id)
    entry = request_log(caplog)
    assert expected_trace == entry["trace_id"] == response.headers["X-Trace-ID"]
    assert expected_trace != "b" * 32
    assert entry["span_id"] == trace.format_span_id(parent.context.span_id)
    assert parent.attributes is not None
    assert parent.attributes["request.id"] == entry["request_id"]
    assert parent.attributes["outcome"] == "success"
    assert parent.attributes["http.response.status_code"] == status
    assert parent.resource.attributes["service.name"] == "calendar-team-5"
    assert parent.resource.attributes["service.version"] == "a" * 40
    children = provider_spans(exporter)
    assert [s.name for s in children] == [f"google.calendar.{call}" for call in calls]
    for child in children:
        assert child.context is not None and child.parent is not None
        assert child.context.trace_id == parent.context.trace_id
        assert child.parent.span_id == parent.context.span_id
        assert child.status.status_code == StatusCode.UNSET
        assert parent.start_time is not None and parent.end_time is not None
        assert child.start_time is not None and child.end_time is not None
        assert (
            parent.start_time <= child.start_time <= child.end_time <= parent.end_time
        )
    assert_private_data_excluded(exporter)


@pytest.mark.parametrize(
    "method,rpc,status,outcome",
    [
        ("POST", "insert", 502, "provider_error"),
        ("GET", "get", 503, "provider_unavailable"),
        ("PUT", "patch", 502, "provider_error"),
        ("DELETE", "delete", 502, "provider_error"),
    ],
)
def test_provider_failure_keeps_http_semantics_and_exports_no_exception_text(
    traced_client: TestClient,
    exporter: InMemorySpanExporter,
    google_service: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    method: str,
    rpc: str,
    status: int,
    outcome: str,
) -> None:
    monkeypatch.setattr("app.google_events.calendar_client", lambda: google_service)
    error = HttpError(
        Mock(status=503, reason="private-provider-reason"),
        b'{"error":{"message":"private-event-data"}}',
        uri="https://example.test/private-id?token=private-token",
    )
    if rpc == "get":
        execute = Mock(side_effect=error)
        google_service.events.return_value.get.side_effect = lambda **kwargs: Mock(
            execute=execute
        )
    else:
        execute = getattr(google_service.events.return_value, rpc).return_value.execute
        execute.side_effect = error
    response = traced_client.request(
        method,
        "/events" if method == "POST" else "/events/test-event",
        json=PAYLOAD if method in {"POST", "PUT"} else None,
    )
    assert response.status_code == status
    assert response.json()["error"]["code"] == outcome
    if method in {"POST", "PUT"}:
        assert response.json()["error"]["retryable"] is False
    execute.assert_called_once()
    parent = server_span(exporter)
    assert parent.status.status_code == StatusCode.ERROR
    assert parent.attributes is not None and parent.attributes["outcome"] == outcome
    [failed] = [
        s for s in provider_spans(exporter) if s.status.status_code == StatusCode.ERROR
    ]
    assert failed.name == f"google.calendar.events.{rpc}"
    entry = request_log(caplog)
    assert parent.context is not None
    assert entry["trace_id"] == trace.format_trace_id(parent.context.trace_id)
    assert "private" not in json.dumps(entry)
    assert_private_data_excluded(exporter)


@pytest.mark.parametrize("body,status", [('{"title":', 400), ("{}", 422)])
def test_invalid_input_has_a_request_trace_without_provider_spans(
    traced_client: TestClient,
    exporter: InMemorySpanExporter,
    google_service: MagicMock,
    caplog: pytest.LogCaptureFixture,
    body: str,
    status: int,
) -> None:
    response = traced_client.post(
        "/events", content=body, headers={"Content-Type": "application/json"}
    )
    assert response.status_code == status
    google_service.events.return_value.insert.assert_not_called()
    assert provider_spans(exporter) == []
    parent = server_span(exporter)
    assert parent.status.status_code == StatusCode.UNSET
    assert parent.attributes is not None
    assert parent.attributes["outcome"] == "invalid_input"
    assert parent.attributes["failure_source"] == "caller"
    assert request_log(caplog)["trace_id"] == response.headers["X-Trace-ID"]
    assert_private_data_excluded(exporter)


def test_unexpected_exception_is_not_automatically_exported(
    traced_client: TestClient,
    exporter: InMemorySpanExporter,
    google_service: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    google_service.events.return_value.insert.return_value.execute.side_effect = (
        RuntimeError("private-provider-data")
    )
    with pytest.raises(RuntimeError, match="private-provider-data"):
        traced_client.post("/events", json=PAYLOAD)
    parent = server_span(exporter)
    assert parent.status.status_code == StatusCode.ERROR
    assert (
        parent.attributes is not None
        and parent.attributes["outcome"] == "internal_error"
    )
    [child] = provider_spans(exporter)
    assert child.status.status_code == StatusCode.ERROR
    assert request_log(caplog)["outcome"] == "internal_error"
    assert_private_data_excluded(exporter)


def test_bad_provider_result_marks_request_failed_after_rpc_returns(
    traced_client: TestClient,
    exporter: InMemorySpanExporter,
    google_service: MagicMock,
) -> None:
    google_service.events.return_value.insert.return_value.execute.return_value = {
        "id": "private-incomplete-result"
    }
    google_service.events.return_value.insert.return_value.execute.side_effect = None
    response = traced_client.post("/events", json=PAYLOAD)
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "provider_error"
    parent = server_span(exporter)
    assert parent.status.status_code == StatusCode.ERROR
    assert parent.attributes is not None
    assert parent.attributes["failure_source"] == "provider"
    [child] = provider_spans(exporter)
    assert child.status.status_code == StatusCode.UNSET
    assert_private_data_excluded(exporter)


def test_bearer_rejection_is_traced_without_calling_google(
    traced_client: TestClient,
    exporter: InMemorySpanExporter,
    google_service: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(runtime, "hosted", lambda: True)
    app.state.demo_bearer = b"private-expected-bearer"
    response = traced_client.post("/events", json=PAYLOAD)
    assert response.status_code == 401
    google_service.events.return_value.insert.assert_not_called()
    assert provider_spans(exporter) == []
    parent = server_span(exporter)
    assert parent.name == "calendar.create"
    assert parent.attributes is not None
    assert parent.attributes["failure_source"] == "caller"
    assert parent.status.status_code == StatusCode.UNSET
    assert request_log(caplog)["trace_id"] == response.headers["X-Trace-ID"]
    assert_private_data_excluded(exporter)


def test_explicit_oauth_refresh_is_separate_from_calendar_rpc(
    traced_client: TestClient,
    exporter: InMemorySpanExporter,
    google_service: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    credentials = Mock(valid=False)
    credentials.has_scopes.return_value = True
    credentials.refresh.side_effect = lambda request: setattr(
        credentials, "valid", True
    )
    monkeypatch.setattr(google_auth, "hosted_authorization", lambda: credentials)
    monkeypatch.setattr(
        google_create_events, "load_credentials", google_auth.load_hosted_credentials
    )
    response = traced_client.post("/events", json=PAYLOAD)
    assert response.status_code == 201
    assert [span.name for span in provider_spans(exporter)] == [
        "google.calendar.oauth.refresh",
        "google.calendar.events.insert",
    ]
    credentials.refresh.assert_called_once()
    assert_private_data_excluded(exporter)


def test_metadata_extension_has_a_provider_span(
    traced_client: TestClient,
    exporter: InMemorySpanExporter,
    google_service: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build = MagicMock()
    build.return_value.__enter__.return_value = google_service
    monkeypatch.setattr("app.google_calendar.build", build)
    monkeypatch.setattr(
        "app.google_calendar.Credentials.from_authorized_user_file", lambda path: Mock()
    )
    google_service.calendars.return_value.get.return_value.execute.return_value = {
        "summary": "private-calendar-title",
        "timeZone": "UTC",
    }
    assert traced_client.get("/calendars/primary").status_code == 200
    assert server_span(exporter).name == "calendar.get_calendar"
    assert [span.name for span in provider_spans(exporter)] == [
        "google.calendar.calendars.get"
    ]
    assert_private_data_excluded(exporter)


def test_span_start_failure_does_not_change_or_repeat_google_write(
    traced_client: TestClient,
    google_service: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    tracer = Mock(spec=Tracer)
    tracer.start_span.side_effect = RuntimeError("private-telemetry-error")
    monkeypatch.setattr(app.state, "request_tracer", tracer)
    response = traced_client.post("/events", json=PAYLOAD)
    assert response.status_code == 201
    google_service.events.return_value.insert.return_value.execute.assert_called_once_with(
        num_retries=0
    )
    entry = request_log(caplog)
    assert entry["trace_id"] is None and entry["span_id"] is None
    assert "X-Trace-ID" not in response.headers
    assert "private" not in json.dumps(entry)


def test_sdk_call_span_excludes_local_credential_loading(
    traced_client: TestClient,
    google_service: MagicMock,
) -> None:
    positions: list[SpanKind] = []
    loader = google_create_events.load_credentials
    assert isinstance(loader, Mock)
    loader.side_effect = lambda: positions.append(trace.get_current_span().kind)  # type: ignore[attr-defined]
    execute = google_service.events.return_value.insert.return_value.execute
    original: Callable[..., dict[str, object]] = execute.side_effect

    def call(*, num_retries: int = 0) -> dict[str, object]:
        positions.append(trace.get_current_span().kind)  # type: ignore[attr-defined]
        return original(num_retries=num_retries)

    execute.side_effect = call
    assert traced_client.post("/events", json=PAYLOAD).status_code == 201
    assert positions == [SpanKind.SERVER, SpanKind.CLIENT]


def test_concurrent_requests_do_not_share_traces(
    traced_client: TestClient,
    exporter: InMemorySpanExporter,
    google_service: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    barrier = Barrier(2)
    monkeypatch.setattr("app.google_events.calendar_client", lambda: google_service)
    get = google_service.events.return_value.get
    original: Callable[..., Mock] = get.side_effect

    def request(*, calendarId: str, eventId: str) -> Mock:
        rpc = original(calendarId=calendarId, eventId=eventId)
        execute: Callable[..., dict[str, object]] = rpc.execute

        def call() -> dict[str, object]:
            barrier.wait(timeout=5)
            return execute()

        return Mock(execute=call)

    get.side_effect = request
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(
            executor.map(lambda _: traced_client.get("/events/test-event"), range(2))
        )
    assert all(response.status_code == 200 for response in responses)
    parents = [s for s in exporter.get_finished_spans() if s.kind == SpanKind.SERVER]
    assert len(parents) == 2
    ids = {s.context.trace_id for s in parents if s.context}
    assert len(ids) == 2
    for child in provider_spans(exporter):
        assert child.parent is not None and child.context is not None
        [parent] = [
            s
            for s in parents
            if s.context and s.context.trace_id == child.context.trace_id
        ]
        assert parent.context is not None
        assert child.parent.span_id == parent.context.span_id
    entries = [
        json.loads(r.getMessage())
        for r in caplog.records
        if r.name == "calendar_service"
    ]
    assert {entry["trace_id"] for entry in entries} == {
        trace.format_trace_id(value) for value in ids
    }
    assert_private_data_excluded(exporter)


def test_lifespan_drops_tracer_initialization_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        runtime, "create_tracer_provider", Mock(side_effect=RuntimeError("private"))
    )
    with TestClient(app) as test_client:
        response = test_client.get("/health")
        assert response.status_code == 200
        assert "X-Trace-ID" not in response.headers


@pytest.mark.parametrize("phase", ["start", "end"])
def test_processor_failure_does_not_change_or_repeat_google_write(
    exporter: InMemorySpanExporter,
    google_service: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    phase: str,
) -> None:
    class FailingProcessor(SpanProcessor):
        def on_start(self, span: trace.Span, parent_context: object = None) -> None:
            if phase == "start":
                raise RuntimeError("private-processor-error")

        def on_end(self, span: ReadableSpan) -> None:
            if phase == "end":
                raise RuntimeError("private-processor-error")

    original: Callable[[], TracerProvider] = getattr(runtime, "create_tracer_provider")

    def provider() -> TracerProvider:
        sdk = original()
        sdk.add_span_processor(FailingProcessor())
        return sdk

    monkeypatch.setattr(runtime, "create_tracer_provider", provider)
    with TestClient(app) as test_client:
        assert test_client.post("/events", json=PAYLOAD).status_code == 201
    google_service.events.return_value.insert.return_value.execute.assert_called_once_with(
        num_retries=0
    )
    assert_private_data_excluded(exporter)
