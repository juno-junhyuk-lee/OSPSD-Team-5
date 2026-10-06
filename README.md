# OSPSD-Team-5

This is Team 5's repository for CS 3943 OSPSD.

## Calendar service — Milestone 1

Kristie Lee owns `GET /events/{event_id}` through Levels 1–5. This operation
now retrieves timed events from Google Calendar using locally authorized tokens.
Calendar metadata retrieval and event creation still use their Level 1 local
implementations. Jim Lo owns creation and Juno Lee owns calendar metadata.

This branch is in a transitional state: local POST events are not written to
Google and cannot be retrieved by the Google-backed GET. The shared create/read
workflow requires POST Level 2 integration. Fast tests use a controlled provider
response to retain the earlier Level 1 create/read checks.

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
overwrite an existing event. These IDs refer to process-local data; they are not
retrievable through the Google-backed GET until POST Level 2 is integrated.

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

Creation tests verify successful writes, validation and local state cleanup.
The provider fake retains historical create/read coverage; a real create/read
workflow remains pending POST integration. Review and verification details are
in the [work plan](docs/WORK_PLAN.md) and [verification notes](docs/VERIFICATION.md).

### Code map and request flow

`app/main.py` owns the FastAPI routes and the local calendar/POST mappings.
For event GET, FastAPI parses the ID and calls `retrieve_event` in
`app/google_events.py`. That module makes Google's `events.get` request on
`primary` and converts the result to `Event` in `app/models.py`.
`app/google_auth.py` loads the repository-root token and refreshes it when needed.
No browser login occurs on an HTTP request. SDK objects stay within the Google
modules; routes receive the public model or service-specific exceptions.

The synchronous GET handler keeps blocking SDK work off the async event loop.
Each request constructs its own authorized client. No cross-request client cache,
provider-independent interface, or retry layer is introduced at this level.

Calendar GET still uses `LOCAL_CALENDARS`. POST still validates with
`CreateEventRequest`, generates an unused ID, and stores an Event in `LOCAL_EVENTS`.
Their Google integrations belong to their respective operation owners.

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
It covers HTTP contracts, provider response translation, token handling and
failure cases. The shared fixture restores local state and substitutes the
Google client. Its local POST-to-GET checks do not establish a live Google write.

All 46 tests, Ruff and strict mypy passed on Windows with Python 3.14.8. A real
Google request through FastAPI TestClient verified event retrieval and missing-ID
handling. A second member's endpoint reproduction, edge-case policy review and
this PR's CI are pending. TestClient emits an existing Starlette deprecation warning.

See [verification notes](docs/VERIFICATION.md) for test coverage, defect-detection
evidence, real-provider reproduction steps and historical Level 1 verification.

### Shared Google Calendar authentication

The team uses one shared test account and its primary calendar. Enable the
Calendar API and create a Desktop OAuth client in the shared Cloud project.
For an External app in Testing, register the shared account as a test user and
configure `https://www.googleapis.com/auth/calendar.events` in Data Access.
The authentication script requests this scope for all event operations.

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
The setup script authorizes the account; the FastAPI event GET now uses that token.
The flow follows the [Google Python quickstart](https://developers.google.com/workspace/calendar/api/quickstart/python).


### Remaining provider integrations

Calendar metadata and POST remain local. Their owners will connect them to
Google while preserving their contracts. The live create/read workflow becomes
available after POST writes to the same primary calendar that GET reads.
[Integration notes](docs/VERIFICATION.md) retain the operation-specific handoffs.

## Contributor documentation

- [AGENTS.md](AGENTS.md): code map, contributor instructions, and review/release rules.
- [Work plan](docs/WORK_PLAN.md): owners, progress, and milestone responsibilities.

## Team Members

- Juno Lee
- Niriti Pahadi
- Kristie Lee
- Jim Lo
- Ka Pui Cheung
