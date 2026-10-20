# PATCH Level 5 verification

Niriti Pahadi owns `PATCH /events/{event_id}`. This record covers Level 5 shared
errors, Google failure classification, and sanitized logging on
`feature/calendar-patch-level5-errors`. It does not verify a final release tag.

Subsequent completion: Ka Pui [re-tested and approved PR #33](https://github.com/juno-junhyuk-lee/OSPSD-Team-5/pull/33#pullrequestreview-5565972640)
at `6dc7861` (289 tests and real PATCH checks).
[Matching checks passed](https://github.com/juno-junhyuk-lee/OSPSD-Team-5/actions/runs/39183346699/job/117840571060),
and the PR merged. Final-tag verification is tracked separately in PR #35;
only the executions actually recorded below are claimed.

## Contract and checks

The Google adapter translates SDK failures into update service errors. The PATCH
route maps them through the shared `ServiceError` handler:

| Failure | HTTP | Code | Retryable |
| --- | --- | --- | --- |
| Invalid event ID, JSON, missing fields, or invalid values | 422 | `invalid_input` | false |
| Missing, deleted, or cancelled event | 404 | `not_found` | false |
| Permission refused | 403 | `access_denied` | false |
| Authorization unavailable or rejected | 503 | `provider_unavailable` | false |
| Provider failure or unconfirmed update | 502 | `provider_error` | false |

The shared handler logs operation, error category, provider involvement, and
status once. It omits credentials, bodies, and raw provider exceptions. Success
remains 200 with exactly four Event fields. An uncertain write is never
automatically retried or replaced with local data.

Follow README setup with Python 3.14 and the locked dependencies:

```sh
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest -q
git diff --check
```

Controlled updater tests verify exact responses, no operation on invalid input
or invalid IDs, one sanitized failure log, no failure log on success, and
provider-involvement flags. Adapter tests distinguish authorization, permission,
rate-limit, and cancelled-event cases.

## Real Google results

| Date | Verifier | Revision | Result |
| --- | --- | --- | --- |
| 2026-10-18 | Ka Pui Cheung | `6dc7861` (PR #33 head) | POST → PATCH 200 → GET shows the change; end before start 422 `invalid_input`; `bad id!` 422 with no Google call; unknown ID 404; PATCH after DELETE 404. Each failure logged one sanitized line. Repeated on `main` `2fc8c4c`; see [DELETE Level 5 verification](DELETE_LEVEL5_VERIFICATION.md). |

## Reproduce the live checks

1. Follow README shared authorization and start the service with
   `uv run uvicorn app.main:app --host 127.0.0.1 --port 8000`, without reload.
2. POST a timed event, PATCH it, then GET; expect matching public fields.
3. PATCH with equal start/end times; expect 422 / `invalid_input` /
   `retryable=false` and one provider=false log.
4. DELETE the event, then PATCH the same ID; expect 404 / `not_found`.
5. Delete only your verification event if still present, and stop the server.

Ka Pui's review and matching checks completed for PR #33, as linked above.
Final-tag verification remains separate from those operation-level results.
