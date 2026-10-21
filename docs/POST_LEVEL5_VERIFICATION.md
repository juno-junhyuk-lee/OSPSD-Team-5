# POST Level 5 verification

Subsequent completion: Ka Pui [re-tested and approved PR #32](https://github.com/juno-junhyuk-lee/OSPSD-Team-5/pull/32#pullrequestreview-5560450930)
at `c671279` (277 tests and real creation/validation checks).
[Matching checks passed](https://github.com/juno-junhyuk-lee/OSPSD-Team-5/actions/runs/39072703265/job/117513424120),
and the PR merged. Original working-tree revisions and results below are
preserved; their pending-review statements are historical. Final-tag verification
and release status are tracked separately in PR #35.

Jim Lo owns `POST /events`. This record verifies implementation commit
`ba8ebf3b3a144149b66a2c0831847d8873b187d4` on
`feature/calendar-post-level5-errors`, including provider classification from
`b4c721e`. It does not verify a release tag, PR CI, or a teammate's checkout.

## Contract and checks

The Google adapter translates SDK failures into creation service errors.
The POST route maps them through the shared `ServiceError` handler:

| Failure | HTTP | Code | Retryable |
| --- | --- | --- | --- |
| Invalid JSON, missing fields, invalid values | 422 | `invalid_input` | false |
| Permission refused | 403 | `access_denied` | false |
| Authorization unavailable or rejected | 503 | `provider_unavailable` | false |
| Provider failure or unconfirmed creation | 502 | `provider_error` | false |

The shared handler logs operation, error category, provider involvement, and
status once. It omits credentials, bodies, and raw provider exceptions. Request
validation uses the matched operation name and provider=false; PATCH also uses
this shared 422 format. Success remains 201 with exactly four Event fields.
An uncertain write is never automatically retried or replaced with local data.

Follow README setup with Python 3.14 and the locked dependencies:

```sh
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest -q
git diff --check
```

On October 17, 2026, local checks on Python 3.14.8 passed: Ruff lint/format,
strict mypy (36 source files), diff checks, and 239 tests. The full suite also
passed with external socket connections blocked; loopback remained allowed.
The existing Starlette TestClient deprecation warning remains. The local runs
used an isolated environment installed from the same unchanged `uv.lock`.

Controlled creator tests verify exact responses, no operation on invalid input,
one sanitized failure log, no failure log on success, provider-involvement flags,
and one call per failed request. Adapter tests distinguish authorization,
permission, and quota failures and cover unusable responses and cleanup. The
lost-response regression records an accepted provider write, returns 502 without
retrying, and confirms the event is still retrievable. Shared validation tests
exercise POST and PATCH with missing, malformed, and invalid bodies, including
sensitive sample input that must not appear in the public error or service log.

## Real Google results

Codex executed the following checks in Jim's macOS environment on October 17,
2026, at 17:33 EDT. Existing team test authorization was usable; no browser
consent was needed. The run used HTTP requests against live, single-worker
Uvicorn servers with normal provider dependency wiring and no SDK response
mocks. An independent Google SDK client checked state and cleanup.

| Check | Observed result |
| --- | --- |
| Valid POST | 201; generated ID, trimmed title, four fields, and matching time instants |
| HTTP GET | 200; identical JSON to POST |
| Independent Google read | Active event; title and time instants matched |
| Invalid equal-start/end POST | 422 / `invalid_input` / retryable=false; no Google event with that unique title; valid event etag unchanged |
| Normal-run logs | No failure log for success; one `create_event` validation log with provider=false and status=422 |
| Server stopped and restarted | Independent read confirmed persistence; restarted HTTP GET returned matching JSON |
| Isolated invalid-token POST | Actual Google 401 observed; API returned 503 / `provider_unavailable` / retryable=false |
| Failure-run logs | Exactly one observed Google POST/401 and one sanitized application failure log with provider=true |
| Rejected-write state | No event with the failure request's unique title; normal token file unchanged during the probe |
| Cleanup | HTTP DELETE 204; independent Google read showed cancelled; HTTP GET then returned 404 / `not_found` |
| Processes | All verification servers stopped |

The one created event was titled
`Jim POST Level 5 verification 31a89952fb61`, with ID
`dnmuq3jlnvb8v1cfh5aej2ou10`. Its times were
`2026-10-22T10:00:00-04:00` through `2026-10-22T11:00:00-04:00`.
Invalid and rejected requests used this title with ` INVALID` and ` REJECTED`
suffixes respectively. Only one valid creation request was sent.

Recorded service logs:

```json
{"operation": "create_event", "error": "invalid_input", "provider": false, "status": 422}
{"operation": "create_event", "error": "provider_unavailable", "provider": true, "status": 503}
```

The failure server used a temporary token file containing an intentionally
invalid access token, a future local expiry, the expected event scope, no
refresh token, and dummy client fields. Only that server's `TOKEN_PATH` was
redirected. Local scope/expiry checks therefore passed and Google rejected the
actual Calendar insertion request. A response-observation wrapper called the
original `httplib2.Http.request` unchanged and recorded only method/status.
It observed one POST with HTTP 401; it did not fabricate a response.

After Google's 401, the SDK attempted credential refresh, which could not
proceed without refresh material. The resulting `RefreshError` became the
documented 503 authorization error. This live run exercises that SDK-mediated
authorization path; direct `HttpError(401)` translation is separately tested
offline. It is not a permission-denial 403 test or a local missing-token test.
No shared account permissions, OAuth-client settings, or normal token contents
were changed by the failure probe. The temporary invalid token was removed.

## Reproduce the live checks

1. Follow README shared authorization and start the service with
   `uv run uvicorn app.main:app --host 127.0.0.1 --port 8000`, without reload.
2. Use the README POST walkthrough with a new unique title. Expect 201, then
   HTTP GET 200 with identical JSON. Independently inspect that event through
   Google and compare all public fields, allowing equivalent UTC offsets.
3. Submit the same fields with a distinct title and equal start/end times.
   Expect 422 / `invalid_input` / retryable=false and one provider=false log.
   Search Google for that exact unique title to confirm no event was created.
4. Stop and restart the service and retrieve the successful event again.
5. Run the isolated rejection probe below, then use normal authorization to
   confirm its unique title has no event. Do not replace the normal token.
6. Delete only your successful verification event through the API. Expect 204,
   independently confirm cancelled/missing state, and expect GET 404. Stop the
   server. If creation is uncertain, inspect the unique title before retrying.

The following rejection-only reproduction uses TestClient rather than a separate
server. It uses the real SDK and network, normal dependency selection, and a
temporary token-path configuration. It does not need a real refresh token.
Run from the repository root with `uv run python`:

```python
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

import httplib2
from fastapi.testclient import TestClient

from app import google_create_events
from app.main import app

observed = []
original_request = httplib2.Http.request


def observe(self, uri, method="GET", *args, **kwargs):
    result = original_request(self, uri, method, *args, **kwargs)
    if "/calendar/v3/calendars/primary/events" in str(uri):
        observed.append((method, int(result[0].status)))
    return result


title = f"POST Level 5 rejected probe {uuid4().hex}"
assert not app.dependency_overrides
with TemporaryDirectory() as directory:
    token = Path(directory) / "invalid-token.json"
    token.write_text(
        json.dumps(
            {
                "token": "deliberately-invalid-post-level5-probe",
                "refresh_token": None,
                "client_id": "unused",
                "client_secret": "unused",
                "scopes": ["https://www.googleapis.com/auth/calendar.events"],
                "expiry": (datetime.now(timezone.utc) + timedelta(hours=1)).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                ),
            }
        ),
        encoding="utf-8",
    )
    with (
        patch.object(google_create_events, "TOKEN_PATH", token),
        patch.object(httplib2.Http, "request", observe),
        TestClient(app) as client,
    ):
        assert google_create_events.load_credentials().valid
        response = client.post(
            "/events",
            json={
                "title": title,
                "start_time": "2026-10-22T10:00:00-04:00",
                "end_time": "2026-10-22T11:00:00-04:00",
            },
        )
assert observed == [("POST", 401)]
assert response.status_code == 503
assert response.json()["error"]["code"] == "provider_unavailable"
assert response.json()["error"]["retryable"] is False
print(title, response.status_code, response.json())
```

Check the service log for one `create_event` / `provider_unavailable` line with
provider=true and status=503. The instrumentation only observes actual responses;
do not replace SDK results or exceptions and call that a real-provider check.

## Integration with calendar GET Level 5

On October 17, 2026, at 17:45 EDT, the uncommitted merge of POST head `2b8af4b`
with main `a6b6fa3` (PR #31) passed 277 tests, Ruff lint/format, strict mypy,
and diff checks. Import and documentation conflicts were resolved by preserving
calendar metadata errors and POST's schema/validation handler. The Python
reproduction block above was formatted to satisfy the repository's format check.

The merged working tree also passed a fresh live Uvicorn run: POST 201, HTTP GET
200 matching the POST response, independent Google reads, invalid input without
a write, persistence across restart, and HTTP DELETE 204 cleanup. Calendar GET
returned 200 with metadata matching an independent read; an unsupported calendar
returned 404/not_found with one provider=false log. The isolated invalid-token
POST again reached Google, received one 401, and became 503/provider_unavailable
with retryable=false and one provider=true log. Normal credentials were unchanged
by that probe. All servers stopped, and independent Google retrieval confirmed
the test event was cancelled; HTTP GET then returned 404.

This run created only `Jim POST Level 5 verification 316d9def527b`, ID
`3fbsncep4926aqa16itn07oqt8`, with the same time instants as the earlier run.
It verifies the pending merged working tree, not a new commit or release tag.

## Remaining verification

Permission denial, quota/rate limits, outages, malformed responses, and uncertain
accepted writes are covered by controlled tests, not deliberately induced
against Google. Another teammate must review the changes and reproduce the
documented workflow. Matching PR CI, final tag/fresh-checkout verification, and
the team demonstration remain separate milestone work. This record does not
claim that other owners' Level 5 implementations or the final release are done.
