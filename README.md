# OSPSD-Team-5

This is Team 5's repository for CS 3943 OSPSD.

## Calendar service — Milestone 1

The service retrieves local calendar details and events through FastAPI.
POST now calls Google Calendar and mirrors a successful result for local GET.
Offline checks and one real POST run cover this integration; a second teammate's
real verification and Level 2 PR review/CI remain pending.
Jim Lo owns event creation through Levels 1–5. Its public contract is below.

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
idempotency. The Google event persists independently of the server. Successful
results are temporarily mirrored in memory for the current local GET route;
this mirror is lost on restart and is not shared across workers. Real GET
integration remains separate work. All-day events are outside this contract.

Setup failure returns 503 with a `detail` string directing the developer to the
authorization script. Provider HTTP/transport failure or an unusable response
returns 502 with a `detail` string stating that creation could not be confirmed
and to check the calendar before retrying. Neither failure adds a local mirror
or falls back to local creation. A 502 does not guarantee that Google created
no event; do not blindly repeat a write with an uncertain result. Raw provider
errors and credential contents are not included in these HTTP responses.

Acceptance requires HTTP tests demonstrating successful
creation, retrieval through GET, distinct IDs for repeated creation, and
rejection without state changes for the invalid inputs above. Existing GET
tests must continue to pass, and creation tests must restore local state so
they remain independent. Another teammate must review the contract,
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
The rejected request must not create an event. Restarting removes local mirrors;
the current GET then returns `404` for their IDs, while Google events remain.

### Code map and request flow

`app/main.py` owns the FastAPI app, local calendar/event mappings, and GET/POST
handlers. Calendar retrieval uses the `Calendar` model in `app/models.py` to
return metadata; unknown IDs produce the documented calendar 404.
FastAPI parses the path parameter, the handler looks up the ID, and the existing
`Event` model in `app/models.py` defines the serialized success response. A missing
ID raises HTTPException, which FastAPI renders as the documented 404 JSON.
There are no SDK calls or credentials in this path.

For POST, `CreateEventRequest` in `app/models.py` validates and normalizes the
input before the handler runs. The handler calls `create_google_event`, which
loads authorization, creates the Google event, and translates the response.
Only a successful translated result is stored in the local mirror and returned
with status 201. Setup/provider failures return the errors documented above.

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
HTTP tests also use a scoped SDK mock from this fixture, exercising the actual
creation/translation module without accessing credentials or making requests.

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
- Provider integration: Google IDs and outgoing fields are checked, invalid
  input makes no provider write, and setup/provider failures leave local state
  unchanged. A simulated accepted write with a lost response returns 502 without
  retrying; the caller is told to investigate the calendar.
- Responsiveness: a controlled SDK call signals that it started and waits for
  release while an unrelated GET completes. Cleanup releases the call even on
  failure; no arbitrary sleep establishes the ordering. This is an in-process
  TestClient check, not a live single-worker server demonstration.

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
all-day support, multi-worker sharing, or durability. Juno reproduced the POST
checks locally, and PR #5 was approved and merged with passing CI. The
PowerShell walkthrough has not been executed locally. Real POST provider
verification remains Level 2 work.

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
This setup script does not replace the FastAPI endpoint's local lookup yet.
The flow follows the [Google Python quickstart](https://developers.google.com/workspace/calendar/api/quickstart/python).


### Level 2 POST handoff

The creation module, HTTP connection, and offline tests are implemented;
one real-provider run has passed. A second teammate's run and PR review/CI remain
pending. Jim connected POST to `primary`
using `events.insert`. The existing `calendar.events` scope permits creation;
see Google's [events.insert documentation](https://developers.google.com/workspace/calendar/api/v3/reference/events/insert).

Preserve the three request fields, title normalization, time validation, 201
response, and four-field `Event` model. Invalid input must return 422 before
any provider write. Callers do not supply the ID or calendar configuration.

| Public field | Google field | Translation |
| --- | --- | --- |
| `title` | `summary` | Send the normalized title; translate the result back. |
| `start_time` | `start.dateTime` | Send RFC 3339 with an offset; preserve the instant on return. |
| `end_time` | `end.dateTime` | Send RFC 3339 with an offset; preserve the instant on return. |
| `id` | `id` | Return Google's event ID; do not require the Level 1 UUID format. |

Let Google assign the event ID. Repeated valid requests still create distinct
events. Hide other provider fields, credentials, and configuration from the
public response. Timed events remain the supported input; all-day events,
attendees, and recurring-event options are outside this contract.

#### Local setup for the integration

Reuse the shared setup merged in [PR #6](https://github.com/juno-junhyuk-lee/OSPSD-Team-5/pull/6).
Do not create another Cloud project or OAuth client. From the repository root:

1. Install the current pinned requirements using the Installation instructions.
2. Obtain the shared client JSON privately and save it as `credentials.json`.
3. Run the existing authentication script and sign in to the shared test account:

   ```sh
   # macOS/Linux
   .venv/bin/python scripts/google_calendar_auth.py
   ```

   ```powershell
   # Windows
   ./.venv/Scripts/python.exe scripts/google_calendar_auth.py
   ```

4. Keep the generated `token.json` on your own machine. Both JSON files are
   ignored by Git; do not include their contents in logs, PRs, or test fixtures.

The HTTP integration loads local authorization and refreshes an
expired usable token when needed. Browser authorization stays in the setup
script, outside HTTP requests. Missing or unusable authorization must be
reported as a setup problem, without silently falling back to local creation.

#### Integration and verification plan

`app/google_calendar.py` loads `token.json`, checks the event scope, refreshes
usable expired authorization, and saves refreshed tokens locally. It does not
start browser authorization. `create_google_event` inserts into `primary` and
validates Google's returned ID, title, and timed-event fields before returning
an `Event`. Extra Google fields are excluded from the public result.
Setup failures raise `GoogleCalendarSetupError`; provider failures and unusable
responses are handled by the route as documented 503/502 responses. Creation uses
`execute(num_retries=0)`, including when the response may have been lost.

[Module tests](tests/test_google_calendar.py) replace token loading and SDK
responses with scoped mocks. They check outgoing fields, returned provider IDs,
time instants across offsets, repeated creation, unusable responses, and errors
without retries. Authorization tests use temporary files and controlled refresh
results to check missing/malformed tokens, scope, reuse, refresh, and revocation.
All token values in these tests are fictional. No credentials or live requests
are needed; these checks do not establish real-provider correctness.

The synchronous route runs the blocking SDK call through FastAPI's thread pool.
The final provider interface and dependency injection belong to later levels.

The event GET route currently reads local data. During this transition, mirror
only a successfully created and translated Google event into the local mapping,
using its Google ID, to preserve same-process POST-to-GET behavior. This mirror
is not evidence of provider persistence and disappears on restart; the Google
event remains. Once Kristie's GET uses Google on the same calendar, coordinate
removal of the mirror and verify the real POST-to-GET workflow together.

Level 1 contract assertions and existing GET tests are preserved. Fast tests control
SDK responses without credentials or network access and verify field mapping,
provider IDs, repeated creation, and invalid requests causing no provider write.
Rejected writes must not produce a local success mirror. Do not automatically
retry creation; a timeout can leave an event created even if no response arrived.
Comprehensive failure translation remains Level 5 work.

Real verification will start the service and POST a uniquely named timed test
event through HTTP. Check 201 and the four response fields, then independently
read the returned ID from Google using the existing script:

```sh
.venv/bin/python scripts/google_calendar_auth.py --event-id <returned-id>
```

Replace `<returned-id>` before running. On Windows, use the Python executable
shown above. Compare the title and time instants against the submitted request;
if the script does not display the times, inspect them in Google Calendar or a
provider read. Record the revision, commands, expected/observed results, and any
gaps. Remove only the test events created for this verification from the shared
calendar and confirm cleanup; stopping the server does not remove Google events.

Before merging, a teammate must review the provider call, authentication,
translation, and ID assumptions. At least two team members must run POST against
Google, each with their own local token. Authentication-only verification does
not establish POST Level 2 completion. Jim's environment has completed real POST,
independent Google reads, persistence checks, and test-event cleanup. Another
teammate's real POST verification remains pending.

Follow [POST Level 2 verification](docs/POST_LEVEL2_VERIFICATION.md) for the
separately runnable workflow, independent Google time checks, persistence,
cleanup, and current evidence. Each teammate records their own real run.


## Contributor documentation

- [AGENTS.md](AGENTS.md): code map, contributor instructions, and review/release rules.
- [Work plan](docs/WORK_PLAN.md): owners, progress, and milestone responsibilities.

## Team Members

- Juno Lee
- Niriti Pahadi
- Kristie Lee
- Jim Lo
- Ka Pui Cheung
