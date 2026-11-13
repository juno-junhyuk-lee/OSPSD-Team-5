# OSPSD-Team-5

This is Team 5's repository for CS 3943 OSPSD.

## HW3 Milestone 1 — issue integration in progress

Member 3's [issue tracker integration](docs/ISSUE_TRACKER_INTEGRATION.md)
provides a configurable HTTP adapter using Team 4's tagged shared contract,
offline tests, and the handoff to the composed workflow. No live Trello
verification is claimed yet. The documented cache-bypass limitation and
outstanding access/review work remain explicit.

Member 1's [scheduled-issue workflow](docs/WORKFLOW.md) adds
`POST /workflows/scheduled-issues`. It creates an issue, then a Calendar event,
then stores a Markdown summary, and reports failed steps and leftovers. It is
tested offline with controlled dependencies. Summary storage is a placeholder
that returns 503 until Member 4's adapter is connected.

## Calendar service — HW2 shared contract adoption

Juno Lee owns `GET /calendars/{calendar_id}`, Kristie Lee owns
`GET /events/{event_id}`, Jim Lo owns `POST /events`, Ka Pui Cheung owns
`DELETE /events/{event_id}`, and Niriti Pahadi owns `PATCH /events/{event_id}`
through Levels 1–5. These operations call Google Calendar with locally
authorized tokens. POST creates timed events in the same primary calendar that
event GET reads; created events can be retrieved after a server restart.
Offline tests control provider responses and do not require credentials or
network access.

### Shared contract adoption (HW2)

The dependency is `calendar-contract` at annotated tag
[`v0.1.0-rc.1`](https://github.com/Airbus-A330/OSPSD-Calendar/tree/v0.1.0-rc.1), commit
`1c1cad7a0732ddb242a05400d8833d94e4422424`. `pyproject.toml` selects the tag;
`uv.lock` fixes its commit. The package supports Python 3.14 and supplies
`CalendarService`, `Event`, `CreateEvent`, `ReplaceEvent`, `CalendarError`, and
`ErrorCode`. Google SDK and OAuth code remain in this service repository.

| Operation | Success | Shared service method |
| --- | --- | --- |
| POST /events | 201 with Event | create |
| GET /events/{event_id} | 200 with Event | get |
| PUT /events/{event_id} | 200 with Event | replace |
| DELETE /events/{event_id} | 204, no body | delete |

POST and PUT require `title`, `start`, and `end`. Times are RFC 3339 **strings**
with an explicit offset, and end must follow start by instant. Event responses
use `id`, `title`, `start`, and `end`. Old `start_time`/`end_time` inputs and
unknown fields are rejected with 422, even when the new fields are also present.
There are no compatibility aliases. PATCH uses the new names and continues to
require all three editable fields; it is not a partial-update implementation.

Malformed or empty JSON returns 400. Valid JSON that fails field/model rules
returns 422. Both use the common error envelope. Missing events and repeated
DELETE return 404. Permission denial is 403; missing/unusable OAuth is 503 with
`retryable=false`. Temporary failure before a write or an explicit rate limit
is 503 with `retryable=true`. An uncertain POST/PUT is 502 with
`retryable=false` and is never automatically retried.

Team 5 trims titles at the Google write boundary, preserves unrelated Google
fields on PUT, and does not deliberately truncate timestamp strings. Responses
follow provider-stored instants; output offset and fractional precision are not
guaranteed. Use whole-second times for cross-team verification. Listing and
all-day events remain outside the shared core; calendar metadata and PATCH
remain extensions.

See the [migration and verification guide](docs/SHARED_CONTRACT_ADOPTION.md) for
installation, ownership, reproducible checks, and remaining evidence. The
[manual tutorial](TUTORIAL.md) uses the current fields. Level 1–5 subsections
below retain HW1 implementation history; their historical verification records
refer to their recorded commits and do not prove tagged HW2 verification.
The [November 4 real Google record](docs/SHARED_CONTRACT_VERIFICATION.md)
separately verifies the tagged normal workflow at clean commit `327e8bc`;
shared conformance wiring is integrated. Historical run evidence remains tied
to its recorded commit, while final deployed verification remains separate.

### Milestone 3 deployment and pipeline

See [DEPLOYMENT.md](docs/DEPLOYMENT.md) for manual deployment and the
[Level 2 pipeline/recovery procedure](docs/DEPLOYMENT.md#level-2-automated-deployment-and-recovery).
**Verify deployment, failure detection, and recovery are verified**, including
real Google smoke and cleanup. The merged Level 4 revision `191b006` passed
[automatic deployment](https://github.com/juno-junhyuk-lee/OSPSD-Team-5/actions/runs/43100667215),
including Google smoke/cleanup and verified-release artifact publication.
The [deployed shared-conformance record](docs/DEPLOYED_CONFORMANCE_VERIFICATION.md)
documents the HTTPS suite, controlled-failure scope, and independent cleanup
search. Release publication remains separate from pipeline artifact creation.

### Installation

Run commands from the repository root. Use Python 3.14 and
[uv](https://docs.astral.sh/uv/) for environments and locked dependencies.
`pyproject.toml` and `uv.lock` are authoritative; `requirements.txt` is a
historical HW1 export and does not install the shared package; use uv for HW2.

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

For a step-by-step Create → Read → Replace → Read → Delete walkthrough with example
requests, responses, and shared error handling, see [TUTORIAL.md](TUTORIAL.md).

Endpoints that call Google need a local `token.json`. Create it first with [Shared Google Calendar authentication](#shared-google-calendar-authentication); reviewers outside the team should follow [External reviewers](#external-reviewers). The offline tests need neither.

### Event retrieval contract

`GET /events/{event_id}` reads one timed event from the authenticated test
account's primary Google Calendar without changing state. `event_id` is a
required string path parameter using Google's API event ID, not a Calendar UI
link or the old local `test-event` ID. No query/body parameters are required.
Run the shared authentication command below before starting the server.

Success returns `200 OK` with exactly four fields: string `id` and `title`,
and RFC 3339 timestamp strings `start` and `end`. The provider mapping
is `id` → `id`, `summary` → `title`, `start.dateTime` → `start`, and
`end.dateTime` → `end`. Additional Google fields remain hidden.

Illustrative response shape; choose an existing event ID from your test calendar:

```sh
curl -i http://localhost:8000/events/lf797iogm23bfjn97ogpfocl80
```

```json
{
  "id": "lf797iogm23bfjn97ogpfocl80",
  "title": "Team 5 GET Test",
  "start": "2026-10-05T13:30:00-04:00",
  "end": "2026-10-05T14:00:00-04:00"
}
```

An absent provider title is represented as an empty string. All-day events use
Google date fields and are rejected because this public model represents timed
events. These policies are covered by tests and require teammate review.
The shared Event model validates RFC 3339 timestamps with explicit offsets and
requires the end instant to follow the start. It permits an empty read title.

#### Level 5 event retrieval errors

Historical HW1 local and real Google verification at `9fad9af` is recorded in
[Level 5 verification and reproduction](docs/EVENT_GET_LEVEL5_VERIFICATION.md).
That evidence does not establish tagged HW2 integration or release completion. Kristie owns this change. The service never starts browser
authorization during a request.

Successful reads retain the existing `200` response and four-field Event model.
Failures use the shared [error format](#error-format), for example:

```json
{"error": {"code": "not_found", "message": "Event not found.", "retryable": false}}
```

| Condition | HTTP status | `error.code` | `retryable` | Caller action |
| --- | --- | --- | --- | --- |
| ID violates the local format below | 422 | `invalid_input` | `false` | Correct the ID |
| Google returns 404/410 or an event with `status: cancelled` (including deleted events) | 404 | `not_found` | `false` | Check the ID or choose another event |
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
and maps temporary failures to 503. Those were the boundaries of the HW1 GET
change. HW2 now applies the shared request models, error types, and HTTP
validation rules to event routes. Controlled-provider HTTP tests, Google adapter
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
failure. The shared service calls the typed `EventReader` boundary and converts its
errors to `CalendarError`; the HTTP handler selects the documented statuses.

The Level 3 boundary was merged in PR #17. Codex assisted with implementation,
tests, and documentation. Those were the HW1 boundaries. Current HW2 routing composes the existing
operation interfaces beneath the shared `CalendarService`.

#### Level 4 event provider injection

`get_event_reader()` in `app/event_dependencies.py` selects `GoogleEventReader`
and returns it as an `EventReader`. FastAPI supplies it to the shared service
through a subdependency; the route does not construct or import the concrete reader.
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
through Levels 1–5. HW2 renames the time fields to match the common contract. Local authorization
is required; follow Shared Google Calendar authentication below. Historical HW1
runs are separate from the [tagged HW2 verification](docs/SHARED_CONTRACT_VERIFICATION.md)
recorded on November 4 at `327e8bc`.

The request uses `Content-Type: application/json` and requires three body fields:

| Field | Type | Rule |
| --- | --- | --- |
| `title` | string | Must not be blank after trimming. The shared model preserves the string; Team 5 trims it at the Google write boundary. |
| `start` | RFC 3339 string | Must include a UTC offset or `Z`. |
| `end` | RFC 3339 string | Must include a UTC offset or `Z` and represent an instant after `start`. |

There are no required path or query parameters. The caller does not supply
the event ID; Google generates it. For example:

```json
{
  "title": "Team Meeting",
  "start": "2026-10-05T10:00:00-04:00",
  "end": "2026-10-05T11:00:00-04:00"
}
```

Success returns `201 Created` with exactly the existing `Event` response fields:
`id`, `title`, `start`, and `end`. For example:

```json
{
  "id": "<server-generated-id>",
  "title": "Team Meeting",
  "start": "2026-10-05T10:00:00-04:00",
  "end": "2026-10-05T11:00:00-04:00"
}
```

The response contains the stored title and timestamps returned by Google. Equivalent datetime serialization, such as `Z` versus
`+00:00`, is permitted. The generated ID identifies the new event and must not
overwrite an existing event. The event can then be retrieved through
`GET /events/{event_id}` in the same running process.

Missing required fields, invalid field values, timezone-free timestamps, and
an end time equal to or earlier than the start time return `422 Unprocessable
Entity` using the shared `invalid_input` error format with `retryable=false`.
Rejected requests do not add an event or change existing events. The shared models validate both write inputs and returned event timestamps.

Each valid POST creates a new event, even when its body matches a previous
request. Repeated requests receive different IDs; this operation does not provide
idempotency. The Google event persists independently of the server. Event GET
retrieves the provider event by the returned ID, including after a server restart.
The service does not keep a local event mirror. All-day events are outside this
contract.

Setup failure or rejected Google authorization returns 503 with code
`provider_unavailable` and a message directing the developer to the authorization
script. Permission denial returns 403 with code `access_denied`.
A temporary failure before sending the write, or an explicit quota/rate-limit
rejection, returns 503 / `provider_unavailable` with `retryable=true`. A failed
or unusable response after sending a write returns 502 / `provider_error` with
`retryable=false`; inspect the calendar before retrying. Missing or rejected
authorization instead uses 503 with `retryable=false`. No failure falls back to local
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
| `create_event(request)` | A shared `CreateEvent` with a validated title and RFC 3339 start/end strings | An `Event` with a generated ID, stored title, and provider-returned time instants | Creates one new timed event in the configured calendar |

The interface uses service models and exposes no SDK requests, credentials, or
provider response types. The provider implementation is responsible for
authorization, creation, and translation to `Event`. The Google implementation
keeps `events.insert`, the `primary` calendar selection, and Google field
mapping inside `app/google_create_events.py`. Callers rely on the returned ID,
not on a particular ID format. Repeating a successful request creates another
event; this contract does not provide idempotency.

At Level 3, two service errors described POST failure behavior:

- `EventCreationUnavailableError`: local authorization is unusable before any
  provider write; the route preserves the existing 503 response.
- `EventCreationUnconfirmedError`: a provider call failed or its response could
  not confirm creation; the route preserves the existing 502
  response. A provider event may already exist, so creation is not automatically
  retried. This error does not promise rollback or unchanged provider state.

`GoogleEventCreator` in `app/google_create_events.py` implements the interface.
It delegates insertion and translation to the existing `create_google_event`
helper and converts its known setup, SDK, transport, and response-validation
failures into operation-specific errors. `GoogleCalendarService` calls the
`EventCreator` and translates those failures without exposing SDK exceptions.
At implementation commit `8741c90`, Level 3 selected Google in `app/main.py`.
Current provider injection is described below. The shared `load_credentials`
helper remains unchanged for
PATCH and DELETE. [POST Level 3 verification](docs/POST_LEVEL3_VERIFICATION.md)
records offline checks, real create/read, restart persistence, and cleanup for
implementation commit `8741c90`. Teammate review and matching PR CI were pending at that HW1 checkpoint.

#### Level 4 event creation provider injection

`get_event_creator()` in `app/event_creation_dependencies.py` selects
`GoogleEventCreator` and returns it as an `EventCreator`. FastAPI supplies it
to `GoogleCalendarService` through a subdependency. The shared service calls
the operation interface; the route calls `CalendarService` without constructing
or importing the concrete creator. The dependency creates a lightweight,
stateless creator per request. Authorization and SDK client creation happen
inside its creation operation, after request validation. HW1 Level 4 preserved
its existing input and responses; HW2 adds shared field/model validation and
the 400/422 distinction described above.

`tests/test_create_event_contract.py` replaces `get_event_creator` through
`app.dependency_overrides` with a `ControlledEventCreator`. Its own TestClient
fixture uses no Google SDK mocks, credentials, or network access. The controlled
implementation records validated shared requests and returns predictable Event
values or raises a configured service error. Tests check the exact 201 response,
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

#### Level 5 event creation errors

POST maps provider-independent errors to the shared HTTP format:

| Service error | Meaning | HTTP response |
| --- | --- | --- |
| `EventCreationUnavailableError` | Local authorization is unusable, token refresh was rejected, or Google returned 401 | `503 / provider_unavailable`, not retryable until authorization is fixed |
| `EventCreationDeniedError` | Google returned a permission-denied 403, excluding known quota/rate limits | `403 / access_denied`, not retryable |
| `EventCreationProviderUnavailableError` | Temporary failure before insertion, or explicit quota/rate-limit rejection | `503 / provider_unavailable`, retryable later |
| `EventCreationUnconfirmedError` | Insertion started but its failed or unusable response prevents confirmation | `502 / provider_error`, not retryable without checking the calendar |

The authorization error's `provider` flag is false for local setup failures and
true for rejected refreshes, unusable refreshed credentials, or remote 401s.
The shared setup exception adds this flag without changing credential loading,
refresh, or storage behavior for PATCH and DELETE. SDK details remain inside
the Google adapter. Known 403 rate/quota failures remain provider failures,
not permission denials. Google insertion still uses `num_retries=0`.

Malformed or empty JSON returns 400; valid JSON with missing, unknown, or
invalid fields returns 422. Both use `invalid_input`, the message "Invalid
request. Check required fields, types, and values.", and `retryable=false`.
Validation rejects these requests without calling the creator. The shared
request-validation handler also covers PUT and PATCH.

The shared service translates POST failures into `CalendarError`; the HTTP
handler adds `ServiceError` log context and writes exactly one structured log
with `operation=create_event`. Local validation and setup failures log `provider=false`; remote authorization and provider outcomes log
`provider=true`. Logs omit titles, event bodies, authorization headers, raw SDK
errors, and stack traces. Successful creation produces no failure log.

Compatibility: POST errors change from `detail` to `error`, and a permission
denial changed to 403 instead of the earlier broad 502 in HW1. HW2 additionally
renames time fields, rejects unknown fields, and distinguishes malformed JSON
from model-validation failures. FastAPI request-validation errors across
the app now use the shared shape, including PATCH. Swagger documents the shared
validation response and operation 403/404/502/503 responses.

POST does not take an existing resource ID, so it does not add a missing-event
error merely to mirror GET or DELETE. Controlled tests verify failure responses
and logs, including that uncertain writes are never automatically retried.
At implementation commit `ba8ebf3`, real Google verification passed for creation,
matching reads, restart persistence, invalid input without a write, and cleanup.
An isolated invalid-token request reached Google and returned 401, translated
through the SDK authorization path to 503 / `provider_unavailable` with one safe
provider=true log. No shared permissions or normal token were changed by that
probe. See [POST Level 5 verification](docs/POST_LEVEL5_VERIFICATION.md) for
evidence, test boundaries, and reproduction. Teammate review and PR CI remain
required.

### Create and retrieve an event

Install the locked dependencies and complete Shared Google Calendar authentication
below, then start the server using the Run instructions above. In another terminal,
create an event (macOS/Linux or Git Bash):

```sh
curl -i http://localhost:8000/events \
  -H 'Content-Type: application/json' \
  -d '{"title":"  Team Meeting  ","start":"2026-10-05T10:00:00-04:00","end":"2026-10-05T11:00:00-04:00"}'
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
    start = "2026-10-05T10:00:00-04:00"
    end = "2026-10-05T11:00:00-04:00"
} | ConvertTo-Json
$event = Invoke-RestMethod -Method Post -Uri "http://localhost:8000/events" -ContentType "application/json" -Body $body
$event
Invoke-RestMethod -Uri "http://localhost:8000/events/$($event.id)"
```

To check validation, use Swagger UI's `POST /events` operation and submit a
body with `end` equal to `start`. Expect `422` with code `invalid_input`
and `retryable=false` in the shared error format.
The rejected request must not create an event. Restarting the server preserves
Google events; event GET should still return 200 for the created ID. Delete only your own verification events afterward.

Detailed reproduction steps, cleanup instructions, historical results, and
teammate verification links are in [POST Level 2 verification](docs/POST_LEVEL2_VERIFICATION.md).

### Event update contract

PATCH remains a full-field extension and requires title, start, and end.

`PATCH /events/{event_id}` updates one timed event on the shared test account's
`primary` Google Calendar. Niriti Pahadi owns this operation through Levels 1–5.
`event_id` is a required string path parameter (a Google event ID, as returned
by POST). The body uses the same required fields and validation as create:

```json
{
  "title": "  Updated Meeting  ",
  "start": "2026-10-06T11:00:00-04:00",
  "end": "2026-10-06T12:00:00-04:00"
}
```

Success returns `200 OK` with the existing four-field `Event` response. The `id`
is unchanged. The title is stripped of surrounding whitespace. A following
`GET /events/{event_id}` returns the same JSON.

| Result | Status | `error.code` | `retryable` | State change? |
| --- | --- | --- | --- | --- |
| Updated | `200` | none | Not needed | Yes |
| Malformed or empty JSON | `400` | `invalid_input` | `false` | No |
| ID is empty, over 1024 characters, or has characters other than letters, digits, `_`, `-` | `422` | `invalid_input` | `false` | No |
| Unknown, deleted, or cancelled ID (Google 404/410, or `events.get` status `cancelled` before patch) | `404` | `not_found` | `false` | No |
| Missing/invalid fields, timezone-free times, or `end <= start` | `422` | `invalid_input` | `false` | No |
| Google refused access (403 that is not a rate limit) | `403` | `access_denied` | `false` | No |
| Local authorization missing or unusable, or remote authorization rejected | `503` | `provider_unavailable` | `false` | No |
| Temporary failure before patch or explicit rate-limit rejection | `503` | `provider_unavailable` | `true` | No |
| Response after patch is lost, failed, or unusable | `502` | `provider_error` | `false`; check calendar before retry | Uncertain |

Failures use the shared [error format](#error-format). An invalid ID is
rejected before any Google call. Partial/optional fields, all-day events, and
changing `id` are outside this contract. Offline tests cover success with GET
match, unknown ID, validation without state changes, provider failures, and
missing authorization. Real Google verification evidence is in
[PATCH Level 2 verification](docs/PATCH_LEVEL2_VERIFICATION.md).

#### Level 3 event update provider boundary

`EventUpdater` in `app/event_update_provider.py` defines the provider-independent
update contract. Niriti Pahadi owns this boundary for PATCH through Levels 1–5.

| Operation | Input | Return value | External state |
| --- | --- | --- | --- |
| `update_event(event_id, request)` | A provider event ID and a validated `ReplaceEvent` | An `Event` with the same ID and refreshed title/times | Updates one existing timed event in the configured calendar |

The interface uses service models and exposes no SDK requests, credentials, or
provider response types. `GoogleEventUpdater` in `app/google_update_events.py`
keeps `events.get`/`events.patch`, cancelled-status checks, and Google field
mapping behind that contract. FastAPI supplies the updater through
`get_event_updater` in `app/event_update_dependencies.py` (Level 4).

See [PATCH Level 3 verification](docs/PATCH_LEVEL3_VERIFICATION.md) and
[PATCH Level 4 verification](docs/PATCH_LEVEL4_VERIFICATION.md).

#### Level 5 event update errors

Niriti Pahadi owns PATCH Level 5. The Google adapter classifies authorization,
permission, not-found, and unconfirmed failures into update service errors. The
shared service maps them to `CalendarError`, then the HTTP handler renders them:

| Service error | HTTP | Code | Retryable |
| --- | --- | --- | --- |
| Malformed or empty JSON | `400` | `invalid_input` | `false` |
| Invalid event ID or valid-JSON body | `422` | `invalid_input` | `false` |
| `EventUpdateNotFoundError` | `404` | `not_found` | `false` |
| `EventUpdateDeniedError` | `403` | `access_denied` | `false` |
| `EventUpdateUnavailableError` | `503` | `provider_unavailable` | `false` |
| `EventUpdateProviderUnavailableError` | `503` | `provider_unavailable` | `true` |
| `EventUpdateProviderError` | `502` | `provider_error` | `false` |
| `EventUpdateUnconfirmedError` | `502` | `provider_error` | `false` |

One sanitized failure log is written per failure. Uncertain updates are never
automatically retried. See
[PATCH Level 5 verification](docs/PATCH_LEVEL5_VERIFICATION.md).

### Event replacement contract

`PUT /events/{event_id}` replaces the shared fields of one timed event, as the
HW2 joint Calendar contract requires. Ka Pui Cheung owns this operation. It
takes the same path parameter, body, validation, and failure table as PATCH
above, and returns `200 OK` with the four-field `Event`. The body must contain
`title`, `start`, and `end`; the `id` never changes.

PUT replaces only the title and both times. Google fields outside the shared
model (description, location, attendees, reminders, recurrence) are kept,
because the request reaches Google as `events.patch` with only `summary`,
`start`, and `end`. A missing, deleted, or cancelled event returns `404` without
a write. Failure logs use the operation name `replace_event`.

### Unsupported replacements and recurring instances

PUT and PATCH reject all-day events and recurring-series parents with
400 `invalid_input`, `retryable=false`, after reading the target and before
writing. Individual timed recurring instances can be replaced by ID; the patch
updates only title/start/end and preserves their series metadata and other
Google fields. GET retains its existing 422 for all-day events and can read
timed series/instances. DELETE behavior is unchanged. These are Team 5 policies;
listing and recurrence editing are outside the shared core.

Controlled coverage is in `tests/test_event_shape_policy.py`; it verifies
unchanged provider state on rejection and preservation of instance metadata.
See [the adoption guide](docs/SHARED_CONTRACT_ADOPTION.md#local-event-shape-policy).

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
| Local authorization missing/unusable, or remote authorization rejected | `503` | `provider_unavailable` | `false`; fix setup with the auth script first |
| Temporary failure before deletion or explicit rate-limit rejection | `503` | `provider_unavailable` | `true` |
| Deletion response failed or was lost | `502` | `provider_error` | `true` |

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
- `EventDeletionUnavailableError`: local authorization is unusable or Google
  rejects it; the shared service returns a non-retryable authorization failure.
- `EventDeletionProviderUnavailableError`: temporary setup failure or an explicit
  rate limit; the HTTP outcome is 503 with `retryable=true`.
- `EventDeletionUnconfirmedError`: the provider call failed or its result was
  lost; the route keeps the existing 502. The event may already be deleted, so
  the implementation does not retry; a caller's retry is safe and returns 404
  if the first attempt succeeded.

`GoogleEventDeleter` in `app/google_delete_events.py` implements the interface.
It delegates to the existing `delete_google_event` helper, which keeps
`events.delete`, the `primary` calendar, `sendUpdates="none"`, and Google's
404/410 handling, and converts known setup, SDK, and transport failures into
the service errors above. The shared service calls an `EventDeleter` and converts operation-specific
failures to `CalendarError`; routes do not inspect SDK exceptions. `GoogleEventNotFoundError` stays in the
same module because PATCH still uses it. `tests/test_google_delete_events.py`
checks the translation; `tests/test_delete_events.py` keeps the HTTP contract
tests. See [DELETE Level 3 verification](docs/DELETE_LEVEL3_VERIFICATION.md).

#### Level 4 event deletion provider injection

`get_event_deleter()` in `app/event_deletion_dependencies.py` is the only place that
selects `GoogleEventDeleter`; it returns it as an `EventDeleter`. FastAPI
supplies it to the shared service through a subdependency, so the route neither
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

See [DELETE Level 5 verification](docs/DELETE_LEVEL5_VERIFICATION.md) for real Google results, the operation's cost, and why the service uses one shared error format.

### Error format

Operations moved to Level 5 return failures in one shape, defined in
`app/errors.py`:

```json
{"error": {"code": "not_found", "message": "Event not found.", "retryable": false}}
```

| `code` | Status | When | Retry? |
| --- | --- | --- | --- |
| `invalid_input` | `400` | Malformed or empty JSON | No; fix the request |
| `invalid_input` | `422` | Valid JSON with invalid/missing/unknown fields, or a bad ID | No; fix the request |
| `not_found` | `404` | The resource does not exist or was deleted | No |
| `access_denied` | `403` | The provider refused access to the resource | No |
| `provider_error` | `502` | The provider failed or its result is unknown | Per operation; see `retryable` |
| `provider_unavailable` | `503` | The provider cannot be reached or authorization is not set up | Per operation; see `retryable` |

`message` is a short service-written sentence; provider error text, IDs from
provider responses, and credentials are never included. `retryable` tells the
caller whether repeating the same request unchanged is safe and useful.

Core operation failures cross the shared interface as `CalendarError` with
`ErrorCode` from `calendar_contract`. `app/errors.py` adds `ServiceError` HTTP
and log context. Calendar metadata and local ID validation use `ServiceError`
directly. The handlers registered in `app/main.py` render the envelope and log
one JSON line on the `calendar_service` logger:

```json
{"operation": "delete_event", "error": "not_found", "provider": true, "status": 404}
```

`provider` is true when the provider was called or caused the failure. 5xx
failures log at ERROR, others at WARNING, without stack traces, request bodies,
or tokens. The service has no request ID yet, so none is logged. DELETE, both
GETs, POST, PUT, and PATCH use this format, as do FastAPI request-validation
failures. Request-validation logs use the matched route's operation name and
`provider=false`; they never serialize the validation exception's inputs or body.

### Code map and request flow

FastAPI event routes in `app/main.py` receive `CalendarService` through
`get_calendar_service` in `app/calendar_service_dependencies.py`:

```text
HTTP input -> shared request model -> GoogleCalendarService
           -> existing Google adapter -> primary Google Calendar
           -> shared Event or CalendarError -> HTTP response
```

`GoogleCalendarService` in `app/calendar_service.py` delegates `create`, `get`,
`replace`, and `delete` to `GoogleEventCreator`, `GoogleEventReader`,
`GoogleEventUpdater`, and `GoogleEventDeleter`. PATCH is a full-field extension
using the same `replace` path. It still requires title and both times.

The existing operation factories remain FastAPI subdependencies. Tests may
replace an individual adapter or override `get_calendar_service` with another
implementation of the shared protocol. Overrides must be restored after tests.
Adapters remain responsible for authorization, SDK calls, field translation,
and closing clients. The shared service translates their known failures to
`CalendarError`; it does not log or retry operations. `app/errors.py` adds HTTP
status and safe error context and returns the common error envelope. The request
middleware emits one sanitized outcome log at request completion. Unexpected
programming errors propagate.

Calendar metadata remains an extension using `CalendarReader` and
`get_calendar_reader` in `app/calendar_dependencies.py`. It shares the HTTP
error envelope but is not a method of `CalendarService`. Authorization remains
noninteractive in every route; the separate setup script requests both scopes.
Synchronous route handlers keep blocking SDK work off the async event loop.

### Checks and testing

The [Level 3 observability guide](docs/OBSERVABILITY.md) describes request
counters, error categories, latency histograms, correlated logs, and request/RPC
traces. Lifespan-managed runs produce SDK trace IDs, also returned in
`X-Trace-ID` on responses reaching the middleware. Set
`CALENDAR_TELEMETRY_PROJECT` only when cloud export is wanted; local runs do not
discover cloud credentials. Cloud Run uses its runtime identity, separate from
Calendar OAuth. The guide covers bounded export, saturation, the Terraform
dashboard, and the separate deployed/teammate verification requirements.
See the [cloud evidence](docs/OBSERVABILITY_VERIFICATION.md) and
[Ka Pui walkthrough and Level 4 handoff](docs/OBSERVABILITY_HANDOFF.md).
Ka Pui completed independent interpretation in PR #49; deployment evidence for
the eventual reviewed merge remains pending.

Run the same commands on macOS, Linux, or Windows:

```sh
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run mypy scripts/deploy_release.py scripts/verify_put_live.py
uv run pytest -v
git diff --check
```

Ruff checks lint and formatting; mypy checks both app and tests in strict mode.
Configuration is in pyproject.toml and pytest.ini. GitHub Actions runs these
uv-based lint, formatting, type, and test checks on pushes and pull requests
using Python 3.14 on Linux. For intentional formatting changes, run
`uv run ruff format .` and review the diff.

CI also checks controlled shared conformance and both Terraform roots without
live Google calls or deployment credentials. See [DEPLOYMENT.md](docs/DEPLOYMENT.md#level-2-automated-deployment-and-recovery)
for deployment and recovery.

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


### Historical Level 2 integration status

The following status was recorded during HW1; current HW2 progress is in the
[adoption guide](docs/SHARED_CONTRACT_ADOPTION.md).

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
