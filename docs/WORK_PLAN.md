# HW1 work plan

Proposed split for team agreement. The foundations were drafted with Codex;
the endpoint and tests are left for Kristie to implement. Record actual work
and reviews in PRs. Aim for similar effort and adjust if one side takes longer.

## Level 1

| Owner | Work | Reviewer |
| --- | --- | --- |
| Juno Lee | App scaffold, Event model, API contract, setup docs, pinned dependencies, and CI | Kristie Lee |
| Kristie Lee | Fixed event lookup, GET route, HTTP tests, test evidence, and endpoint demonstration | Juno Lee |

Agree on the README contract first. Juno's foundation is ready for Kristie when
setup works and the model matches the documented fields. Kristie's part is done
when known and unknown IDs behave as documented and offline HTTP tests pass.
Both review each other's work and reproduce setup, running, and testing.

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
GitHub Actions. Current gaps: endpoint, tests, GitHub CI execution, teammate
review/setup reproduction, and Google integration. CI will fail until tests
are added. Follow the release rules in [AGENTS.md](../AGENTS.md).

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
