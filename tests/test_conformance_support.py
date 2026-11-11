from unittest.mock import Mock

import httpx
import pytest
from calendar_contract import CalendarError, CreateEvent, ErrorCode, Event
from calendar_contract.conformance import CREATE

from tests.conformance_support import (
    HttpCalendarService,
    SafeConformanceCleanup,
    cleanup_events,
    create_missing_event,
)


def test_cleanup_attempts_all_ids_after_provider_and_unexpected_failures() -> None:
    service = Mock()
    service.delete.side_effect = [
        CalendarError(ErrorCode.PROVIDER_UNAVAILABLE, "private-provider-error", True),
        RuntimeError("private-unexpected-error"),
        None,
    ]
    with pytest.raises(RuntimeError, match="cleanup failed for 2 event") as error:
        cleanup_events(service, ["first", "second", "third"])
    assert service.delete.call_count == 3
    assert "private" not in str(error.value)
    assert service.delete.call_args_list[-1].args == ("third",)


def test_cleanup_ignores_already_deleted_events_and_deduplicates() -> None:
    service = Mock()
    service.delete.side_effect = [
        CalendarError(ErrorCode.NOT_FOUND, "gone", False),
        None,
    ]
    cleanup_events(service, ["gone", "gone", "remaining"])
    assert service.delete.call_count == 2


def test_missing_fixture_registers_event_before_initial_delete_fails() -> None:
    service = Mock()
    service.create.return_value = Event(id="owned-event", **CREATE)
    service.delete.side_effect = [RuntimeError("temporary failure"), None]
    event_ids: list[str] = []
    with pytest.raises(RuntimeError, match="temporary failure"):
        create_missing_event(service, event_ids)
    assert event_ids == ["owned-event"]
    cleanup_events(service, event_ids)
    assert service.delete.call_count == 2


def test_http_bridge_keeps_id_for_cleanup_when_event_shape_is_invalid() -> None:
    requests: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request.method)
        if request.method == "POST":
            return httpx.Response(201, json={"id": "owned-event"})
        return httpx.Response(204)

    with httpx.Client(
        base_url="https://calendar.example", transport=httpx.MockTransport(respond)
    ) as client:
        service = HttpCalendarService(client)
        with pytest.raises(RuntimeError, match="invalid Event"):
            service.create(CreateEvent(**CREATE))
        cleanup_events(service, service.created_ids)
    assert requests == ["POST", "DELETE"]


def test_http_bridge_does_not_retry_uncertain_creation() -> None:
    requests: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request.method)
        raise httpx.ReadTimeout("private-transport-detail")

    with httpx.Client(
        base_url="https://calendar.example", transport=httpx.MockTransport(respond)
    ) as client:
        with pytest.raises(RuntimeError, match="do not retry") as error:
            HttpCalendarService(client).create(CreateEvent(**CREATE))
    assert requests == ["POST"]
    assert "private" not in str(error.value)


def test_http_bridge_requires_boolean_retry_advice() -> None:
    with httpx.Client(
        base_url="https://calendar.example",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                404,
                json={"error": {"code": "not_found", "retryable": "false"}},
            )
        ),
    ) as client:
        with pytest.raises(RuntimeError, match="unexpected HTTP 404"):
            HttpCalendarService(client).get("missing")


def test_changed_start_check_detects_an_ignored_update() -> None:
    event = Event(id="owned-event", **CREATE)
    service = Mock()
    service.replace.return_value = event
    service.get.return_value = event
    with pytest.raises(AssertionError):
        SafeConformanceCleanup().test_replace_changes_start_instant(service, event)
