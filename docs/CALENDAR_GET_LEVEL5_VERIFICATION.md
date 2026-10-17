# Calendar GET Level 5 verification

Owner: Juno Lee. Reviewers: all teammates.
Branch: `feature/calendar-get-level5-errors`.
Codex assisted with implementation, tests, documentation, and verification.

## Contract and boundaries

`GET /calendars/primary` keeps its three-field success response. Other string
calendar IDs keep returning 404 before a provider read. The operation does not
accept a body or impose another ID syntax rule; it has no operation-specific
422 case. App-wide request validation remains a separate team concern.

The [README contract](../README.md#level-5-calendar-metadata-errors) defines every
error category, status, response shape, and retry policy. The adapter raises
provider-independent exceptions from `app/calendar_provider.py`. The route maps
them to the existing shared `ServiceError` handler, which renders and logs once.
SDK exceptions remain inside the adapter. Unexpected programming errors are not
converted to expected provider failures.

Compatibility changes: errors use the shared envelope instead of `detail`;
permission denial becomes 403, and temporary failures become 503. Successful
metadata, the `primary` alias, dependency injection, and read-only behavior stay
unchanged. No credentials, provider response bodies, or private calendar metadata
are recorded here.

## Offline testing strategy

- `tests/test_calendars.py`: controlled dependency override checks exact success
  and failure responses, retryability, provider involvement, no reader call for
  unsupported IDs, and one sanitized JSON log per expected failure. Success has
  no failure log. Each fixture restores prior overrides.
- `tests/test_google_calendar.py`: independent expected metadata checks translation
  and hidden fields; deterministic SDK errors cover 401/403/404, quota 403s,
  temporary statuses, auth renewal errors, and transport failures. Invalid JSON,
  non-object responses, missing fields, and wrong field types produce 502-category
  service errors. Tests check client exit and one metadata attempt with retries
  disabled. A programming-error case proves TypeError is not mislabeled.
- These tests establish contracts and translation, not a live Google workflow.

On October 17, 2026, macOS/Python 3.14.2, all 44 calendar tests also passed with
socket `connect`/`connect_ex` and real credential loading replaced by functions
that raise AssertionError. Individual tests still supplied their isolated fakes.

## Defect-detection evidence

An in-memory mutation changed the permission-denial branch from
`CalendarMetadataAccessDeniedError` to `CalendarMetadataUnavailableError`.
`test_provider_failures_are_translated[error2-CalendarMetadataAccessDeniedError]`
failed because a permission-denied 403 raised the temporary-failure exception.
The focused run reported 1 failed and 20 passed. This models incorrectly telling
a caller that a permission problem can be retried.

The mutation was compiled into a separate Python process; no source file was
modified. The correct implementation passed again in the blocked-network run.
To reproduce, load `app/google_calendar.py`, replace only that raise statement
in memory, execute the modified module source, then run the parametrized provider
failure test with `pytest.main`. Run the unmodified tests in a fresh process.

## Real Google verification

On October 17, the uncommitted implementation was exercised through FastAPI
TestClient. No FastAPI dependency overrides or SDK fakes were active for the
normal request. The local token was loaded normally; no browser login ran.

| Request / setup | Observed result |
| --- | --- |
| Normal `/calendars/primary` | 200, exactly `id`, `title`, `time_zone`, all strings; ID `primary`; no failure log |
| Unsupported calendar ID | 404 / `not_found`, retryable false; one log with provider false |
| Token path temporarily points to an absent file | 503 / `provider_unavailable`, retryable false; one log with provider false |
| In-memory credentials contain an intentionally invalid token; real Google request | Google HTTP 401 observed; API 503 / `provider_unavailable`, retryable false; one log with provider true |

The invalid-token check replaced only credential loading in memory. An observer
wrapped the real HTTP transport and recorded the returned status, 401; it did
not replace the network response. Google rejected the read, and the SDK's failed
renewal was translated by the adapter. Saved token and OAuth client files were
not edited. No calendar or event data changed.

For teammate reproduction, follow README setup and authorize separately, then:

```sh
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
curl -i http://127.0.0.1:8000/calendars/primary
curl -i http://127.0.0.1:8000/calendars/unsupported-calendar
```

Expect 200 metadata, then 404 with the shared envelope and one sanitized log.
To reproduce the real rejected-token failure without altering saved credentials,
run a separate Python process with TestClient and temporarily patch
`app.google_calendar.Credentials.from_authorized_user_file` to return
`google.oauth2.credentials.Credentials(token="invalid-calendar-level5-verification")`.
Keep the actual SDK and network enabled. Expect 503, retryable false, and
provider true in the log. Never print token contents or real calendar metadata
in public verification evidence.

## Required checks and remaining work

Verification applies to the uncommitted working tree based on main `ef1afe8`,
not a release tag or a published PR commit. Frozen dependency setup, Ruff lint,
Ruff formatting, strict mypy, the full pytest suite, and diff checks were run.
Final results: 254 tests passed; Ruff lint passed; all 54 Python files passed
formatting; strict mypy passed for 35 source files; `git diff --check` passed.
The known Starlette TestClient deprecation warning remains.

Real permission denials, quota exhaustion, and outages were simulated offline;
they were not induced against Google. The live check used TestClient rather
than a separate server/curl demonstration. Teammate review, matching PR CI,
final release-tag verification, and the team demonstration remain required.
The shared logging suggestion is addressed for calendar GET; POST's owner must
finish the original POST review line independently.
