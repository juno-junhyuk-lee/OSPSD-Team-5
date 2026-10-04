# OSPSD-Team-5
This is Team 5's repository for CS 3943 OSPSD.

## Calendar service — Milestone 1, Level 1

This repository currently contains the FastAPI scaffold and Event response model.
The second Level 1 teammate will implement the local endpoint and HTTP tests.
The API below is the agreed target contract, not implemented behavior yet.
Google Calendar integration is planned for Level 2.

### Installation

Target: Python 3.10 or newer. The scaffold has been checked locally on Python
3.14.2; other versions and a fresh dependency install still need verification.
Dependencies currently use version ranges and are not yet pinned or locked.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

### Run

From the repository root:

```sh
uvicorn app.main:app --reload
```

Swagger UI: http://localhost:8000/docs

### Target API (implementation pending)

`GET /events/{event_id}` retrieves one calendar event without changing state.
It takes one required string path parameter, `event_id`, with no query or body
parameters. Success returns `200 OK` with exactly four fields: string `id` and
`title`, and ISO 8601 datetime strings `start_time` and `end_time`.
Level 1 uses local data and has no authentication; Level 2 will use the
authenticated user's primary Google Calendar.

```sh
curl http://localhost:8000/events/test-event
```

```json
{
  "id": "test-event",
  "title": "Example Event",
  "start_time": "2026-10-05T18:00:00Z",
  "end_time": "2026-10-05T19:00:00Z"
}
```

The planned local event is `test-event`. Unknown IDs will return `404` with
`{"detail": "Event not found"}`.
Until the route is implemented, the curl example returns FastAPI's default
404 response instead of the target contract.

### Test

```sh
pytest
```

Tests are pending; pytest currently collects no tests (exit code 5).
Use FastAPI TestClient to check public HTTP behavior without Google credentials
or network access:

- Known ID: expect 200 and the exact JSON above, catching missing/extra fields
  and incorrect values.
- Unknown ID: expect 404 and the documented error, catching an incorrect success.

Write expected values independently of the lookup data. Keep tests independent
and read-only. Demonstrate one test catching an incorrect title, record the
failing assertion in the PR, restore the code, and rerun tests. Once implemented,
verify the curl example from another teammate's checkout. These checks do not
establish real-provider behavior; document that verification separately in Level 2.

### Level 2 handoff

After Level 1 is implemented, replace the fixed lookup in `app/main.py` with a Google Calendar event lookup
using the authenticated user's `primary` calendar. Preserve the route and
`Event` response model in `app/models.py`; do not expose `calendar_id` or raw
Google fields. Map `summary` to `title`, `start.dateTime` to `start_time`, and
`end.dateTime` to `end_time`. The planned fixture represents a timed event;
agree on all-day event behavior before expanding that contract.

Google authentication, local configuration, and real-provider verification
will be documented in Level 2. Keep secrets and generated tokens out of Git.
Decide missing-title behavior as well as all-day event behavior before claiming
support. The current model does not enforce timezone awareness or start/end
ordering; those guarantees are not part of the current contract.

## Contributor documentation

- [AGENTS.md](AGENTS.md): code map, contributor instructions, and review/release rules.
- [Work plan](docs/WORK_PLAN.md): Level 1 split and milestone responsibilities.

These docs are drafts for team review. Dependency pinning, CI, teammate review,
and Level 2 provider integration remain pending.

## Team Members

- Juno Lee
- Niriti Pahadi
- Kristie Lee
- Jim Lo
- Ka Pui Cheung
