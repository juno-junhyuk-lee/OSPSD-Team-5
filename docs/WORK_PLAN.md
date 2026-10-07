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
| Juno Lee | `GET /calendars/{calendar_id}` | Level 2 merged in PR #9 | See PR #9 reviews |
| Kristie Lee | `GET /events/{event_id}` | Level 2 merged in PR #8 | See PR #8 reviews |
| Ka Pui Cheung | `DELETE /events/{event_id}` | Levels 1–2 in PR #11, stacked on PR #10; real Google run recorded in `docs/DELETE_LEVEL2_VERIFICATION.md`; second verifier and review pending | Requested in PR #11 |
| Jim Lo | `POST /events` | Level 1 merged in PR #5; Level 2 PR #10 has teammate approval and real verification; integration with main awaits reviewed merge commit and CI | Juno and Ka Pui |
| Niriti Pahadi | `PATCH /events/{event_id}` | Levels 1–2 implemented on `feature/calendar-patch-events`; real Google run recorded in `docs/PATCH_LEVEL2_VERIFICATION.md`; PR review and second verifier pending | TBD |

Ka Pui's DELETE ownership is recorded above. Niriti owns event update.
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
after Ka Pui and Juno approved it, with passing CI. Google integration is Level 2 work.

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

This implementation was merged in
[PR #8](https://github.com/juno-junhyuk-lee/OSPSD-Team-5/pull/8), including client
cleanup on success and failure paths. The current POST integration uses the same
primary calendar and ID space. Historical test counts above describe Kristie's
earlier revision; current combined results are in the POST verification guide.

## Jim Lo's POST Level 2 work

Start from the current merged main, including POST Level 1, shared authentication
(PR #6), and calendar details (PR #7). Use the shared test account's primary
calendar and the existing OAuth client and `calendar.events` scope. The README
records field mapping, setup, behavior, and tests.

Work is split into four reviewable changes:

1. Document the integration design and local setup, and update Level 1 status.
2. Add Google creation and response translation with offline tests.
3. Connect POST to Google and preserve HTTP contract tests and existing routes.
4. Record real HTTP create/read verification, cleanup, and teammate instructions.

All four changes are committed in the original PR revision. The third connects
HTTP POST to Google
and preserves offline HTTP tests through scoped SDK responses. The route returns
503 for setup failure and 502 when creation cannot be confirmed, without local
fallback or creation retries. A controlled lost-response test covers an accepted
write, and a waiting SDK call allows an unrelated GET to complete in TestClient.
The fourth change records real verification in Jim's environment and a walkthrough
for the second verifier. Codex assisted with planning, implementation, offline
tests, and HTTP/SDK verification; Jim completed browser login and consent.

Local checks for this change passed on Python 3.14.8: 47 tests, Ruff lint/format,
strict mypy, dependency compatibility, and diff checks. The existing TestClient
deprecation warning remains. Real verification against implementation revision
`af62da5` passed: HTTP POST 201, local GET 200, independent Google read with
matching times, invalid input 422 without a matching provider event, provider
persistence after stopping the server, and local GET 404 after restart. The
verification event was deleted and confirmed cancelled; the server was stopped.
See [POST Level 2 verification](POST_LEVEL2_VERIFICATION.md) for details and
teammate reproduction. Juno and Ka Pui subsequently recorded real POST
verification and approved
PR #10. Their reviews establish additional-member execution; environment and
cleanup details not provided in those comments are not inferred.

Keep the API inputs, 201 response, validation rules, and returned event shape.
Use Google's event ID. The original revision used a temporary local mirror while
GET was local.
Integration with merged PRs #8 and #9 removes that mirror: POST writes Google
and event GET reads Google, including after a server restart. The POST module
and its tests are renamed to `google_create_events` to preserve Juno's separate
`google_calendar` metadata implementation and tests.
Do not silently use local creation when authorization fails or automatically
retry a write with an uncertain outcome.

Completion requires passing offline checks, a real HTTP POST followed by an
independent Google read, cleanup of verification events, teammate review, and
at least two members running POST against Google with their own local tokens.
The shared authentication script alone does not complete this operation.

The integration is one proposed merge commit. Keep both GET implementations,
POST's validation and failure behavior, both OAuth scopes, and all provider tests.
The shared fixture now stores data inside the mocked provider insertion rather
than the application. Local integration checks passed: 76 offline tests, lint, formatting, strict
mypy, dependency compatibility, and diff checks. Real HTTP POST-to-GET, calendar
metadata, restart persistence, invalid input, and cleanup also passed. See the
POST verification guide for the uncommitted merge revision and execution details. Updated PR CI
and review of the integration diff remain required after publication.

## Provider integration requirements

The earlier plan to assign three members exclusively to Level 2 support tasks
has been superseded by operation ownership. The existing GET handoff uses the
authenticated user's primary calendar; POST uses the same calendar and Google
event IDs. At least two members must verify the real
integration; by the first checkpoint everyone must be able to run the service
and fast tests.

## Milestones (before class)

- October 7, 2026: Levels 1 and 2.
- October 14, 2026: Levels 3 and 4, review prerelease, and sister-team review.
- October 21, 2026: Level 5, final release, review fixes, and demonstration.

Foundation setup uses Python 3.14, pinned dependencies, Ruff, strict mypy, and
GitHub Actions. Both GET Level 2 PRs are merged. POST Level 2 teammate execution
and review are recorded in PR #10; the combined branch still needs its reviewed
merge commit and updated PR checks. Historical test counts refer to the revisions
where they were recorded, not the combined suite.
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
