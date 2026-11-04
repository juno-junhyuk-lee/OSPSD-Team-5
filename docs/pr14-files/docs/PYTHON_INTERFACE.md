# Calendar Python interface

This is the shared Python interface for issue #2, matching the conformance suite
in this repository. Public names and synchronous signatures are the cross-team
contract for Create, Get by ID, Replace, and Delete.

## Public API

Import `CalendarService`, `Event`, `CreateEvent`, `ReplaceEvent`, `CalendarError`,
and `ErrorCode` from `calendar_contract`. Module imports such as
`calendar_contract.service.CalendarService` remain supported.

```python
class CalendarService(Protocol):
    def create(self, request: CreateEvent) -> Event: ...
    def get(self, event_id: str) -> Event: ...
    def replace(self, event_id: str, request: ReplaceEvent) -> Event: ...
    def delete(self, event_id: str) -> None: ...
```

An implementation supplies these methods without inheriting from the protocol.
The service selects its calendar through implementation configuration; callers
supply opaque event IDs, not calendar IDs. Each service repository owns its
provider adapter, credentials, HTTP translation, and dependency injection.

`create` receives validated title/start/end values and returns the created Event
with a provider-assigned ID. Creation is not idempotent. `get` reads an existing
event. `replace` requires all shared editable fields and preserves the event ID;
what happens to extension fields remains implementation-specific. `delete`
returns `None` on success. Missing get/replace/delete operations, including a
repeated delete, raise a non-retryable `NOT_FOUND` error.

## Failures and validation

Operation failures use `CalendarError(code, message, retryable, details=None)`:

| ErrorCode | Meaning | Conformance retryable |
| --- | --- | --- |
| `INVALID_INPUT` | A request cannot be accepted under the shared rules. | `false` at the model boundary |
| `NOT_FOUND` | The requested event is missing or deleted. | `false` |
| `ACCESS_DENIED` | The configured provider identity lacks permission. | `false` |
| `PROVIDER_ERROR` | An unexpected provider response or uncertain create/replace. | `false` |
| `PROVIDER_UNAVAILABLE` | Temporary provider unavailability. | `true` |

An uncertain create/replace uses `PROVIDER_ERROR` and `retryable=False`; the
implementation never automatically retries it. Sanitize messages and optional
details before exposing them externally. Translate SDK exceptions to these
shared errors. HTTP statuses and headers belong to the HTTP boundary.

Constructing an invalid Pydantic request model raises `pydantic.ValidationError`
before a service call. That is distinct from a `CalendarError` raised by an
operation. The HTTP boundary maps malformed JSON to 400 and invalid valid-JSON
input to 422, both with the shared `invalid_input` error body.

## Consumer example

```python
from calendar_contract import CalendarService, CreateEvent, Event


def create_and_read(service: CalendarService) -> Event:
    created = service.create(
        CreateEvent(
            title="Interface review",
            start="2030-01-07T15:00:00Z",
            end="2030-01-07T15:30:00Z",
        )
    )
    return service.get(created.id)
```

The caller owns cleanup for events it creates. Timestamp comparisons use
instants; equivalent output offsets are allowed. Whole-second inputs avoid
implementation-specific sub-second handling.

## Conformance integration

The suite imports this exact protocol from `calendar_contract.service`.
Subclass `CalendarServiceConformance` in a test module and provide fixtures:

```python
import pytest

from calendar_contract import CalendarService
from calendar_contract.conformance import CalendarServiceConformance


class TestCalendar(CalendarServiceConformance):
    @pytest.fixture
    def service(self) -> CalendarService:
        return make_isolated_service()

    @pytest.fixture
    def access_denied_service(self) -> CalendarService:
        return make_service_that_denies_create()

    @pytest.fixture
    def provider_error_service(self) -> CalendarService:
        return make_service_that_errors_on_create()

    @pytest.fixture
    def provider_unavailable_service(self) -> CalendarService:
        return make_service_that_is_temporarily_unavailable()

    @pytest.fixture
    def uncertain_write_service(self) -> CalendarService:
        return make_service_with_uncertain_create()
```

The failure fixtures are test-only substitution points. Each must return a normal
`CalendarService` configured to fail in the required way. Do not add test-control
methods to the four-operation production protocol.

The suite covers successful CRUD, missing-event `NOT_FOUND`, access denial,
unexpected provider error, temporary unavailability, uncertain writes with
`retryable=False`, and representative invalid input via request-model validation.

Install pytest in the consuming test environment. Importing the public package
or service interface does not import the pytest-based suite. Offline checks
must use controlled providers without credentials or network access. Passing
against the suite's in-memory service does not establish Google integration.
