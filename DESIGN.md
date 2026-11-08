# Team 5: adopting the shared Calendar API

| Item | Value |
| --- | --- |
| Status | In review; adoption integrated; Level 2 verify deployment, failure detection, and recovery verified; merged-revision deployment pending |
| Author | Juno Lee, with team input, Niriti Pahadi's review revisions, and Kristie Lee's Level 2 updates |
| Team / vertical | Team 5 / Calendar |
| Team members | Juno Lee, Jim Lo, Kristie Lee, Ka Pui Cheung, Niriti Pahadi |
| Last updated | November 7, 2026 |
| Complete-design reviewer | Niriti Pahadi; [review revisions #42][design-review], final review of this revision pending |
| Contract-facing reviewer | Team 2 or Team 7 representative; assignment and final review pending |
| Shared agreement | [Joint decision memo][memo], version 4, October 28, 2026; staff access needs verification |
| Shared contract revision | [calendar-contract v0.1.0-rc.1][shared-tag], commit `1c1cad7a0732ddb242a05400d8833d94e4422424`; installed distribution version `0.1.0` |
| Python / HTTP contracts | [Python interface][python-contract] and [HTTP contract][http-contract] at the shared revision above |
| Implementation work | [Design #40][design-pr], [local PUT #41][put-pr], [package adoption #43][adoption-pr], [conformance #44][conformance-pr] |
| Inspected HW1 baseline | `143be358c1c6086c47035b4088d967895d7f9ebb` |

## Context, goals, and non-goals

A consumer should create, retrieve, replace, and delete a timed event against
Teams 2, 5, and 7 using the same request shapes and outcome handling. HW1 Team 5
used `start_time` and `end_time`; callers moving between teams had to change
serialization. It also ignored unknown body fields and returned 422 for
malformed JSON. These differences could hide client mistakes or require
service-specific error handling.

By November 4 before class, the team must preserve a reviewed design in its
repository and demonstrate at least one Google-backed operation through a tagged
shared package. PUT was selected as the early integration operation because it
exercises replacement requests, the provider boundary, translation, and errors.
Full required conformance and deployment remain November 11 checkpoints.

The current integration branch already contains local PUT and its live evidence
from #41. Jim's #43 merged shared-package adoption into `hw2/milestone-2`
on November 4 at commit `b088ad9c182f4de823f728038a724fdb6b88675e`.
Ka Pui's #44 merged shared conformance wiring into `hw2/milestone-2` on
November 4 at commit `671b63a913a7275e4cce29f04a283a30077db0cd`.
Observed runs still apply to their recorded commits; both changes are integrated
into `hw2/milestone-2`, while the combined PR to `main` remains separate.

Listing, all-day support, extra editable fields, data migration, and runtime
provider switching are excluded from this redesign. Calendar metadata and PATCH
remain extensions. PATCH keeps full-field replacement behavior. No local event
mirror is introduced; Google Calendar owns persistent event state.

## Architecture and request flow

This section describes the implementation merged through
[adoption #43][adoption-pr] into `hw2/milestone-2`. The shared package supplies `Event`, `CreateEvent`,
`ReplaceEvent`, `CalendarService`, `CalendarError`, `ErrorCode`, and validation.
Team 5 retains FastAPI, dependency injection, OAuth, Google SDK calls, HTTP
translation, and logging. The package remains provider-independent.

```text
HTTP caller
  -> FastAPI route + shared request-model validation
  -> injected CalendarService (GoogleCalendarService)
  -> operation-specific Google adapter
  -> authenticated account's primary Google Calendar
  -> shared Event, or adapter error translated to CalendarError
  -> HTTP response + one sanitized request outcome log
```

`app/calendar_service.py` implements `CalendarService` structurally by composing
the existing four adapters, rather than duplicating their SDK code:

| Shared method | Team 5 adapter |
| --- | --- |
| `create(CreateEvent) -> Event` | `GoogleEventCreator.create_event` |
| `get(event_id) -> Event` | `GoogleEventReader.get_event` |
| `replace(event_id, ReplaceEvent) -> Event` | `GoogleEventUpdater.update_event` |
| `delete(event_id) -> None` | `GoogleEventDeleter.delete_event` |

`get_calendar_service` in `app/calendar_service_dependencies.py` receives the
existing operation factories as FastAPI subdependencies and constructs the
composition object. POST, event GET, PUT, and DELETE receive the shared protocol.
PATCH delegates to `replace`. Tests can substitute the complete service or an
operation subdependency. This composition has one concrete responsibility:
exposing the common methods and translating existing adapter failures.

Adapters create and close Google clients per operation using context management.
They translate Google fields and validate returned data before constructing the
shared Event. SDK outcomes become operation-specific errors inside adapters;
`GoogleCalendarService` converts those errors to `CalendarError`. The HTTP
handler selects the public response and supplies safe error context to the
request middleware, which emits one outcome log at request completion.
Programming errors propagate rather than being presented as known provider errors.

Before requests, a developer runs `scripts/google_calendar_auth.py`. Routes never
launch browser authorization. Local credential loading and refresh remain in
`app/google_auth.py` and the existing shared write-authorization helper. Both
setup scopes are retained. Calendar metadata keeps its existing separate reader
and dependency injection.

### Successful replacement

FastAPI validates a `ReplaceEvent` containing all of `title/start/end` and rejects
unknown fields before a provider operation. The route calls `service.replace`.
`GoogleEventUpdater` reads the event to detect missing/cancelled state, then
patches `summary`, `start`, and `end`. It checks the returned ID and converts
Google's result to Event. The route returns 200 with that same ID. The patch
preserves unrelated Google fields, including description.

### Expected failure

If the patch is sent but its response is lost, the updater raises
`EventUpdateUnconfirmedError`. The service converts it to `CalendarError` with
`PROVIDER_ERROR` and `retryable=False`; the HTTP handler returns 502 and logs one
sanitized entry. Neither layer retries the uncertain write. The response does
not establish whether Google changed the event.

## API, data model, and compatibility

The linked memo and versioned Python/HTTP contracts define the shared agreement.
This section records Team 5's migration choices rather than duplicating that
agreement. This revision corrects the inherited `v0.1.0` source pin to the
published `v0.1.0-rc.1` tag, updates lock metadata and current references, and
keeps the shared commit unchanged. The correction was integrated through #40;
historical output retains its original labels with the clarification below.
Both names have referred to commit `1c1cad7`; the current published tag is the
reproducible reference. The distribution's internal version remains `0.1.0`.

| Operation | Success | Adoption behavior |
| --- | --- | --- |
| POST `/events` | 201 + Event | `CreateEvent`; Google assigns the opaque ID |
| GET `/events/{event_id}` | 200 + Event | Shared response fields; empty title allowed for untitled provider events |
| PUT `/events/{event_id}` | 200 + Event | `ReplaceEvent`; same ID, complete replacement of shared editable fields |
| DELETE `/events/{event_id}` | 204, no body | Missing or repeated deletion returns 404 |
| PATCH `/events/{event_id}` (extension) | 200 + Event | Same shared fields and full-field replacement path as PUT |

Requests and Event responses use string `start` and `end`. Legacy
`start_time/end_time` inputs are rejected with 422, including when canonical
fields are also supplied. Unknown fields are rejected. There are no temporary
aliases. Existing clients, tests, tutorial examples, and scripts must migrate
together. Calendar metadata retains `id/title/time_zone`.

POST, PUT, and PATCH require non-null string `title/start/end`. The shared models
check RFC 3339 timestamps, explicit offsets, and `end > start` by instant. Team 5
passes timestamp strings without deliberately truncating fractions; provider
precision and equivalent output offsets can differ. Whole-second timestamps are
the portable consumer choice. Accepted memo rule 14 requires ordering validation
after truncation if an implementation truncates. Team 2's October 28 acceptance
resolved the old approval question.

Write titles must be nonblank after trimming. The package preserves submitted
text, while Team 5 trims before writing to Google. Reads of untitled provider
events return an empty title. No new application title-length maximum is added.

IDs identify events in the configured primary calendar, not globally across
accounts. The shared model treats them as opaque. Team 5 retains HTTP ID
validation of 1-1024 letters, digits, underscores, or hyphens. This
restriction is a Team 5 HTTP policy, not a shared-model rule. Controlled
tests verify boundary lengths, unchanged forwarding, and recurring-instance
IDs. IDs are not parsed to infer recurrence; provider metadata determines shape.

Illustrative expected request/response, not an observed event:

```http
PUT /events/example-provider-id
Content-Type: application/json

{"title":"Design review","start":"2026-11-04T15:00:00Z","end":"2026-11-04T15:30:00Z"}
```

```http
HTTP/1.1 200 OK
Content-Type: application/json

{"id":"example-provider-id","title":"Design review","start":"2026-11-04T15:00:00Z","end":"2026-11-04T15:30:00Z"}
```

The shared representation omits description, location, attendees, recurrence,
and other Google fields without requiring those fields to be deleted. All-day
and unsupported provider shapes remain outside the timed-event model.
GET retains 422 `invalid_input` for all-day events and can read the timed
representation of a recurring series or instance. PUT/PATCH reject all-day
events and recurring-series parents with 400 `invalid_input`, `retryable=false`,
before any patch. Individual timed recurring instances can be replaced;
`recurringEventId`, `originalStartTime`, description, and the parent are retained
by the controlled patch checks. Malformed provider time structures return 502.
DELETE keeps its existing behavior; these guards concern replacement only.
This local policy does not add operations or fields to the shared interface.
Google identifies series and instances through
[recurrence metadata](https://developers.google.com/workspace/calendar/api/guides/recurringevents);
Team 5 tests the behavior offline and does not claim new live recurrence evidence.
[Observed verification][adoption-evidence] records actual sanitized results and
reproduction steps for the adopted shared commit.

## Alternatives and tradeoffs

**Reuse Google's patch operation for common-field replacement.** Requiring every
shared editable field at the HTTP boundary supplies full common-model
replacement while retaining non-shared Google state. Reusing the updater avoids
a second SDK/authentication path. Controlled tests inspect its payload, and the
live workflow independently checks that description survives replacement.

Google's full update operation is the alternative. It would require copying
unrelated fields or accepting their removal, conflicting with Team 5's
preservation choice. Revisit patching if the common contract requires replacing
provider extensions or provider evidence contradicts preservation. There is no
atomic read/write or concurrent-edit guarantee.

**Use shared models directly and compose existing adapters.** Separate local
models would reduce initial edits but introduce ongoing conversions and risk
validation drift. Direct adoption changes more callers now, while a small
composition object retains operation ownership and existing provider tests.
Revisit this choice if a required extension cannot be represented without
breaking the shared boundary.

**Reject legacy field names.** Aliases or versioned compatibility routes would
reduce immediate client disruption but add ambiguous mixed-name cases and more
validation paths. A direct rename makes unknown-field rejection predictable;
its cost is a documented client migration. Revisit compatibility support only
with a concrete consumer requirement and cross-team review.

## Failures and operational concerns

Request construction can raise Pydantic `ValidationError` before a service call.
FastAPI request validation renders invalid client input in the common envelope;
manually constructed models need equivalent handling at their HTTP boundary.
Known operation failures instead cross the service boundary as `CalendarError`.

| Outcome | HTTP/code | Retry advice |
| --- | --- | --- |
| Malformed or empty JSON | 400 `invalid_input` | False; correct input |
| Invalid valid-JSON input or HTTP ID | 422 `invalid_input` | False |
| All-day or series-parent replacement | 400 `invalid_input` | False; event unchanged |
| All-day GET | Existing 422 `invalid_input` | False |
| Missing/cancelled/deleted event | 404 `not_found` | False |
| Confirmed permission denial | 403 `access_denied` | False |
| Missing/unusable OAuth or rejected authorization | 503 `provider_unavailable` | False; repair setup |
| Temporary pre-write failure or explicit rate-limit rejection | 503 `provider_unavailable` | True; wait before caller retry |
| Invalid provider response or uncertain POST/PUT | 502 `provider_error` | False for uncertain writes |
| Unconfirmed DELETE | 502 `provider_error` | True; a completed deletion is subsequently 404 |

A PUT existence-read failure occurs before a write and can safely be classified
as temporary unavailability. A transport failure after sending POST/PUT preserves
write uncertainty. Automatic uncertain writes remain disabled. No meaningful
retry delay is currently known; do not invent `Retry-After`. Supply it if a
meaningful wait becomes available.

The common error envelope is `{"error":{"code":"...","message":"...","retryable":false}}`.
The service supplies safe messages, a Boolean provider-involvement flag, and
a controlled reason for unsupported shapes. The HTTP handler uses that reason
to select 400 without changing other `INVALID_INPUT` mappings.
`app/errors.py` logs operation, code, status, and that flag once; it does not
expose raw exception messages, request bodies, titles, tokens, or authorization
headers. Credential files stay outside Git and evidence. Deployment must define
secret injection, refresh-token persistence, and write permissions separately.

PUT's local work is proportional to the encoded field sizes. Its normal provider
path performs one existence read and one patch, with possible credential refresh.
It does not scan the calendar; network timing does not establish Google's
internal complexity. Tests check that failures do not cause extra writes.

Every live run owns its created data and records cleanup results. The workflow
script keeps an obtained ID and cleans up in `finally`, attempting its remaining
checks after failures. If creation is uncertain without an ID, inspect the
calendar using the printed run marker before another POST. The shared live
suite's cleanup gaps remain a separate review concern described below.

### Milestone 3 deployment

Juno owns the Cloud Run deployment, billing checks, and teardown. Deploy one
service in `us-central1`, with zero minimum instances, a maximum
of one instance, and one concurrent request per instance. The workload is
occasional classroom demonstrations. The first request after idle may be slow.
Level 3 uses always-allocated CPU so background telemetry can run after a
response. This uses instance-based billing while an instance exists; do not
carry forward the earlier request-billing free-tier assumption. The project
requires billing, and compute, telemetry ingestion, and registry storage can
incur charges. Juno owns billing review. Keep classroom traffic bounded and check
billing through February 28, 2027, then tear down the deployment.

| Responsibility | Implementation |
| --- | --- |
| Infrastructure | Terraform with a protected, versioned Cloud Storage state bucket and a separate state prefix for each environment |
| Build | Non-root Python 3.14 container with dependencies installed from `uv.lock`; record the source commit and deploy by Artifact Registry digest |
| Secrets | Mount pinned Secret Manager versions for Google OAuth and the demo bearer key. Terraform records references only |
| Authorization | The Google refresh token survives instance replacement in Secret Manager. All hosted Google adapters share in-memory credentials. Rotate a durable refresh token by adding a secret version and deploying that version |
| Access | Cloud Run serves HTTPS. The application authenticates requests before routing, with only the health and readiness endpoints exempt |
| Health | `/ready` confirms hosted startup checks passed and gates startup. `/health` checks process health. The live workflow checks provider connectivity separately |
| Handoff | Level 2 automates deployments using immutable image digests and verified release manifests. Rollback restores application code and configuration. Google Calendar writes need separate cleanup |

A hosted service does not require a persistent disk. Google Calendar remains
the authoritative store for events. The deployed application loads the durable
OAuth grant at startup without contacting Google, then refreshes access tokens in
memory when needed. Google outages therefore surface as operation failures without
making Cloud Run restart the process. Check the OAuth consent status before the
deployment. External apps in Testing can issue refresh tokens that expire after
seven days.

See [the deployment runbook](docs/DEPLOYMENT.md) for bootstrap, plan/apply,
verification, and teardown. An independent teammate must reproduce the steps in
a disposable environment. Keep the review evidence separate from the design.

### Level 2: release pipeline and recovery

Kristie's `deploy.yml` reuses Checks before deploying an immutable image digest.
An administrator bootstraps environment-scoped OIDC permissions in `infra/ci`;
CI cannot administer its own IAM or bootstrap state. The checked Terraform plan
permits only an update/no-op of the existing service. Deployment and recovery
share environment concurrency and state locking.

The ready revision and traffic must match, then deployed HTTP operations,
independent Google read-back, and cleanup must pass before a verified release
artifact is published. Manual recovery validates a successful trusted artifact,
restores its original Terraform configuration, image, and secret versions without
rebuilding, and repeats the same checks. It does not undo Calendar writes.

See [the deployment runbook](docs/DEPLOYMENT.md#level-2-automated-deployment-and-recovery)
for setup and recovery. **Verify deployment, failure detection, and recovery are
verified**, including real Google smoke, cleanup, and a no-change Terraform plan.
The merged PR #48 revision `ed6ab9e` subsequently passed the
[demo Deploy run, attempt 2](https://github.com/juno-junhyuk-lee/OSPSD-Team-5/actions/runs/42409430131/attempts/2),
including ready revision/traffic, real Google smoke, cleanup and verified-release
artifact publication. This Level 2 result does not establish deployment of the
later Level 3 implementation.

### Level 3: request observability

Jim's `RequestTelemetryMiddleware` wraps caller access, validation, and route
execution. It records fixed-label request/error counters and duration histograms,
then emits one sanitized outcome log. Existing error handlers supply categories
and provider context without duplicating that log. The common metric operation
names are `create`, `get`, `replace`, and `delete`, matching the shared Python
interface; PATCH and calendar metadata remain separate extensions.

The lifespan owns an isolated OpenTelemetry tracing SDK provider. Each request
has one SERVER span and explicit Google execute/credential-refresh calls have
CLIENT child spans. PUT/PATCH separates its pre-read from its write. Logs and
responses reaching the middleware carry the SDK trace ID; logs retain a separate
request UUID as well. Resources contain the service name and sanitized release.
Incoming trace/baggage headers, raw URLs, event data, exception text, and
tracebacks are not exported. Tracing failure does not change the API result or
repeat provider work.

An explicit project setting attaches official OTLP/HTTP exporters to the
app-owned SDK providers. Cloud Run's runtime identity authenticates to Google's
Telemetry API; Calendar credentials are never used for export. Traces queue at
most 512 spans, export batches of 64, and have a 256 KiB payload limit and
three-second export timeout. Metrics aggregate in the SDK and export every
30 seconds in batches of at most 256 points with the same payload/timeout limit.
Worker failures drop observations without changing or retrying API work.
No global SDK provider is installed. Shutdown attempts a final export.

Request-entry saturation measures active common-operation requests divided by
the configured instance concurrency of one; the histogram preserves brief work
that a periodic gauge could miss. It is not a time-weighted utilization or
queue measurement. Cloud Run memory relative to its 512 MiB limit supplies
additional instance-wide context. `infra/observability` provisions a dashboard
with all four signals for each common operation, release/environment legends,
and log/trace investigation links. It owns separate administrator state; the
release pipeline cannot change its IAM. No SLO targets or alerts are added here.

See [the observability guide](docs/OBSERVABILITY.md) for setup, interpretation,
export limits, independent verification, and the handoff to Level 4. Deployed
evidence is separate from controlled SDK tests; teammate interpretation and
the eventual reviewed release remain required before Level 3 sign-off.
The [walkthrough and Level 4 handoff](docs/OBSERVABILITY_HANDOFF.md) records
Ka Pui’s completed independent interpretation and approval in PR #49, with
optional documentation clarifications. Reviewed-merge deployment remains
pending. The handoff also defines the existing metric
names/units and query boundaries that Level 4 can use without assuming an SLO
policy from HTTP status alone.

## Testing and verification

| Guarantee | Check and what it establishes |
| --- | --- |
| Shared validation and migration | `test_shared_model_migration.py` and HTTP validation tests: required/unknown/legacy fields, malformed JSON, ordering, and no provider operation on rejection |
| Shared interface and DI | `test_calendar_service.py` and `test_shared_calendar_http.py`: composition, service substitution, statuses/errors, and restored overrides |
| Local ID and event-shape policy | `test_event_shape_policy.py`: no writes for all-day/series replacement, timed instance preservation, existing GET policy, HTTP ID boundaries |
| Google translation and write phases | Adapter tests and `test_shared_provider_failures.py`: controlled SDK outcomes, unchanged replacement ID, before/after-write classification, no retry |
| Sanitized request observations | `test_observability.py` and existing HTTP log assertions: counters, histograms, one outcome entry, correlation, bounded labels, privacy, and fail-open recording |
| Request and provider traces | `test_tracing.py`: normal HTTP/adapter wiring with fake Google, real SDK span export, parentage, error/retry semantics, request isolation, and privacy; not deployed evidence |
| Same vertical suite | #44's `test_shared_conformance.py`: tagged `CalendarServiceConformance` against Team 5's implementation |
| Real persistence and extension preservation | Workflow script and recorded live conformance: actual Google reads/writes, description preservation, cleanup |
| Deployment and rollback guards | `test_deploy_release.py` and `test_rollback_release.py`: immutable references, service-only plans, ready revision/traffic, trusted artifact provenance, and original configuration inputs |
| Smoke failure/cleanup behavior | `test_verify_put_live.py`: controlled remote HTTP transport, readiness before writes, faulty PUT detection, cleanup, and no uncertain-create retry; not live pipeline evidence |

In #44, the offline `service` fixture constructs `GoogleCalendarService` using
real adapters backed by the isolated fake Google client. `failing_service`
receives `ProviderFailure` and builds the real composition object with adapters
raising controlled Team 5 errors. The suite therefore checks shared error
translation; Google-to-adapter classification is covered separately by offline
provider tests. Failure hooks remain in tests, not the production protocol.

Adoption #43 and conformance #44 are integrated into `hw2/milestone-2`.
Run the shared suite offline with:

```sh
uv run pytest tests/test_shared_conformance.py -v -k 'not Live'
```

An explicit live run uses real Google adapters for success/not-found behavior:

```sh
CALENDAR_LIVE_CONFORMANCE=1 uv run pytest tests/test_shared_conformance.py -v -k Live
```

Its failure groups still use controlled adapters, and invalid-input cases test
request models. They do not induce real Google failures. This distinction also
applies to the recorded 24-test live run. Passing Python conformance alone does
not prove HTTP serialization, statuses, malformed-JSON handling, or deployment.

The consumer workflow remains POST, GET, PUT, GET, DELETE, GET expecting 404,
then repeated DELETE expecting 404. Only base URL and setup vary between
services. Compare instants rather than timestamp strings. An ignored start
update must be caught with a replacement start representing a different instant;
the tagged suite currently has a gap here, so retain Team 5's separate
replacement checks.

The tagged suite also does not register `missing_id` fallback cleanup and stops
cleanup after its first unexpected deletion failure. Ka Pui owns a local fixture
override or corrected shared release before final live-suite approval. Track IDs
immediately, attempt every cleanup, and test both failure paths offline. A prior
successful live run does not establish cleanup behavior during failures.

### Observed evidence and limits

- [Local PUT evidence][put-evidence] from #41 uses HW1 field names and establishes
  local PUT before adoption; it is not shared-package evidence.
- [Adoption evidence][adoption-evidence] records Jim's November 4 real Google
  workflow at clean service commit `327e8bc`, using shared commit `1c1cad7`.
  POST/GET/PUT/GET, independent Google checks, description preservation, and
  DELETE/404 checks passed. Requests use TestClient in-process HTTP through
  normal dependencies; the run does not establish a Uvicorn listener, restart,
  or deployment. Its original tag label requires clarification to the currently
  published `v0.1.0-rc.1` without rewriting historical observations.
- [Conformance evidence][conformance-evidence] records Ka Pui's November 4 run
  at adoption base `aa11f9c` plus the conformance test content committed in #44:
  24 passed, exit 0, followed by a Google search reporting no remaining test
  events. It identifies controlled failure cases separately from real Google.
- Independent review of `aa11f9c` passed 433 offline tests; review of #44 at
  `86fd81e` passed 457 with 24 live tests skipped, plus lint, formatting, and
  strict typing. These counts belong to those revisions, not every later head.
  Adoption head `6d1611f` also has [passing CI][adoption-ci] and was merged via
  #43 at `b088ad9`. The earlier live run remains tied to `327e8bc`; it is not
  relabeled as a new run at the merge commit.

The local policy revision passed 475 offline tests, Ruff lint/format, strict
mypy, verification-script typing, and whitespace checks on Python 3.14.2.
These checks cover the ID/event-shape guards; no new live Google run was made.
Record the committed revision and matching CI before treating this as final
submission evidence.

Before final integration, repeat the README checks at the selected commit:

```sh
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run mypy scripts/verify_put_live.py
uv run pytest -v
git diff --check
```

Match CI and recorded evidence to the submitted revisions. Initial installation
needs network access; fast controlled tests require neither network nor Google
credentials. Historical HW1 results cannot substitute for HW2 checks.

## Ownership, coordination, and checkpoints

| Owner | Output | Dependency and checkpoint |
| --- | --- | --- |
| Juno Lee | This design and initial shared-interface contribution | Consolidate #42 into #40, resolve feedback, obtain reviews before November 4 submission |
| Niriti Pahadi | Complete-design review and verification support | Review the consolidated revision and record concerns/outcomes; help reproduce adoption as needed |
| Kristie Lee | Shared-contract and contract-facing coordination | Record accepted revision, cross-team review, and release references before submission |
| Jim Lo | #43 adoption merged; migration, models/errors, examples | Review #40's tag-reference correction and unchanged shared commit before integration |
| Ka Pui Cheung | #41 PUT and #44 conformance merged; real verification recorded | Follow up on inherited live cleanup concerns and verify the combined submission revision |
| Juno Lee | Level 1 Cloud Run runtime, Terraform, billing, and teardown | Verify provisioning, repeat apply, and teardown independently before Level 2 handoff |
| Kristie Lee | Level 2 CI, deployment, and recovery | Verify deployment/failure/recovery verified; merged-revision deployment pending |

Milestone 3 uses `hw2/milestone-3`. Level 2 work on
`hw2/milestone-3-level-2` targets that branch; the combined milestone PR targets
`main` after review and verification.

If a common contract change is incompatible, Kristie coordinates Teams 2, 5,
and 7 and their consumers before publication. Explain changed requests/outcomes,
update memo, package, tests, and service migration together, and obtain affected
team review. Publish a new tag rather than moving an existing published tag.

## Review record and unresolved decisions

| Concern | Disposition / next step | Owner / checkpoint |
| --- | --- | --- |
| Stale progress and missing local PUT | Incorporated Niriti's #42 corrections and #41 evidence; shared release and merged #43/#44 recorded | Juno; this revision |
| Concrete CalendarService/error boundary | Documented #43's composition, DI, and adapter-to-CalendarError translation | Jim/Ka Pui; confirm during implementation/design review |
| Old names and PATCH behavior | Documented #43's rejection of legacy names and full-field PATCH with `start/end` | Jim; review with affected callers before integration |
| Shared tag pin | Corrected source/lock/current references to `v0.1.0-rc.1` in this revision; shared commit unchanged, historical output retained with clarification | Juno implements; Jim reviews before #40 integration |
| Shared-suite failure hooks | Implemented in released suite; documented #44's two fixtures and scope | Ka Pui; verify the combined submission revision |
| Replacement-start and live cleanup gaps | Keep separate start-change tests; fix cleanup fixtures locally or via a new shared release | Ka Pui; before relying on those guarantees/live-suite approval |
| HTTP IDs and unsupported event shapes | Local policy implemented and checked in `tests/test_event_shape_policy.py`: ID forwarding/rejection, no unsupported writes, instance metadata preserved | Juno implements; Jim/Ka Pui review with the consolidated design before final acceptance |
| Hosting and credential persistence | Cloud Run, Terraform, and durable Secret Manager credentials replace the original Render proposal | Juno; record live provisioning, billing setup, and independent verification before Level 2 |
| Final complete-design and contract-facing reviews | Review the consolidated revision, link substantive comments/resolutions and scope of approval | Niriti and Team 2/7 reviewer; before submission |

Niriti's #42 provides review revisions; it does not approve this later revision.
Kristie's feedback supplied in team coordination requested fresh progress notes,
concrete architecture/error conversion, compatibility policy, suite execution,
and final revision/evidence links. This document now incorporates the known code
and evidence for those items; final review and unresolved dispositions remain
explicit. Kristie's coordination feedback is not a substitute for the required
outside-team review. No final design approval is claimed.

## Submission and change record

Before submission, record the final reviewed design commit, package tag and
commit, integrated service revision, matching CI, implementation PRs, provider
evidence, reviewer outcomes, and owned remaining-work issues. Verify staff can
access every artifact and submit the team/vertical/member details required by
the assignment. A reviewed plan and a successful provider run are separate
requirements.

- November 2: initial design proposal against the inspected HW1 baseline.
- November 3: added shared links, claimed owners, interface proposal, validation
  boundaries, and conformance strategy; resolved stale rule 14 approval note.
- November 3: Niriti's #42 recorded local PUT/#41 evidence and began the complete
  design review; those revisions are incorporated in this document.
- November 4: consolidated #42 into #40's document, linked the released contract,
  described #43/#44 implementation choices and observed evidence, and replaced
  stale progress notes with current review dependencies. Adoption merged via
  #43 at `b088ad9`; #44 subsequently merged at `671b63a`. Final reviews and
  hosting decisions remain pending. The source-pin correction is supplied in the subsequent revision below.
- November 4: Juno took deployment-proposal ownership. Added local pre-write
  shape guards and controlled policy checks; preserved the shared interface and
  existing GET/ID behavior. Runtime policy changes still require teammate review.
- November 4: proposed a Render/Docker/Blueprint deployment with token
  persistence, access controls, health checks, rollout/rollback, estimated budget,
  and teardown; team approval and actual provisioning remain pending. Corrected
  the shared source tag to `v0.1.0-rc.1` without changing its locked commit and
  clarified historical verification labels.
- November 4: recorded #44 as merged at `671b63a`, removed stale retargeting
  instructions, and retained historical test/live-run revisions. Integration
  does not establish that the inherited cleanup concerns are resolved.
- November 5: selected Cloud Run and Terraform for Level 1. Added the container,
  hosted runtime, infrastructure configuration, and deployment runbook. Live
  provisioning and independent verification remain separate evidence.
- November 6: added Level 2 CI, OIDC bootstrap, immutable deployment, smoke
  gating, and manual recovery. Local checks passed.
- November 7: verified pipeline deployment, controlled failure detection, and
  recovery in verify, including real Google smoke/cleanup and a no-change plan.
- Codex assisted with drafting, repository inspection, and review checks.
  Students must understand, verify, and own their submitted work.

[memo]: https://docs.google.com/document/d/1bVv6tLLtfGKt75HH1OPBTuJ3d1kkMdkEgzz9ef3UcOI/edit
[shared-tag]: https://github.com/Airbus-A330/OSPSD-Calendar/tree/v0.1.0-rc.1
[python-contract]: https://github.com/Airbus-A330/OSPSD-Calendar/blob/1c1cad7a0732ddb242a05400d8833d94e4422424/docs/PYTHON_INTERFACE.md
[http-contract]: https://github.com/Airbus-A330/OSPSD-Calendar/blob/1c1cad7a0732ddb242a05400d8833d94e4422424/docs/HTTP_CONTRACT.md
[design-pr]: https://github.com/juno-junhyuk-lee/OSPSD-Team-5/pull/40
[design-review]: https://github.com/juno-junhyuk-lee/OSPSD-Team-5/pull/42
[put-pr]: https://github.com/juno-junhyuk-lee/OSPSD-Team-5/pull/41
[adoption-pr]: https://github.com/juno-junhyuk-lee/OSPSD-Team-5/pull/43
[conformance-pr]: https://github.com/juno-junhyuk-lee/OSPSD-Team-5/pull/44
[put-evidence]: https://github.com/juno-junhyuk-lee/OSPSD-Team-5/blob/e52d656/docs/PUT_LIVE_VERIFICATION.md
[adoption-evidence]: https://github.com/juno-junhyuk-lee/OSPSD-Team-5/blob/aa11f9ccbd75dd66fd280aa22a06186a29a47564/docs/SHARED_CONTRACT_VERIFICATION.md
[conformance-evidence]: https://github.com/juno-junhyuk-lee/OSPSD-Team-5/blob/86fd81e250543610d7a51bbe7197a95236b5b08b/docs/SHARED_CONTRACT_VERIFICATION.md

[adoption-ci]: https://github.com/juno-junhyuk-lee/OSPSD-Team-5/actions/runs/41897518692
