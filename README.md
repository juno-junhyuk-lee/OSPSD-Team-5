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

Run commands from the repository root. Use Python 3.14. Installation and checks
were verified on Windows with Python 3.14.8; the foundation was also checked on
macOS with Python 3.14.2. Requirements are pinned in requirements.txt. On Windows,
pip also installs pytest's platform-specific colorama dependency.

macOS/Linux:

```sh
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Windows PowerShell:

```powershell
py -3.14 -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements.txt
```

Windows Git Bash:

```bash
py -3.14 -m venv .venv
source .venv/Scripts/activate
python -m pip install -r requirements.txt
```

Git Bash paths use forward slashes. The PowerShell commands below invoke the
virtual environment directly, so activation and execution-policy changes are
unnecessary.

### Run

macOS/Linux or activated Git Bash:

```sh
python -m uvicorn app.main:app --reload
```

PowerShell:

```powershell
./.venv/Scripts/python.exe -m uvicorn app.main:app --reload
```

Keep the server running while making requests in another terminal. Stop it with
Ctrl+C. Swagger UI: http://localhost:8000/docs

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

| Condition | HTTP status | JSON detail |
| --- | --- | --- |
| Google returns 404 | 404 | `Event not found` |
| Missing/invalid token, insufficient token scope, or failed refresh | 503 | `Calendar authentication required` |
| All-day event | 422 | `Only timed events are supported` |
| Other Google HTTP errors, handled transport failures, or malformed provider data | 502 | `Calendar provider request failed` |

The API does not expose provider error messages or launch browser login during
requests. For 503, rerun the authentication script. Error handling does not cover
every SDK exception; retry, cancellation, and uncertain write policies are later work.

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
`{"detail": "Calendar not found"}` before any Google request.
This operation does not list calendars or events and does not alter event routes.

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

### Create and retrieve an event

Install current requirements and complete Shared Google Calendar authentication
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
| Unknown or deleted ID (Google 404 or 410) | `404` | `{"detail": "Event not found"}` | No |
| Missing/invalid fields, timezone-free times, or `end_time <= start_time` | `422` | FastAPI `detail` array | No |
| Local authorization missing or unusable | `503` | `detail` naming the auth script | No |
| Google rejected the call, failed, or the response was unusable | `502` | update could not be confirmed | Uncertain — check calendar before retry |

Partial/optional fields, all-day events, and changing `id` are outside this
contract. Offline tests cover success with GET match, unknown ID, validation
without state changes, provider failures, and missing authorization. Real
Google verification evidence belongs in a follow-up Level 2 writeup.

### Event deletion contract

`DELETE /events/{event_id}` deletes one event from the shared test account's
`primary` Google Calendar. Ka Pui Cheung owns this operation through Levels 1–5.
It takes one required string path parameter, `event_id` (a Google event ID, as
returned by POST), and no query or body parameters.

| Result | Status | Body | Retry? |
| --- | --- | --- | --- |
| Deleted | `204 No Content` | empty | Not needed |
| Unknown or already-deleted ID (Google 404 or 410) | `404` | `{"detail": "Event not found"}` | No |
| Local authorization missing or unusable | `503` | `{"detail": "..."}` naming the auth script | After fixing setup |
| Google rejected the call, failed, or the response was lost | `502` | `{"detail": "..."}` | Yes |

Deleting the same ID twice returns `204` then `404`. Retrying after a `502` is
safe: if the first attempt succeeded, the retry returns `404`. Deletion uses
`sendUpdates="none"`, so attendees are not emailed. Raw Google errors are never
returned. See [DELETE Level 2 verification](docs/DELETE_LEVEL2_VERIFICATION.md).

### Code map and request flow

`app/main.py` owns the FastAPI routes.
Calendar GET calls `get_primary_calendar` in `app/google_calendar.py`,
which loads local OAuth authorization, retrieves Google metadata, and
returns the `Calendar` model. Unsupported calendar IDs return 404 locally.

Event GET calls `retrieve_event` in `app/google_events.py`, which requests
Google's `events.get` on `primary` and translates the result to `Event`.
`app/google_auth.py` loads and refreshes the local token for event retrieval.
Neither GET operation starts browser authorization during a request.

The synchronous handlers keep blocking SDK work off the async event loop.
Each request constructs its own authorized client. No cross-request client cache,
provider-independent interface, or retry layer is introduced at this level.

POST validates and normalizes `CreateEventRequest`, then calls
`create_google_event` in `app/google_create_events.py`. That module loads or
refreshes local event authorization, calls `events.insert` on `primary`, closes
the client, and translates the Google response to `Event`. Invalid input is
rejected before a write. Each creation request uses `num_retries=0`; an uncertain
result must be investigated before retrying. Authorization helpers remain
operation-specific at this level; the shared setup script obtains both scopes.

PATCH validates and normalizes `UpdateEventRequest`, then calls
`update_google_event` in `app/google_update_events.py`. That module reuses
POST's `load_credentials`, calls `events.patch` on `primary` once without
retries, and translates the response to `Event`. Google 404/410 raise
`GoogleEventNotFoundError`; the handler maps that and other failures to the
documented responses.

DELETE calls `delete_google_event` in `app/google_delete_events.py`, which
reuses POST's `load_credentials` and calls `events.delete` on `primary` once,
without retries. Google 404/410 raise `GoogleEventNotFoundError`; the handler
maps that and other failures to the documented responses.

### Checks and testing

macOS/Linux or activated Git Bash:

```sh
python -m pip check
python -m ruff check .
python -m ruff format --check .
python -m mypy
python -m pytest -v
git diff --check
```

PowerShell:

```powershell
./.venv/Scripts/python.exe -m pip check
./.venv/Scripts/python.exe -m ruff check .
./.venv/Scripts/python.exe -m ruff format --check .
./.venv/Scripts/python.exe -m mypy
./.venv/Scripts/python.exe -m pytest -v
git diff --check
```

Ruff checks lint and formatting; mypy checks both app and tests in strict mode.
Configuration is in pyproject.toml and pytest.ini. GitHub Actions runs lint,
formatting, types, and tests on pushes and pull requests using Python 3.14 on
Linux. For intentional formatting changes, run `python -m ruff format .` and
review the diff.

The fast suite runs without Google credentials or external network access.
It covers HTTP contracts, provider translation, event authentication,
and event failure cases. The shared fixture provides isolated provider data
for mocked Google insertion and retrieval. Data is populated by the fake insert,
not by the HTTP handler, so POST-to-GET checks exercise both provider paths.
Offline checks do not establish a live Google write.

Calendar HTTP tests use a controlled metadata lookup.
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

Token-file loading errors produce 503 with
`{"detail": "Google authorization unavailable"}`.
Handled Google HTTP/authentication errors and incomplete metadata produce
502 with `{"detail": "Calendar provider unavailable"}`.
Detailed failure handling, failure tests, and structured logging remain
future work; some unhandled failures may return 500.

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
Run all local checks and verify CI after resolving these conflicts.

### Shared Google Calendar authentication

The team uses one shared test account and its primary calendar. Enable the
Calendar API and create a Desktop OAuth client in the shared Cloud project.
For an External app in Testing, register the shared account as a test user and
configure `https://www.googleapis.com/auth/calendar.events` in Data Access.
The authentication script also requests `calendar.calendars.readonly` for
calendar metadata; add that scope in Data Access as well.

Privately obtain the client JSON and save it as `credentials.json` in the
repository root. Install the updated pinned requirements, then run:

```sh
# Windows Git Bash or PowerShell; no activation required
./.venv/Scripts/python.exe scripts/google_calendar_auth.py
```

On macOS/Linux, use `.venv/bin/python` instead. Sign in to the shared test account
in the browser and approve event access within five minutes. The script stores
`token.json` locally, refreshes usable expired tokens, and requests authorization
again if a token is revoked or lacks the agreed scope. Each teammate generates
their own local token. Never commit either JSON file or print its contents.

The verification request lists up to ten events from `primary` without changing
state. Copy a returned API event ID to verify that specific event:

```sh
./.venv/Scripts/python.exe scripts/google_calendar_auth.py --event-id EVENT_ID
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
