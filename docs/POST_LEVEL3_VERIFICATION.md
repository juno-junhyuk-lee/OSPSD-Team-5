# POST Level 3 verification

Jim Lo owns `POST /events`, the `EventCreator` contract, and its Google
implementation. This record verifies implementation commit `8741c90` after the
Level 3 refactor. It does not verify a release tag or another teammate's checkout.

## Boundary to review

- `app/event_creation_provider.py` defines the typed creation operation using
  `CreateEventRequest` and `Event`, plus two service errors.
- `GoogleEventCreator` in `app/google_create_events.py` keeps Google insertion,
  response translation, and known failure translation behind that contract.
- The POST handler calls an `EventCreator` and maps service errors to the
  existing 503 and 502 responses. Request validation still happens before a write.
- `app/main.py` still selects Google directly for Level 3. External injection
  and controlled creator substitution are Level 4 work.
- The shared `load_credentials` helper remains compatible with PATCH and DELETE.

## Reproduce the real workflow

Follow the README installation and shared Google authorization instructions.
Use the [POST Level 2 walkthrough](POST_LEVEL2_VERIFICATION.md) at this revision:

1. Start one Uvicorn worker without reload.
2. POST one uniquely named timed event; expect 201, a normalized title, a generated
   ID, and exactly the four public Event fields.
3. GET the returned ID through HTTP and read it independently through Google.
   Compare the ID, title, and start/end instants, allowing equivalent UTC offsets.
4. Submit a differently named equal-start/end request; expect 422. Search Google
   for its exact title and confirm it created no live event.
5. Stop the server and independently confirm the valid event still exists.
   Restart the server; GET must return the same JSON.
6. Check primary calendar metadata and an unknown event ID to confirm the
   existing GET operations still behave as documented.
7. Delete only this run's events and independently confirm they are cancelled.
   Stop the server even if an earlier assertion failed.

Keep credentials and tokens local and ignored. If a POST result is uncertain,
inspect Google for the unique title before sending another creation request.

## Recorded results

On October 12, 2026, Codex executed the checks in Jim's macOS environment using
his existing local authorization. No browser consent was needed for this run.

| Item | Observed result |
| --- | --- |
| Implementation | `8741c901598e686a9d3860dff4828f030ef5a217` |
| Runtime | Python 3.14.8 with the repository's existing dependency packages |
| Offline checks | 115 tests; Ruff lint/format; strict mypy; pinned dependency versions and installed dependency compatibility; diff checks passed |
| Network isolation | All 115 tests also passed with external socket connections blocked; loopback remained allowed |
| Real POST | 201; four fields, generated ID, trimmed title, and submitted time instants |
| Real HTTP GET | 200; identical JSON to POST |
| Independent Google read | ID, title, and both time instants matched; event was active |
| Invalid POST | 422; no Google event with the invalid title; valid event's etag unchanged |
| Calendar GET | 200; title and timezone matched an independent Google metadata read |
| Unknown event GET | 404 with `{"detail": "Event not found"}` |
| Server stopped | Independent Google read confirmed the event persisted unchanged |
| Server restarted | HTTP GET returned 200 with identical JSON |
| Cleanup | Only this run's event was deleted; independent read confirmed `status: cancelled`; server stopped |

The local HTTP requests used Python `requests` against a live single-worker
Uvicorn server. Independent reads, searches, and cleanup used the Google SDK.
Normal route/provider wiring was used, without dependency overrides or SDK mocks.
The checks used a working Python 3.14.8 interpreter because the original local
virtual environment's interpreter was missing its standard library. Existing
dependency packages were reused; no application workaround was needed.

The created title was `Jim POST Level 3 verification e60b89b8db6e`, with Google
ID `0nkroifk72nvdscrnrceqkp6rc`. The request included surrounding title spaces
and times `2026-10-13T10:00:00-04:00` through `2026-10-13T11:00:00-04:00`.
The invalid title appended ` INVALID` and used equal start/end times. Only one
valid POST was sent; repeated creation and uncertain-write behavior were tested
offline rather than induced against Google.

The existing Starlette TestClient deprecation warning remains. Another teammate
must review the provider boundary and its translation responsibilities. Matching
PR CI and release verification remain pending. Earlier Level 2 reviews establish
historical execution, not review of this refactor.
