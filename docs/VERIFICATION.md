# Verification and integration notes

## Event GET Level 5 verification

On October 17, 2026, implementation `9fad9af` passed locked environment setup,
Ruff lint/format, strict mypy, all 212 tests, and diff checks on Windows with
Python 3.14.8. A separate controlled-reader run passed all 18 cases with external
connections, real credential loading, and real Google client creation blocked.
The existing TestClient deprecation warning remains.

Real Google reads through normal FastAPI injection and TestClient verified 200
with four public fields matching an independent Google read, real 404/not_found,
and local 422/invalid_input. Each failure logged exactly one sanitized line with
the correct provider flag. No events were changed. This is implementation
verification, not a server/curl demo, teammate execution, or final-tag verification.
See [the full record and PowerShell guide](EVENT_GET_LEVEL5_VERIFICATION.md).
Teammate review, matching PR CI, and final release verification remain pending.
Earlier sections below describe their historical revisions and error contracts.

## POST Level 4 verification

Implementation commit `c54f52e` was verified on October 12, 2026, in Jim's macOS
environment with Python 3.14.8. All 130 tests and required checks passed. The 15
controlled creator cases also passed with socket connections and real credential
loading blocked, and an earlier creator override was restored afterward.

Real HTTP requests through normal FastAPI injection verified POST 201, matching
GET and independent Google reads, invalid POST 422 without a created event,
calendar metadata and missing-ID responses, and restart persistence. Only this
run's event was deleted and confirmed cancelled; the server was stopped.
See [POST Level 4 verification](POST_LEVEL4_VERIFICATION.md) for wiring,
substitution, reproduction steps, environment details, and results. Teammate
review of both paths, matching PR CI, and release verification remain pending.

## POST Level 3 verification

Implementation commit `8741c90` was verified on October 12, 2026, in Jim's macOS
environment with Python 3.14.8. All 115 offline tests and required checks passed;
the tests also passed with external socket connections blocked. Real HTTP POST
returned 201, HTTP GET returned matching JSON, and an independent Google read
matched all public fields. Invalid input returned 422 without creating an event.
The valid event persisted after stopping and restarting the server. Calendar
metadata GET and missing-event GET also matched their contracts. Only this run's
event was deleted and confirmed cancelled; the server was stopped.

See [POST Level 3 verification](POST_LEVEL3_VERIFICATION.md) for the boundary,
reproduction steps, environment details, and recorded results. This Level 3
revision used fixed Google selection; current injection is recorded above.
Teammate review,
matching PR CI, and release verification remain pending.

## Event GET Level 4 verification

On October 11, 2026, implementation revision `c6ca9c6` was verified on Windows
with Python 3.14.8: 107 tests, Ruff lint/format, strict mypy, dependency compatibility,
and diff checks passed. The existing Starlette TestClient warning remains.

All five `tests/test_events.py` cases passed in a separate run that blocked
external socket `connect`/`connect_ex` calls and made real credential loading fail.
Loopback was allowed for Windows event-loop internals. The module uses a controlled
`EventReader` dependency override, checks exact 200/404/422/503/502 responses and
request ID forwarding, and restores prior overrides in `finally`. Google provider
and CRUD tests retain their existing SDK fixtures. Offline results do not prove
real Google integration.

Separate TestClient requests with no overrides used normal dependency wiring and
the local token. The existing event `/events/lf797iogm23bfjn97ogpfocl80` returned
200 with exactly four string fields, the requested ID, and valid `Event` data.
`/events/00000000000000000000000000` returned 404 with
`{"detail": "Event not found"}`. No events changed; metadata and credentials were
omitted from output. This verifies local implementation, not a release tag,
server/curl demonstration, or another teammate's execution.

Teammate reviewers should use the GET reproduction steps below with the Level 4
PR revision and inspect `get_event_reader`, the route's `Depends`, and controlled
reader substitution/cleanup. Matching PR CI and a teammate review of both paths
remain required. Codex assisted with implementation and verification.

## PR 17 merge integration verification

On October 11, 2026, the working merge of event GET Level 3 revision `6d82a42`
and main revision `958c44d` was verified on Windows with Python 3.14.8.
Calendar GET retains FastAPI dependency injection and controlled reader tests;
event GET retains the `EventReader` boundary and `GoogleEventReader` implementation.
Both operations' documentation and earlier verification evidence are preserved.

Ruff lint/format, strict mypy, all 104 tests, and `git diff --check` passed.
No conflict markers remain in application code, tests, or documentation.
The existing Starlette TestClient deprecation warning remains. These checks
verify the local merge working tree; real Google requests were not rerun for
this merge. Updated PR CI and reviewer confirmation remain required after push.

## Event GET Level 3 verification

On October 11, 2026, implementation revision `ce55c7a` on
`feature/calendar-event-get-level3-interface` was verified on Windows with
Python 3.14.8. Ruff lint and formatting, strict mypy, all 104 tests, and
`git diff --check` passed; `python -m pip check` reported no broken requirements.
The existing Starlette TestClient deprecation warning remains.

The additional `test_event_reader_translates_requested_event` test uses a
`GoogleEventReader` through the typed `EventReader` interface. It checks the
four-field domain result, the requested ID and primary calendar passed to
Google, and client closure. Existing HTTP tests retain success, missing-event,
authentication, all-day, malformed-data, transport-failure, and cleanup coverage.
These controlled tests do not establish real Google integration.

A separate FastAPI TestClient run used the real implementation and local token,
without pytest fixtures or SDK replacements:

- `GET /events/lf797iogm23bfjn97ogpfocl80` returned 200. Assertions confirmed
  exactly `id`, `title`, `start_time`, and `end_time`, all strings, the requested
  ID, and successful `Event` model validation.
- `GET /events/00000000000000000000000000` returned 404 with exactly
  `{"detail": "Event not found"}`.

Event metadata and credentials were omitted from output. No events were created,
updated, or deleted. This verifies the implementation commit locally, not a
release tag, server/curl demonstration, or another teammate's execution.
Matching PR CI and teammate review of the boundary remain pending.

For teammate reproduction, use the existing GET Level 2 walkthrough below with
the Level 3 branch or PR commit. Confirm the current event metadata independently
and record the tested revision, environment, commands, and results in the review.
At this Level 3 revision, event GET selected Google in `app/main.py`.
Current event GET injection is documented in the Level 4 evidence above.

## Calendar GET Level 4 verification

October 11, 2026, macOS/Python 3.14.2, working changes on
`feature/calendar-level4-injection`: all 103 tests, dependency checks, Ruff,
strict mypy, and diff checks passed. The five calendar HTTP tests also passed
with networking blocked, using a controlled reader and dependency overrides.

Real Google GET through normal injection returned 200 with the three expected
fields; an unsupported ID returned 404. No calendar data changed. PR CI and
teammate review remain pending. The existing TestClient warning remains.

## Calendar GET Level 3 verification

October 9, 2026, macOS/Python 3.14.2: all 103 tests and required checks passed
on the uncommitted Level 3 refactor. Real Google GET returned 200 with exactly
`id`, `title`, and `time_zone`, with ID `primary`. No calendar data changed.
Level 3 was subsequently merged in PR #15; see that PR for review evidence.

## Test coverage

See [README](../README.md) for setup and commands. Fast tests use isolated data
and controlled providers without credentials or network access. Calendar HTTP
tests override `CalendarReader`; event tests use the SDK fake in
[conftest.py](../tests/conftest.py). Offline tests do not prove real Google writes;
see [POST verification](POST_LEVEL2_VERIFICATION.md) for provider evidence.

- GET: exact responses and missing-ID 404s.
- POST: 201, trimmed titles, generated IDs, create/read, and distinct repeated IDs.
- Validation: invalid titles/times and equal or reversed ranges return 422 without
  writes; ordering accounts for UTC offsets.

## Level 1 verification history

October 4, 2026, macOS/Python 3.14.8: all 22 tests and required checks passed.
Local curl verified POST 201, GET 200, invalid input 422, and unchanged predefined
data. The server was stopped afterward.

Defect checks caught a wrong GET title (`Incorrect Event` instead of
`Example Event`) and discarded POST writes (GET returned 404 instead of 200).
Restoring the in-memory behavior made the tests pass again; source files were
unchanged.

This evidence covers the earlier local implementation. At that revision,
teammate verification, POST review, and CI were pending; the PowerShell
walkthrough was unverified.

### GET Level 2 tests and verification

On Windows with Python 3.14.8, all 46 tests, Ruff lint/format checks, strict mypy,
and diff checks passed. The full suite also passed with external socket
connections blocked; loopback was allowed for Windows event-loop internals.
Tests do not use the real credentials or token.

- [Google event tests](../tests/test_google_events.py): exact field translation,
  hidden provider fields, missing title, all-day rejection, HTTP 401/403/429/5xx,
  timeout, malformed payloads, and authentication-required HTTP responses.
- [Token tests](../tests/test_google_auth.py): missing/invalid token, token reuse,
  insufficient scope, refresh and save, revoked token, and absent refresh token.
- Existing GET success and 404 cases remain covered through the provider fake.

A temporary in-memory title defect caused `test_google_fields_are_translated`
to fail with `Incorrect Event` instead of `Provider meeting`. The original
implementation was restored and all 46 tests passed again.

Real-provider verification through FastAPI TestClient succeeded: the shared timed
event returned 200 with the event JSON in the README, and an absent valid-shaped ID returned
404 with `Event not found`. This was a real Google call through the HTTP route,
not an offline fake. It was not a separate curl/server demonstration.

To reproduce from this branch or the PR commit:

1. Install requirements and privately place credentials.json in the repository root.
2. Authenticate using the shared account and the command in the README authentication section.
3. Start the server using the README Run instructions.
4. In another terminal, run the two requests below (PowerShell: use curl.exe).
5. Confirm the event's current ID, title and times against Google Calendar.
6. Record commit SHA, OS/Python version, commands and results in the PR review.

```sh
curl -i http://localhost:8000/events/lf797iogm23bfjn97ogpfocl80
curl -i http://localhost:8000/events/00000000000000000000000000
```

Expect 200 and four event fields, then 404 with `{"detail":"Event not found"}`.
Use your own local token, keep the GET test event intact, and do not attach token
contents to the review. At least two team members must be able to run the
provider-backed operation (Level 2 section 2.7). At that revision, Kristie's execution was complete and
additional-member reproduction and review were pending. PR #8 is now merged;
its conversation records later verification and reviews. Provider outages and token-expiry branches were simulated in
fast tests; they were not induced against the live service.

### Local creation walkthrough (Level 1 history)

This walkthrough records the earlier all-local behavior, including loss of
created events after restart. The current branch uses Google for both POST and
GET and requires authorization. Use [POST Level 2 verification](POST_LEVEL2_VERIFICATION.md)
for the current workflow, restart behavior, and provider cleanup.

Start the server using the README Run instructions. In another terminal,
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

Jim's Level 2 implementation replaces the local write with authenticated Google
creation while preserving the request, 201 response, and validation rules.
Invalid local input must be rejected before calling the provider.

Use Google's [events.insert documentation](https://developers.google.com/workspace/calendar/api/v3/reference/events/insert)
to verify the operation and write permissions. Translate `title` to `summary`,
`start_time` to `start.dateTime`, and `end_time` to `end.dateTime`. Translate the
created provider event back to the four-field `Event` response. Its returned ID
works with the team's GET implementation on the same primary calendar; callers
must not depend on Level 1's UUID format. Agree on the target test calendar
and configuration with the team before integrating the operations.

Keep fast tests offline by controlling the provider result. Separately document
credentials, configuration, a real create/read verification, and cleanup of test
events. Record behavior for rejected writes and uncertain outcomes rather than
assuming a timeout means no event was created. No Google writes or provider
failure handling have been verified by the Level 1 implementation.
