# HW1 work plan

The Level 1 foundations and endpoint/tests were developed with Codex assistance.
Student owners remain responsible for understanding and verifying their work.
Record actual work and reviews in PRs; adjust ownership if effort changes.

## Level 1

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

## Level 2

Assign the other three members to authentication/configuration, Google event
retrieval, and response translation/real verification. Preserve the Level 1
contract and use the authenticated user's primary calendar. At least two members
must verify the real integration; by the first checkpoint everyone must be able
to run the service and fast tests.

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
