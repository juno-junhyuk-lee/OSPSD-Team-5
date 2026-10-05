# OSPSD-Team-5

This is Team 5's repository for CS 3943 OSPSD.

## Calendar service — Milestone 1, Level 1

The service retrieves calendar details and retrieves and creates local events
through FastAPI. These operations are implemented with offline HTTP tests. Google Calendar
integration remains for Level 2; the contracts below are the handoff boundaries.
Jim Lo owns event creation through Levels 1–5. Its Level 1 contract is below.

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

### API contract

`GET /events/{event_id}` retrieves one calendar event without changing state.
It takes one required string path parameter, `event_id`, with no required query
or body parameters. Success returns `200 OK` with exactly four fields: string
`id` and `title`, and ISO 8601 datetime strings `start_time` and `end_time`.
Level 1 uses local data and has no authentication.

Git Bash/macOS/Linux:

```sh
curl -i http://localhost:8000/events/test-event
curl -i http://localhost:8000/events/missing-event
```

PowerShell: use `curl.exe -i` with the same URLs to invoke curl directly.
The known ID returns 200 and:

```json
{
  "id": "test-event",
  "title": "Example Event",
  "start_time": "2026-10-05T18:00:00Z",
  "end_time": "2026-10-05T19:00:00Z"
}
```

`test-event` is predefined. POST-created events are also available through GET
in the same process. Unknown IDs return `404 Not Found` with
`{"detail": "Event not found"}`. Restarting retains only the predefined event;
created events are not persisted.

### Calendar details contract

`GET /calendars/{calendar_id}` retrieves calendar metadata without changing state.
It helps callers identify their calendar and its timezone. `calendar_id` is a
required string path parameter; no query or body parameters are required.
Juno Lee owns this operation through Levels 1–5. Level 1 uses fixed local data
and requires no authentication.

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

Only `primary` is locally defined. Its ID is a service lookup alias and remains
`primary` in the response; callers must not interpret it as a Google account ID.
The timezone is an IANA timezone name. Other IDs return `404 Not Found` with
`{"detail": "Calendar not found"}`. Restarting retains the fixed calendar data.
This operation does not list calendars or events and does not alter event routes.

### Event creation contract

`POST /events` creates one timed event in the service's local memory. Jim Lo
owns this operation, including its implementation, tests, and documentation
through Levels 1–5. This endpoint implements the Level 1 behavior below.

The request uses `Content-Type: application/json` and requires three body fields:

| Field | Type | Rule |
| --- | --- | --- |
| `title` | string | Strip leading and trailing whitespace; the result must not be empty. |
| `start_time` | ISO 8601 datetime string | Must include a UTC offset or `Z`. |
| `end_time` | ISO 8601 datetime string | Must include a UTC offset or `Z` and represent an instant after `start_time`. |

There are no required path or query parameters. The caller does not supply
the event ID; the service generates it. For example:

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
request. Repeated requests receive different IDs; Level 1 does not provide
idempotency. Created events are process-local and are lost on restart. The
Level 1 workflow assumes one server process, with no cross-worker sharing,
provider authentication, Google Calendar writes, or durable storage. All-day
events are outside this timed-event contract.

Acceptance requires HTTP tests demonstrating successful
creation, retrieval through GET, distinct IDs for repeated creation, and
rejection without state changes for the invalid inputs above. Existing GET
tests must continue to pass, and creation tests must restore local state so
they remain independent. Another teammate must review the contract,
implementation, tests, and documentation; the reviewer is not assigned yet.

### Create and retrieve an event

Start the server using the Run instructions above. In another terminal,
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
The rejected request must not create an event. Restarting the server removes
created events; GET then returns `404` for their IDs.

### Code map and request flow

`app/main.py` owns the FastAPI app, local calendar/event mappings, and GET/POST
handlers. Calendar retrieval uses the `Calendar` model in `app/models.py` to
return metadata; unknown IDs produce the documented calendar 404.
FastAPI parses the path parameter, the handler looks up the ID, and the existing
`Event` model in `app/models.py` defines the serialized success response. A missing
ID raises HTTPException, which FastAPI renders as the documented 404 JSON.
There are no SDK calls or credentials in this path.

For POST, `CreateEventRequest` in `app/models.py` validates and normalizes the
input before the handler runs. The handler generates an unused ID, stores the
new `Event` in local memory, and returns it with status 201.

A dictionary keeps the one-ID lookup simple and makes the local implementation
easy to replace in Level 2. No provider interface or dependency injection is
needed for this level.

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

Testing strategy: the GET and POST suites exercise the HTTP boundary through
TestClient without a server, network access, or Google credentials.
[tests/conftest.py](tests/conftest.py) restores local events after each test,
including failures. Expected values are independent of the application's data.

- [Calendar GET tests](tests/test_calendars.py): primary returns 200 with exact
  metadata JSON; unknown IDs return the documented calendar 404.
- [Event GET tests](tests/test_events.py): known ID returns 200 with exact JSON;
  unknown ID returns the documented 404.
- [POST tests](tests/test_create_events.py): creation returns 201 with the four
  response fields, a generated ID, a trimmed title, and the correct instants.
  GET retrieves the same event; repeated creation produces distinct IDs.
- Invalid creation: missing fields, blank or invalid titles, malformed or
  timezone-free times, numeric timestamps, and equal/reversed time ranges
  return 422 with a `detail` array and leave local events unchanged.
- Time boundaries: ordering is checked across different UTC offsets, including
  a valid end time whose displayed local hour is earlier than the start hour.

On October 4, 2026, the POST implementation was verified on macOS with Python
3.14.8: all 22 tests, Ruff lint/format checks, strict mypy, dependency compatibility
(`uv pip check`), and `git diff --check` passed. TestClient emits an existing
Starlette deprecation warning with the pinned HTTPX dependency.

A single-worker Uvicorn server on `127.0.0.1:8765` was also checked with curl:
POST returned 201 with a trimmed title, GET returned the same event with 200,
an equal-time request returned 422, and the predefined event remained unchanged.
The server was stopped after verification.

Defect-detection evidence: temporarily changing the in-memory title to
`Incorrect Event` made `test_get_known_event` fail at its JSON assertion:

```text
{'title': 'Incorrect Event'} != {'title': 'Example Event'}
```

The original title was restored without modifying source files, and both tests
passed again. Include this evidence in the implementation PR.

For POST, temporarily discarding writes to the local event mapping made
`test_create_and_retrieve_event` fail: POST returned 201, but the following GET
returned 404 instead of 200. Restoring the mapping made the test pass. The
experiment changed only in-memory behavior; source files were not modified.

These checks establish local behavior, not Google integration, authentication,
all-day support, multi-worker sharing, or durability. Teammate verification from
another checkout, POST review, and CI for this branch remain pending. The
PowerShell walkthrough has not been executed locally.

### Level 2 event GET handoff

The Level 2 owners should replace the local lookup in `app/main.py` with a Google
Calendar lookup using the authenticated user's `primary` calendar. Preserve the
route, `Event` response model, and Level 1 tests. Do not expose `calendar_id` or
raw Google fields. The planned field mapping is `summary` to `title`,
`start.dateTime` to `start_time`, and `end.dateTime` to `end_time`; verify provider
assumptions against its documentation and a real test account.

The local GET fixture represents a timed event. Agree on missing-title and
all-day behavior before claiming support for GET. The shared response model
does not enforce timezone awareness or start/end ordering; POST validates
those rules separately in its creation request model.

Google authentication, configuration, and real-provider verification remain
Level 2 work. Keep secrets and generated tokens out of Git. Keep fast tests
independent of live credentials when replacing the local implementation, and
document how at least two teammates can verify the real integration.

### Level 2 calendar details handoff

Retrieve the authenticated user's primary calendar from Google,
map `summary` to `title` and `timeZone` to `time_zone`, and retain the service
alias `primary` as the response ID. Confirm metadata permissions separately:
the event CRUD scope is not automatically sufficient for calendar metadata.
Google's returned title and timezone replace the fixture values; decide any
missing-title behavior before integration. Other calendar IDs remain unsupported
until the team intentionally expands the contract. No Google lookup is added
in Level 1.

### Level 2 POST handoff

Jim will replace the local creation write with an authenticated Google Calendar
write while preserving the POST request, 201 response, and validation rules.
Invalid local input must be rejected before calling the provider.

Use Google's [events.insert documentation](https://developers.google.com/workspace/calendar/api/v3/reference/events/insert)
to verify the operation and write permissions. Translate `title` to `summary`,
`start_time` to `start.dateTime`, and `end_time` to `end.dateTime`. Translate the
created provider event back to the four-field `Event` response. Its returned ID
must work with the team's GET implementation on the same calendar; callers
must not depend on Level 1's UUID format. Agree on the target test calendar
and configuration with the team before integrating the operations.

Keep fast tests offline by controlling the provider result. Separately document
credentials, configuration, a real create/read verification, and cleanup of test
events. Record behavior for rejected writes and uncertain outcomes rather than
assuming a timeout means no event was created. No Google writes or provider
failure handling have been verified by the Level 1 implementation.

## Contributor documentation

- [AGENTS.md](AGENTS.md): code map, contributor instructions, and review/release rules.
- [Work plan](docs/WORK_PLAN.md): owners, progress, and milestone responsibilities.

## Team Members

- Juno Lee
- Niriti Pahadi
- Kristie Lee
- Jim Lo
- Ka Pui Cheung
