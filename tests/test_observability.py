"""Check request outcomes with real SDK aggregation and controlled operations."""

import json
import logging
import re
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from typing import cast
from unittest.mock import Mock

import pytest
from calendar_contract import CalendarError, CalendarService, ErrorCode, Event
from fastapi import FastAPI
from fastapi.testclient import TestClient
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    Histogram,
    HistogramDataPoint,
    InMemoryMetricReader,
    NumberDataPoint,
    Sum,
)

from app import observability, runtime
from app.calendar_service_dependencies import get_calendar_service
from app.main import app
from app.observability import RequestMetrics, RequestTelemetryMiddleware
from app.runtime import require_hosted_access

PAYLOAD = {
    "title": "private-title",
    "start": "2030-01-07T15:00:00Z",
    "end": "2030-01-07T15:30:00Z",
}
ROUTES = [
    ("POST", "/events", "create", 201),
    ("GET", "/events/private-event-id", "get", 200),
    ("PUT", "/events/private-event-id", "replace", 200),
    ("DELETE", "/events/private-event-id", "delete", 204),
    ("PATCH", "/events/private-event-id", "patch", 200),
]


@pytest.fixture
def observed(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[TestClient, Mock, InMemoryMetricReader, RequestMetrics]]:
    monkeypatch.setenv("CALENDAR_RELEASE", "a" * 40)
    reader = InMemoryMetricReader()
    provider = MeterProvider(metric_readers=[reader])
    request_metrics = RequestMetrics(provider.get_meter("test.calendar.requests"))
    service = Mock(spec=CalendarService)
    for operation in (service.create, service.get, service.replace):
        operation.return_value = Event(id="private-event-id", **PAYLOAD)
    test_app = FastAPI()
    test_app.include_router(app.router)
    for exception, handler in app.exception_handlers.items():
        test_app.add_exception_handler(exception, handler)
    test_app.dependency_overrides[get_calendar_service] = lambda: service
    test_app.middleware("http")(require_hosted_access)
    test_app.add_middleware(RequestTelemetryMiddleware, request_metrics=request_metrics)
    try:
        with TestClient(test_app, raise_server_exceptions=False) as client:
            yield client, service, reader, request_metrics
    finally:
        provider.shutdown()


def points(
    reader: InMemoryMetricReader, name: str
) -> list[NumberDataPoint | HistogramDataPoint]:
    data = reader.get_metrics_data()
    if data is None:
        return []
    result: list[NumberDataPoint | HistogramDataPoint] = []
    for resource in data.resource_metrics:
        for scope in resource.scope_metrics:
            for metric in scope.metrics:
                if metric.name == name:
                    assert isinstance(metric.data, Sum | Histogram)
                    result.extend(metric.data.data_points)
    return result


def logs(caplog: pytest.LogCaptureFixture) -> list[dict[str, object]]:
    return [
        json.loads(record.getMessage())
        for record in caplog.records
        if record.name == "calendar_service"
    ]


@pytest.mark.parametrize(("method", "path", "operation", "status"), ROUTES)
def test_success_has_one_correlated_log_counter_and_histogram(
    observed: tuple[TestClient, Mock, InMemoryMetricReader, RequestMetrics],
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    path: str,
    operation: str,
    status: int,
) -> None:
    client, _, reader, _ = observed
    clock = iter([10.0, 10.25])
    monkeypatch.setattr(observability, "perf_counter", lambda: next(clock))
    response = client.request(
        method,
        path,
        json=PAYLOAD if method in {"POST", "PUT", "PATCH"} else None,
        headers={
            "Authorization": "Bearer private-token",
            "X-Request-ID": "private-untrusted-request-id",
        },
    )
    assert response.status_code == status
    [entry] = logs(caplog)
    assert entry["service"] == "calendar-team-5"
    assert entry["release"] == "a" * 40
    assert entry["contract_operation"] == operation
    assert entry["outcome"] == "success"
    assert entry["error"] is None
    assert entry["failure_source"] == "none"
    assert entry["status"] == status
    assert entry["duration_ms"] == 250.0
    assert entry["request_id"] == response.headers["X-Request-ID"]
    assert re.fullmatch(r"[0-9a-f]{32}", str(entry["request_id"]))
    [count] = points(reader, "calendar.requests")
    assert isinstance(count, NumberDataPoint) and count.value == 1
    assert count.attributes == {
        "operation": operation,
        "outcome": "success",
        "failure_source": "none",
        "http.response.status_code": status,
    }
    [duration] = points(reader, "calendar.request.duration")
    assert isinstance(duration, HistogramDataPoint)
    assert duration.count == 1 and duration.sum == 0.25
    assert sum(duration.bucket_counts) == 1
    assert points(reader, "calendar.request.errors") == []
    assert "private" not in json.dumps(entry) + str(count.attributes)


@pytest.mark.parametrize("method,path,operation,success", ROUTES[:4])
@pytest.mark.parametrize(
    "code,status,source",
    [
        (ErrorCode.INVALID_INPUT, 422, "caller"),
        (ErrorCode.NOT_FOUND, 404, "caller"),
        (ErrorCode.ACCESS_DENIED, 403, "provider"),
        (ErrorCode.PROVIDER_ERROR, 502, "provider"),
        (ErrorCode.PROVIDER_UNAVAILABLE, 503, "provider"),
    ],
)
def test_shared_error_categories_are_counted_once_without_details(
    observed: tuple[TestClient, Mock, InMemoryMetricReader, RequestMetrics],
    caplog: pytest.LogCaptureFixture,
    method: str,
    path: str,
    operation: str,
    success: int,
    status: int,
    code: ErrorCode,
    source: str,
) -> None:
    client, service, reader, _ = observed
    getattr(service, operation).side_effect = CalendarError(
        code, "Operation failed.", False, details={"provider": True, "raw": "private"}
    )
    response = client.request(
        method, path, json=PAYLOAD if method in {"POST", "PUT"} else None
    )
    assert response.status_code == status
    assert response.json()["error"]["code"] == code.value
    [entry] = logs(caplog)
    assert entry["outcome"] == code.value
    assert entry["failure_source"] == source
    assert entry["provider"] is True
    [count] = points(reader, "calendar.requests")
    [error] = points(reader, "calendar.request.errors")
    assert isinstance(count, NumberDataPoint) and count.value == 1
    assert isinstance(error, NumberDataPoint) and error.value == 1
    assert error.attributes is not None
    assert error.attributes["outcome"] == code.value
    assert error.attributes["failure_source"] == source
    assert getattr(service, operation).call_count == 1
    assert "private" not in json.dumps(entry)


@pytest.mark.parametrize("body,status", [('{"title":', 400), ("{}", 422)])
def test_validation_failure_is_observed_before_provider_work(
    observed: tuple[TestClient, Mock, InMemoryMetricReader, RequestMetrics],
    caplog: pytest.LogCaptureFixture,
    body: str,
    status: int,
) -> None:
    client, service, reader, _ = observed
    assert (
        client.post(
            "/events", content=body, headers={"Content-Type": "application/json"}
        ).status_code
        == status
    )
    service.create.assert_not_called()
    [entry] = logs(caplog)
    assert entry["contract_operation"] == "create"
    assert entry["outcome"] == "invalid_input"
    assert entry["failure_source"] == "caller"
    [error] = points(reader, "calendar.request.errors")
    assert isinstance(error, NumberDataPoint) and error.value == 1


def test_unexpected_exception_is_sanitized_and_not_retried(
    observed: tuple[TestClient, Mock, InMemoryMetricReader, RequestMetrics],
    caplog: pytest.LogCaptureFixture,
) -> None:
    client, service, reader, _ = observed
    service.get.side_effect = RuntimeError("private-provider-data")
    assert client.get("/events/private-id").status_code == 500
    service.get.assert_called_once()
    [entry] = logs(caplog)
    assert entry["outcome"] == "internal_error"
    assert entry["failure_source"] == "service"
    assert entry["status"] == 500
    assert "private" not in json.dumps(entry)
    [error] = points(reader, "calendar.request.errors")
    assert isinstance(error, NumberDataPoint) and error.value == 1
    [record] = [r for r in caplog.records if r.name == "calendar_service"]
    assert record.levelno == logging.ERROR and record.exc_info is None


def test_success_and_failure_latencies_are_separate_distributions(
    observed: tuple[TestClient, Mock, InMemoryMetricReader, RequestMetrics],
) -> None:
    client, service, reader, _ = observed
    assert client.get("/events/first-private-id").status_code == 200
    service.get.side_effect = CalendarError(
        ErrorCode.PROVIDER_UNAVAILABLE, "Unavailable.", True
    )
    assert client.get("/events/second-private-id").status_code == 503
    durations = points(reader, "calendar.request.duration")
    assert len(durations) == 2
    assert {point.attributes["outcome"] for point in durations if point.attributes} == {
        "success",
        "provider_unavailable",
    }
    assert all(
        isinstance(point, HistogramDataPoint) and point.count == 1
        for point in durations
    )


@pytest.mark.parametrize("failure", ["metrics", "logging"])
def test_telemetry_failure_does_not_change_or_repeat_operation(
    observed: tuple[TestClient, Mock, InMemoryMetricReader, RequestMetrics],
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    client, service, _, request_metrics = observed
    failing = Mock(side_effect=RuntimeError("private-telemetry-error"))
    if failure == "metrics":
        monkeypatch.setattr(request_metrics, "record", failing)
    else:
        monkeypatch.setattr(observability.logger, "log", failing)
    assert client.post("/events", json=PAYLOAD).status_code == 201
    service.create.assert_called_once()
    failing.assert_called_once()


def test_distinct_ids_and_headers_do_not_create_distinct_metric_series(
    observed: tuple[TestClient, Mock, InMemoryMetricReader, RequestMetrics],
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _, reader, _ = observed
    monkeypatch.setenv("CALENDAR_RELEASE", "private-untrusted-config")
    for index in range(10):
        assert client.get(f"/events/private-{index}?secret=private").status_code == 200
    [count] = points(reader, "calendar.requests")
    assert isinstance(count, NumberDataPoint) and count.value == 10
    entries = logs(caplog)
    assert len({entry["request_id"] for entry in entries}) == 10
    assert all(entry["release"] == "local" for entry in entries)
    assert "private" not in json.dumps(entries) + str(count.attributes)


def test_authentication_rejection_is_observed_before_routing(
    observed: tuple[TestClient, Mock, InMemoryMetricReader, RequestMetrics],
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, service, reader, _ = observed
    monkeypatch.setattr(runtime, "hosted", lambda: True)
    cast(FastAPI, client.app).state.demo_bearer = b"private-expected-bearer"
    response = client.post("/events", json=PAYLOAD)
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    service.create.assert_not_called()
    [entry] = logs(caplog)
    assert entry["contract_operation"] == "create"
    assert entry["outcome"] == "access_denied"
    assert entry["failure_source"] == "caller"
    [error] = points(reader, "calendar.request.errors")
    assert isinstance(error, NumberDataPoint) and error.value == 1


def test_unknown_paths_use_one_bounded_operation_label(
    observed: tuple[TestClient, Mock, InMemoryMetricReader, RequestMetrics],
) -> None:
    client, _, reader, _ = observed
    for index in range(5):
        assert client.get(f"/private-unknown-{index}").status_code == 404
    [count] = points(reader, "calendar.requests")
    assert isinstance(count, NumberDataPoint) and count.value == 5
    assert count.attributes is not None
    assert count.attributes["operation"] == "http_other"


def test_response_validation_error_is_not_recorded_as_success(
    observed: tuple[TestClient, Mock, InMemoryMetricReader, RequestMetrics],
    caplog: pytest.LogCaptureFixture,
) -> None:
    client, service, reader, _ = observed
    service.get.return_value = {"id": "private-invalid-response"}
    assert client.get("/events/private-id").status_code == 500
    [entry] = logs(caplog)
    assert entry["outcome"] == "internal_error"
    [error] = points(reader, "calendar.request.errors")
    assert isinstance(error, NumberDataPoint) and error.value == 1
    assert "private" not in json.dumps(entry)


def test_concurrent_requests_keep_error_context_and_ids_separate(
    observed: tuple[TestClient, Mock, InMemoryMetricReader, RequestMetrics],
    caplog: pytest.LogCaptureFixture,
) -> None:
    client, service, reader, _ = observed
    barrier = Barrier(2)

    def get(event_id: str) -> Event:
        barrier.wait(timeout=5)
        if event_id == "private-failing-id":
            raise CalendarError(ErrorCode.PROVIDER_UNAVAILABLE, "Unavailable.", True)
        return Event(id=event_id, **PAYLOAD)

    service.get.side_effect = get
    with ThreadPoolExecutor(max_workers=2) as executor:
        successful = executor.submit(client.get, "/events/private-success-id")
        failing = executor.submit(client.get, "/events/private-failing-id")
        assert successful.result(timeout=10).status_code == 200
        assert failing.result(timeout=10).status_code == 503
    entries = logs(caplog)
    assert len(entries) == 2
    assert len({entry["request_id"] for entry in entries}) == 2
    assert {entry["outcome"] for entry in entries} == {
        "success",
        "provider_unavailable",
    }
    counts = points(reader, "calendar.requests")
    assert len(counts) == 2
    assert all(
        isinstance(point, NumberDataPoint) and point.value == 1 for point in counts
    )
    [error] = points(reader, "calendar.request.errors")
    assert isinstance(error, NumberDataPoint) and error.value == 1
    assert "private" not in json.dumps(entries)
