# POST Level 4 verification

Jim Lo owns POST provider injection and controlled creator tests. This record
verifies implementation commit `c54f52e` on `feature/calendar-post-level4-injection`,
which is based on the pending Level 3 branch at `b1eb94e`. It does not verify a
release tag or another teammate's checkout.

## Wiring and substitution to review

- `EventCreator` in `app/event_creation_provider.py` defines the service models
  and creation errors; it exposes no provider SDK types.
- `get_event_creator()` in `app/event_creation_dependencies.py` selects a
  lightweight `GoogleEventCreator` for normal requests.
- FastAPI supplies that implementation through `Depends`. The POST handler
  receives an `EventCreator` and does not construct the concrete provider.
- `GoogleEventCreator` owns Google insertion, field translation, and known
  failure translation. Authorization and client creation happen during the
  operation, after request validation, and the SDK client closes after use.
- `tests/test_create_event_contract.py` overrides the factory with a controlled
  implementation. Each test gets fresh state and restores previous dependency
  overrides in `finally`; Google provider and CRUD tests keep their own fixtures.

Replacing Google requires another `EventCreator` implementation and a change
to the factory's selection. The POST handler continues using the same contract.
The controlled creator verifies HTTP behavior, not Google's storage behavior.

## Reproduce the checks

Follow README installation and shared Google authorization instructions. Run
the required offline checks and the controlled creator tests:

```sh
python -m ruff check .
python -m ruff format --check .
python -m mypy
python -m pytest -q
python -m pytest -q tests/test_create_event_contract.py
git diff --check
```

For real verification, use the [POST Level 3 workflow](POST_LEVEL3_VERIFICATION.md#reproduce-the-real-workflow)
at this revision with normal dependency wiring and no overrides. Create a
uniquely named event, compare HTTP GET and an independent Google read, verify
invalid input and restart persistence, then delete only this run's events.
Inspect Google before retrying any creation request whose result is uncertain.

## Recorded results

On October 12, 2026, Codex executed the checks in Jim's macOS environment using
his existing local authorization. No browser consent was needed for this run.

| Item | Observed result |
| --- | --- |
| Implementation | `c54f52e08467070f62abbd0f72baf7430fd96b79` |
| Runtime | Python 3.14.8 with the repository's existing dependency packages |
| Offline checks | 130 tests; Ruff lint/format; strict mypy; pinned dependency versions and installed dependency compatibility; diff checks passed |
| Controlled tests | All 15 cases passed with socket connections and real credential loading blocked |
| Override isolation | A pre-existing creator override was replaced during tests and restored afterward |
| Normal injected POST | 201; generated ID, trimmed title, and exactly four public Event fields |
| HTTP GET | 200; identical JSON to POST |
| Independent Google read | ID, title, and both time instants matched; event was active |
| Invalid POST | 422; no Google event with the invalid title; valid event's etag unchanged |
| Other GET operations | Primary calendar metadata matched an independent read; unknown event returned 404 |
| Server stopped | Independent Google read confirmed the event persisted unchanged |
| Server restarted | HTTP GET returned 200 with identical JSON |
| Cleanup | Only this run's event was deleted and independently confirmed cancelled; server stopped |

The real run used Python `requests` against a live single-worker Uvicorn server,
with Google SDK reads, searches, and cleanup. It used the normal factory and
route wiring without dependency overrides or SDK mocks. The environment used
a working Python 3.14.8 interpreter with existing dependency packages because
the original local virtual environment's interpreter was missing its standard
library. No application workaround was needed.

The created title was `Jim POST Level 4 verification bd94acecf824`, with Google
ID `qng70ui1rqaq15n6s3sq643sk4`. The request included surrounding title spaces
and times `2026-10-13T10:00:00-04:00` through `2026-10-13T11:00:00-04:00`.
The invalid title appended ` INVALID` and used equal start/end times. Only one
valid POST was sent. Distinct IDs for repeated requests, service errors, and
disabled retries were checked offline rather than induced against Google.

The existing Starlette TestClient warning remains. The blocked-test runner also
emitted a pytest import-order warning; all assertions passed. Another teammate
must review both normal wiring and controlled substitution. Matching PR CI and
release verification remain pending. Earlier Level 3 evidence does not replace
review of this injection change.
