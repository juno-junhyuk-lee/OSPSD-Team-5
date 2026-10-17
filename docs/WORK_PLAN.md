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
| Juno Lee | `GET /calendars/{calendar_id}` | Level 5 implemented locally; verification and remaining work in calendar Level 5 guide | Level 5 reviewer to be agreed |
| Kristie Lee | `GET /events/{event_id}` | Level 5 implementation at `9fad9af` passes offline and real Google checks; see Level 5 verification guide; teammate review and matching PR CI pending | Level 5 reviewer to be agreed |
| Ka Pui Cheung | `DELETE /events/{event_id}` | Levels 1–2 on main (`4a0865a`, PR #11); Level 3 at `89fb596` and Level 4 at `8057588` pass offline checks; real Google runs, review, and PR CI pending | Reviewer to be agreed |
| Jim Lo | `POST /events` | Level 3 locally verified at `8741c90`; Level 4 injection, controlled tests, and real wiring locally verified at `c54f52e`; teammate review and matching PR CI pending | Level 3/4 teammate review pending; Level 2 reviewed by Juno and Ka Pui |
| Niriti Pahadi | `PATCH /events/{event_id}` | Levels 1–2 and Level 3 merged (PR #21); Level 4 injection on `feature/calendar-patch-level4-injection` | Level 4 reviewer: Ka Pui (approved; resolve main conflicts) |

Ka Pui's DELETE ownership is recorded above. Niriti owns event update.

## Niriti Pahadi's event PATCH Level 3 work

Branch: `feature/calendar-patch-level3-interface`. Niriti owns the event update
interface and Google implementation. The changes:

1. Define `EventUpdater` and update service errors in `event_update_provider.py`.
2. Implement `GoogleEventUpdater` and route PATCH through the interface.
3. Add offline provider translation tests and document the boundary.

## Niriti Pahadi's event PATCH Level 4 work

Branch: `feature/calendar-patch-level4-injection` (stacked on Level 3). Niriti
owns dependency injection for event PATCH:

1. Select Google in `event_update_dependencies.py` and inject `EventUpdater`.
2. Test the HTTP contract with a controlled updater and dependency overrides.
3. Document wiring and verification evidence.

The public PATCH contract is unchanged.

The tables below retain the earlier GET implementation history; they do not
establish the team's final operation ownership.

## Juno Lee's calendar GET Level 3 work

Juno owns the implementation. The deliverable is a documented
`CalendarReader` interface and Google implementation preserving the existing
calendar GET contract. Completion requires passing checks, real-provider
verification, and teammate review of the shared boundary. Local checks and real
calendar GET passed. See PR #15 for reviews and `VERIFICATION.md` for local evidence.
Codex assisted with the refactor,
tests, and documentation. Injection remains Level 4 work.

## Kristie Lee's event GET Level 3 work

Branch: `feature/calendar-event-get-level3-interface`. Kristie owns the event
GET interface and Google implementation. The changes are split into three commits:

1. Define `EventReader` and move existing retrieval errors to the provider boundary.
2. Connect `GoogleEventReader` to the route and verify the interface and ID mapping.
3. Update the code map, contract documentation, and verification evidence.

Implementation revision `ce55c7a` passed all 104 tests, Ruff lint/format, strict
mypy, dependency compatibility, and diff checks on Windows with Python 3.14.8.
Real Google requests through TestClient returned 200 for the existing timed event
and 404 for an absent ID. See [verification evidence](VERIFICATION.md#event-get-level-3-verification).
Level 3 was subsequently merged in PR #17; see that PR for review evidence.
Codex assisted with implementation, tests, documentation, and verification.

## Kristie Lee's event GET Level 4 work

Kristie owns dependency injection for event GET. The work is split into three commits:

1. Select Google in `event_dependencies.py` and inject `EventReader` into the route.
2. Test the HTTP contract with a controlled reader and isolated dependency overrides.
3. Document wiring, test boundaries, and local/real-provider verification.

Implementation revision `c6ca9c6` passed 107 tests and required local checks on
Windows/Python 3.14.8. The five controlled reader tests also passed with external
socket connections and real credential loading blocked. Real Google retrieval
through normal injection returned 200 for the existing event and 404 for an absent
ID. See [verification evidence](VERIFICATION.md#event-get-level-4-verification).
Another teammate's review of production wiring and test substitution and matching
PR CI remain required. Codex assisted with implementation, tests, and verification.

## Kristie Lee's event GET Level 5 work

Branch: `feature/calendar-event-get-level5-errors`. Kristie owns event retrieval
errors, tests, and documentation. Provider translation and HTTP error/logging
integration are implemented on this branch. Local checks and real Google Level 5
verification passed at `9fad9af`; teammate review and matching PR CI remain
pending. Reviewer: not yet assigned; assign one for PR review. Codex assisted
with implementation, tests, documentation, and verification. The contract is in the README's
[Level 5 event retrieval section](../README.md#level-5-event-retrieval-errors).
The operation-specific status/retry policy and DELETE-compatible ID rule were
confirmed by the student owner; this does not claim team-wide agreement.
Have the team review these choices before merging.

On October 17, 2026, all 212 tests and required local checks passed. The 18
controlled-reader cases also passed with external connections and real
credentials/provider creation blocked. Real TestClient requests with normal
injection verified Google success, a Google missing-event failure, and local
invalid input, including sanitized logs. No events changed. See
[Level 5 verification and reproduction](EVENT_GET_LEVEL5_VERIFICATION.md).
This evidence covers the implementation revision, not a later documentation
commit, human server/curl demonstration, PR CI, or final release tag.

Review follow-up: kc5931 identified cancelled events returning 200 after DELETE
in PR #30. The uncommitted fix based on `997261f` now rejects cancelled records
before field translation. All 216 tests and required checks passed, and an
existing cancelled Google event returned 404/not_found with one sanitized log
through normal injection. No events were changed in the live check. See the
[follow-up evidence](EVENT_GET_LEVEL5_VERIFICATION.md#cancelled-event-review-follow-up).
Updated reviewer confirmation and matching PR CI remain pending.

Work is split into four commits:

1. Document the planned failure contract, compatibility changes, scope, and
   acceptance criteria. Keep the current behavior clearly distinguished.
2. Add provider-independent permission and temporary-failure distinctions,
   translate Google failures inside `GoogleEventReader`, and test the adapter.
   Do not treat rate-limit 403s as permission denials or hide programming errors.
3. Validate IDs before calling the reader and map expected failures to the
   existing `ServiceError` handler. Update controlled-reader HTTP tests and
   affected regression expectations, including one sanitized log per failure.
4. Record complete checks and real Google verification, update the README to
   describe implemented behavior, and request teammate review and matching CI.

Acceptance requires:

- Preserve `200` and the existing four-field Event, timed-event restriction,
  empty-title policy, dependency injection, and provider client cleanup.
- Implement every row of the error table, including distinct access
  denial, retryable temporary failures, and non-retryable invalid provider data.
- Reject invalid ID syntax without calling the reader; accept recurring-instance
  syntax and distinguish a valid but nonexistent ID from invalid input.
- Keep SDK types and raw errors behind the provider boundary. Use fixed public
  messages and the common logger without duplicate logs or sensitive content.
- Cover success, invalid input, missing resource, access denial, unavailable
  authorization, temporary provider failure, malformed data, and unsupported
  events with deterministic offline tests. Restore dependency overrides.
- Run required README checks on the final implementation revision. Verify a real
  timed-event read and a syntactically valid missing ID through normal injection;
  record responses, sanitized logs, revision, and any unverified cases honestly.
- Obtain another teammate's review of the contract, translation, HTTP behavior,
  tests, and docs, with CI evidence matching the revision to be merged.

The shared handler from PR #28 supplies the logging requested by the sister-team
[review comment](https://github.com/juno-junhyuk-lee/OSPSD-Team-5/pull/27#discussion_r4278070800).
No separate route/provider failure logger is planned. App-wide FastAPI request
validation and other owners' operations are separate team tasks, not silently
included here. Final release, fresh-tag verification, demonstration, and private
reflection remain milestone tasks beyond this operation PR.

## Juno Lee's calendar GET Level 4 work

Juno owns the implementation; The deliverable is FastAPI
injection of `CalendarReader` with Google selected outside the route and a
controlled reader supplied by calendar HTTP tests. Preserve existing responses.
Completion requires passing checks, real Google GET verification, and another
teammate's review of both production wiring and test substitution. Codex assisted
with implementation, tests, documentation, and checks. Verification is recorded
in `VERIFICATION.md`; teammate review remains pending.

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

## Jim Lo's POST Level 3 work

Start from main `aa97365`, including the event GET Level 4 injection in PR #18.
Jim owns `EventCreator` and its Google implementation. Follow the small typed
interface style used by `EventReader` and `CalendarReader`.

The work is split into three reviewable changes:

1. Define `EventCreator` and its existing failure contract, and document the
   input, return value, external write, and implementation responsibilities.
2. Implement `GoogleEventCreator`, keep SDK calls and translation behind the
   interface, connect POST to it, and update provider and HTTP regression tests.
3. Record required checks and real create/read, restart, and cleanup verification.

The first change defines and documents `EventCreator`. The second introduces
`GoogleEventCreator`, which delegates to the existing Google insertion helper
and translates known failures into the interface's service errors. POST now
calls a module-level `EventCreator` and maps service errors to its existing
responses. Provider tests use the typed interface and check error translation;
HTTP regression tests continue checking validation, uncertain writes, retrieval,
and responses. Google selection is still fixed for Level 3. Codex assisted with
the refactor, tests, documentation, and verification; teammate review is pending.

Implementation commit `8741c90` passed 115 offline tests, Ruff lint/format,
strict mypy, dependency compatibility, and diff checks on Python 3.14.8. All
tests also passed with external socket connections blocked. Eight additional
parametrized cases cover known transport error families at the provider and
HTTP boundaries. Separate real Google verification passed: POST 201, matching
HTTP and independent provider reads, invalid POST 422 without a created event,
restart persistence, existing GET checks, and cleanup. See
[POST Level 3 verification](POST_LEVEL3_VERIFICATION.md). Teammate review and
matching PR CI remain required before treating Level 3 as complete.

Preserve the public request, 201 response, four-field Event, 422 validation,
503 authorization response, and 502 uncertain-creation response. Translate
existing Google failures into service errors without exposing SDK types to the
POST handler. Preserve the shared `load_credentials` behavior used by PATCH and
DELETE. Keep creation retries disabled and keep real verification separate from
offline tests. Completion also requires teammate review of the provider boundary.

The Level 3 results above describe fixed Google selection at `8741c90`.
Current injection work is recorded below.

## Jim Lo's POST Level 4 work

Branch: `feature/calendar-post-level4-injection`, based on the Level 3 branch
at `b1eb94e`. Keep this work separate from the pending Level 3 PR.

The changes are split into three reviewable commits:

1. Select Google in `event_creation_dependencies.py` and inject `EventCreator`
   into POST while preserving its public contract and existing tests.
2. Test POST with a controlled creator, isolated dependency overrides, and
   cleanup, without real credentials or network access.
3. Record required checks, blocked-network controlled tests, and real Google
   verification through normal injection, including test-event cleanup.

The first change removes the module-level creator from `app/main.py`. The
factory supplies a lightweight `GoogleEventCreator` through FastAPI `Depends`.
The handler uses `EventCreator` and retains its existing service-error mapping.
Google provider and CRUD tests still use their original fixtures. The second
change adds `tests/test_create_event_contract.py` with a controlled creator and
a separate TestClient fixture. It records normalized requests, returns
predictable events, or raises configured service errors. Tests cover exact
responses, returned IDs, UTC-offset ordering, validation before a creator call,
and no retry after failure. Each test restores previous dependency overrides in
`finally`. The third change records normal wiring verification and reproduction
steps. Teammate review and PR CI remain pending. Codex assisted with the wiring,
tests, documentation, and verification.

Wiring commit `6e2bb8a` passed all 115 existing tests, Ruff lint/format,
strict mypy, and diff checks on Python 3.14.8. These checks preserve the existing
provider-backed test coverage. The second change adds independent controlled
creator substitution rather than replacing those Google integration tests.

Implementation commit `c54f52e` passed 130 tests and required local checks on
Python 3.14.8. Its 15 controlled creator cases also passed with socket connections
and real credential loading blocked. A pre-existing creator override was restored
after the run, confirming that the fixture preserves earlier override state.
These controlled results verify substitution and HTTP behavior. Separate real
Google verification at the same commit passed: injected POST 201, matching
HTTP GET and independent Google reads, invalid input without a created event,
restart persistence, other GET checks, and cleanup. See
[POST Level 4 verification](POST_LEVEL4_VERIFICATION.md). Another teammate must
review both normal wiring and test substitution; matching PR CI and release
verification remain required.

## Ka Pui Cheung's DELETE Level 3 work

Ka Pui owns `EventDeleter` and its Google implementation, following the
`EventCreator` style. The work is split into two reviewable changes:

1. Define `EventDeleter`, wrap the existing Google call in `GoogleEventDeleter`,
   route DELETE through it, and add provider translation tests (`89fb596`).
2. Document the contract, code map, and verification evidence.

Public responses stay 204, 404, 503, and 502. Google selection stays fixed in
`app/main.py` for Level 3. Offline checks passed; see
[DELETE Level 3 verification](DELETE_LEVEL3_VERIFICATION.md). A real Google run,
teammate review of the boundary, and matching PR CI remain required.

## Ka Pui Cheung's DELETE Level 4 work

Ka Pui owns dependency injection for DELETE, following event GET's Level 4 work:

1. Select Google in `get_event_deleter`, inject `EventDeleter` into the route,
   and test the HTTP contract with a controlled deleter (`8057588`).
2. Document wiring, test boundaries, and verification.

The controlled tests passed with socket connections and credential loading
blocked. A real Google DELETE run through normal injection, another teammate's
review of production wiring and test substitution, and matching PR CI remain
required. See [DELETE Level 4 verification](DELETE_LEVEL4_VERIFICATION.md).

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

## Juno Lee's calendar GET Level 5 work

Owner: Juno Lee. Reviewer: Level 5 reviewer to be agreed.
Branch: `feature/calendar-get-level5-errors`.

Scope: calendar metadata failure translation, shared `ServiceError` responses,
controlled HTTP and Google adapter tests, sanitized logs, and documentation.
Preserve the three-field success response, `primary` alias, unsupported-ID 404,
dependency injection, noninteractive authorization, and client cleanup.

Acceptance: distinguish missing calendar, authorization setup/renewal, permission,
temporary failures, and invalid provider metadata; document retryability and
compatibility changes. Offline tests must check public responses, one sanitized
log per failure, and provider translation without credentials or network.
Run all README checks and record practical real-provider verification.

The endpoint has no new ID syntax rule or operation-specific 422 case. Shared
request-validation work and other owners' routes stay outside this change.
Teammate approval and matching CI are required before merge; release verification
is separate. Codex assisted with implementation, tests, docs, and verification.
See [calendar Level 5 verification](CALENDAR_GET_LEVEL5_VERIFICATION.md).
