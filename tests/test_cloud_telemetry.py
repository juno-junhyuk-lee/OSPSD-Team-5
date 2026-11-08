"""Exercise SDK/OTLP lifecycle, wire payloads, and unavailable-backend behavior."""

import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from typing import Any, cast
from unittest.mock import Mock

import google.auth
import pytest
from fastapi.testclient import TestClient
from google.auth.transport.requests import AuthorizedSession
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import (
    ExportMetricsServiceRequest,
)
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
)
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import Histogram, InMemoryMetricReader
from opentelemetry.sdk.trace import TracerProvider
from requests import Response

from app import cloud_telemetry, runtime
from app.main import app
from app.observability import RequestMetrics


def test_local_lifespan_never_discovers_cloud_credentials(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    monkeypatch.delenv("CALENDAR_TELEMETRY_PROJECT", raising=False)
    adc = Mock(side_effect=AssertionError("Local tests must remain offline"))
    monkeypatch.setattr(google.auth, "default", adc)
    assert cloud_telemetry.configure_cloud(TracerProvider()) is None
    assert client.get("/health").status_code == 200
    adc.assert_not_called()


def test_actual_otlp_payloads_and_log_trace_correlation(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("CALENDAR_TELEMETRY_PROJECT", "ospsd-team5")
    monkeypatch.setenv("CALENDAR_ENV", "verify")
    monkeypatch.setenv("CALENDAR_RELEASE", "b" * 40)
    frames: list[tuple[str, bytes]] = []
    sessions: list[Mock] = []

    def session(project: str) -> AuthorizedSession:
        assert project == "ospsd-team5"
        value = Mock(spec=AuthorizedSession)

        def request(**kwargs: Any) -> Response:
            assert kwargs["timeout"] <= 3
            assert kwargs["allow_redirects"] is False
            frames.append((kwargs["url"], kwargs["data"]))
            response = Response()
            response.status_code = 200
            response._content = b""
            return response

        value.request.side_effect = request
        sessions.append(value)
        return cast(AuthorizedSession, value)

    monkeypatch.setattr(cloud_telemetry, "authorized_session", session)
    with TestClient(app) as client:
        response = client.post(
            "/events",
            json={"title": "sensitive-provider-title"},
            headers={"Authorization": "Bearer sensitive-token"},
        )
        assert response.status_code == 422
        assert app.state.request_metrics is not None
        trace_id = response.headers["X-Trace-ID"]
    assert frames and all(s.close.called for s in sessions)
    trace_frame = next(data for url, data in frames if url.endswith("/v1/traces"))
    metric_frame = next(data for url, data in frames if url.endswith("/v1/metrics"))
    traces = ExportTraceServiceRequest.FromString(trace_frame)
    assert any(
        a.key == "gcp.project_id" and a.value.string_value == "ospsd-team5"
        for r in traces.resource_spans
        for a in r.resource.attributes
    )
    spans = [
        s for r in traces.resource_spans for scope in r.scope_spans for s in scope.spans
    ]
    assert len(spans) == 1
    assert spans[0].trace_id.hex() == trace_id
    assert spans[0].name == "calendar.create"
    metrics = ExportMetricsServiceRequest.FromString(metric_frame)
    assert any(
        a.key == "gcp.project_id" and a.value.string_value == "ospsd-team5"
        for r in metrics.resource_metrics
        for a in r.resource.attributes
    )
    names = {
        m.name
        for r in metrics.resource_metrics
        for scope in r.scope_metrics
        for m in scope.metrics
    }
    assert {
        "calendar.requests",
        "calendar.request.errors",
        "calendar.request.duration",
        "calendar.request.saturation",
    } <= names
    exported = str(traces) + str(metrics)
    assert "b" * 40 in exported
    assert "sensitive-provider-title" not in exported
    assert "sensitive-token" not in exported
    [entry] = [
        json.loads(r.getMessage())
        for r in caplog.records
        if r.name == "calendar_service"
    ]
    assert (
        entry["logging.googleapis.com/trace"]
        == f"projects/ospsd-team5/traces/{trace_id}"
    )
    assert entry["logging.googleapis.com/spanId"] == spans[0].span_id.hex()
    assert entry["severity"] == "WARNING"


def test_export_cannot_block_or_retry_an_http_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CALENDAR_TELEMETRY_PROJECT", "ospsd-team5")
    blocked = Event()
    release = Event()
    original = OTLPSpanExporter

    def exporter(**kwargs: Any) -> Any:
        value = original(**kwargs)

        def export(*args: Any, **options: Any) -> Any:
            blocked.set()
            assert release.wait(5)
            raise RuntimeError("sensitive-exporter-exception")

        monkeypatch.setattr(value, "export", export)
        return value

    monkeypatch.setattr(cloud_telemetry, "OTLPSpanExporter", exporter)
    monkeypatch.setattr(cloud_telemetry, "authorized_session", lambda _: Mock())
    try:
        with TestClient(app) as client:
            assert client.get("/health").status_code == 200
            assert blocked.wait(3)
            # The worker is still blocked; the next API call must finish.
            assert client.get("/ready").status_code == 204
            release.set()
    finally:
        release.set()


def test_cloud_startup_failure_preserves_http_behavior(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        runtime, "configure_cloud", Mock(side_effect=RuntimeError("private"))
    )
    with TestClient(app) as client:
        assert client.post("/events", json={}).status_code == 422
        assert client.get("/health").status_code == 200


def test_saturation_measures_parallel_work_and_releases_capacity() -> None:
    reader = InMemoryMetricReader()
    provider = MeterProvider(metric_readers=[reader])
    metrics = RequestMetrics(provider.get_meter("test"))
    barrier = Barrier(2)

    def request(operation: str) -> None:
        assert metrics.enter(operation)
        barrier.wait(timeout=3)
        metrics.leave()

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(request, ["create", "get"]))
        assert metrics.active == 0
        assert not metrics.enter("health")
        assert metrics.active == 0
        data = reader.get_metrics_data()
        assert data is not None
        points = [
            p
            for r in data.resource_metrics
            for s in r.scope_metrics
            for m in s.metrics
            if m.name == "calendar.request.saturation"
            if isinstance(m.data, Histogram)
            for p in m.data.data_points
        ]
        assert sorted(p.max for p in points) == [1, 2]
        assert {p.attributes["operation"] for p in points if p.attributes} == {
            "create",
            "get",
        }
    finally:
        provider.shutdown()


def test_exporter_diagnostics_cannot_leak_exceptions(
    caplog: pytest.LogCaptureFixture,
) -> None:
    import logging

    logger = logging.getLogger("test.telemetry.safety")
    sanitizer = cloud_telemetry.SafeTelemetryLog()
    logger.addFilter(sanitizer)
    try:
        try:
            raise RuntimeError("private-refresh-token")
        except RuntimeError:
            logger.exception("private-response %s", "private-secret")
        assert "private" not in caplog.text
        assert "observations may be dropped" in caplog.text
    finally:
        logger.removeFilter(sanitizer)
