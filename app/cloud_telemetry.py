"""Opt-in OTLP export using the runtime identity, never Calendar credentials."""

import logging
import os
import re
from uuid import uuid4

import google.auth
from google.auth.transport.requests import AuthorizedSession
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.metrics import NoOpMeterProvider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.metrics.view import View
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app.tracing import SERVICE, release_identity


class SafeTelemetryLog(logging.Filter):
    """SDK errors must not print remote responses, headers, or exceptions."""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args if isinstance(record.args, tuple) else ()
        signal = next(
            (
                value
                for value in args
                if isinstance(value, str) and value in {"spans", "metrics"}
            ),
            "unknown",
        )
        status = next(
            (value for value in args if type(value) is int and 400 <= value < 600), None
        )
        cause = next(
            (type(value).__name__ for value in args if isinstance(value, Exception)),
            "unknown",
        )
        record.msg = (
            f"Telemetry export unavailable; signal={signal}, status={status}, "
            f"cause={cause}; observations may be dropped."
        )
        record.args = ()
        record.exc_info = None
        record.exc_text = None
        record.stack_info = None
        return True


def cloud_project() -> str | None:
    value = os.getenv("CALENDAR_TELEMETRY_PROJECT", "")
    return value if re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]", value) else None


def cloud_resource() -> Resource:
    environment = os.getenv("CALENDAR_ENV", "local")
    if environment not in {"demo", "verify"}:
        environment = "local"
    return Resource(
        {
            "service.name": SERVICE,
            "service.namespace": environment,
            "service.version": release_identity(),
            # Separate cumulative streams after an instance/process restart.
            "service.instance.id": uuid4().hex,
            "cloud.region": "us-central1",
            "gcp.project_id": cloud_project() or "",
        }
    )


def authorized_session(project: str) -> AuthorizedSession:
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
        quota_project_id=project,
    )
    return AuthorizedSession(  # type: ignore[no-untyped-call]
        credentials, max_refresh_attempts=0, refresh_timeout=3
    )


def configure_cloud(provider: TracerProvider) -> MeterProvider | None:
    """Export in SDK worker threads; local runs never discover cloud credentials."""
    project = cloud_project()
    if project is None:
        return None
    for name in (
        "opentelemetry.exporter.otlp.proto.http.trace_exporter",
        "opentelemetry.exporter.otlp.proto.http.metric_exporter",
        "opentelemetry.exporter.otlp.common.http",
        "opentelemetry.exporter.otlp.proto.http._common",
        "opentelemetry.sdk._shared_internal",
        "opentelemetry.sdk.metrics._internal.export",
    ):
        logger = logging.getLogger(name)
        if not any(isinstance(f, SafeTelemetryLog) for f in logger.filters):
            logger.addFilter(SafeTelemetryLog())
    trace_exporter = OTLPSpanExporter(
        endpoint="https://telemetry.googleapis.com/v1/traces",
        session=authorized_session(project),
        headers={},
        timeout=3,
        max_request_size=262144,
        meter_provider=NoOpMeterProvider(),
    )
    processor = BatchSpanProcessor(
        trace_exporter,
        max_queue_size=512,
        max_export_batch_size=64,
        schedule_delay_millis=1000,
        export_timeout_millis=3000,
    )
    reader = None
    try:
        metric_exporter = OTLPMetricExporter(
            endpoint="https://telemetry.googleapis.com/v1/metrics",
            session=authorized_session(project),
            headers={},
            timeout=3,
            max_export_batch_size=256,
            max_request_size=262144,
            meter_provider=NoOpMeterProvider(),
        )
        reader = PeriodicExportingMetricReader(
            metric_exporter, export_interval_millis=30000, export_timeout_millis=3000
        )
        metrics = MeterProvider(
            resource=cloud_resource(),
            metric_readers=[reader],
            views=[
                View(
                    instrument_name="calendar.*",
                    attribute_keys={
                        "operation",
                        "outcome",
                        "failure_source",
                        "http.response.status_code",
                        "release",
                        "environment",
                    },
                )
            ],
            shutdown_on_exit=False,
        )
        provider.add_span_processor(processor)
        return metrics
    except Exception:
        processor.shutdown()  # type: ignore[no-untyped-call]
        if reader is not None:
            reader.shutdown(timeout_millis=3000)
        raise
