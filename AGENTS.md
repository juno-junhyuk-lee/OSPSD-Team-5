# Contributor instructions

## Code and setup

- `GET /calendars/{calendar_id}`: Local calendar metadata operation.
- `tests/test_calendars.py`: offline calendar success and missing-ID tests.
  The Calendar response model lives in `app/models.py`; its lookup is in `app/main.py`.

- `app/main.py`: FastAPI routes; Google-backed event GET and local POST/calendar GET.
- `app/google_auth.py`: noninteractive token loading and refresh for API requests.
- `app/google_events.py`: Google event retrieval, translation, and service errors.
- `tests/test_google_events.py`: offline Google-backed HTTP contract and failure tests.
- `tests/test_google_auth.py`: isolated token lifecycle tests.
- `app/models.py`: Event response model and creation input validation.
- `tests/test_events.py`: offline HTTP success and missing-ID contract tests.
- `tests/test_create_events.py`: offline creation and validation contract tests.
- `tests/conftest.py`: controlled Google client, shared HTTP fixture, local state cleanup.
- [README.md](README.md): setup, API contract, and testing strategy.
- [Work plan](docs/WORK_PLAN.md): task owners and milestone dates.

Use the README setup and commands. Each member owns one distinct, useful public
operation through Levels 1–5, including its tests and documentation. Keep Level 1
operations small and backed by local data. Jim Lo owns `POST /events`; its
implemented Level 1 creation contract is in the README. Preserve existing
GET behavior when adding POST. Creation tests must restore local state.
Preserve each operation's public contract for Level 2 and translate Google
fields before returning them. Do not commit credentials or add unnecessary layers.
Fast tests must run without internet or Google credentials.

Kristie owns event GET. It uses the shared account's primary Google Calendar;
run scripts/google_calendar_auth.py before serving requests. Never start browser
authorization in a route. Preserve the four-field Event response and existing 404.
Local POST IDs are not retrievable from Google until POST Level 2 is integrated.
The provider fake bridges local creation and retrieval only in fast tests; do not
claim it verifies the real create/read workflow.

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
app and tests in strict mode. All 46 tests pass locally on Windows with Python 3.14.8.
Keep expected values independent of lookup data and fast tests offline.
Do not bypass checks or report missing tests as passing. Implementation PR CI
results for this GET Level 2 branch still need verification. See the README for
real GET evidence and the additional teammate's required reproduction.

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
