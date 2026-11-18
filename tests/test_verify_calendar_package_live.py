"""Verify live-check control flow with disposable, entirely local provider state."""

import json
import sys
from unittest.mock import MagicMock, Mock

import pytest
from calendar_contract import CalendarError, CreateEvent, ErrorCode, Event, ReplaceEvent

from scripts import verify_calendar_package_live as verification

MARKER = "controlled-package-verification"


class ControlledCalendar:
    def __init__(self, failure: str | None = None) -> None:
        self.failure = failure
        self.event: Event | None = None
        self.calls: list[str] = []
        self.reads = 0

    def create(self, request: CreateEvent) -> Event:
        self.calls.append("create")
        self.event = Event(id="controlled-id", **request.model_dump())
        if self.failure == "uncertain-create":
            raise CalendarError(ErrorCode.PROVIDER_ERROR, "PRIVATE create", False)
        return self.event

    def get(self, event_id: str) -> Event:
        self.calls.append("get")
        self.reads += 1
        if self.event is None:
            raise CalendarError(ErrorCode.NOT_FOUND, "Missing", False)
        assert event_id == self.event.id
        if self.reads == 1:
            if self.failure == "read":
                raise CalendarError(ErrorCode.PROVIDER_ERROR, "PRIVATE read", False)
            if self.failure == "wrong-read":
                return self.event.model_copy(update={"title": "Mismatched title"})
        return self.event

    def replace(self, event_id: str, request: ReplaceEvent) -> Event:
        self.calls.append("replace")
        assert self.event is not None and event_id == self.event.id
        if self.failure == "replace":
            raise CalendarError(ErrorCode.PROVIDER_ERROR, "PRIVATE replace", False)
        self.event = Event(id=event_id, **request.model_dump())
        return self.event

    def delete(self, event_id: str) -> None:
        self.calls.append("delete")
        if self.event is None:
            raise CalendarError(ErrorCode.NOT_FOUND, "Missing", False)
        assert event_id == self.event.id
        self.event = None
        if self.failure == "delete":
            raise CalendarError(ErrorCode.PROVIDER_ERROR, "PRIVATE delete", True)


def direct_google(service: ControlledCalendar) -> MagicMock:
    google = MagicMock()

    def listed(*, num_retries: int) -> dict[str, object]:
        assert num_retries == 0
        return {"items": [] if service.event is None else [{"id": service.event.id}]}

    def retrieved(*, num_retries: int) -> dict[str, object]:
        assert num_retries == 0
        assert service.event is not None
        event = service.event
        return {
            "id": event.id,
            "summary": event.title,
            "start": {"dateTime": event.start},
            "end": {"dateTime": event.end},
        }

    google.events.return_value.list.return_value.execute.side_effect = listed
    google.events.return_value.get.return_value.execute.side_effect = retrieved
    return google


@pytest.mark.parametrize(
    "failure", [None, "read", "replace", "wrong-read", "delete", "uncertain-create"]
)
def test_operation_and_cleanup_results_remain_accurate(
    failure: str | None, capsys: pytest.CaptureFixture[str]
) -> None:
    service = ControlledCalendar(failure)
    google = direct_google(service)

    assert verification.verify(service, google, MARKER) is (failure is None)
    assert service.calls.count("create") == 1
    rows = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    results = {row["step"]: row for row in rows}
    if failure == "uncertain-create":
        assert service.calls == ["create"]
        assert results["cleanup_id_known"]["inspect_marker_before_retry"] is True
        assert results["independent_google_cleanup"]["active_matches"] == 1
    else:
        assert service.calls.count("delete") == 2
        assert service.event is None
        assert results["independent_google_cleanup"]["passed"] is True
        assert results["read_after_delete"]["passed"] is True
        assert results["repeat_delete"]["passed"] is True
        if failure is not None:
            assert any(row["passed"] is False for row in rows)
    assert "PRIVATE" not in json.dumps(rows)
    assert "controlled-id" not in json.dumps(rows)


def test_existing_marker_prevents_any_create(
    capsys: pytest.CaptureFixture[str],
) -> None:
    service = ControlledCalendar()
    service.event = Event(
        id="existing-id",
        title=MARKER,
        start="2030-01-07T15:00:00Z",
        end="2030-01-07T15:30:00Z",
    )
    assert verification.verify(service, direct_google(service), MARKER) is False
    assert service.calls == []
    rows = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert rows == [{"step": "google_before", "passed": False}]


def test_marker_search_reads_every_google_page() -> None:
    google = MagicMock()
    google.events.return_value.list.return_value.execute.side_effect = [
        {"items": [{"id": "first"}], "nextPageToken": "next-page"},
        {"items": [{"id": "second"}]},
    ]
    assert verification.matching_events(google, MARKER) == 2
    calls = google.events.return_value.list.call_args_list
    assert [call.kwargs["pageToken"] for call in calls] == [None, "next-page"]
    assert all(call.kwargs["q"] == MARKER for call in calls)
    assert all(call.kwargs["showDeleted"] is False for call in calls)


def test_live_writes_require_explicit_opt_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "argv", ["verify", "--token-file", "/unused/token.json"])
    factory = Mock(side_effect=AssertionError("Flag guard must precede setup"))
    monkeypatch.setattr(verification, "create_calendar_service", factory)
    with pytest.raises(SystemExit) as caught:
        verification.main()
    assert caught.value.code == 2
    factory.assert_not_called()
