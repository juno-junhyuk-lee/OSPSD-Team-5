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
| Juno Lee | `GET /calendars/{calendar_id}` | Level 2 Google lookup and offline tests implemented; Juno verified real HTTP retrieval; second-teammate verification, review, and PR CI pending | To be agreed with the team |
| Kristie Lee | `GET /events/{event_id}` | Level 2 implementation and 46-test suite verified locally; second-member reproduction, policy review, PR CI pending | To be agreed with the team |
| Jim Lo | `POST /events` | Level 1 code, tests, walkthrough, and local verification complete; teammate review and branch CI pending | To be agreed with the team |

The team still needs to record Niriti's and Ka Pui's final operation assignments.
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

Remaining steps: assign a reviewer, verify setup from another checkout, and
check GitHub CI after publishing the branch. Google integration is Level 2 work.

Level 1 completion requires `201` creation, generated IDs, retrieval through
the existing GET route, documented `422` validation failures without state
changes, isolated tests, passing checks, and matching documentation. Local
memory is sufficient; Google authentication and actual provider writes belong
to Jim's Level 2 work.

## Kristie Lee's GET Level 2 work

The shared authentication setup was merged in PR #6. GET now uses Google's
primary calendar and translates its response to the existing Event contract.
Implementation, offline tests, and documentation are split into three commits.
Missing events retain 404; authentication-required, all-day and provider failures
have documented 503, 422 and 502 responses. Missing titles become empty strings;
these edge-case policies require teammate review.

Local evidence (Windows, Python 3.14.8): 46 tests, Ruff, strict mypy and diff
checks passed. Fast tests also passed with external network connections blocked.
A deliberately incorrect translated title was caught by a JSON assertion, then
restored. Real Google requests through the FastAPI TestClient verified 200 for
Team 5 GET Test and 404 for an absent ID. See the README for reproduction steps.

Remaining: publish the PR, verify its CI, and have an additional teammate run
the provider-backed FastAPI endpoint and record the commit/environment/results.
Do not mark Level 2 fully verified before that second member's execution.
The live POST-to-GET workflow is incomplete until Jim's POST uses Google;
the offline fixture bridges local data only for historical Level 1 tests.

## Provider integration requirements

The earlier plan to assign three members exclusively to Level 2 support tasks
has been superseded by operation ownership. The existing GET handoff uses the
authenticated user's primary calendar; POST provider details will be defined
when its Level 2 work begins. At least two members must verify the real
integration; by the first checkpoint everyone must be able to run the service
and fast tests.

## Milestones (before class)

- October 7, 2026: Levels 1 and 2.
- October 14, 2026: Levels 3 and 4, review prerelease, and sister-team review.
- October 21, 2026: Level 5, final release, review fixes, and demonstration.

Foundation setup uses Python 3.14, pinned dependencies, Ruff, strict mypy, and
GitHub Actions. Current calendar-details gaps: second-teammate real verification,
review, and branch CI. Event provider integrations remain separate work. The foundation PR's CI initially failed
at pytest because it had no tests; GET PR CI passed; the current Level 2 branch has 25 passing offline tests.
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
