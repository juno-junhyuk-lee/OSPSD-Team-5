# Milestone 1 submission — Team 5

## Release pointer

| Field | Value |
| --- | --- |
| Annotated tag | `v0.1.0-alpha.1` |
| Commit SHA | `9500e0309f7cd43b39f8b08941c7b7bff3b287f0` |
| Tag URL | https://github.com/juno-junhyuk-lee/OSPSD-Team-5/releases/tag/v0.1.0-alpha.1 |
| Commit URL | https://github.com/juno-junhyuk-lee/OSPSD-Team-5/commit/9500e0309f7cd43b39f8b08941c7b7bff3b287f0 |

This PR branch includes the calendar service implementation (merged from `main`)
plus submission docs and uv-based setup. Reviewers should inspect the full
branch, not only this markdown file. The original Milestone 1 freeze remains
tag `v0.1.0-alpha.1`.

Checkout this PR branch:

```sh
git fetch origin docs/milestone-1-submission
git checkout docs/milestone-1-submission
uv sync
```

Or checkout the tagged Milestone 1 freeze:

```sh
git fetch origin tag v0.1.0-alpha.1
git checkout v0.1.0-alpha.1
```

## Team

| | |
| --- | --- |
| Team | OSPSD Team 5 |
| Vertical | Calendar service (HTTP API) |
| Provider | Google Calendar (shared test account primary calendar) |
| Members | Juno Lee, Niriti Pahadi, Kristie Lee, Jim Lo, Ka Pui Cheung |

## Operation ownership

| Owner | Operation |
| --- | --- |
| Juno Lee | `GET /calendars/{calendar_id}` |
| Kristie Lee | `GET /events/{event_id}` |
| Jim Lo | `POST /events` |
| Niriti Pahadi | `PATCH /events/{event_id}` |
| Ka Pui Cheung | `DELETE /events/{event_id}` |

## Setup and contributor docs

- [README.md](../README.md): Python 3.14, uv (`uv sync` / `uv.lock`), install/run, API contracts, shared Google auth (`credentials.json` / `token.json` local only), cleanup, and check commands.
- [AGENTS.md](../AGENTS.md): code map, architectural constraints, contribution and release rules.
- Tests: offline suite under [`tests/`](../tests/) (`uv run pytest`; no Google credentials required).
- Provider verification: [POST](POST_LEVEL2_VERIFICATION.md), [PATCH](PATCH_LEVEL2_VERIFICATION.md), [DELETE](DELETE_LEVEL2_VERIFICATION.md), [GET](VERIFICATION.md).
- Never commit secrets (`credentials.json`, `token.json` are gitignored).

## Provider credentials and permissions

- OAuth scopes (requested by `scripts/google_calendar_auth.py`):
  - `https://www.googleapis.com/auth/calendar.events`
  - `https://www.googleapis.com/auth/calendar.calendars.readonly`
- Place the shared Desktop OAuth client JSON as `credentials.json`, run
  `uv run python scripts/google_calendar_auth.py`, and sign in as
  `ospsd.team5@gmail.com`.
- Fast offline tests do not require credentials or network access.

## CI

GitHub Actions **Checks** use `uv sync --frozen` then ruff/mypy/pytest.
See the Actions tab for this branch and for tagged commit `9500e03`.

Reproduce locally:

```sh
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest -v
```

## Development workflow (summary)

Recorded in [AGENTS.md](../AGENTS.md) and [WORK_PLAN.md](WORK_PLAN.md):

- One owned public operation per member through Levels 1–5, with tests and docs.
- Agree owner/reviewer/behavior before starting; PR review required before merge.
- Review prerelease tag `v0.1.0-alpha.1`; final release `v0.1.0-beta.1`.
- Coordinator creates the annotated tag; a different teammate verifies from a fresh checkout.
- Never move published tags; fix defective releases with a new version.

## Staff reviews and access

TA and professor have been given access to the repo, PR, tag, and Actions logs,
and are requested as reviewers on this PR.
