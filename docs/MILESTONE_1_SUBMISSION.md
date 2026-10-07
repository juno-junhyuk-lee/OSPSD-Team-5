# Milestone 1 submission — Team 5

## Release pointer

| Field | Value |
| --- | --- |
| Annotated tag | `v0.1.0-alpha.1` |
| Commit SHA | `9500e0309f7cd43b39f8b08941c7b7bff3b287f0` |
| Tag URL | https://github.com/juno-junhyuk-lee/OSPSD-Team-5/releases/tag/v0.1.0-alpha.1 |
| Commit URL | https://github.com/juno-junhyuk-lee/OSPSD-Team-5/commit/9500e0309f7cd43b39f8b08941c7b7bff3b287f0 |

Checkout the tagged revision:

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

- [README.md](../README.md): Python 3.14, pinned `requirements.txt`, install/run, API contracts, shared Google auth (`credentials.json` / `token.json` local only), cleanup, and check commands.
- [AGENTS.md](../AGENTS.md): code map, architectural constraints, contribution and release rules.
- Provider verification: [POST](POST_LEVEL2_VERIFICATION.md), [PATCH](PATCH_LEVEL2_VERIFICATION.md), [DELETE](DELETE_LEVEL2_VERIFICATION.md), [GET](VERIFICATION.md).
- Never commit secrets (`credentials.json`, `token.json` are gitignored).

## CI for the tagged commit

GitHub Actions **Checks** on `9500e03`: success  
https://github.com/juno-junhyuk-lee/OSPSD-Team-5/actions/runs/37679291707

Local verification on that revision: `pip check`, Ruff lint/format, strict mypy, pytest (100 passed), `git diff --check`.

## Development workflow (summary)

Recorded in [AGENTS.md](../AGENTS.md) and [WORK_PLAN.md](WORK_PLAN.md):

- One owned public operation per member through Levels 1–5, with tests and docs.
- Agree owner/reviewer/behavior before starting; PR review required before merge.
- Review prerelease tag `v0.1.0-alpha.1`; final release `v0.1.0-beta.1` (increment suffix for fixes).
- Coordinator creates the annotated tag on a checked commit; a different teammate verifies from a fresh checkout of the tag.
- Never move published tags; fix defective releases with a new version and document external state that code revert would not undo.

## Staff access

Repository: https://github.com/juno-junhyuk-lee/OSPSD-Team-5  
Please ensure the TA and professor can view the repo, this PR, the tag, and Actions logs. Request their GitHub reviews on this PR once usernames are confirmed.
