# OSPSD-Team-5

This is Team 5's repository for CS 3943 OSPSD.

## Calendar service — Milestone 1, Level 1

The service retrieves one locally defined calendar event through FastAPI.
The GET endpoint and two offline HTTP tests are implemented. Google Calendar
integration remains for Level 2; the public contract below is the handoff boundary.

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

Only `test-event` is locally defined. Other IDs return `404 Not Found` with
`{"detail": "Event not found"}`. Restarting the service retains the fixed data;
there is no persistence or write operation.

### Code map and request flow

`app/main.py` owns the FastAPI app, local event mapping, and GET handler.
FastAPI parses the path parameter, the handler looks up the ID, and the existing
`Event` model in `app/models.py` defines the serialized success response. A missing
ID raises HTTPException, which FastAPI renders as the documented 404 JSON.
There are no SDK calls or credentials in this path.

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

Testing strategy: [tests/test_events.py](tests/test_events.py) exercises the HTTP
boundary through TestClient without starting a server, using network access, or
requiring Google credentials. Each test uses a scoped client with cleanup.

- Known ID: check 200 and exact JSON, detecting missing/extra fields or wrong values.
- Unknown ID: check 404 and the documented error, detecting an incorrect success.

Expected values are written independently of the application's lookup data.
Both tests and all code checks passed locally on Python 3.14.8. TestClient emits
a Starlette deprecation warning with the pinned HTTPX dependency; tests still pass.

Defect-detection evidence: temporarily changing the in-memory title to
`Incorrect Event` made `test_get_known_event` fail at its JSON assertion:

```text
{'title': 'Incorrect Event'} != {'title': 'Example Event'}
```

The original title was restored without modifying source files, and both tests
passed again. Include this evidence in the implementation PR.

These tests establish the local HTTP contract. They do not verify Google
Calendar, authentication, or all-day events. Teammate setup and curl verification
from another checkout, implementation review, and CI for the implementation PR
remain pending.

### Level 2 handoff

The Level 2 owners should replace the local lookup in `app/main.py` with a Google
Calendar lookup using the authenticated user's `primary` calendar. Preserve the
route, `Event` response model, and Level 1 tests. Do not expose `calendar_id` or
raw Google fields. The planned field mapping is `summary` to `title`,
`start.dateTime` to `start_time`, and `end.dateTime` to `end_time`; verify provider
assumptions against its documentation and a real test account.

The local fixture represents a timed event. Agree on missing-title and all-day
behavior before claiming support. The current model does not enforce timezone
awareness or start/end ordering; those guarantees are not part of this contract.

Google authentication, configuration, and real-provider verification remain
Level 2 work. Keep secrets and generated tokens out of Git. Keep fast tests
independent of live credentials when replacing the local implementation, and
document how at least two teammates can verify the real integration.

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

## Contributor documentation

- [AGENTS.md](AGENTS.md): code map, contributor instructions, and review/release rules.
- [Work plan](docs/WORK_PLAN.md): owners, progress, and milestone responsibilities.

## Team Members

- Juno Lee
- Niriti Pahadi
- Kristie Lee
- Jim Lo
- Ka Pui Cheung
