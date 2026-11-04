# Team 5: adopting the shared Calendar API

| Item | Value |
| --- | --- |
| Status | Draft under Team 5 review; shared package not yet adopted |
| Author | Juno Lee, with team input |
| Team / vertical | Team 5 / Calendar |
| Team members | Juno Lee, Jim Lo, Kristie Lee, Ka Pui Cheung, Niriti Pahadi |
| Last updated | November 3, 2026 |
| Complete-design reviewer | Niriti Pahadi (in progress on this revision) |
| Contract-facing reviewer | Representative from Team 2 or Team 7; assignment pending |
| Shared agreement | [Calendar API joint decision memo](https://docs.google.com/document/d/1bVv6tLLtfGKt75HH1OPBTuJ3d1kkMdkEgzz9ef3UcOI/edit), version 4, October 28, 2026; staff access needs verification |
| Shared Python / HTTP contract revision | [calendar-contract repository](https://github.com/Airbus-A330/OSPSD-Calendar); interface docs merged via [#15](https://github.com/Airbus-A330/OSPSD-Calendar/pull/15) into conformance [#14](https://github.com/Airbus-A330/OSPSD-Calendar/pull/14); HTTP reference [#11](https://github.com/Airbus-A330/OSPSD-Calendar/pull/11); adopted release tag pending |
| Implementation work | Design [#40](https://github.com/juno-junhyuk-lee/OSPSD-Team-5/pull/40); PUT + live verify [#41](https://github.com/juno-junhyuk-lee/OSPSD-Team-5/pull/41) on `hw2/milestone-2`; shared suite [#14](https://github.com/Airbus-A330/OSPSD-Calendar/pull/14); package adoption PR pending (Jim) |
| Inspected HW1 baseline | `143be358c1c6086c47035b4088d967895d7f9ebb` |

This draft uses the supplied Markdown and plain-text exports of the joint
contract. Their substantive rules match. Neither export is committed here.
The canonical memo URL above comes from the coordination email; Kristie will confirm its
revision and staff access. The linked
[coordination email record](https://drive.google.com/file/d/1qE08aNXGlD3jSa44s1nrngVPM_KyZNqR/view?usp=drive_link)
is supporting material, not the Python package specification.

This document records current behavior separately from proposals. As of
`hw2/milestone-2` merge `e52d656` (PR [#41](https://github.com/juno-junhyuk-lee/OSPSD-Team-5/pull/41)),
Team 5 has a local `PUT /events/{event_id}` and recorded live PUT → read-back →
cleanup evidence in [docs/PUT_LIVE_VERIFICATION.md](docs/PUT_LIVE_VERIFICATION.md).
That path still uses Team 5's own models (`start_time` / `end_time`) and does
**not** yet depend on a tagged shared Calendar package. Shared-package adoption
and re-verification through that package remain open for the November 4 bar.

## Context, goals, and non-goals

A consumer should create, retrieve, replace, and delete a timed event against
Teams 2, 5, and 7 using the same request shapes and outcome handling. Today,
Team 5 uses `start_time` and `end_time`, while the joint contract uses `start`
and `end`. A client switching to Team 5 must change its serialization. Local
PUT now exists on `hw2/milestone-2`, but Team 5 still ignores unknown body
fields and returns 422 for malformed JSON. Until field names and the tagged
shared package are adopted, the common workflow still does not match the other
teams' serialization.

The goals are to implement the four shared operations, adopt a tagged shared
Python package, and pass the same vertical conformance suite as the other
implementations. By November 4 before class, at least one operation must use
that package end to end against Google Calendar. PUT is the proposed early
operation because it closes an existing gap and exercises request models,
provider translation, errors, and response models together.

Listing, all-day event support, extra editable fields, data migration, and
runtime provider switching are outside this redesign. Existing calendar
metadata and PATCH endpoints remain extensions. Their compatibility consequences
must be reviewed rather than assumed away. Full shared-operation conformance
and infrastructure delivery remain required by November 11 before class.

## Current implementation and proposed architecture

[app/main.py](app/main.py) owns HTTP routes and maps operation failures to the
shared local error envelope. [app/models.py](app/models.py) defines event and
request models. Operation-specific protocols and dependency factories select
Google adapters. Google SDK calls and field translation stay in those adapters.
There is no local event mirror; Google Calendar owns persistent event state.

The proposed flow is:

```text
HTTP caller
  -> FastAPI route and shared request validation
  -> application/provider boundary using shared Python types
  -> Google adapter: field conversion and SDK operation
  -> authenticated user's primary Google Calendar
  -> shared response model or domain failure
  -> HTTP response and one sanitized failure log when applicable
```

The shared Python proposal defines `calendar_contract.service.CalendarService`
with these synchronous methods:

```python
class CalendarService(Protocol):
    def create(self, request: CreateEvent) -> Event: ...
    def get(self, event_id: str) -> Event: ...
    def replace(self, event_id: str, request: ReplaceEvent) -> Event: ...
    def delete(self, event_id: str) -> None: ...
```

`Event`, `CreateEvent`, `ReplaceEvent`, `CalendarError`, and `ErrorCode` come
from the shared package. [PR #15](https://github.com/Airbus-A330/OSPSD-Calendar/pull/15)
proposes public package-root imports and documents the interface used by
[conformance PR #14](https://github.com/Airbus-A330/OSPSD-Calendar/pull/14).
These are review proposals, not a released or accepted Python API.

Team 5 will retain FastAPI HTTP translation, dependency selection, credential
handling, and Google SDK details. Jim and Ka Pui must agree on the concrete
implementation of `CalendarService` and how it connects to the existing
operation-specific adapters. Jim owns package adoption; Ka Pui owns PUT.
Whether existing adapters satisfy the boundary directly or need a thin
composition adapter remains pending. Local protocol names are not an agreed
shared API.

Dependency factories currently construct lightweight adapter objects. Adapters
create Google clients for operations and close them with context management.
Preserve that ownership for PUT. Request validation happens before the provider
operation. Provider responses are converted and validated inside adapters;
known SDK failures become domain failures, then HTTP responses in the route
and shared handlers. No additional service layer is proposed without a concrete
responsibility that existing components cannot cover.

Local startup continues to select Google through existing dependencies. Before
requests, a developer performs browser authorization with
[scripts/google_calendar_auth.py](scripts/google_calendar_auth.py). Routes must
never start interactive authorization. Deployment startup configuration and
credential storage are a separate proposed change below.

### Successful PUT trace

FastAPI validates required `title`, `start`, and `end`, rejects unknown fields,
and checks ordering by instant. The injected replacement implementation receives
the shared input type. The proposed Google path checks that the event exists,
then patches all three shared editable fields, preserving unrelated fields.
It translates Google's result into `id`, `title`, `start`, and `end` and returns
200. Tests must verify that the returned ID is unchanged.

### Expected failure trace

If the patch response is lost after Google may have accepted the write, the
adapter raises an unconfirmed-write domain failure. The HTTP boundary returns
502 `provider_error` with `retryable: false`; the shared handler emits one
sanitized log. The service does not retry or fall back to local state. A 502
does not establish whether the event changed.

## API and data model

The authoritative shared rules are in the linked joint memo. The Python
interface is proposed in shared PR #15 and the HTTP reference in shared PR #11.
Record their accepted revision and the exact adopted package tag before
claiming reproducible integration.

| Operation | Shared route | Success | Team 5 change |
| --- | --- | --- | --- |
| Create | `POST /events` | 201 with event | Adopt shared names and validation |
| Read | `GET /events/{event_id}` | 200 with event | Adopt shared response names |
| Replace | `PUT /events/{event_id}` | 200 with event | Local route merged in [#41](https://github.com/juno-junhyuk-lee/OSPSD-Team-5/pull/41); still needs shared-boundary types after package adoption |
| Delete | `DELETE /events/{event_id}` | 204, empty body | Verify existing behavior against common checks |

The shared event contains a provider-generated string `id`, string `title`, and
RFC 3339 `start` and `end` timestamps. IDs identify events in the configured
primary calendar; callers must not assume an ID identifies an event in another
account. Team 5 currently validates IDs with a bounded character pattern in
`app/main.py`; its compatibility with the shared Python contract needs review.

POST and PUT require all three editable fields, reject nulls and unknown fields,
and require an explicit timestamp offset and an end strictly after the start.
PUT replaces shared fields, never the ID. Team 5 will preserve non-shared
Google fields. Titles remain trimmed on writes, with no new application maximum
proposed. Reads of untitled provider events continue returning an empty title.

Team 5 does not promise preservation of timestamp formatting or request offsets;
responses follow provider-returned instants. Under accepted rule 14,
implementations may drop sub-seconds; if they do,
they must validate `end > start` after truncation. Whole-second inputs are the
portable choice. The October 28 coordination email records Team 2 accepting
this clarification; the old pending-approval question is resolved. Team 5
still needs to document its concrete precision policy. Numeric timestamps
and offset-free values must fail before a provider call. Existing
ISO 8601 validation must be checked against the narrower RFC 3339 agreement.

Illustrative request and expected response, not observed HW2 evidence:

```http
PUT /events/example-provider-id
Content-Type: application/json

{"title":"Design review","start":"2026-11-03T15:00:00Z","end":"2026-11-03T15:30:00Z"}
```

```http
HTTP/1.1 200 OK
Content-Type: application/json

{"id":"example-provider-id","title":"Design review","start":"2026-11-03T15:00:00Z","end":"2026-11-03T15:30:00Z"}
```

The shared model omits Google fields such as description, attendees, recurrence,
and location. This narrows the public representation without requiring those
provider fields to be deleted. All-day events and unsupported provider shapes
need explicit Team 5 failure semantics consistent with the shared agreement;
the current GET policy is documented in [README.md](README.md).

## Alternatives and tradeoffs

**Proposed PUT implementation: reuse the existing Google patch mechanism.**
[app/google_update_events.py](app/google_update_events.py) already performs an
existence read followed by a patch of title and both times. Requiring all shared
fields at the HTTP boundary gives replacement semantics for those fields while
preserving unrelated Google state. Reusing the mechanism reduces duplicated
SDK and cleanup paths, but shared failure classification must still be reviewed.

The alternative is Google's full update operation. That would require obtaining
and preserving unrelated fields or accepting their removal, which contradicts
Team 5's stated preservation commitment. Before accepting this choice, verify
preservation with controlled adapter tests and a live event containing a
non-shared field. Revisit it if the shared contract requires whole-provider
replacement or a tested Google behavior prevents the guarantee. No atomic
read-and-write or concurrent-edit guarantee is proposed.

**Proposed migration: shared models at the common API boundary.** Maintaining
separate local and shared models would reduce immediate edits but require
ongoing conversion and risk validation drift. Adopting the shared types more
directly changes more tests now but makes conformance easier to inspect. The
final choice depends on the actual package API. Do not duplicate validation
merely to preserve existing class names.

For old field names, a direct rename gives one unambiguous public shape but
breaks existing callers. Temporary aliases or a versioned compatibility route
could reduce that disruption but add ambiguity and tests. Jim must propose
a policy for team and contract-facing review before implementation; this draft
does not approve accepting old names alongside unknown-field rejection.

## Failure behavior and operational concerns

| Outcome | Public response | Retry policy |
| --- | --- | --- |
| Malformed JSON | 400 `invalid_input` | False; fix the request |
| Invalid valid-JSON body or parameter | 422 `invalid_input` | False; fix the request |
| Missing event, including repeated DELETE | 404 `not_found` | False |
| Provider identity lacks permission | 403 `access_denied` | False; fix permissions |
| Invalid provider response or uncertain POST/PUT | 502 `provider_error` | False for uncertain writes |
| Temporary provider unavailability | 503 `provider_unavailable` | Operation-specific; meaningful `Retry-After` when known |
| Missing or unusable local authorization | Existing 503 `provider_unavailable` | False; repair setup |

Errors use `{"error":{"code":"...","message":"...","retryable":false}}`.
The Boolean is selected for the actual outcome. Constructing an invalid shared
Pydantic request model raises `ValidationError` before a service operation;
The HTTP boundary must map invalid client input to the shared validation
response, including FastAPI request-validation failures. If integration
constructs a request model manually, it must handle that validation path too. Operation-level failures instead use shared
`CalendarError` and `ErrorCode`. Team 5 must translate its existing
operation-specific provider exceptions before they cross the shared interface,
then map `CalendarError` to the public response and one sanitized log entry.
The exact adapter and handler wiring remains a Jim/Ka Pui integration decision.
Existing local handlers map
`invalid_input` only to 422, so malformed-JSON handling requires an explicit
change. Existing update classification also needs examination so confirmed
temporary failures and uncertain writes are not conflated. Only confirmed-safe
retry advice is allowed; automatic uncertain writes remain disabled.

Preserve the one-log policy in [app/errors.py](app/errors.py): operation, public
code, status, and provider involvement. Never include tokens, raw bodies, event
titles, authorization headers, or raw SDK exception text. Credential files stay
out of Git and artifacts. Preserve both setup scopes and noninteractive token
refresh; document where refreshed credentials are stored in deployment.

For proposed PUT, normal local work parses and serializes a bounded number of
fields, with work proportional to their encoded size. It performs one existence
read and one patch, plus possible authorization refresh calls. It does not scan
the calendar. Network latency is not evidence of Google's internal complexity.
Tests must detect extra writes or retries. Every live test must delete data it
creates, recording cleanup failures rather than silently leaving events behind.

### Deployment planning for November 11

Hosting, Infrastructure as Code tooling, registry, protected state storage,
runtime secret store, deployment pipeline, and telemetry backend are undecided.
The team must assign a deployment proposal owner; this work is not implicitly
assigned through shared-package coordination. Account owners, expected cost,
and teardown date must be named before acceptance of that portion of the plan.
This is a dependency for Milestone 3, not a claim of deployed infrastructure.

The plan must support locked builds, startup configuration validation, separate
readiness reporting, repeatable provisioning and teardown, automated deployment
and rollback verification, and the required observability and operational
documentation. A temporary provider outage should not cause restart loops.
Review token refresh persistence and write access before choosing hosting.

## Migration, ownership, and branch workflow

The owners below reflect the team's claimed Milestone 2 roles. Juno is also
helping Kristie with the initial interface draft. Each implementation owner
must agree on a different reviewer; reviewer assignments and remaining Team 5
implementation issue/PR links are still pending.

| Member | Owns | Deliverable |
| --- | --- | --- |
| Kristie Lee | Shared-contract coordination and interface finalization | Coordinate memo links, interface review with Teams 2 and 7, conformance responsibilities, and readiness for Team 7's shared-package release. Initial draft supported by Juno in shared PR #15. |
| Juno Lee | Team 5's `DESIGN.md` and initial shared-interface draft | Maintain this design and obtain complete-design and cross-team reviews; prepare shared interface documentation, exports, and typing check in shared PR #15 for Kristie's review/finalization. |
| Jim Lo | Shared-package adoption and models | Install and lock the agreed tagged dependency; adapt shared field names, strict input validation, and agreed compatibility behavior; update affected routes, tests, examples, and configuration. |
| Ka Pui Cheung | PUT implementation | Local PUT merged in [#41](https://github.com/juno-junhyuk-lee/OSPSD-Team-5/pull/41) (preserves Google-only fields; offline + live checks). Rewire through shared package types after Jim's adoption. |
| Ka Pui Cheung | Conformance and real verification | Shared suite draft in calendar-contract [#14](https://github.com/Airbus-A330/OSPSD-Calendar/pull/14); Team 5 live PUT evidence in [docs/PUT_LIVE_VERIFICATION.md](docs/PUT_LIVE_VERIFICATION.md). Still need suite wiring against Team 5 and re-verify through a tagged package. |
| Niriti Pahadi | Complete-design review and leftover support | Review/update this design against current `hw2/milestone-2` work; help with remaining Member 4/5 follow-ups and package-adoption verification once the tag exists. |

`hw2/milestone-2` is the integration branch created from the inspected baseline.
`doc/design.md` branches from it for this document. Other work branches should
also target the integration branch through small reviewed PRs. Dependent work
must state which merged change it requires. The combined milestone PR targets
`main` after design review, passing checks, and initial provider verification.
After merge, create the later milestone branch from the resulting `main`.

Before the November 4 submission checkpoint:

1. Kristie records the accepted interface, package tag, and shared review outcomes.
2. Juno updates design PR #40; Niriti records Team 5 complete-design review outcomes.
3. Ka Pui's local PUT and live verification landed first on `hw2/milestone-2` ([#41](https://github.com/juno-junhyuk-lee/OSPSD-Team-5/pull/41)) ahead of the shared tag.
4. Jim adopts the released package and updates common boundary models (`start`/`end`, strict unknown fields).
5. Ka Pui (with Niriti helping as needed) rewires PUT through that boundary, reruns live PUT → read-back → cleanup, and records package tag + commit.

Open issues for each remaining change with owner, dependency, and verification
criteria. Work not required for the initial operation remains visible and must
finish before November 11. These checkpoint dates do not imply implementation
or reviews are complete.

If the shared contract changes incompatibly, Kristie coordinates with affected
Teams 2, 5, and 7 and their consumers, circulates examples and migration consequences,
and obtains review before a replacement version is published. Update the memo,
package, tests, and this design together. Do not move an existing published tag.

## Testing and verification

Existing HW1 tests and [verification records](docs/WORK_PLAN.md) provide regression
coverage, not evidence that the new package or PUT works. Keep fast controlled
tests independent of Google credentials, network access, and live fixtures.

| Guarantee | Planned check and what it establishes |
| --- | --- |
| Shared input rules | Model/HTTP tests for missing/null/unknown fields, wrong types, numeric or offset-free times, malformed JSON, and ordering; assert no provider operation on rejection. |
| Shared success and errors | Controlled implementations injected through FastAPI; assert exact statuses, response fields, retry advice, and restored dependency overrides. |
| Google replacement semantics | Adapter tests inspect the patch payload and unchanged ID; failure cases cover missing/cancelled events, permissions, bad responses, and an accepted write with a lost response and no retry. |
| Sanitized failure context | HTTP log assertions verify one failure entry and absence of sensitive inputs or raw provider exceptions. |
| Cross-service behavior | Proposed `calendar_contract.conformance.CalendarServiceConformance` in shared PR #14 runs the same service-operation checks using an implementation-supplied `service` fixture; Team 5 fixture wiring and invocation are pending. |
| Real shared-package path | Live HTTP PUT, read-back, independent Google confirmation, non-shared-field preservation, and cleanup at a recorded commit. |

At the Python boundary, each team subclasses `CalendarServiceConformance` in
its own test module and supplies a fresh `service` fixture returning its
`CalendarService` implementation. Ka Pui will connect Team 5's implementation
to controlled provider state so this suite runs offline. The fixture may vary
by team; the shared operation logic must remain unchanged. Its Team 5 test-file
location and exact invocation must be recorded before integration is accepted.

These Python checks do not establish HTTP statuses, malformed-JSON handling,
Google translation, or live persistence. Keep separate controlled HTTP tests,
Google adapter tests, and real provider verification. A run against the shared
suite's in-memory reference service validates the suite, not Team 5's adapter.

The common HTTP consumer workflow is POST, GET, PUT, GET, DELETE, then GET
expecting 404; repeated DELETE also expects 404. Only base URL and
implementation-specific setup may change between services. Compare timestamp
instants rather than string formatting. Use whole-second timestamps for portable cases.

Shared fixtures should create uniquely identifiable disposable events, keep
their IDs, and clean up in `finally`, treating a confirmed 404 as already gone.
For uncertain creation without an ID, automatic cleanup through the core alone
is insufficient; avoid blind creation retries and record manual provider
inspection obligations. Controlled tests, rather than deliberately ambiguous
live writes, should exercise that failure mode.

A failing missing-field or unknown-field test reveals validation drift; a PUT
read-back mismatch reveals incomplete replacement; repeated DELETE returning
204 reveals missing-event policy drift. Preservation of non-shared fields is a
Team 5-specific check because the joint agreement permits team differences.

Ka Pui will add sanitized observed requests/responses, exact commit and package
tag, commands, environment prerequisites, and cleanup results to a linked HW2
verification record. Existing HW1 live evidence cannot substitute for this run.

Implementation PRs use Python 3.14 and the README commands: `uv sync --frozen`,
`uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`,
`uv run pytest -v`, and `git diff --check`. Add the shared controlled checks to
CI once their invocation is agreed. Passing unit tests alone does not establish
live provider or cross-service compatibility.

### Shared-package progress and release dependencies

As of November 3, shared PR #15 contains the initial interface documentation,
exports, and a structural typing check; shared PR #14 contains the proposed
reusable suite. Neither establishes Team 5 integration or full conformance.

- Team 2 completed strict write-model handling in
  [PR #12](https://github.com/Airbus-A330/OSPSD-Calendar/pull/12), merged into
  `team2-models-errors`. [Timestamp validation #5](https://github.com/Airbus-A330/OSPSD-Calendar/issues/5)
  and [Event/read-model #7](https://github.com/Airbus-A330/OSPSD-Calendar/issues/7)
  remain open. Timestamp helpers still accept invalid strings; passing current
  model tests does not establish the full timestamp contract.
- Team 7's [PR #13](https://github.com/Airbus-A330/OSPSD-Calendar/pull/13)
  proposes Python 3.12-3.14 compatibility, needed by Team 5's Python 3.14 setup.
  [PR #11](https://github.com/Airbus-A330/OSPSD-Calendar/pull/11) proposes HTTP
  documentation, release guidance, and the `py.typed` marker needed by external
  strict-mypy consumers. Combined integration must preserve Pydantic and the
  widened Python requirement, regenerate the lockfile, and rerun checks.
- PR #14's replacement start currently represents the original instant, so a
  service that ignores start changes can pass. Its `missing_id` fixture does
  not register fallback cleanup, and cleanup stops on the first unexpected
  deletion failure. Ka Pui owns the conformance follow-up: change the start
  instant, track every created ID, attempt all cleanup, and test those paths
  before relying on the suite for replacement/cleanup guarantees.
- Provider permission, availability, unexpected-response, and uncertain-write
  conformance checks remain deferred. Kristie and Ka Pui must agree on
  controlled failure hooks without adding test-control methods to the public
  protocol; record the approach by November 4 and complete required conformance
  by November 11. HTTP validation remains separately exercised.
- No adopted shared tag is recorded. Kristie coordinates readiness with Teams
  2 and 7; Jim installs and locks the reviewed tag after publication. Open PRs
  and development branches do not substitute for that milestone requirement.

## Open questions and review record

| Question or concern | Consequence | Proposed owner | Resolution checkpoint |
| --- | --- | --- | --- |
| Accepted shared API revision and tag; repo/proposals now linked | Adoption cannot be implemented reproducibly without a reviewed tag | Kristie with Teams 2/7; Jim for adoption | Before November 4 integration |
| Team 5 service fixture, suite invocation, and deferred failure hooks | Shared suite cannot yet establish Team 5 conformance | Kristie and Ka Pui | Record strategy by November 4; full conformance by November 11 |
| Team 5 precision policy under accepted rule 14 | Truncation could collapse an otherwise positive interval | Jim and Ka Pui | Before model/PUT behavior is accepted |
| Old field names and PATCH compatibility | Existing callers and extension tests may break | Jim Lo | Before model changes are approved |
| Unsupported all-day/recurring cases and ID syntax | Implementations may disagree on public outcomes | Ka Pui with Kristie | Before PUT behavior is accepted |
| Partial failure and temporary-outage classification | Unsafe retry advice or inconsistent public errors | Ka Pui Cheung | Before PUT review completes |
| Hosting, credentials, state, costs, and teardown | Deployment may not be reproducible or suitable for token refresh | Deployment proposal/account owners pending; team to assign | Proposal reviewed by November 4; implemented by November 11 |
| Team 5 implementation issue links and named reviewers | Claimed owners are recorded, but review and execution remain untracked | Juno and team | Before implementation review and November 4 submission |

No design approvals or resolved reviewer comments are recorded yet. A different
Team 5 member must review the complete design, and Team 2 or Team 7 must review
contract-facing behavior. Record links, substantive concerns, responses, accepted
risks, and the scope of approval here. Required behaviors cannot be deferred
beyond their milestone. The shared package and conformance placeholders are
assignment requirements, not optional additions.

## Submission and change record

For November 4, submit one Brightspace entry with team name, Calendar vertical,
all members, `DESIGN.md` at the reviewed commit, and relevant PR links. Include
links to package adoption and real-operation evidence and owned remaining-work
issues. Check staff access to each linked artifact. A reviewed design is not
proof of a working implementation.

- November 2, 2026: initial draft based on the supplied joint agreement and
  inspected HW1 code. Shared-package details, ownership, reviews, deployment
  choices, and HW2 verification remain open.
- November 3, 2026: linked the shared repo and open contract/packaging PRs;
  recorded claimed owners, the proposed `CalendarService`, validation/error
  boundaries, and conformance integration strategy. Resolved the stale rule 14
  approval question using the October 28 email. Recorded unfinished validation,
  packaging, suite coverage, cleanup, and release dependencies; concrete wiring,
  compatibility, hosting, reviewer assignments, and live evidence remain pending.
- November 3, 2026 (evening): Ka Pui merged local PUT + live verification
  ([#41](https://github.com/juno-junhyuk-lee/OSPSD-Team-5/pull/41)). Niriti began
  complete-design review and refreshed this draft so it no longer claims PUT is
  missing; shared-package adoption and contract-facing review remain open.
- Codex assisted with drafting and repository inspection. Students must verify
  technical claims and own the decisions and submitted work.
