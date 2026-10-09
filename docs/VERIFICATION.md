# Verification and integration notes

## Calendar GET Level 3 verification

On October 9, 2026, the working changes on `codex/calendar-level3-interface`
passed checks on macOS with Python 3.14.2: dependency compatibility, Ruff
lint/format, strict mypy, all 103 offline tests, and `git diff --check`.
The existing Starlette TestClient deprecation warning remains.

A separate FastAPI TestClient request to `/calendars/primary` used the real
Google implementation and existing local token. It returned 200; assertions
confirmed exactly `id`, `title`, and `time_zone`, all strings, with ID `primary`.
Metadata and credentials were omitted from output. No calendar data was changed.
This verifies the uncommitted refactor, not release CI or another teammate's
execution. Teammate review of the interface remains pending.

See [README](../README.md) for current setup, authentication, commands and API contracts.
This document preserves test strategy, verification evidence and earlier Level 1
walkthroughs. Historical local create/read examples do not describe this branch's
Google-backed GET behavior.

Testing strategy: the GET and POST suites exercise the HTTP boundary through
TestClient without a server, network access, or Google credentials.
[tests/conftest.py](../tests/conftest.py) replaces the Google client with controlled
provider responses and isolates fake event data for each test. The fake insert
stores events that the fake GET retrieves; no application memory bridge is used.
Offline checks do not prove real Google writes. Expected values are independent
of application data. Current real POST evidence is in
[POST Level 2 verification](POST_LEVEL2_VERIFICATION.md).

- [Calendar GET tests](../tests/test_calendars.py): primary returns 200 with exact
  metadata JSON; unknown IDs return the documented calendar 404.
- [Event GET tests](../tests/test_events.py): known ID returns 200 with exact JSON;
  unknown ID returns the documented 404.
- [POST tests](../tests/test_create_events.py): creation returns 201 with the four
  response fields, a generated ID, a trimmed title, and the correct instants.
  GET retrieves the same event; repeated creation produces distinct IDs.
- Invalid creation: missing fields, blank or invalid titles, malformed or
  timezone-free times, numeric timestamps, and equal/reversed time ranges
  return 422 with a `detail` array without a provider write.
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

The preceding Level 1 checks establish local behavior, not Google integration, authentication,
all-day support, multi-worker sharing, or durability. At that revision, teammate verification from
another checkout, POST review, and CI remained pending. The
PowerShell walkthrough has not been executed locally.

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
