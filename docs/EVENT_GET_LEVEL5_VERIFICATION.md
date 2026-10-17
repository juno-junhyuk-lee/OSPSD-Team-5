# Event GET Level 5 verification

Kristie Lee owns `GET /events/{event_id}`. Codex assisted with implementation,
tests, documentation, and the executions recorded below. These results verify
the local implementation; they do not establish teammate approval, PR CI,
a published release, or a final-tag checkout.

The original verification below applies to `9fad9af`. The later
[cancelled-event review follow-up](#cancelled-event-review-follow-up) records
the regression fix separately; earlier results are preserved as history.

## Revision and environment

- Implementation: `9fad9af0de1bcf10279d2383ed3889cf494e7c37`.
- Branch: `feature/calendar-event-get-level5-errors`.
- Date: October 17, 2026, America/New_York. Live verification began at
  00:13 EDT (04:13 UTC).
- Windows PowerShell, Python 3.14.8, uv, locked `uv.lock` dependencies.
- The implementation working tree was clean before verification. Subsequent
  edits for this documentation commit do not change application or test code.

## Checks executed

| Command | Result |
| --- | --- |
| `uv sync --frozen` | Environment synchronized; 50 packages checked |
| `uv run --frozen python --version` | Python 3.14.8 |
| `uv run --frozen ruff check .` | Passed |
| `uv run --frozen ruff format --check .` | 52 files formatted |
| `uv run --frozen mypy` | No issues in 35 source files |
| `uv run --frozen pytest -q` | 212 passed; one existing TestClient deprecation warning |
| `git diff --check` | Passed |

The existing warning concerns Starlette TestClient's deprecated `httpx`
integration. Dependencies were not changed or warnings suppressed.

## Coverage and boundaries

- `tests/test_events.py` injects a controlled `EventReader`: exact success/error
  responses, invalid IDs before a reader call, ID length boundaries, recurring
  instances, HTTP status, retryability, and one sanitized failure log. Each
  fixture restores previous dependency overrides.
- `tests/test_google_events.py` covers Google response translation, 401, 404,
  permission denial versus quota/rate-limit 403, temporary HTTP/transport
  failures, malformed data, all-day events, client cleanup, and propagation of
  unexpected programming errors. HTTP regression tests exercise those mappings.
- `tests/test_google_auth.py` verifies local token and refresh behavior, including
  the provider-involvement flag: local setup failure is false; remote refresh
  failure is true. Google 401 also logs provider=true.
- Other operations retain their existing behavior. The shared `ServiceError`
  renderer/logger and DELETE implementation were reused without changes.

Controlled tests check the public HTTP result independently of SDK failures.
Adapter tests separately check that SDK outcomes reach the correct service
error. Neither set alone proves real Google integration.

A separate run of `tests/test_events.py` passed all 18 cases with external
socket `connect`/`connect_ex` calls blocked and both real credential loading and
Google client creation configured to fail if used. Loopback was allowed for
Windows event-loop internals. This demonstrates controlled-reader isolation;
the full 212-test run was not executed under these additional guards.

## Real Google verification executed

A separate Python process used FastAPI TestClient with **no dependency
overrides** and the local authorization. `get_event_reader()` selected
`GoogleEventReader` normally. The verifier first listed up to ten events from
the authenticated account's primary calendar and selected an existing timed
event. It compared the HTTP response with that independent Google read; no
private event values or credentials were included in the output.

| Request | Observed result |
| --- | --- |
| GET existing timed event | 200; exactly `id`, `title`, `start_time`, `end_time`; ID/title and datetime instants matched the independent Google read; no failure log |
| GET random 32-character hexadecimal ID | Real Google 404 translated to 404 / `not_found` / `retryable=false`; one failure log with provider=true |
| GET `/events/bad%20id!` | 422 / `invalid_input` / `retryable=false`; one failure log with provider=false |

Recorded missing-event response:

```json
{"error": {"code": "not_found", "message": "Event not found.", "retryable": false}}
```

Recorded failure logs:

```json
{"operation": "get_event", "error": "not_found", "provider": true, "status": 404}
{"operation": "get_event", "error": "invalid_input", "provider": false, "status": 422}
```

The actual response and log counts were asserted during execution. No events
were created, updated, or deleted, so no event cleanup was needed. Authentication
may refresh the local token; that file remains private and untracked.

Permission denial, rate limiting, outages, malformed responses, expired/revoked
authorization, and recurring-instance success were simulated in automated tests;
they were not induced against Google during this run. This execution used
TestClient rather than a separately running Uvicorn server or a human-observed
curl demonstration.

## Cancelled-event review follow-up

On October 17, 2026, kc5931's
[PR #30 review](https://github.com/juno-junhyuk-lee/OSPSD-Team-5/pull/30#pullrequestreview-5558912210)
reported that event GET returned 200 after deletion. Google can retain a
`status="cancelled"` record, while the public contract treats deleted resources
as missing. The existing DELETE-to-GET test had explicitly expected 200.

The follow-up rejects cancelled records in `GoogleEventReader.get_event` after
checking for a dictionary but before translating fields. Both full event bodies
and ID/status-only records therefore raise `EventNotFoundError`; the existing
HTTP handler returns 404/not_found, retryable=false, with one provider=true log.
DELETE implementation and the shared error handler were not changed.

Verification was executed on the uncommitted follow-up working tree based on
`997261f`, on Windows/Python 3.14.8. This does not claim a test of a future commit
SHA or updated PR CI.

- Before the implementation fix, the new HTTP cases failed with 200 for a full
  cancelled event and 502 for a minimal cancellation record; the updated
  DELETE-to-GET expectation also failed with 200. All three selected tests failed,
  demonstrating that the regression checks detect the defect.
- After the fix, all 216 tests passed, Ruff lint/format checks passed (53 files
  formatted), strict mypy reported no issues in 35 source files, and
  `git diff --check` passed. The existing TestClient warning remains.
- New adapter cases verify that full and minimal cancelled responses raise
  `EventNotFoundError`. HTTP cases verify exact 404 JSON, one sanitized log, and
  client cleanup. The CRUD test retains the fake cancelled record but now
  verifies that public GET returns 404 after DELETE.
- A separate real Google run listed up to 100 events with `showDeleted=True`,
  selected an already-cancelled event, and retrieved its ID through TestClient
  using normal FastAPI injection with no overrides. It returned the exact
  404/not_found/retryable=false response and one provider=true failure log.
  No events were created, updated, or deleted in this verification.

The post-fix live run checked an existing cancelled record; a new live
POST/DELETE/GET sequence was not performed. That sequence is covered by the
offline integration test. Updated teammate review and CI remain required after
the owner commits and pushes the follow-up.

## Reproduce in PowerShell

### Prepare the checkout and authorization

Open PowerShell in the repository root. Record the revision and environment:

```powershell
git branch --show-current
git rev-parse HEAD
git status --short
uv sync --frozen
uv run python --version
```

For the current owner environment, local credentials and a token were present
and the real requests above succeeded. Another verifier needs their own local
authorization following the README. If authorization needs repair, privately
obtain `credentials.json`, then run:

```powershell
uv run python scripts/google_calendar_auth.py
```

If a browser opens, select the agreed test account and approve the requested
scopes. External reviewers follow the README's External reviewers instructions.
Do not publish either JSON file or browser authorization details. The script
lists up to ten events and prints API event IDs; choose an existing **timed test
event** on that account's primary calendar. A Calendar web URL is not an API ID.
Do not rely on an old example ID being present in a different account.

### Start the HTTP server

In terminal A, run:

```powershell
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Wait for application startup to complete and keep this terminal open. If port
8000 is occupied, use another unused port and change every URL below to match.

### Check the success response

In terminal B, also in the repository root, replace the placeholder:

```powershell
$eventId = 'PASTE_TIMED_TEST_EVENT_API_ID'
curl.exe -i "http://127.0.0.1:8000/events/$eventId"
```

Expect 200 and exactly the four public event fields. Compare the title and
start/end instants with the test event. Equivalent timezone representations
can express the same instant. There should be no `calendar_service` failure
line for this request; Uvicorn's normal access log is separate.

### Check a real missing-resource failure

Use a newly generated, syntactically valid ID:

```powershell
$missingId = [guid]::NewGuid().ToString('N')
curl.exe -i "http://127.0.0.1:8000/events/$missingId"
```

Expect 404 and the `not_found` response above. Terminal A should show exactly
one application failure line with operation=get_event, error=not_found,
provider=true, status=404. A 503 authentication response means this request did
not verify a real missing resource; repair authorization and repeat it.

### Check local input validation

```powershell
curl.exe -i 'http://127.0.0.1:8000/events/bad%20id!'
```

Expect 422 with code=invalid_input and retryable=false. Terminal A should show
one application failure line with provider=false and status=422. This is local
rejection, not evidence of a Google failure.

### Record results and stop

Record the tested SHA, working-tree changes if any, OS/Python version, expected
versus actual status/code/retryability, and sanitized log lines in the PR or a
review. The owner may also record this server/curl run for the demonstration.
Do not publish private event data or authentication files. Stop terminal A with
Ctrl+C. No event cleanup is required for these GET-only steps.

## Review and release handoff

- Assign a teammate reviewer. Confirm the operation-specific retry policy and
  shared error contract before merging.
- The reviewer should inspect provider exception translation, narrow exception
  handling, ID validation before reader calls, error subclass ordering, sanitized
  logs, local-versus-remote auth logging, and dependency override restoration.
- After the owner commits/pushes the documentation, link this evidence and CI for
  the exact PR revision. Record later runs against their actual SHA; do not label
  this implementation-SHA run as a test of a later commit or release tag.
- Team-wide request-validation migration, other operations, final release/tag
  verification, demonstration participation, and private reflection remain
  separate milestone responsibilities.

The sibling-team logging suggestion is addressed for event GET by routing
expected failures through the existing shared handler; no additional provider
or route logger is required. The GET contract exposes stable service codes,
statuses, safe messages, and retryability. SDK exceptions and provider payloads
remain internal. Narrow errors require a few explicit mappings, but avoid
hiding programming defects behind a generic provider response. Revisit the
mapping when a documented provider outcome is not represented accurately.
