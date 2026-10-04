# HW1 work plan

The Level 1 foundations and endpoint/tests were developed with Codex assistance.
Student owners remain responsible for understanding and verifying their work.
Record actual work and reviews in PRs; adjust ownership if effort changes.

## Operation ownership

Following clarification with the instructor, each member must own one distinct
public operation through Levels 1–5, including its tests and documentation.
Shared setup and integration work support those operations but do not replace
individual operation ownership.

| Owner | Operation | Current status | Reviewer |
| --- | --- | --- | --- |
| Jim Lo | `POST /events` | Level 1 contract documented; implementation and tests pending | To be agreed with the team |

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

Kristie's scope ends with the Level 1 implementation PR. Remaining team steps:
Juno reviews that PR; the team verifies its CI and reproduces setup and curl
requests from another checkout. Merge and later releases are handled by the team. A TestClient
check has verified Swagger availability; a separate live-server demonstration
remains pending.

## Jim Lo's POST Level 1 work

The planned contract is in the README's event creation section. Work is split
into three reviewable changes:

1. Document the POST contract and ownership, and update contributor instructions.
2. Implement local event creation and input validation with offline HTTP tests.
3. Add a usage walkthrough, verification evidence, and Level 2 handoff notes.

The first change contains documentation only. POST is not implemented, and
Levels 1–5 are not complete. Jim must understand and verify AI-assisted work;
another teammate must review substantive changes before merging. Codex assists
with this contract documentation; Jim reviews each change before authorizing
its commit.

Level 1 completion requires `201` creation, generated IDs, retrieval through
the existing GET route, documented `422` validation failures without state
changes, isolated tests, passing checks, and matching documentation. Local
memory is sufficient; Google authentication and actual provider writes belong
to Jim's Level 2 work.

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
GitHub Actions. Current gaps: implementation PR CI, teammate review/setup
reproduction, live-server demonstration, and Google integration. The foundation
PR's CI failed at pytest because it had no tests; the two new tests pass locally.
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
