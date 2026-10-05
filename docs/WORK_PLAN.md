# HW1 work plan

The Level 1 foundations and endpoint/tests were developed with Codex assistance.
Record actual work and reviews in PRs; adjust ownership if effort changes.

## Operation ownership

Following clarification with the instructor, each member must own one distinct
public operation through Levels 1–5, including its tests and documentation.
Shared setup and integration work support those operations but do not replace
individual operation ownership.

| Owner | Operation | Current status | Reviewer |
| --- | --- | --- | --- |
| Juno Lee | `GET /calendars/{calendar_id}` | Level 1 local metadata lookup and HTTP tests implemented; review and PR CI pending | To be agreed with the team |
| Jim Lo | `POST /events` | Level 1 approved and merged in PR #5 with passing CI; Level 2 design documented, implementation and real verification pending | Level 1: Ka Pui and Juno; Level 2: to be agreed |

The team still needs to record the other members' operation assignments.
The tables below retain the earlier GET implementation history; they do not
establish the team's final operation ownership.

## Existing Level 1 GET work

| Owner | Work | Reviewer |
| --- | --- | --- |
| Juno Lee | App scaffold, Event model, API contract, setup docs, pinned dependencies, and CI | Kristie Lee |
| Kristie Lee | Fixed event lookup, GET route, HTTP tests, test evidence, and endpoint demonstration | Juno Lee |

Juno's foundation was merged in [PR #3](https://github.com/juno-junhyuk-lee/OSPSD-Team-5/pull/3).
Kristie's endpoint and two offline HTTP tests are implemented, preserving the
README contract. Python 3.14.8 installation, dependency checks, Ruff, strict mypy,
and both tests passed locally. The success test detected a deliberately incorrect
title; restoring it made both tests pass again. See the README for evidence.

Kristie's GET implementation was merged in [PR #4](https://github.com/juno-junhyuk-lee/OSPSD-Team-5/pull/4)
after Juno's approval, with passing PR CI. Local curl verification was completed
during the POST work. Setup and workflow verification from another teammate's
checkout remain pending; releases are handled by the team.

## Jim Lo's POST Level 1 work

The contract is in the README's event creation section. Work is split
into three reviewable changes:

1. Document the POST contract and ownership, and update contributor instructions.
2. Implement local event creation and input validation with offline HTTP tests.
3. Add a usage walkthrough, verification evidence, and Level 2 handoff notes.

The first change defines the contract. The second implements POST with offline
tests. The third documents usage, local verification, and the Level 2 handoff.
Another teammate must review substantive changes before merging.

Local verification on October 4, 2026 (macOS, Python 3.14.8): 22 tests, Ruff,
strict mypy, dependency compatibility, and diff checks passed. Live curl checks
confirmed creation, retrieval, validation failure, and unchanged predefined
data. A controlled missing-write defect was detected by the POST-to-GET test;
restoring normal storage made it pass. Details are in the README. Codex assisted
with the POST implementation, tests, documentation, and local verification.

Level 1 was merged in [PR #5](https://github.com/juno-junhyuk-lee/OSPSD-Team-5/pull/5)
after Ka Pui and Juno approved it. Juno reproduced the 22 tests, Ruff checks,
and strict mypy locally. [PR CI](https://github.com/juno-junhyuk-lee/OSPSD-Team-5/actions/runs/37237676633)
passed. Real Google creation remains Jim's Level 2 work.

Level 1 completion requires `201` creation, generated IDs, retrieval through
the existing GET route, documented `422` validation failures without state
changes, isolated tests, passing checks, and matching documentation. Local
memory is sufficient; Google authentication and actual provider writes belong
to Jim's Level 2 work.

## Jim Lo's POST Level 2 work

Start from the current merged main, including POST Level 1, shared authentication
(PR #6), and calendar details (PR #7). Use the shared test account's primary
calendar and the existing OAuth client and `calendar.events` scope. The README's
Level 2 POST handoff records field mapping, setup, transition behavior, and tests.

Work is split into four reviewable changes:

1. Document the integration design and local setup, and update Level 1 status.
2. Add Google creation and response translation with offline tests.
3. Connect POST to Google and preserve HTTP contract tests and existing routes.
4. Record real HTTP create/read verification, cleanup, and teammate instructions.

The first change is committed. The second adds `app/google_calendar.py` and
offline creation/authorization tests; HTTP wiring and real verification remain
pending. The module checks returned data, uses provider IDs, and avoids creation
retries. Codex assisted with planning, module implementation, and offline tests.

Keep the API inputs, 201 response, validation rules, and returned event shape.
Use Google's event ID. A temporary local mirror preserves same-process retrieval
until Kristie's GET reads Google; verify persistence independently against Google.
Do not silently use local creation when authorization fails or automatically
retry a write with an uncertain outcome.

Completion requires passing offline checks, a real HTTP POST followed by an
independent Google read, cleanup of verification events, teammate review, and
at least two members running POST against Google with their own local tokens.
The shared authentication script alone does not complete this operation.

## Provider integration requirements

The earlier plan to assign three members exclusively to Level 2 support tasks
has been superseded by operation ownership. The existing GET handoff uses the
authenticated user's primary calendar; POST uses the same calendar and ID space
as described in the README. At least two members must verify the real
integration; by the first checkpoint everyone must be able to run the service
and fast tests.

## Milestones (before class)

- October 7, 2026: Levels 1 and 2.
- October 14, 2026: Levels 3 and 4, review prerelease, and sister-team review.
- October 21, 2026: Level 5, final release, review fixes, and demonstration.

Foundation setup uses Python 3.14, pinned dependencies, Ruff, strict mypy, and
GitHub Actions. POST Level 1 review and CI are complete. Current POST gaps:
Google creation, offline integration tests, real verification by two members,
and Level 2 PR review/CI. The foundation PR's CI initially failed at pytest
because it had no tests; GET and POST Level 1 PR CI now pass.
Follow the release rules in [AGENTS.md](../AGENTS.md).

## Evidence to keep as work progresses

Use PRs and release notes for design reasoning, defect-detection evidence, bug
investigations, and teammate extensions (or why an extension was unnecessary).
Later, explain the cost of an operation whose work grows with input size.
Respond to substantive sister-team feedback and make one justified usability
improvement. Submit the final PR, release, tag, commit, matching checks, and a
note linking completed requirements and gaps. Have a teammate check the final
rubric and verify the release. Every member participates in the demonstration
and submits a private reflection. Before each class, post a linked team update
covering shipped work, changed decisions, blockers, and next steps.
