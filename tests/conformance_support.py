"""Test-only HTTP bridge and cleanup for the tagged conformance suite."""

from collections.abc import Iterator
from datetime import datetime
from urllib.parse import quote

import httpx
import pytest
from calendar_contract import (
    CalendarError,
    CalendarService,
    CreateEvent,
    ErrorCode,
    Event,
    ReplaceEvent,
)
from calendar_contract.conformance import CREATE


def cleanup_events(service: CalendarService, event_ids: list[str]) -> None:
    failures = 0
    for event_id in dict.fromkeys(event_ids):
        try:
            service.delete(event_id)
        except CalendarError as error:
            failures += error.code != ErrorCode.NOT_FOUND
        except Exception:
            failures += 1
    if failures:
        raise RuntimeError(f"Conformance cleanup failed for {failures} event(s).")


def create_missing_event(service: CalendarService, event_ids: list[str]) -> str:
    event = service.create(CreateEvent(**CREATE))
    event_ids.append(event.id)
    service.delete(event.id)
    return event.id


class SafeConformanceCleanup:
    @pytest.fixture
    def created_ids(self, service: CalendarService) -> Iterator[list[str]]:
        event_ids: list[str] = []
        yield event_ids
        cleanup_events(service, event_ids)

    @pytest.fixture
    def missing_id(self, service: CalendarService, created_ids: list[str]) -> str:
        return create_missing_event(service, created_ids)

    def test_replace_changes_start_instant(
        self, service: CalendarService, created: Event
    ) -> None:
        replacement = ReplaceEvent(
            title=created.title,
            start="2030-01-07T18:00:00Z",
            end="2030-01-07T18:30:00Z",
        )
        result = service.replace(created.id, replacement)
        fetched = service.get(created.id)
        assert result.id == created.id
        assert fetched.id == created.id
        for event in (result, fetched):
            assert datetime.fromisoformat(event.start) == datetime.fromisoformat(
                replacement.start
            )
            assert datetime.fromisoformat(event.end) == datetime.fromisoformat(
                replacement.end
            )


class HttpCalendarService:
    def __init__(self, client: httpx.Client) -> None:
        self.client = client
        self.created_ids: list[str] = []

    def request(
        self, method: str, path: str, expected: int, body: dict[str, str] | None = None
    ) -> httpx.Response:
        try:
            response = self.client.request(method, path, json=body)
        except httpx.HTTPError:
            raise RuntimeError(
                f"Conformance {method} transport failed; do not retry uncertain writes."
            ) from None
        if method == "POST":
            known_id = False
            try:
                event_id = response.json().get("id")
                if isinstance(event_id, str) and event_id:
                    self.created_ids.append(event_id)
                    known_id = True
            except ValueError, AttributeError:
                pass
            if not known_id and (
                200 <= response.status_code < 300 or response.status_code >= 500
            ):
                raise RuntimeError(
                    "Uncertain creation without an ID; inspect the test calendar."
                )
        if response.status_code == expected:
            return response
        try:
            error = response.json()["error"]
            code = ErrorCode(error["code"])
            retryable = error["retryable"]
            if not isinstance(retryable, bool):
                raise ValueError
        except ValueError, KeyError, TypeError:
            raise RuntimeError(
                f"Conformance {method} returned unexpected HTTP {response.status_code}."
            ) from None
        raise CalendarError(code, "HTTP conformance operation failed.", retryable)

    @staticmethod
    def event(response: httpx.Response) -> Event:
        try:
            return Event.model_validate(response.json())
        except ValueError:
            raise RuntimeError("HTTP conformance returned an invalid Event.") from None

    def create(self, request: CreateEvent) -> Event:
        return self.event(self.request("POST", "/events", 201, request.model_dump()))

    def get(self, event_id: str) -> Event:
        return self.event(
            self.request("GET", f"/events/{quote(event_id, safe='')}", 200)
        )

    def replace(self, event_id: str, request: ReplaceEvent) -> Event:
        return self.event(
            self.request(
                "PUT", f"/events/{quote(event_id, safe='')}", 200, request.model_dump()
            )
        )

    def delete(self, event_id: str) -> None:
        response = self.request("DELETE", f"/events/{quote(event_id, safe='')}", 204)
        if response.content:
            raise RuntimeError("DELETE 204 must have an empty body.")


class HttpInputConformance:
    @pytest.mark.parametrize("method", ["POST", "PUT"])
    @pytest.mark.parametrize(
        "body",
        [
            {**CREATE, "location": "Room 101"},
            {"title": CREATE["title"], "start": CREATE["start"]},
            {
                "title": CREATE["title"],
                "start_time": CREATE["start"],
                "end_time": CREATE["end"],
            },
        ],
        ids=["unknown-field", "missing-field", "legacy-fields"],
    )
    def test_http_rejects_invalid_json_fields(
        self, service: HttpCalendarService, method: str, body: dict[str, str]
    ) -> None:
        path = "/events" if method == "POST" else "/events/conformance-missing"
        response = service.request(method, path, 422, body)
        assert response.json()["error"]["code"] == "invalid_input"
        assert response.json()["error"]["retryable"] is False

    @pytest.mark.parametrize("body", [b"", b"{"])
    def test_http_rejects_malformed_json(
        self, service: HttpCalendarService, body: bytes
    ) -> None:
        response = service.client.post(
            "/events", content=body, headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "invalid_input"
