# POST Level 2 verification

Jim Lo owns `POST /events`. This walkthrough verifies the real HTTP-to-Google
path separately from the offline suite. Each verifier uses their own local
token for the shared test account's primary calendar.

## Prerequisites

Follow the README Installation and Shared Google Calendar authentication steps.
Keep `credentials.json` and `token.json` local and ignored by Git. Run all commands
from the repository root. On Windows, replace `.venv/bin/python` with
`./.venv/Scripts/python.exe` and use `curl.exe` or the README PowerShell example.

```sh
.venv/bin/python scripts/google_calendar_auth.py
```

Token creation and a successful read confirm authentication, not event creation.
Complete the workflow below.

## Create and independently retrieve

Start one server worker without reload:

```sh
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8765
```

In another terminal, choose a unique title identifying the verifier and run.
Send one POST and save the returned ID and response:

```sh
curl -i http://127.0.0.1:8765/events \
  -H 'Content-Type: application/json' \
  -d '{"title":"  Jim POST Level 2 verification UNIQUE_RUN  ","start_time":"2026-10-06T10:00:00-04:00","end_time":"2026-10-06T11:00:00-04:00"}'
```

Replace `UNIQUE_RUN` before running. Expect 201 and exactly `id`, `title`,
`start_time`, and `end_time`. The title has no surrounding spaces, the times
represent the submitted instants, and the ID comes from Google.

Retrieve through the Google-backed GET, replacing `RETURNED_ID`:

```sh
curl -i http://127.0.0.1:8765/events/RETURNED_ID
.venv/bin/python scripts/google_calendar_auth.py --event-id RETURNED_ID
```

Expect GET 200 with the same four fields and an independent Google read of
the same ID/title. The auth script does not print start/end times. Inspect them
in Google Calendar or a direct SDK read; compare instants, not offset spelling.
For a direct read, replace the ID in this local command:

```sh
.venv/bin/python - <<'PY'
from googleapiclient.discovery import build
from app.google_create_events import load_credentials

with build("calendar", "v3", credentials=load_credentials()) as service:
    event = service.events().get(
        calendarId="primary", eventId="RETURNED_ID"
    ).execute()
for field in ("id", "summary", "start", "end"):
    print(field, event[field])
PY
```

Submit an equal-start/end request and expect 422. It must not create a Google
event. Confirm the shared timed GET test event and primary calendar metadata
remain available.
If a write returns 502 or times out, investigate the shared calendar for the
unique title before repeating it; a lost response does not prove no write occurred.

## Persistence and cleanup

Stop the server with Ctrl+C. A Google read by the created ID should still succeed.
After restarting, the Google-backed GET should still return 200 with the same
event ID, title, and time instants. There is no local event mirror.

Delete only this run's verification events from Google Calendar and confirm
that an independent read no longer returns a live event. Stopping the server
does not clean up Google resources. Record cleanup even if an earlier assertion
failed. Do not delete another teammate's test events.

## Historical verification record before GET integration

The following results belong to revision `af62da5`, where GET read a local mirror.
Its restart 404 is historical and is not the current expected behavior.

| Item | Result |
| --- | --- |
| Implementation revision | `af62da5` |
| Verifier and date | Jim's macOS environment, October 4, 2026 (America/New_York); Jim completed browser consent and Codex executed HTTP/SDK checks |
| Environment | macOS, Python 3.14.8 |
| Offline checks | 47 tests, Ruff lint/format, strict mypy, dependency and diff checks passed before this walkthrough |
| Local setup | Shared OAuth client saved locally; authorization script completed consent, token creation, and a real list request |
| Real HTTP POST and Google read | POST 201; local GET 200 with identical JSON; independent Google SDK GET matched ID, normalized title, and both time instants |
| Invalid input and existing GET checks | Equal-time POST 422; Google search found no event with the unique invalid-request title; predefined event/calendar GET 200 and unknown event GET 404 |
| Provider persistence after stopping server | Google GET succeeded after stop; after restart, local mirror GET returned 404 |
| Verification event cleanup | Google deletion completed; independent GET returned `status: cancelled`, confirming no live event remains; server stopped |
| Second teammate verification | Subsequently recorded by Juno and Ka Pui in PR #10; see links below |

The real run used Python `urllib.request` for local HTTP and the Google SDK
for independent reads/search/cleanup. The curl commands above reproduce the
same request. One valid event was created; no repeated valid POST was needed
for this run. Repetition/distinct-ID behavior is covered by the offline tests.

The unique title was `Jim POST Level 2 verification df51d27498d2` and Google
assigned ID `s4spd98m1clb1jj01neil65ou0`. The normalized HTTP response was:

```json
{
  "id": "s4spd98m1clb1jj01neil65ou0",
  "title": "Jim POST Level 2 verification df51d27498d2",
  "start_time": "2026-10-06T10:00:00-04:00",
  "end_time": "2026-10-06T11:00:00-04:00"
}
```

Google returned the same times in `start.dateTime` and `end.dateTime` with
`timeZone: America/New_York`. Both were compared as datetime instants. The
invalid title was `Jim invalid POST df51d27498d2`; its end equaled its start.
After 422, a Google `events.list` query for that title returned no matching
live event. Cleanup deleted only the ID above after confirming its unique title.
The cancellation result is normal provider behavior; do not claim deletion
always makes `events.get` return 404.

Record the verifier, revision, date, commands, expected/observed results, and
cleanup outcome after execution. Never paste credentials, tokens, or OAuth URLs.
The existing offline TestClient deprecation warning does not fail the suite.
POST Level 2 is not complete until real verification is recorded and at least
two members can run POST against Google. PR review and CI are separate checks.

## Teammate verification of the original PR revision

- [Juno's review](https://github.com/juno-junhyuk-lee/OSPSD-Team-5/pull/10#pullrequestreview-5420558817)
  records passing 47 tests and local checks, real POST to the shared Google
  Calendar, independent retrieval, and approval.
- [Ka Pui's comment](https://github.com/juno-junhyuk-lee/OSPSD-Team-5/pull/10#issuecomment-6007063845)
  records real POST and retrieval of the created event; Ka Pui also approved.

These comments establish additional team members' real execution. They do not
specify every environment, command, or cleanup detail; none is inferred here.
They concern the earlier PR revision, so the merged integration is checked separately.

## Combined GET and POST integration verification

| Item | Result |
| --- | --- |
| Revision | Uncommitted integration of POST `993b27b` with main `c881366` (merged PRs #8 and #9) |
| Verifier and date | Jim's macOS environment, October 5, 2026, 21:32 America/New_York; Codex executed HTTP/SDK checks with the existing local authorization |
| Environment | macOS, Python 3.14.8 |
| Offline checks | 76 tests passed; Ruff lint/format, strict mypy, dependency compatibility, and diff checks passed |
| Real creation and retrieval | POST 201 with normalized title; Google-backed HTTP GET 200; all four fields matched an independent Google SDK read |
| Invalid input | Equal-time POST 422; Google search found no event with the unique invalid-request title |
| Other routes | Primary calendar GET 200 matched independent Google metadata; shared timed event GET 200; unknown calendar/event GET 404 |
| Restart | Stopped and restarted the server; Google-backed GET returned 200 with the same ID, title, and time instants |
| Cleanup | Deleted only this run's event; independent Google read confirmed `status: cancelled`; server stopped |
| Remaining | Jim's review of this integration diff, merge commit, push, and updated PR CI |

The run used live single-worker Uvicorn on `127.0.0.1:8765`, Python
`urllib.request` for HTTP, and independent Google SDK reads/search/cleanup.
One valid event was created with title
`Jim merged POST GET verification 072a10b46bc5` and Google ID
`auejlssnrmq9gfnifqf7o9k8nc`. It ran through both real provider operations;
the GET result did not use a local mirror. No shared teammate events were deleted.
The historical `af62da5` results above remain unchanged.
