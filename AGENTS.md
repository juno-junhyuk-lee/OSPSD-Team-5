# Contributor instructions

## Code and setup

- `app/observability.py`: request counters/histograms and one sanitized outcome
  log around authentication, validation, and HTTP handling. Error handlers pass
  safe context to it instead of logging the same failure twice.
- `tests/test_observability.py`: controlled HTTP checks with the real
  OpenTelemetry SDK in-memory reader; no live Google or cloud export.
- `app/tracing.py`: app-owned SDK traces, safe request/RPC spans, and sanitized
  resource metadata. Never enable automatic exception/event or body capture.
- `tests/test_tracing.py`: normal HTTP/adapter wiring with fake Google clients
  and a local span exporter; parentage, correlation, privacy, and failure checks.
- [Observability guide](docs/OBSERVABILITY.md): labels, correlation, limits,
  and remaining Level 3 integration/verification.

HW2 uses calendar-contract tag `v0.1.0-rc.1`, commit
`1c1cad7a0732ddb242a05400d8833d94e4422424`. Import shared Event, CreateEvent,
ReplaceEvent, CalendarService, CalendarError, and ErrorCode from that package.
Use start/end string fields; reject legacy start_time/end_time and unknown
request fields. PATCH remains full-field replacement. This migration supersedes
HW1 field-name and per-route error wiring descriptions in historical evidence.

- `app/calendar_service.py`: composes the four existing Google adapters and
  translates operation-specific errors into CalendarError before the shared
  interface returns. No provider errors or SDK types cross that boundary.
- `app/calendar_service_dependencies.py`: get_calendar_service supplies the
  shared protocol; existing operation factories remain its subdependencies.
- `tests/test_calendar_service.py` and `tests/test_shared_calendar_http.py`:
  direct shared-boundary checks and whole-service HTTP substitution.
- `tests/test_shared_provider_failures.py`: controlled adapter failure phases.
- `tests/test_event_shape_policy.py`: offline HTTP ID checks, pre-write rejection
  of all-day/series replacements, and timed-instance preservation.
- `tests/test_shared_conformance.py`: the shared `CalendarServiceConformance`
  suite against `GoogleCalendarService`, offline on the fake Google client;
  `CALENDAR_LIVE_CONFORMANCE=1` also runs it against real Google.
- `scripts/verify_put_live.py`: tagged POST/GET/PUT/GET/DELETE workflow with
  independent Google checks and cleanup. This command changes Google state.
- `tests/test_verify_put_live.py`: controlled script checks; not live evidence.
- [Shared adoption guide](docs/SHARED_CONTRACT_ADOPTION.md): migration and setup.
- [Tagged Google evidence](docs/SHARED_CONTRACT_VERIFICATION.md): successful
  normal workflow at clean `327e8bc`; conformance/review/CI remain separate.

- `GET /calendars/{calendar_id}`: Google-backed primary calendar metadata operation.
- `tests/test_calendars.py`: offline calendar success and missing-ID tests.
  The Calendar response model lives in `app/models.py`; its provider lookup is in `app/google_calendar.py`.
- `app/calendar_provider.py`: typed calendar metadata interface; Google SDK details
  stay in `GoogleCalendarReader` in `app/google_calendar.py`. Metadata failures
  use its service exceptions; calendar GET maps them to shared `ServiceError`.
- `app/calendar_dependencies.py`: selects the calendar reader; calendar HTTP tests
  substitute it through FastAPI dependency overrides.

- `app/errors.py`: Level 5 shared error format (`ServiceError`, `ErrorCode`),
  response schema, CalendarError/ServiceError/request-validation handlers, and
  sanitized failure logs. DELETE, both GETs, POST, PUT, and PATCH use it.
- `app/main.py`: FastAPI routes; Google-backed calendar GET, event GET, POST, PATCH, PUT, and DELETE.
  PUT and PATCH share `EventUpdater` and its failure mapping; PUT keeps non-shared Google fields.
- `app/google_auth.py`: noninteractive token loading and refresh for API requests.
- `app/google_calendar.py`: Google calendar metadata retrieval and translation.
- `app/google_create_events.py`: `GoogleEventCreator`, shared authorization,
  creation, response translation, and creation error translation.
- `app/event_creation_provider.py`: `EventCreator` contract and creation service errors;
  the shared service receives it through a FastAPI subdependency.
- `app/event_creation_dependencies.py`: selects the creator supplied to POST.
- `tests/test_google_calendar.py`: offline calendar metadata translation tests.
- `tests/test_google_create_events.py`: offline POST provider and token tests.
- `app/event_update_provider.py`: `EventUpdater` contract and update service errors.
- `app/event_update_dependencies.py`: selects the event updater; PATCH HTTP tests
  can substitute it through FastAPI dependency overrides.
- `app/google_update_events.py`: `GoogleEventUpdater`, shared authorization,
  patch/get, response translation, and update error translation.
- `tests/test_update_events.py`: offline update contract and provider-failure tests.
- `app/event_deletion_provider.py`: `EventDeleter` contract and deletion service errors.
- `app/google_delete_events.py`: `GoogleEventDeleter`; DELETE provider call and
  error translation; reuses POST's token loading.
- `tests/test_google_delete_events.py`: offline DELETE provider translation tests.
- `tests/test_google_update_events.py`: offline PATCH provider translation tests.
- `tests/test_update_event_contract.py`: controlled updater HTTP contract tests.
- `tests/test_delete_events.py`: offline deletion contract and provider-failure tests.
- `tests/test_delete_event_contract.py`: controlled deleter HTTP contract tests and
  dependency overrides.
- `app/event_provider.py`: `EventReader` contract and event retrieval service errors.
- `app/event_dependencies.py`: selects the event reader for FastAPI injection.
- `app/event_deletion_dependencies.py`: selects the event deleter for FastAPI injection.
- `app/google_events.py`: `GoogleEventReader` implementation and Google field translation.
- `tests/test_google_events.py`: offline Google-backed HTTP contract and failure tests.
- `tests/test_google_auth.py`: isolated token lifecycle tests.
- `app/models.py`: local Calendar metadata model; event/request models come
  directly from calendar_contract.
- `tests/test_events.py`: controlled reader HTTP contract tests and dependency overrides.
- `tests/test_create_events.py`: offline creation and validation contract tests.
- `tests/test_create_event_contract.py`: controlled creator HTTP tests with
  isolated dependency overrides and cleanup, separate from Google SDK fixtures.
- `tests/test_request_validation.py`: shared POST/PATCH validation errors,
  no provider operation on invalid input, safe logs, and OpenAPI contracts.
- `tests/conftest.py`: isolated provider data, Google clients, and shared HTTP fixture.
- [README.md](README.md): setup, API contract, and testing strategy.
- [Work plan](docs/WORK_PLAN.md): task owners and milestone dates.

Use the README setup and commands. Each member owns one distinct, useful public
operation through Levels 1–5, including its tests and documentation. Keep Level 1
operations small and backed by local data. Jim Lo owns `POST /events`; its
implemented Level 1 creation contract is in the README. Preserve existing
GET behavior when adding POST. Creation tests must isolate fake provider state.
Preserve each operation's public contract for Level 2 and translate Google
fields before returning them. Do not commit credentials or add unnecessary layers.
Fast tests must run without internet or Google credentials.

Kristie owns event GET. It uses the shared account's primary Google Calendar;
run scripts/google_calendar_auth.py before serving requests. Never start browser
authorization in a route. Preserve the four-field Event response and existing 404.
The shared service delegates event GET to the typed `EventReader` boundary;
SDK calls and translation stay inside `GoogleEventReader`. Adapter errors come from `app/event_provider.py`
and become CalendarError in the shared service.
The shared service receives the event reader through `app/event_dependencies.py`.
Contract tests use dependency overrides and restore prior overrides after each test. Keep Google
provider and CRUD fixtures separate from these controlled reader tests.
Calendar GET already receives its reader through `app/calendar_dependencies.py`.
Jim's POST writes to the same primary calendar and returns Google's event ID.
The shared service delegates POST to EventCreator in app/event_creation_provider.py.
Google calls, translation, and known failure handling stay in `GoogleEventCreator`.
GoogleCalendarService translates permission, authorization, temporary, and
unconfirmed creation failures into CalendarError. The HTTP handler maps them
to 403/503/502 and preserves operation-specific retry advice. Use the shared
handler for one sanitized failure log; do not add route/adapter logging or expose raw input.
FastAPI request validation uses the shared shape: malformed/empty JSON is 400,
while invalid valid-JSON input is 422. POST, PUT, and PATCH use shared strict
models. Preserve the shared `load_credentials` helper used by PATCH and DELETE.
`app/event_creation_dependencies.py` selects Google for the service subdependency;
POST receives CalendarService and does not construct the provider.
Controlled creator HTTP tests override that dependency, use fresh
creator state, and restore prior overrides in `finally`. Keep Google provider
and CRUD fixtures separate from these interface-based tests.
GET reads the provider directly; no local event mirror is used. Never fall back
to local creation or automatically retry uncertain writes. The provider fake
stores insert results for GET only in fast tests; do not claim it verifies a
real create/read workflow. Keep both OAuth scopes in the shared setup script.
See [POST verification](docs/POST_LEVEL2_VERIFICATION.md) for real-run evidence.
See [POST Level 3 verification](docs/POST_LEVEL3_VERIFICATION.md) for the provider
boundary, refactor checks, and teammate reproduction steps.
See [POST Level 4 verification](docs/POST_LEVEL4_VERIFICATION.md) for normal wiring,
controlled substitution, and real verification through dependency injection.
See [POST Level 5 verification](docs/POST_LEVEL5_VERIFICATION.md) for shared errors,
sanitized logs, real creation/cleanup, and an isolated real authorization failure.
Keep strict mypy checks. Calls to untyped Google credentials and auth exceptions
are scoped in pyproject.toml; SDK imports have local `import-untyped` exclusions.

## Working together

Agree on a task's owner, reviewer, expected behavior, and completion criteria
before starting. Work on one implementation task at a time. Report blockers or
urgent tasks to the team and agree on reassignment; leave unfinished work visible.

The owner implements the task, runs checks, and opens a linked PR. Another
teammate reviews the code, contract, tests, dependencies, and docs. The owner
resolves comments and merges after approval and passing checks. Disclose AI
assistance; each student must understand and verify their submitted work.
Discuss contract changes together and update tests and docs with the code.

Use Python 3.14 with uv and the locked dependencies in `uv.lock`. Run
`uv sync --frozen`, then the README checks: `uv run ruff check .`,
`uv run ruff format --check .`, `uv run mypy`, `uv run pytest -v`, and
`git diff --check`. Also run `uv run mypy scripts/verify_put_live.py` when editing
the verification script. GitHub Actions runs the uv-based checks on pushes and PRs.
Mypy currently covers
app and tests in strict mode. Calendar metadata and event retrieval have offline
tests using controlled provider responses.
Keep expected values independent of lookup data and fast tests offline.
Do not bypass checks or report missing tests as passing. See the README for
real-provider verification evidence and remaining teammate verification.

## Releases

Use `v0.1.0-alpha.1` for the review prerelease and `v0.1.0-beta.1` for the final
release; increment the suffix for fixes. Explain compatibility and setup changes
in PRs and release notes.

Before each release, name a coordinator and a different teammate as verifier.
The coordinator selects a checked commit and creates an annotated tag. The
verifier follows setup and runs tests and a provider workflow from a fresh
checkout of that tag. Publish a GitHub Release with changes, issue/PR links,
limitations, and matching verification/CI evidence. Use a different coordinator
for the final release. Merged work is only released once publication happens.

Never move published tags. Fix defective releases in a new version and tell
users whether to return to an earlier version or wait, including any external
state that reverting code would not restore. After the review release, record
one observation about the process and any adjustment.

## Comments

Keep comments short and explain only non-obvious behavior. Use direct phrases;
for simple definitions prefer `name = meaning`. Add detail only when requested.
