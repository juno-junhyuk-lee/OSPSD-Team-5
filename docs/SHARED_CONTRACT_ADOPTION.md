# Shared Calendar package adoption

## Scope and status

Team 5 uses `calendar-contract` tag `v0.1.0-rc.1`, pointing to commit
`1c1cad7a0732ddb242a05400d8833d94e4422424` in
[OSPSD-Calendar](https://github.com/Airbus-A330/OSPSD-Calendar/tree/v0.1.0-rc.1).
The package supplies provider-independent models, validation, errors, the
four-operation interface, and reusable conformance tests. Google SDK, OAuth,
FastAPI, and configuration remain in this repository.

Implementation checkpoints:

- `cb1d112`: install the tagged dependency and adopt shared event/request models.
- `9a71587`: connect the shared service, dependency injection, and HTTP errors.
- `327e8bc`: migration documentation and the verification script. A successful
  real Google workflow was then recorded at this clean commit; see the
  [observed verification record](SHARED_CONTRACT_VERIFICATION.md). Teammate
  execution, shared conformance wiring, review, and CI remain separate work.

Work targets `hw2/milestone-2`. The existing `main` branch does not yet contain
this adoption work. Use the adoption PR's checkout instructions when available.
Historical HW1 verification files retain the field names and results observed
at their recorded revisions; those records are not HW2 evidence.

## Install the fixed dependency

Use Python 3.14, Git, and uv from the repository root:

```sh
uv sync --frozen
uv run python -c "import calendar_contract; print(calendar_contract.__version__)"
git rev-parse HEAD
git status --short
```

The installed package version must be `0.1.0`. `pyproject.toml` selects tag
`v0.1.0-rc.1`, and `uv.lock` pins the commit above. Initial installation needs network
access; the fast test suite does not. Do not replace the tag with a moving branch
or run a dependency update merely to reproduce this revision.

The shared package supports Python 3.12 and later. Team 5 continues using Python
3.14 and Pydantic 2.13.5, which satisfies the package's `>=2.12.5,<3` requirement.
The legacy `requirements.txt` export does not replace this locked setup.

## Public migration

| Before HW2 | Current behavior |
| --- | --- |
| `start_time` / `end_time` | `start` / `end` for POST, PUT, PATCH, and Event responses |
| Local event/write models | `Event`, `CreateEvent`, and `ReplaceEvent` from `calendar_contract` |
| Time fields held as Python datetime objects | RFC 3339 strings at the shared Python boundary |
| Unknown request fields ignored | 422 `invalid_input`, before a provider operation |
| All body-validation failures returned 422 | Malformed/empty JSON is 400; valid JSON violating model rules is 422 |
| Per-route operation error conversion | `GoogleCalendarService` raises `CalendarError`; HTTP handlers render it |

Old field names are rejected, including when the canonical fields are also
present. No compatibility aliases are provided. Update clients, fixtures,
examples, and scripts together. Calendar metadata retains `id/title/time_zone`.

POST, PUT, and PATCH require all of `title/start/end`; null, wrongly typed,
missing, and unknown fields fail validation. PATCH remains a full-field update
extension, not a partial-update implementation. PUT preserves the event ID and
non-shared Google fields by patching only summary and both times.

Write titles must not be blank after trimming. The shared model retains the
submitted title; Team 5 trims it before writing to Google. GET can return an
existing untitled event with `title: ""`. Both request and Event models validate
timestamps and ordering by instant. The application passes timestamp strings
without deliberately truncating fractions, but provider precision and output
offset formatting can differ. Use whole-second timestamps for portable checks.

## Service and failure boundaries

`app/calendar_service.py` implements `CalendarService` structurally:

| Method | Existing adapter method |
| --- | --- |
| `create(CreateEvent) -> Event` | `GoogleEventCreator.create_event` |
| `get(event_id) -> Event` | `GoogleEventReader.get_event` |
| `replace(event_id, ReplaceEvent) -> Event` | `GoogleEventUpdater.update_event` |
| `delete(event_id) -> None` | `GoogleEventDeleter.delete_event` |

`get_calendar_service` in `app/calendar_service_dependencies.py` composes the
existing operation factories. Normal event routes receive the shared protocol;
tests can override either the whole service or an operation subdependency.
No route constructs a Google client or starts browser authorization.

Adapters classify known SDK outcomes. The shared service translates those
operation-specific failures into `CalendarError`, with a sanitized provider flag
in details for log context. The HTTP handler does not expose those details; it
adds the route's operation name and emits one safe log containing operation,
code, provider involvement, and status. Messages are service-written. Raw SDK
exceptions, bodies, tokens, and titles are not logged. Programming errors propagate.

| Failure | HTTP/code | Retry advice |
| --- | --- | --- |
| Malformed or empty JSON | 400 `invalid_input` | False; correct the request |
| Invalid valid-JSON input or event ID | 422 `invalid_input` | False |
| Missing/deleted event, including repeated DELETE | 404 `not_found` | False |
| Explicit permission denial | 403 `access_denied` | False |
| Missing/unusable local OAuth or rejected authorization | 503 `provider_unavailable` | False; repair setup |
| Temporary failure before a write, or an explicit quota/rate-limit rejection | 503 `provider_unavailable` | True; wait before retrying |
| Unexpected provider response or uncertain POST/PUT | 502 `provider_error` | False for uncertain writes |
| Unconfirmed DELETE | 502 `provider_error` | True; already-deleted events return 404 |

A POST/PUT transport failure or failed response after sending the write may
mean Google accepted it. That path remains 502 with `retryable=false`; the
service does not automatically resend. A PUT existence-read failure happens
before patch and can instead be temporary unavailability. No meaningful retry
delay is currently known, so the service does not invent `Retry-After` values.

## Offline checks and handoff

```sh
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run mypy scripts/verify_put_live.py
uv run pytest -v
git diff --check
```

`tests/test_calendar_service.py` checks the shared Python boundary directly.
`tests/test_shared_calendar_http.py` replaces the shared service and checks
HTTP routing, status/error mappings, and sanitized logs.
`tests/test_shared_provider_failures.py` checks actual adapter translation with
controlled Google responses, including before/after-write failures.
`tests/test_verify_put_live.py` verifies the script with controlled providers;
it does not contact Google or establish live persistence.

`tests/test_shared_conformance.py` runs the tagged `CalendarServiceConformance`
suite against `GoogleCalendarService`. Its `service` fixture uses the real
Google adapters on the offline fake Google client from `tests/conftest.py`.
Its `failing_service` fixture receives a `ProviderFailure` and wires
`GoogleCalendarService` to adapters raising Team 5's matching operation errors,
so the suite checks the translation to shared `CalendarError` codes. Keep
failure hooks in tests, not in the production protocol.

To run the live test class against the real primary calendar:

```sh
CALENDAR_LIVE_CONFORMANCE=1 uv run pytest tests/test_shared_conformance.py -v -k Live
```

Success and not-found cases use real Google; provider-failure cases still use
controlled adapters. Tests attempt cleanup of created events; the inherited
cleanup failure paths remain a separate review concern.

See the tag's [Python interface guide](https://github.com/Airbus-A330/OSPSD-Calendar/blob/v0.1.0-rc.1/docs/PYTHON_INTERFACE.md).
Running against the package's in-memory reference service alone does not test
Team 5's Google adapters. Offline, live, and cross-team checks remain distinct.

## Real Google reproduction

This section gives reproduction instructions and expected results. The
[observed run](SHARED_CONTRACT_VERIFICATION.md) records the actual November 4
Google workflow and cleanup at `327e8bc`.
The command creates and deletes one disposable event in the authenticated
account's primary calendar. Obtain local `credentials.json`, follow the
[authentication instructions](../README.md#shared-google-calendar-authentication),
and keep credential/token files out of Git and evidence.

```sh
uv run python scripts/google_calendar_auth.py
uv run python -m scripts.verify_put_live
```

The retained script name is `verify_put_live`; it now checks the complete tagged
workflow using TestClient's **in-process HTTP** calls through normal dependencies
and real Google adapters. It does not start a Uvicorn listener or prove a
network/server-restart workflow. The [manual tutorial](../TUTORIAL.md) covers a
running server separately.

The script first checks installed package version and Git commit. Then it:

1. POSTs a uniquely named event and GETs it back.
2. Adds a non-shared description directly through the Google SDK.
3. PUTs all three shared fields and verifies the unchanged ID and new values.
4. GETs again, comparing timestamps by instant rather than string formatting.
5. Independently reads Google and checks ID, title, both times, and description.
6. Attempts DELETE, GET expecting 404, and repeated DELETE expecting 404.

Evidence is one JSON line per step: public package version/commit, a generated
run marker, statuses, and Boolean checks. No event ID, title, credential, or raw
exception message is printed. Only exit code 0 with every check passing is a
successful run. A failed value check, exception, or cleanup check returns 1.

Once the created ID is known, cleanup runs in `finally`, even if later checks
fail. Cleanup accepts a first DELETE of 204 or already-gone 404, and attempts
the remaining checks even after an earlier failure. If a failed POST yields no
ID, automatic cleanup cannot identify an event. Inspect the test calendar for
the printed run marker before repeating the workflow; never blindly resend an
uncertain POST. Report unresolved cleanup explicitly.

## Remaining evidence and owners

Jim owns tagged package adoption and its tests/docs. Ka Pui owns formal
conformance wiring and real-operation re-verification; they can reproduce this
script against the reviewed adoption commit. Juno/Niriti maintain DESIGN.md,
and Kristie coordinates interface/design review and accepted revisions.

Real Google verification of the four common operations passed on November 4
at clean commit `327e8bc`, with shared commit `1c1cad7`. Its historical output
used the former tag label `v0.1.0`; that commit is now published as
`v0.1.0-rc.1`. The
[verification record](SHARED_CONTRACT_VERIFICATION.md) contains environment,
provenance, exact commands, sanitized output, exit status, and cleanup results.
Formal shared conformance wiring, another teammate's reproduction, and adoption
PR/CI approval remain open. Future runs must record their own revisions and
observed results; HW1 evidence does not establish this shared-package path.

## Local event-shape policy

Team 5 retains the HTTP ID policy: 1-1024 letters, digits, underscores, or
hyphens, forwarded unchanged. The shared package keeps IDs opaque. Tests cover
ordinary and recurring-instance IDs and invalid character/length rejection
before provider calls. Recurrence is determined from Google metadata, not IDs.

GET retains 422 `invalid_input` for all-day events; timed series/instances can
be read through the four-field representation. PUT/PATCH read the target first
and reject all-day events and recurring-series parents with 400 `invalid_input`
and `retryable=false`, without patching. Individual timed instances are allowed;
only summary/start/end are patched, leaving series metadata and unrelated fields
untouched. DELETE behavior is unchanged. Malformed provider time structures are
502 `provider_error`. Body-validation errors remain 422.

`tests/test_event_shape_policy.py` verifies these behaviors using controlled
provider state; it does not establish real Google recurrence behavior. See
[Google's recurrence guide](https://developers.google.com/workspace/calendar/api/guides/recurringevents)
for the distinction between series parents and instances.
