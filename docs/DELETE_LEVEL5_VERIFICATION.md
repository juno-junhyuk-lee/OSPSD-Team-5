# DELETE Level 5 verification

Owner: Ka Pui Cheung. Implementation: [PR #28](https://github.com/juno-junhyuk-lee/OSPSD-Team-5/pull/28) (shared error format and DELETE), reviewed by Jim Lo.

## Real Google results

Each run used the shared test account's `primary` calendar, the normal FastAPI dependencies (real `GoogleEventDeleter`, no overrides), and `TestClient`. Each run created its own test event and deleted it.

| Date | Verifier | Revision | Result |
| --- | --- | --- | --- |
| 2026-10-16 | Ka Pui Cheung | `4b4575c` (PR #28 head) | POST 201; DELETE 204 with empty body; repeated DELETE 404 `not_found`; unknown ID 404 `not_found` (real Google 404); `bad id!` 422 `invalid_input` with no Google call. Each failure logged exactly one sanitized line. |
| 2026-10-18 | Ka Pui Cheung | `2fc8c4c` (`main` after PR #33, fresh clone) | Full workflow in the table below. |

Full workflow on `2fc8c4c`, run from a fresh clone after `uv sync --frozen`, Ruff, format check, strict mypy, 289 tests, `uv pip check` and `git diff --check` all passed:

| Step | Expected | Actual |
| --- | --- | --- |
| POST a timed event | 201 with Google's ID | 201 |
| GET it | 200, same four fields | 200 |
| PATCH title and end | 200 with new fields | 200 |
| GET after PATCH | 200 with new fields | 200 |
| POST with end before start | 422 `invalid_input` | 422, one log line |
| DELETE it | 204, empty body | 204 |
| GET, PATCH, DELETE the deleted ID | 404 `not_found` each | 404 each, one log line each |
| GET `bad id!` | 422 `invalid_input`, no Google call | 422, `provider: false` |
| GET an all-day event | 422 `invalid_input` | 422; the event was then deleted (204) |

Calendar GET returned 403 `access_denied` in this run because the local token predates the `calendar.calendars.readonly` scope. The README requires reauthorizing such tokens; this is a local setup issue, not a DELETE result.

Not exercised live: the 403 `access_denied`, 502 and 503 paths. Offline tests in `tests/test_google_delete_events.py`, `tests/test_delete_events.py` and `tests/test_delete_event_contract.py` cover them.

## Operation cost

DELETE makes one provider request, `events.delete`, with `num_retries=0`, plus at most one token refresh when the saved token has expired. It never lists or searches the calendar, so its cost does not grow with the number of events. Local work is the ID check, which is linear in the ID length and capped at 1024 characters. A delete-by-title or delete-by-time design would have to list the calendar first, so its cost would grow with the number of matching events and pages.

## Design decision: one shared error format

**Problem.** Before Level 5, each route raised its own `HTTPException` with a free-text `detail`. A caller could not reliably tell invalid input, a missing event, a permission denial and a provider failure apart, or know whether a retry was safe. Failures were not logged, which the sister-team review also pointed out.

**Alternatives.**

1. Keep per-route `HTTPException` responses and document them per operation.
2. Give each operation its own error enum and response shape.
3. One shared `ServiceError` with five codes, a `retryable` flag and one handler that renders and logs every failure (chosen, `app/errors.py`).
4. RFC 9457 `application/problem+json` responses.

**Evidence.** All five operations moved onto the shared format in separate PRs (#28, #30, #31, #32, #33) without changing the handler's contract. #32 only added the response schema and the request-validation handler. The real runs above show the same shape and exactly one sanitized log line for every failure across GET, POST, PATCH and DELETE.

**What we gave up.** FastAPI's default 422 body listed the failing field locations; the shared 422 hides them to avoid echoing request data, so callers get one generic message. We also gave up the interoperability of the RFC 9457 standard in exchange for a smaller shape the whole team already uses.

**When to revisit.** If an agent client needs field-level validation details, if we add request IDs or tracing, or if a new provider introduces a failure class the five codes cannot express (for example a 409 conflict).
