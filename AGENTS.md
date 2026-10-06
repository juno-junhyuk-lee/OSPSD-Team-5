# Contributor instructions

## Code and setup

- `GET /calendars/{calendar_id}`: Google-backed primary calendar metadata operation.
- `tests/test_calendars.py`: offline calendar success and missing-ID tests.
  The Calendar response model lives in `app/models.py`; its provider lookup is in `app/google_calendar.py`.

- `app/main.py`: FastAPI routes; Google-backed calendar GET, event GET, POST, and DELETE.
- `app/google_auth.py`: noninteractive token loading and refresh for API requests.
- `app/google_calendar.py`: Google calendar metadata retrieval and translation.
- `app/google_create_events.py`: POST authorization, creation, and response translation.
- `tests/test_google_calendar.py`: offline calendar metadata translation tests.
- `tests/test_google_create_events.py`: offline POST provider and token tests.
- `app/google_delete_events.py`: DELETE provider call; reuses POST's token loading.
- `tests/test_delete_events.py`: offline deletion contract and provider-failure tests.
- `app/google_events.py`: Google event retrieval, translation, and service errors.
- `tests/test_google_events.py`: offline Google-backed HTTP contract and failure tests.
- `tests/test_google_auth.py`: isolated token lifecycle tests.
- `app/models.py`: Event response model and creation input validation.
- `tests/test_events.py`: offline HTTP success and missing-ID contract tests.
- `tests/test_create_events.py`: offline creation and validation contract tests.
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
Jim's POST writes to the same primary calendar and returns Google's event ID.
GET reads the provider directly; no local event mirror is used. Never fall back
to local creation or automatically retry uncertain writes. The provider fake
stores insert results for GET only in fast tests; do not claim it verifies a
real create/read workflow. Keep both OAuth scopes in the shared setup script.
See [POST verification](docs/POST_LEVEL2_VERIFICATION.md) for real-run evidence.
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

Use Python 3.14 and the pinned requirements. Run the README check commands:
Ruff lint/format checks, strict mypy, pytest, and git diff --check. GitHub Actions
runs lint, formatting, types, and tests on pushes and PRs. Mypy currently covers
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
