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

Check the current local GET mirror, replacing `RETURNED_ID`:

```sh
curl -i http://127.0.0.1:8765/events/RETURNED_ID
.venv/bin/python scripts/google_calendar_auth.py --event-id RETURNED_ID
```

Expect local GET 200 with the same response and an independent Google read of
the same ID/title. The auth script does not print start/end times. Inspect them
in Google Calendar or a direct SDK read; compare instants, not offset spelling.
For a direct read, replace the ID in this local command:

```sh
.venv/bin/python - <<'PY'
from googleapiclient.discovery import build
from app.google_calendar import load_credentials

with build("calendar", "v3", credentials=load_credentials()) as service:
    event = service.events().get(
        calendarId="primary", eventId="RETURNED_ID"
    ).execute()
for field in ("id", "summary", "start", "end"):
    print(field, event[field])
PY
```

Submit an equal-start/end request and expect 422. It must not create a Google
event. Confirm predefined event/calendar GET behavior remains available.
If a write returns 502 or times out, investigate the shared calendar for the
unique title before repeating it; a lost response does not prove no write occurred.

## Persistence and cleanup

Stop the server with Ctrl+C. A Google read by the created ID should still succeed.
After restarting, the current local GET mirror returns 404; this is a known
transition limitation until event GET is connected to Google.

Delete only this run's verification events from Google Calendar and confirm
that an independent read no longer returns a live event. Stopping the server
does not clean up Google resources. Record cleanup even if an earlier assertion
failed. Do not delete another teammate's test events.

## Verification record

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
| Second teammate verification | Pending |

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
