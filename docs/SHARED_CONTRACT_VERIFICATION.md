# Tagged Calendar contract: real Google verification

## Revision and environment

| Item | Observed value |
| --- | --- |
| Date | November 4, 2026; recorded after completion at 12:55 EST |
| Service branch | `feature/hw2-calendar-contract-adoption` |
| Service commit | `327e8bc011ea307ab31732551327a158b55223c2` |
| Working tree during the live run | Clean; all code, tests, and script changes committed |
| Shared package | `calendar-contract 0.1.0`, tag `v0.1.0` |
| Shared commit | `1c1cad7a0732ddb242a05400d8833d94e4422424` |
| Python / platform | Python 3.14.8; macOS 27.2, arm64 |
| uv / Pydantic | uv 0.12.17; Pydantic 2.13.5 |
| Calendar | Authenticated account's primary Google Calendar |
| Authorization | Existing repository-local OAuth; no interactive sign-in needed |
| Run marker | `8855f4b0403a` |
| Process exit code | `0` |

This run used normal FastAPI dependency injection, Team 5's
`GoogleCalendarService`, the tagged shared models/errors, and real Google
adapters. No controlled provider or dependency override was installed.
HTTP calls used TestClient in process; a Uvicorn listener, TCP requests,
server restart, and deployment were not exercised.

## Command and observed results

Reproduction uses the repository-root command:

```sh
uv run python -m scripts.verify_put_live
```

The actual local invocation used the available uv executable and task-local
dependency cache, with the frozen lockfile:

```sh
/private/tmp/ospsd-calendar-pr11-tools/bin/uv run --frozen --cache-dir /private/tmp/ospsd-adoption-uv-cache python -m scripts.verify_put_live
```

| Step | Observed result |
| --- | --- |
| Package provenance | Version 0.1.0 and exact shared commit matched |
| POST | 201; returned ID, title, and both time instants matched |
| GET after POST | 200; ID, title, and both time instants matched |
| Seed description | One SDK patch added a non-shared description to this event |
| PUT | 200; ID unchanged, title and both times replaced |
| GET after PUT | 200; replacement values matched |
| Independent Google read | Stored ID, summary, both times, and description matched |
| DELETE | 204 |
| GET after DELETE | 404 |
| Repeated DELETE | 404 |
| Script | Every check passed; exit 0 |

Exact sanitized stdout from this run:

```jsonl
{"step": "package", "passed": true, "tag": "v0.1.0", "version": "0.1.0", "commit": "1c1cad7a0732ddb242a05400d8833d94e4422424"}
{"step": "run", "passed": true, "run_id": "8855f4b0403a"}
{"step": "post", "passed": true, "status": 201, "same_id": true, "title_matches": true, "start_matches": true, "end_matches": true}
{"step": "get_after_post", "passed": true, "status": 200, "same_id": true, "title_matches": true, "start_matches": true, "end_matches": true}
{"step": "seed_description", "passed": true}
{"step": "put", "passed": true, "status": 200, "same_id": true, "title_matches": true, "start_matches": true, "end_matches": true}
{"step": "get_after_put", "passed": true, "status": 200, "same_id": true, "title_matches": true, "start_matches": true, "end_matches": true}
{"step": "google_fields_kept", "passed": true, "same_id": true, "title_matches": true, "start_matches": true, "end_matches": true, "description_kept": true}
{"step": "delete", "passed": true, "status": 204}
{"step": "get_after_delete", "passed": true, "status": 404}
{"step": "repeat_delete", "passed": true, "status": 404}
```

The expected missing-event probes emitted these sanitized application logs:

```jsonl
{"operation": "get_event", "error": "not_found", "provider": true, "status": 404}
{"operation": "delete_event", "error": "not_found", "provider": true, "status": 404}
```

The existing Starlette TestClient/httpx deprecation warning also appeared.
It did not fail verification.

## State changes and cleanup

One disposable event was created through POST. The SDK added its description,
then PUT replaced its shared fields. Cleanup deleted that event and confirmed
missing-event behavior through GET and repeated DELETE. The checks reported
no unresolved cleanup. No other event was targeted.

IDs, titles, calendar contents, credentials, and raw SDK exceptions are omitted
from this record. The generated run marker identifies this verification without
revealing account data. Token files remain local and outside Git.

## Offline verification and limits

The same committed code passed the preceding batch's offline checks:
433 tests, Ruff lint/format, strict mypy for app/tests and the verification
script, frozen dependency synchronization, and `git diff --check`.
Those checks included 11 controlled script cases covering success, incorrect
values, dropped description, exceptions, cleanup failures, wrong package
provenance, an invalid POST response with a known ID, and an uncertain POST
without an ID. These controlled cases are distinct from the successful real
Google run above. No source or test changes were needed after that run; this
follow-up adds documentation only.

This proves one normal real-provider workflow for the four common operations
at the service/shared revisions above. It is not a run of the reusable shared
conformance suite against Team 5, another teammate's execution, or PR/CI
approval. The section below records Ka Pui's run of the shared suite. PATCH and calendar-metadata extensions were
not probed against Google in this run. The adoption branch still needs its
review and matching CI before integration.


## Shared conformance suite against real Google

Ka Pui ran the tagged `CalendarServiceConformance` suite against
`GoogleCalendarService` with the real Google adapters, as a second teammate.

| Item | Observed value |
| --- | --- |
| Date | November 4, 2026, 13:26:52–13:27:06 EST |
| Service base | `aa11f9ccbd75dd66fd280aa22a06186a29a47564` plus this change's `tests/test_shared_conformance.py` (same content as committed) |
| Shared package | `calendar-contract 0.1.0`, commit `1c1cad7a0732ddb242a05400d8833d94e4422424` |
| Python / platform | Python 3.14.6; macOS 26.7.1, arm64 |
| uv / Pydantic | uv 0.13.7; Pydantic 2.13.5 |
| Calendar | Authenticated account's primary Google Calendar; existing repository-local OAuth |
| Result | 24 passed, exit code `0`, 8.8 s |
| Cleanup | A Google search for `Conformance event` in January 2030 afterward returned 0 events |

```sh
CALENDAR_LIVE_CONFORMANCE=1 uv run pytest tests/test_shared_conformance.py -v -k Live
```

The create, get, replace, delete, and `not_found` cases wrote to and read from
real Google. The four `ProviderFailure` groups used `failing_service`, which
raises Team 5's adapter errors, so they check the translation to shared
`CalendarError` codes, not Google's own failure responses; Google-to-adapter
classification is covered offline by `tests/test_shared_provider_failures.py`.
The invalid-input cases exercise the shared request models only. The same 24
tests also run offline on the fake Google client in the full `uv run pytest`.
