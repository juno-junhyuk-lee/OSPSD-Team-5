# OSPSD-Team-5

This is Team 5's repository for CS 3943 OSPSD.

## Calendar service — Milestone 1

Juno Lee owns `GET /calendars/{calendar_id}`, Kristie Lee owns
`GET /events/{event_id}`, Jim Lo owns `POST /events`, Ka Pui Cheung owns
`DELETE /events/{event_id}`, and Niriti Pahadi owns `PATCH /events/{event_id}`
through Levels 1–5. These operations call Google Calendar with locally
authorized tokens. POST creates timed events in the same primary calendar that
event GET reads; created events can be retrieved after a server restart.
Offline tests control provider responses and do not require credentials or
network access.

### Installation

Run commands from the repository root. Use Python 3.14 and
[uv](https://docs.astral.sh/uv/) for environments and locked dependencies.
`pyproject.toml` and `uv.lock` are authoritative; `requirements.txt` is an
exported convenience file.

Install uv using its [installation instructions](https://docs.astral.sh/uv/getting-started/installation/),
then run on macOS, Linux, or Windows:

```sh
uv sync --frozen
```

This creates `.venv` and installs the locked dependencies. Activation is not
required when using `uv run`. Historical installation and verification results
refer to their recorded revisions.

### Run

```sh
uv run uvicorn app.main:app --reload
```

Keep the server running while making requests in another terminal. Stop it with
Ctrl+C. Swagger UI: http://localhost:8000/docs

Endpoints that call Google need a local `token.json`. Create it first with [Shared Google Calendar authentication](#shared-google-calendar-authentication); reviewers outside the team should follow [External reviewers](#external-reviewers). The offline tests need neither.

### Event retrieval contract

`GET /events/{event_id}` reads one timed event from the authenticated test
account's primary Google Calendar without changing state. `event_id` is a
required string path parameter using Google's API event ID, not a Calendar UI
link or the old local `test-event` ID. No query/body parameters are required.
Run the shared authentication command below before starting the server.

Success returns `200 OK` with exactly four fields: string `id` and `title`,
and ISO 8601 datetime strings `start_time` and `end_time`. The provider mapping
is `id` → `id`, `summary` → `title`, `start.dateTime` → `start_time`, and
`end.dateTime` → `end_time`. Additional Google fields remain hidden.

Example from the real shared test calendar (times may change if the event is edited):

```sh
curl -i http://localhost:8000/events/lf797iogm23bfjn97ogpfocl80
```

```json
{
  "id": "lf797iogm23bfjn97ogpfocl80",
  "title": "Team 5 GET Test",
  "start_time": "2026-10-05T13:30:00-04:00",
  "end_time": "2026-10-05T14:00:00-04:00"
}
```

An absent provider title is represented as an empty string. All-day events use
Google date fields and are rejected because this public model represents timed
events. These policies are covered by tests and require teammate review.
The shared Event model does not add timezone or start/end ordering validation;
POST validates its own input separately.

#### Level 5 event retrieval errors

This contract is implemented on `feature/calendar-event-get-level5-errors`.
Local checks and real Google success/failure verification passed at `9fad9af`;
see [Level 5 verification and reproduction](docs/EVENT_GET_LEVEL5_VERIFICATION.md).
Teammate review and matching PR CI remain pending; this does not claim final
release completion. Kristie owns this change. The service never starts browser
authorization during a request.

Successful reads retain the existing `200` response and four-field Event model.
Failures use the shared [error format](#error-format), for example:

```json
{"error": {"code": "not_found", "message": "Event not found.", "retryable": false}}
```

| Condition | HTTP status | `error.code` | `retryable` | Caller action |
| --- | --- | --- | --- | --- |
| ID violates the local format below | 422 | `invalid_input` | `false` | Correct the ID |
| Google returns 404 or an event with `status: cancelled` (including deleted events) | 404 | `not_found` | `false` | Check the ID or choose another event |
| All-day event cannot be represented by the timed-event model | 422 | `invalid_input` | `false` | Choose a timed event |
| Google refuses permission; excludes rate-limit responses | 403 | `access_denied` | `false` | Resolve access before another request |
| Authorization is missing, invalid, insufficiently scoped, needs renewal, or is rejected by Google with HTTP 401 | 503 | `provider_unavailable` | `false` | Repair authorization with the authentication script |
| Timeout, temporary provider outage, or rate limit | 503 | `provider_unavailable` | `true` | Retry later; this read does not change state |
| Malformed provider data or another expected provider failure outside the categories above | 502 | `provider_error` | `false` | Investigate before repeating the request |

The local ID rule is `[A-Za-z0-9_-]{1,1024}`, matching DELETE's
validation policy. It permits recurring-instance IDs such as
`abc123_20261016T150000Z`. Invalid IDs are rejected before calling the reader;
valid syntax does not guarantee an event exists. An absent path segment does
not match this route and is outside this operation's ID-validation contract.

Cancelled/deleted events are rejected before translating title or time fields.
This includes minimal cancellation records containing only an ID and status.
After a successful DELETE, event GET returns 404 even if Google retains the
event in Trash; the API does not expose a Trash or restore operation.

`retryable` describes repeating the same request unchanged; it does not enable
automatic retries. The SDK's raw exception type, response payload, and error
text remain internal to the provider implementation. The public contract is
the status, application code, service-written message, and retryability above.
Unexpected programming errors must not be silently reclassified as expected
provider failures.

Each expected failure raises the shared `ServiceError`, producing one
sanitized log on `calendar_service` with `operation="get_event"`, `error`,
`provider`, and `status`. Local ID rejection has `provider=false`; a failure
from a provider call or provider response has `provider=true`. Authorization
failures use the shared definition (the provider was called or caused the
failure), distinguishing local setup failure from a failed remote refresh.
No tokens, credentials, authorization headers, request/response bodies, or
raw exception messages are logged. No request ID is added in this change.

This intentionally changes GET errors from `{"detail": ...}` to the shared
shape, adds local ID validation and a distinct permission-denied response,
and maps temporary failures to 503. Other operations and the app-wide FastAPI
request-validation handler are outside this change; their owners coordinate
those migrations separately. Controlled-provider HTTP tests, Google adapter
translation tests, and sanitized-log assertions cover the implementation.
Real Google success, missing-event, and local-invalid-input checks are recorded
in the verification guide; teammate and final-release verification remain separate.

#### Level 3 event provider boundary

`EventReader` in `app/event_provider.py` defines
`get_event(event_id: str) -> Event`. It reads one timed event from the authorized
calendar without changing events. The input is a provider-assigned event ID;
the output is the service's four-field `Event` model, with an empty title when
no title is supplied. The interface exposes no Google SDK types or payloads.
The same module declares missing-event, unsupported-event, authentication, and
provider errors. Level 5 adds permission and temporary-failure distinctions;
their current HTTP meanings are in the error table above.

`GoogleEventReader` in `app/google_events.py` implements the contract. It uses
`app/google_auth.py` for local authorization and client construction, owns the
Google request and response translation, and closes the client on success or
failure. The event GET route calls the typed `EventReader` boundary and maps
service errors to the documented 403, 404, 422, 503, and 502 responses.

The Level 3 boundary was merged in PR #17. Codex assisted with implementation,
tests, and documentation. POST uses a provider-independent interface with fixed
Google selection until Level 4; PATCH injects `EventUpdater` through FastAPI;
DELETE retains its existing implementation.

#### Level 4 event provider injection

`get_event_reader()` in `app/event_dependencies.py` selects `GoogleEventReader`
and returns it as an `EventReader`. FastAPI supplies it to the event GET route
through `Depends`; the route does not construct or import the concrete reader.
The dependency creates a lightweight reader per request. Authorization and SDK
client creation occur during retrieval, and the Google implementation closes
the client after use. Level 4 preserved the earlier responses; Level 5 changes
the error contract as described above while preserving the success response.

`tests/test_events.py` overrides that dependency with a `ControlledEventReader`
using its own TestClient fixture, without the shared Google SDK mocks. It checks
success, missing events, 403/422/503/502 errors, and event ID forwarding. Each test
gets fresh reader state and restores previous dependency overrides in `finally`.
Google translation, authentication, cleanup, and CRUD tests keep their existing
provider fixtures; the controlled reader does not reproduce Google's behavior.

Replacing the provider requires an `EventReader` implementation and a change to
`get_event_reader`; the route continues using the same contract.
[Verification notes](docs/VERIFICATION.md#event-get-level-4-verification) record
local checks, blocked-network contract tests, and real Google retrieval.
Another teammate must review both normal wiring and test substitution, and
matching PR CI remains required. Codex assisted with implementation and verification.

### Calendar details contract

`GET /calendars/{calendar_id}` retrieves calendar metadata without changing state.
It helps callers identify their calendar and its timezone. `calendar_id` is a
required string path parameter; no query or body parameters are required.
Juno Lee owns this operation through Levels 1–5. Level 2 reads Google metadata
using local OAuth authorization. The JSON below is an example; title and timezone
come from the authenticated account.

Git Bash/macOS/Linux:

```sh
curl -i http://localhost:8000/calendars/primary
curl -i http://localhost:8000/calendars/missing-calendar
```

PowerShell: use `curl.exe -i` with the same URLs to invoke curl directly.

Success returns `200 OK` with exactly three string fields:

```json
{
  "id": "primary",
  "title": "Team 5 Calendar",
  "time_zone": "America/New_York"
}
```

Only `primary` is supported. Its ID is a service lookup alias and remains
`primary` in the response; callers must not interpret it as a Google account ID.
The timezone is an IANA timezone name. Other IDs return `404 Not Found` with
`{"error":{"code":"not_found","message":"Calendar not found.","retryable":false}}`
before any Google request.
This operation does not list calendars or events and does not alter event routes.

#### Level 3 calendar provider boundary

`CalendarReader` in `app/calendar_provider.py` defines the one operation this
route needs: `get_primary_calendar() -> Calendar`. It accepts no arguments because
the route rejects unsupported IDs before calling the provider. It reads external
metadata without changing state and returns the service alias `primary`, a title,
and a timezone. No Google SDK types or payload fields appear in the interface.

`GoogleCalendarReader` in `app/google_calendar.py` implements that contract. It
owns token loading, the Google request, and translation from `summary` and
`timeZone` into the public model. The route depends on the typed `CalendarReader`
boundary. Level 5 replaces generic exception handling with the calendar-specific
service errors documented below; SDK exceptions remain inside the adapter.

This boundary covers Juno's calendar metadata operation; event GET uses its
own `EventReader` boundary described above. Codex assisted
with the implementation, tests, and documentation.

#### Level 4 calendar provider injection

`app/calendar_dependencies.py` selects Google in `get_calendar_reader()`, which
returns a `CalendarReader`. FastAPI supplies that reader to the calendar route
through `Depends`; the route does not import or construct the concrete calendar
provider. The dependency creates a lightweight reader per request. Credentials
and the SDK client are loaded only when metadata is requested, and the Google
implementation closes the client after use. Unsupported IDs still return 404
without a Google request.

Calendar HTTP tests override `get_calendar_reader` with a controlled implementation
of the same interface. They use their own TestClient fixture, without the shared
event SDK mocks, Google credentials, or network access. The controlled reader
returns fixed metadata or raises a configured error. Each test restores dependency
overrides afterward. Google translation tests remain separate.

Replacing the calendar provider requires another implementation of `CalendarReader`
and a change to the dependency's selection; the route contract remains the same.
Local and real-provider evidence is recorded in `docs/VERIFICATION.md`. Teammate
review of production wiring and test substitution remains required for Level 4.

#### Level 5 calendar metadata errors

Calendar GET uses the shared [error format](#error-format) and one sanitized
failure log with `operation="get_calendar"`. Success still returns exactly
`id`, `title`, and `time_zone`; only `primary` is supported.

| Failure | Code | Status | Retryable |
| --- | --- | --- | --- |
| Unsupported calendar ID, or Google reports the calendar missing | `not_found` | 404 | false |
| Missing/invalid token, rejected authorization, or failed renewal | `provider_unavailable` | 503 | false; authorize again first |
| Google refuses permission | `access_denied` | 403 | false |
| Timeout, transport failure, HTTP 408/429/500/502/503/504, or quota/rate-limit 403 | `provider_unavailable` | 503 | true; wait before retrying |
| Invalid metadata or another handled provider failure | `provider_error` | 502 | false |

Messages are fixed service-written text. For example:

```json
{"error":{"code":"access_denied","message":"Calendar access denied.","retryable":false}}
```

`CalendarReader` documents metadata-specific service exceptions in
`app/calendar_provider.py`. `GoogleCalendarReader` translates Google failures;
the route maps those service exceptions to `ServiceError`. Local authorization
and unsupported-ID failures log `provider=false`; remote authorization and
provider failures log `provider=true`. Expected failures have no stack trace,
provider message, calendar ID, or request body in their log.

The compatibility changes are the new error envelope, distinct 403 permission
denials, and 503 temporary failures that previously returned 502 or escaped as
500. Missing-calendar 404 and authorization-setup 503 statuses are preserved.
This endpoint has no body or additional ID syntax constraint: unsupported
string IDs remain 404. It does not introduce an operation-specific 422 case;
app-wide request validation remains a separate team concern.

`tests/test_calendars.py` checks responses and logs through an isolated controlled
reader. `tests/test_google_calendar.py` checks SDK failure translation, metadata,
client cleanup, and disabled retries. Unexpected programming errors propagate
rather than being mislabeled as provider failures. Reads make one metadata
request without automatic retries; credential renewal may add an auth request.
See [calendar Level 5 verification](docs/CALENDAR_GET_LEVEL5_VERIFICATION.md)
for check results, real-provider verification, and remaining review requirements.

### Event creation contract

`POST /events` creates one timed event in Google Calendar's `primary` calendar. Jim Lo
owns this operation, including its implementation, tests, and documentation
through Levels 1–5. Level 2 preserves the Level 1 input and success contract;
it requires local authorization from the Shared Google Calendar authentication
instructions below. One real-provider run is recorded in the verification guide.

The request uses `Content-Type: application/json` and requires three body fields:

| Field | Type | Rule |
| --- | --- | --- |
| `title` | string | Strip leading and trailing whitespace; the result must not be empty. |
| `start_time` | ISO 8601 datetime string | Must include a UTC offset or `Z`. |
| `end_time` | ISO 8601 datetime string | Must include a UTC offset or `Z` and represent an instant after `start_time`. |

There are no required path or query parameters. The caller does not supply
the event ID; Google generates it. For example:

```json
{
  "title": "Team Meeting",
  "start_time": "2026-10-05T10:00:00-04:00",
  "end_time": "2026-10-05T11:00:00-04:00"
}
```

Success returns `201 Created` with exactly the existing `Event` response fields:
`id`, `title`, `start_time`, and `end_time`. For example:

```json
{
  "id": "<server-generated-id>",
  "title": "Team Meeting",
  "start_time": "2026-10-05T10:00:00-04:00",
  "end_time": "2026-10-05T11:00:00-04:00"
}
```

The response contains the normalized title and datetime strings representing
the supplied instants. Equivalent datetime serialization, such as `Z` versus
`+00:00`, is permitted. The generated ID identifies the new event and must not
overwrite an existing event. The event can then be retrieved through
`GET /events/{event_id}` in the same running process.

Missing required fields, invalid field values, timezone-free timestamps, and
an end time equal to or earlier than the start time return `422 Unprocessable
Entity` using FastAPI's validation error response with a `detail` array.
Rejected requests do not add an event or change existing events. Validation
applies to creation inputs; it does not add guarantees to the existing GET
operation or shared response model.

Each valid POST creates a new event, even when its body matches a previous
request. Repeated requests receive different IDs; this operation does not provide
idempotency. The Google event persists independently of the server. Event GET
retrieves the provider event by the returned ID, including after a server restart.
The service does not keep a local event mirror. All-day events are outside this
contract.

Setup failure returns 503 with a `detail` string directing the developer to the
authorization script. Provider HTTP/transport failure or an unusable response
returns 502 with a `detail` string stating that creation could not be confirmed
and to check the calendar before retrying. Neither failure falls back to local
creation. A 502 does not guarantee that Google created no event; do not blindly repeat a write with an uncertain result. Raw provider
errors and credential contents are not included in these HTTP responses.

Acceptance requires HTTP tests demonstrating successful
creation, retrieval through GET, distinct IDs for repeated creation, and
rejection without state changes for the invalid inputs above. Existing GET
tests must continue to pass, and provider fixtures must be isolated so
tests remain independent. Another teammate must review the contract,
implementation, tests, and documentation. Level 1 was approved by Ka Pui and
Juno and merged in [PR #5](https://github.com/juno-junhyuk-lee/OSPSD-Team-5/pull/5).

#### Level 3 event creation provider boundary

`EventCreator` in `app/event_creation_provider.py` defines the provider-independent
creation contract. Jim Lo owns this boundary for POST through Levels 1–5.

| Operation | Input | Return value | External state |
| --- | --- | --- | --- |
| `create_event(request)` | A validated `CreateEventRequest` with a normalized title and timezone-aware start/end times | An `Event` with a generated ID, normalized title, and the submitted time instants | Creates one new timed event in the configured calendar |

The interface uses service models and exposes no SDK requests, credentials, or
provider response types. The provider implementation is responsible for
authorization, creation, and translation to `Event`. The Google implementation
keeps `events.insert`, the `primary` calendar selection, and Google field
mapping inside `app/google_create_events.py`. Callers rely on the returned ID,
not on a particular ID format. Repeating a successful request creates another
event; this contract does not provide idempotency.

The two service errors describe the existing POST failure behavior:

- `EventCreationUnavailableError`: local authorization is unusable before any
  provider write; the route preserves the existing 503 response.
- `EventCreationUnconfirmedError`: a provider call failed or its response could
  not confirm creation; the route preserves the existing 502
  response. A provider event may already exist, so creation is not automatically
  retried. This error does not promise rollback or unchanged provider state.

`GoogleEventCreator` in `app/google_create_events.py` implements the interface.
It delegates insertion and translation to the existing `create_google_event`
helper and converts its known setup, SDK, transport, and response-validation
failures into the two service errors above. The POST handler calls an
`EventCreator` and handles those errors without inspecting Google SDK exceptions.
At implementation commit `8741c90`, Level 3 selected Google in `app/main.py`.
Current provider injection is described below. The shared `load_credentials`
helper remains unchanged for
PATCH and DELETE. [POST Level 3 verification](docs/POST_LEVEL3_VERIFICATION.md)
records offline checks, real create/read, restart persistence, and cleanup for
implementation commit `8741c90`. Teammate review and matching PR CI remain pending.

#### Level 4 event creation provider injection

`get_event_creator()` in `app/event_creation_dependencies.py` selects
`GoogleEventCreator` and returns it as an `EventCreator`. FastAPI supplies it
to POST through `Depends`; the handler calls the interface without constructing
or importing the concrete creator. The dependency creates a lightweight,
stateless creator per request. Authorization and SDK client creation happen
inside its creation operation, after request validation. The existing input,
201 response, and 422/503/502 behavior remain in place.

`tests/test_create_event_contract.py` replaces `get_event_creator` through
`app.dependency_overrides` with a `ControlledEventCreator`. Its own TestClient
fixture uses no Google SDK mocks, credentials, or network access. The controlled
implementation records normalized requests and returns predictable Event values
or raises a configured service error. Tests check the exact 201 response,
returned IDs, time instants, invalid input without a creator call, and existing
503/502 responses without retries. Each test gets fresh creator state and restores
previous dependency overrides in `finally`. Google translation, token, and CRUD
tests retain their provider fixtures; the controlled creator does not reproduce
Google or verify a real write.
Replacing the provider requires another `EventCreator` implementation and a
change to the factory's selection, while the handler keeps the same contract.
[POST Level 4 verification](docs/POST_LEVEL4_VERIFICATION.md) records 130 passing
tests, blocked-network/credential controlled tests, and a real create/read,
restart, and cleanup workflow through normal injection at `c54f52e`. Teammate
review of both normal wiring and test substitution and matching PR CI remain
pending.

### Create and retrieve an event

Install the locked dependencies and complete Shared Google Calendar authentication
below, then start the server using the Run instructions above. In another terminal,
create an event (macOS/Linux or Git Bash):

```sh
curl -i http://localhost:8000/events \
  -H 'Content-Type: application/json' \
  -d '{"title":"  Team Meeting  ","start_time":"2026-10-05T10:00:00-04:00","end_time":"2026-10-05T11:00:00-04:00"}'
```

Expect `201`, a generated `id`, the title `Team Meeting` without surrounding
spaces, and the supplied times. Copy the returned ID into the next request:

```sh
curl -i "http://localhost:8000/events/<returned-id>"
```

Replace `<returned-id>` before running the command. Expect `200` with the same
event. A second POST with the same body returns a different ID.

In PowerShell, use the same workflow through `Invoke-RestMethod`:

```powershell
$body = @{
    title = "  Team Meeting  "
    start_time = "2026-10-05T10:00:00-04:00"
    end_time = "2026-10-05T11:00:00-04:00"
} | ConvertTo-Json
$event = Invoke-RestMethod -Method Post -Uri "http://localhost:8000/events" -ContentType "application/json" -Body $body
$event
Invoke-RestMethod -Uri "http://localhost:8000/events/$($event.id)"
```

To check validation, use Swagger UI's `POST /events` operation and submit a
body with `end_time` equal to `start_time`. Expect `422` with a `detail` array.
The rejected request must not create an event. Restarting the server preserves
Google events; event GET should still return 200 for the created ID. Delete only your own verification events afterward.

Detailed reproduction steps, cleanup instructions, historical results, and
teammate verification links are in [POST Level 2 verification](docs/POST_LEVEL2_VERIFICATION.md).

### Event update contract

`PATCH /events/{event_id}` updates one timed event on the shared test account's
`primary` Google Calendar. Niriti Pahadi owns this operation through Levels 1–5.
`event_id` is a required string path parameter (a Google event ID, as returned
by POST). The body uses the same required fields and validation as create:

```json
{
  "title": "  Updated Meeting  ",
  "start_time": "2026-10-06T11:00:00-04:00",
  "end_time": "2026-10-06T12:00:00-04:00"
}
```

Success returns `200 OK` with the existing four-field `Event` response. The `id`
is unchanged. The title is stripped of surrounding whitespace. A following
`GET /events/{event_id}` returns the same JSON.

| Result | Status | Body | State change? |
| --- | --- | --- | --- |
| Updated | `200` | `Event` JSON | Yes |
| Unknown, deleted, or cancelled ID (Google 404/410, or `events.get` status `cancelled` before patch) | `404` | `{"detail": "Event not found"}` | No |
| Missing/invalid fields, timezone-free times, or `end_time <= start_time` | `422` | FastAPI `detail` array | No |
| Local authorization missing or unusable | `503` | `detail` naming the auth script | No |
| Google rejected the call, failed, or the response was unusable | `502` | update could not be confirmed | Uncertain — check calendar before retry |

Partial/optional fields, all-day events, and changing `id` are outside this
contract. Offline tests cover success with GET match, unknown ID, validation
without state changes, provider failures, and missing authorization. Real
Google verification evidence is in
[PATCH Level 2 verification](docs/PATCH_LEVEL2_VERIFICATION.md).

#### Level 3 event update provider boundary

`EventUpdater` in `app/event_update_provider.py` defines the provider-independent
update contract. Niriti Pahadi owns this boundary for PATCH through Levels 1–5.

| Operation | Input | Return value | External state |
| --- | --- | --- | --- |
| `update_event(event_id, request)` | A provider event ID and a validated `UpdateEventRequest` | An `Event` with the same ID and refreshed title/times | Updates one existing timed event in the configured calendar |

The interface uses service models and exposes no SDK requests, credentials, or
provider response types. `GoogleEventUpdater` in `app/google_update_events.py`
keeps `events.get`/`events.patch`, cancelled-status checks, and Google field
mapping behind that contract. The PATCH handler calls an `EventUpdater` and maps
service errors to the existing 404, 503, and 502 responses. Fixed Google
selection is supplied by FastAPI through `get_event_updater` in
`app/event_update_dependencies.py` (Level 4).

| Service error | HTTP mapping |
| --- | --- |
| `EventUpdateNotFoundError` | `404` Event not found |
| `EventUpdateUnavailableError` | `503` authorization unavailable |
| `EventUpdateUnconfirmedError` | `502` update could not be confirmed |

See [PATCH Level 3 verification](docs/PATCH_LEVEL3_VERIFICATION.md) and
[PATCH Level 4 verification](docs/PATCH_LEVEL4_VERIFICATION.md).

### Event deletion contract

`DELETE /events/{event_id}` deletes one event from the shared test account's
`primary` Google Calendar. Ka Pui Cheung owns this operation through Levels 1–5.
It takes one required string path parameter, `event_id` (a Google event ID, as
returned by POST), and no query or body parameters.

| Result | Status | `error.code` | `retryable` |
| --- | --- | --- | --- |
| Deleted | `204 No Content` (empty body) | none | Not needed |
| ID is empty, over 1024 characters, or has characters other than letters, digits, `_`, `-` | `422` | `invalid_input` | `false` |
| Unknown or already-deleted ID (Google 404 or 410) | `404` | `not_found` | `false` |
| Google refused access (403 that is not a rate limit) | `403` | `access_denied` | `false` |
| Local authorization missing or unusable; no Google call made | `503` | `provider_unavailable` | `false`; fix setup with the auth script first |
| Google failed, rate-limited, or the response was lost | `502` | `provider_error` | `true` |

Failures use the shared [error format](#error-format). An invalid ID is
rejected before any Google call.
Deleting the same ID twice returns `204` then `404`. Retrying after a `502` is
safe: if the first attempt succeeded, the retry returns `404`. Deletion uses
`sendUpdates="none"`, so attendees are not emailed. Raw Google errors are never
returned. See [DELETE Level 2 verification](docs/DELETE_LEVEL2_VERIFICATION.md).

#### Level 3 event deletion provider boundary

`EventDeleter` in `app/event_deletion_provider.py` defines the provider-independent
deletion contract. Ka Pui Cheung owns this boundary for DELETE through Levels 1–5.

| Operation | Input | Return value | External state |
| --- | --- | --- | --- |
| `delete_event(event_id)` | A provider-assigned event ID string, as returned by POST | Nothing | Deletes that one event from the configured calendar without notifying attendees |

The interface uses only a string ID and exposes no SDK requests, credentials,
or provider responses. Callers may assume that a normal return means the event
is deleted and that no other event changed. They should not assume a particular
ID format. The provider implementation is responsible for authorization, the
provider call, and translating provider outcomes into the service errors below.

- `EventDeletionNotFoundError`: no event has the ID, including one that was
  already deleted; the route keeps the existing 404. A repeated delete reports
  the event as missing.
- `EventDeletionUnavailableError`: local authorization is unusable before any
  provider call; the route keeps the existing 503.
- `EventDeletionUnconfirmedError`: the provider call failed or its result was
  lost; the route keeps the existing 502. The event may already be deleted, so
  the implementation does not retry; a caller's retry is safe and returns 404
  if the first attempt succeeded.

`GoogleEventDeleter` in `app/google_delete_events.py` implements the interface.
It delegates to the existing `delete_google_event` helper, which keeps
`events.delete`, the `primary` calendar, `sendUpdates="none"`, and Google's
404/410 handling, and converts known setup, SDK, and transport failures into
the service errors above. The DELETE handler calls an `EventDeleter` and no
longer inspects Google SDK exceptions. `GoogleEventNotFoundError` stays in the
same module because PATCH still uses it. `tests/test_google_delete_events.py`
checks the translation; `tests/test_delete_events.py` keeps the HTTP contract
tests. See [DELETE Level 3 verification](docs/DELETE_LEVEL3_VERIFICATION.md).

#### Level 4 event deletion provider injection

`get_event_deleter()` in `app/event_deletion_dependencies.py` is the only place that
selects `GoogleEventDeleter`; it returns it as an `EventDeleter`. FastAPI
supplies it to the DELETE route through `Depends`, so the route neither
constructs nor imports the concrete deleter. The dependency creates a
lightweight deleter per request; authorization and SDK client creation happen
during deletion. The real deleter needs the local `token.json` from the shared
setup script. Existing responses are unchanged.

`tests/test_delete_event_contract.py` overrides that dependency with a
`ControlledEventDeleter` that holds a set of IDs. It checks 204 with an empty
body, a repeated delete returning 404, an unknown ID, and the 503/502 responses,
plus that normal requests select Google. Each test gets fresh deleter state and
restores previous dependency overrides in `finally`. These tests use their own
TestClient fixture without the shared Google SDK mocks and need no network
access or credentials. `tests/test_delete_events.py` and
`tests/test_google_delete_events.py` keep covering the Google implementation.

Replacing the provider requires an `EventDeleter` implementation and a change to
`get_event_deleter`; the route keeps the same contract. See
[DELETE Level 4 verification](docs/DELETE_LEVEL4_VERIFICATION.md).

### Error format

Operations moved to Level 5 return failures in one shape, defined in
`app/errors.py`:

```json
{"error": {"code": "not_found", "message": "Event not found.", "retryable": false}}
```

| `code` | Status | When | Retry? |
| --- | --- | --- | --- |
| `invalid_input` | `422` | The request is malformed (bad ID, body, or field) | No; fix the request |
| `not_found` | `404` | The resource does not exist or was deleted | No |
| `access_denied` | `403` | The provider refused access to the resource | No |
| `provider_error` | `502` | The provider failed or its result is unknown | Per operation; see `retryable` |
| `provider_unavailable` | `503` | The provider cannot be reached or authorization is not set up | Per operation; see `retryable` |

`message` is a short service-written sentence; provider error text, IDs from
provider responses, and credentials are never included. `retryable` tells the
caller whether repeating the same request unchanged is safe and useful.

To use it, an operation raises `ServiceError(code, message, operation=...,
retryable=..., provider=...)`; the handler registered in `app/main.py` renders
the response and logs one JSON line on the `calendar_service` logger:

```json
{"operation": "delete_event", "error": "not_found", "provider": true, "status": 404}
```

`provider` is true when the provider was called or caused the failure. 5xx
failures log at ERROR, others at WARNING, without stack traces, request bodies,
or tokens. The service has no request ID yet, so none is logged. DELETE, calendar GET, and
event GET use this format now; the other operations still return `{"detail": ...}` until
their owners move them to Level 5.

### Code map and request flow

`app/main.py` owns the FastAPI routes.
Calendar GET calls the `CalendarReader` interface, implemented by
`GoogleCalendarReader.get_primary_calendar` in `app/google_calendar.py`,
which loads local OAuth authorization, retrieves Google metadata, and
returns the `Calendar` model. Unsupported calendar IDs return 404 locally.
FastAPI supplies the calendar reader through `get_calendar_reader` in
`app/calendar_dependencies.py`.

Event GET validates the ID before calling the `EventReader` interface, implemented by
`GoogleEventReader.get_event` in `app/google_events.py`. It requests Google's
`events.get` on `primary` and translates the result to `Event`.
FastAPI supplies the reader through `get_event_reader` in `app/event_dependencies.py`.
`app/google_auth.py` loads and refreshes the local token for event retrieval.
Neither GET operation starts browser authorization during a request.

Event GET translates expected service errors to `ServiceError`; the registered
handler in `app/errors.py` renders the common error body and one sanitized log.
SDK exceptions stay inside `GoogleEventReader`; local versus remote authorization
failure is carried as provider-independent metadata for logging.

The synchronous handlers keep blocking SDK work off the async event loop.
Each request constructs its own authorized client. Both GET operations use
provider-independent interfaces and receive their readers through FastAPI dependencies.
Neither adds a cross-request client cache or retry layer.

POST validates and normalizes `CreateEventRequest`, then calls
`EventCreator.create_event`. `GoogleEventCreator` in `app/google_create_events.py`
is supplied through `get_event_creator` in `app/event_creation_dependencies.py` and
uses the existing insertion helper, which loads or
refreshes local event authorization, calls `events.insert` on `primary`, closes
the client, and translates the Google response to `Event`. Invalid input is
rejected before a write. Each creation request uses `num_retries=0`; an uncertain
result must be investigated before retrying. The adapter translates known
failures into service errors; the POST handler retains its 503 and 502 responses.
Authorization helpers remain
operation-specific at this level; the shared setup script obtains both scopes.

PATCH validates and normalizes `UpdateEventRequest`, then calls
`EventUpdater.update_event`. FastAPI supplies the updater through
`get_event_updater` in `app/event_update_dependencies.py`.
`GoogleEventUpdater` in `app/google_update_events.py` reuses POST's
`load_credentials`, checks cancelled status with `events.get`, calls
`events.patch` on `primary` once without retries, and translates the response
to `Event`. The adapter maps missing/cancelled events and other failures into
service errors; the PATCH handler retains its 404, 503, and 502 responses.
Controlled updater tests override the dependency without constructing Google
clients.

DELETE calls `EventDeleter.delete_event`. `GoogleEventDeleter` in
`app/google_delete_events.py` reuses POST's `load_credentials` and calls
`events.delete` on `primary` once, without retries. It translates Google 404/410
and other known failures into service errors, which the handler maps to the
documented responses. FastAPI supplies the deleter through `get_event_deleter`
in `app/event_deletion_dependencies.py`.

### Checks and testing

Run the same commands on macOS, Linux, or Windows:

```sh
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest -v
git diff --check
```

Ruff checks lint and formatting; mypy checks both app and tests in strict mode.
Configuration is in pyproject.toml and pytest.ini. GitHub Actions runs these
uv-based lint, formatting, type, and test checks on pushes and pull requests
using Python 3.14 on Linux. For intentional formatting changes, run
`uv run ruff format .` and review the diff.

The fast suite runs without Google credentials or external network access.
It covers HTTP contracts, provider translation, event authentication,
and event failure cases. The shared fixture provides isolated provider data
for mocked Google insertion and retrieval. Data is populated by the fake insert,
not by the HTTP handler, so POST-to-GET checks exercise both provider paths.
Offline checks do not establish a live Google write.

Calendar HTTP tests use a controlled `CalendarReader` dependency override.
`tests/test_google_calendar.py` verifies Google's metadata field translation
and excludes provider-only fields from the public response.

[Google creation tests](tests/test_google_create_events.py) cover outgoing fields,
provider-assigned IDs, response validation, authorization, and disabled retries.
HTTP creation tests also check validation without provider writes, sanitized
503/502 responses, accepted writes with lost responses, and GET responsiveness
while a mocked insertion is waiting. The last check uses TestClient, not a live
single-worker server.

See [verification notes](docs/VERIFICATION.md) for event test coverage,
real-provider reproduction steps, and historical Level 1 verification.

### Level 2 calendar details verification

`app/google_calendar.py` reads repository-root `token.json` and calls Google's
[calendars.get](https://developers.google.com/workspace/calendar/api/v3/reference/calendars/get).
It maps `summary` to `title` and `timeZone` to `time_zone`, retaining
`primary` as the response ID. The Google client closes after use.

The original Level 2 error responses have been replaced by the
[Level 5 calendar metadata errors](#level-5-calendar-metadata-errors).
Token setup failures return 503, permission denials 403, temporary failures 503,
and malformed provider metadata 502, all with the shared envelope and logging.

Calendar metadata requires
`https://www.googleapis.com/auth/calendar.calendars.readonly`.
Add this scope in Google Auth Platform Data Access and rerun the
authentication script. Existing event-only tokens require reauthorization.

Start the service and request `/calendars/primary`. Expect 200 with the
authenticated calendar's title and timezone and the response ID `primary`.
Compare the values with Google Calendar settings. Unsupported calendar IDs
return 404. This read-only verification requires no event cleanup.

Juno verified reauthorization and real HTTP retrieval.
A second teammate must reproduce calendar retrieval.
Run all local checks and verify CI for the revision under review.

### Shared Google Calendar authentication

The team uses one shared test account and its primary calendar. Enable the
Calendar API and create a Desktop OAuth client in the shared Cloud project.
For an External app in Testing, register the shared account as a test user and
configure `https://www.googleapis.com/auth/calendar.events` in Data Access.
The authentication script also requests `calendar.calendars.readonly` for
calendar metadata; add that scope in Data Access as well.

Privately obtain the client JSON and save it as `credentials.json` in the
repository root. Run `uv sync --frozen`, then authorize on any supported platform:

```sh
uv run python scripts/google_calendar_auth.py
```

Sign in to the shared test account
in the browser and approve event access within five minutes. The script stores
`token.json` locally, refreshes usable expired tokens, and requests authorization
again if a token is revoked or lacks the agreed scope. Each teammate generates
their own local token. Never commit either JSON file or print its contents.

#### External reviewers

Reviewers outside the team do not use the shared account or its password. Contact the team privately and send the Google account email you want to test with. We add that email to the app's test users and send you `credentials.json` privately. Save it in the repository root, run the authentication script above, and sign in with your own account.

The service then reads and writes that account's primary calendar, so use an account meant for testing and delete any events you create. While the app is in Testing, Google expires its authorization after seven days; run the script again to reauthorize.

The verification request lists up to ten events from `primary` without changing
state. Copy a returned API event ID to verify that specific event:

```sh
uv run python scripts/google_calendar_auth.py --event-id EVENT_ID
```

A successful API request with no returned events still verifies authentication;
create a timed test event before verifying retrieval. A second execution should
reuse the saved authorization. A second teammate must reproduce the real request.
The setup script authorizes the account and verifies event access.
Both calendar-details GET and event GET use local authorization to call Google.
The flow follows the [Google Python quickstart](https://developers.google.com/workspace/calendar/api/quickstart/python).


### Level 2 integration status

PRs #8 and #9 are merged. POST Level 2 is under review in
[PR #10](https://github.com/juno-junhyuk-lee/OSPSD-Team-5/pull/10).
Juno and Ka Pui recorded real POST verification and approved its earlier revision.
The combined implementation must pass local checks and updated PR CI before
merging. [POST verification](docs/POST_LEVEL2_VERIFICATION.md) records the current
create/read workflow separately from earlier local-mirror evidence.

## Contributor documentation

- [AGENTS.md](AGENTS.md): code map, contributor instructions, and review/release rules.
- [Work plan](docs/WORK_PLAN.md): owners, progress, and milestone responsibilities.

## Team Members

- Juno Lee
- Niriti Pahadi
- Kristie Lee
- Jim Lo
- Ka Pui Cheung
