"""Reusable conformance tests for implementations of `CalendarService`.

Subclass `CalendarServiceConformance` in a test module and override the
fixtures that supply the implementation under test:

```python
class TestMyCalendar(CalendarServiceConformance):
    @pytest.fixture
    def service(self) -> CalendarService:
        return MyCalendarService()

    @pytest.fixture
    def access_denied_service(self) -> CalendarService:
        return MyCalendarService.with_access_denied()

    @pytest.fixture
    def provider_error_service(self) -> CalendarService:
        return MyCalendarService.with_provider_error()

    @pytest.fixture
    def provider_unavailable_service(self) -> CalendarService:
        return MyCalendarService.with_provider_unavailable()

    @pytest.fixture
    def uncertain_write_service(self) -> CalendarService:
        return MyCalendarService.with_uncertain_write()
```

The four failure fixtures are test-only substitution points. They must return
ordinary `CalendarService` objects configured to fail; do not add test-control
methods to the production protocol.

Every event a success-path test creates is deleted afterward.
"""

from collections.abc import Iterator
from datetime import datetime

import pytest
from pydantic import ValidationError

from calendar_contract.errors import CalendarError, ErrorCode
from calendar_contract.event import Event
from calendar_contract.requests import CreateEvent, ReplaceEvent
from calendar_contract.service import CalendarService

CREATE = {
    "title": "Conformance event",
    "start": "2030-01-07T15:00:00Z",
    "end": "2030-01-07T15:30:00Z",
}
REPLACE = {
    "title": "Conformance event (replaced)",
    "start": "2030-01-07T16:00:00+01:00",
    "end": "2030-01-07T17:00:00+01:00",
}


def same_instant(actual: str, expected: str) -> bool:
    """Return whether timestamps `actual` and `expected` name the same instant."""
    return datetime.fromisoformat(actual) == datetime.fromisoformat(expected)


def assert_event_matches(event: Event, fields: dict[str, str]) -> None:
    """Assert that `event` has a non-empty `id` and the shared `fields`."""
    assert event.id
    assert event.title == fields["title"]
    assert same_instant(event.start, fields["start"])
    assert same_instant(event.end, fields["end"])


def assert_calendar_error(
    error: pytest.ExceptionInfo[CalendarError],
    code: ErrorCode,
    *,
    retryable: bool,
) -> None:
    """Assert that the raised `error` has the expected code and retryability."""
    assert error.value.code == code
    assert error.value.retryable is retryable


def assert_not_found(error: pytest.ExceptionInfo[CalendarError]) -> None:
    """Assert that the raised `error` is a non-retryable `not_found` failure."""
    assert_calendar_error(error, ErrorCode.NOT_FOUND, retryable=False)


class CalendarServiceConformance:
    """Shared behavior every `CalendarService` implementation must show."""

    @pytest.fixture
    def service(self) -> CalendarService:
        """Return the implementation under test; subclasses must override this."""
        raise NotImplementedError("override the `service` fixture")

    @pytest.fixture
    def access_denied_service(self) -> CalendarService:
        """Return a service whose create raises non-retryable ACCESS_DENIED."""
        raise NotImplementedError("override the `access_denied_service` fixture")

    @pytest.fixture
    def provider_error_service(self) -> CalendarService:
        """Return a service whose create raises non-retryable PROVIDER_ERROR."""
        raise NotImplementedError("override the `provider_error_service` fixture")

    @pytest.fixture
    def provider_unavailable_service(self) -> CalendarService:
        """Return a service whose create raises retryable PROVIDER_UNAVAILABLE."""
        raise NotImplementedError("override the `provider_unavailable_service` fixture")

    @pytest.fixture
    def uncertain_write_service(self) -> CalendarService:
        """Return a service whose create raises PROVIDER_ERROR with retryable=False."""
        raise NotImplementedError("override the `uncertain_write_service` fixture")

    @pytest.fixture
    def created_ids(self, service: CalendarService) -> Iterator[list[str]]:
        """Collect created event IDs and delete any that still exist afterward."""
        ids: list[str] = []
        yield ids
        for event_id in ids:
            try:
                service.delete(event_id)
            except CalendarError as error:
                if error.code != ErrorCode.NOT_FOUND:
                    raise

    @pytest.fixture
    def created(self, service: CalendarService, created_ids: list[str]) -> Event:
        """Create one event from `CREATE` for the test and return it."""
        event = service.create(CreateEvent(**CREATE))
        created_ids.append(event.id)
        return event

    @pytest.fixture
    def missing_id(self, service: CalendarService) -> str:
        """Return the ID of an event that was created and then deleted."""
        event = service.create(CreateEvent(**CREATE))
        service.delete(event.id)
        return event.id

    def test_create_returns_event_with_shared_fields(self, created: Event) -> None:
        assert_event_matches(created, CREATE)

    def test_create_twice_creates_two_events(
        self, service: CalendarService, created: Event, created_ids: list[str]
    ) -> None:
        second = service.create(CreateEvent(**CREATE))
        created_ids.append(second.id)
        assert second.id != created.id

    def test_get_returns_created_event(
        self, service: CalendarService, created: Event
    ) -> None:
        fetched = service.get(created.id)
        assert fetched.id == created.id
        assert_event_matches(fetched, CREATE)

    def test_get_missing_event_raises_not_found(
        self, service: CalendarService, missing_id: str
    ) -> None:
        with pytest.raises(CalendarError) as error:
            service.get(missing_id)
        assert_not_found(error)

    def test_replace_keeps_id_and_replaces_shared_fields(
        self, service: CalendarService, created: Event
    ) -> None:
        replaced = service.replace(created.id, ReplaceEvent(**REPLACE))
        assert replaced.id == created.id
        assert_event_matches(replaced, REPLACE)
        assert_event_matches(service.get(created.id), REPLACE)

    def test_replace_missing_event_raises_not_found(
        self, service: CalendarService, missing_id: str
    ) -> None:
        with pytest.raises(CalendarError) as error:
            service.replace(missing_id, ReplaceEvent(**REPLACE))
        assert_not_found(error)

    def test_delete_removes_event(
        self, service: CalendarService, created: Event
    ) -> None:
        service.delete(created.id)
        with pytest.raises(CalendarError) as error:
            service.get(created.id)
        assert_not_found(error)

    def test_delete_missing_event_raises_not_found(
        self, service: CalendarService, missing_id: str
    ) -> None:
        with pytest.raises(CalendarError) as error:
            service.delete(missing_id)
        assert_not_found(error)

    def test_create_raises_access_denied(
        self, access_denied_service: CalendarService
    ) -> None:
        with pytest.raises(CalendarError) as error:
            access_denied_service.create(CreateEvent(**CREATE))
        assert_calendar_error(error, ErrorCode.ACCESS_DENIED, retryable=False)

    def test_create_raises_provider_error(
        self, provider_error_service: CalendarService
    ) -> None:
        with pytest.raises(CalendarError) as error:
            provider_error_service.create(CreateEvent(**CREATE))
        assert_calendar_error(error, ErrorCode.PROVIDER_ERROR, retryable=False)

    def test_create_raises_provider_unavailable(
        self, provider_unavailable_service: CalendarService
    ) -> None:
        with pytest.raises(CalendarError) as error:
            provider_unavailable_service.create(CreateEvent(**CREATE))
        assert_calendar_error(error, ErrorCode.PROVIDER_UNAVAILABLE, retryable=True)

    def test_create_uncertain_write_is_not_retryable(
        self, uncertain_write_service: CalendarService
    ) -> None:
        with pytest.raises(CalendarError) as error:
            uncertain_write_service.create(CreateEvent(**CREATE))
        assert_calendar_error(error, ErrorCode.PROVIDER_ERROR, retryable=False)

    def test_invalid_create_request_rejected_before_service(self) -> None:
        """Invalid shared input fails at the request model, before a service call."""
        with pytest.raises(ValidationError):
            CreateEvent(
                title="   ",
                start="2030-01-07T15:00:00Z",
                end="2030-01-07T15:30:00Z",
            )
