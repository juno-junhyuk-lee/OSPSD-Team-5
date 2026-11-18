# Storage failure certainty and cleanup plan

Owner: Kristie (Member 4), with Niriti (Member 1) for workflow behavior and Ka Pui
(Member 5) for integration review. Baseline: `4cbe546`. This document describes
current behavior and proposed follow-up acceptance criteria. It changes no code,
claims no new provider verification. Package integration has since become
mandatory; apply these certainty rules to the package boundary under the
[transition plan](HW3_STORAGE_PACKAGE_TRANSITION.md). HTTP-specific examples
below describe the historical implementation or proposals, not the
selected final integration.

## Decision rules

Classify whether this attempt could have created the summary, not simply whether
the latest request failed. A failure before a download request cannot undo an
earlier successful upload. A known destination is a locator, not proof of state.

- **Definitely not applied:** local rejection before creation, a documented
  pre-send creation failure, or a valid shared rejection that guarantees no write.
  If the issue/event already exist, compensate event first, then issue.
- **May have applied:** transmission or outcome is uncertain, or an upload was
  acknowledged but readback fails. Keep issue/event; return a non-retryable error
  with the possible summary and its optional known path. Do not automatically
  retry, overwrite, or delete the possible summary in the production workflow.
- **Verified success:** creation has usable metadata and downloaded bytes match
  the supplied UTF-8 bytes. Only then return the combined success response.

Cleanup is best effort. A shared NOT_FOUND means already removed. Any other
cleanup error leaves that resource represented in leftovers; do not claim a
complete rollback. Attempt both earlier-resource deletions even if one fails.
`retryable` may be true only when the original failure allows it AND there are
no leftovers. A definitely failed write alone does not make retryable true.
The real store currently defaults it to false; this plan does not change that.

## Implemented package classification (task 5)

The production package factory uses provider-specific summary-store subclasses;
the generic shared store does not infer transport phases from provider names.
This classification depends on pinned Team 3 `fde60d4`, its preserved explicit
exception causes, and the SDK retry counts set to zero by our factory.

Team 1 support (step 4) is pinned to `784be97` with SDK `12.1.0`. Its backend
preserves the Requests exception directly as the shared error's cause, unlike
Team 3's intermediate builtin ConnectionError. Its summary-store subclass checks
that direct cause. Both use the same narrow typed connection-establishment
predicate; neither infers certainty from text or a generic connection failure.
Unknown/lost cause chains remain uncertain. Recheck these assumptions on upgrades.

| Creation or readback outcome | Workflow action |
| --- | --- |
| Known shared conflict, permission, input/operation, size or not-found rejection during create | Compensate event then issue; do not delete any summary |
| Create raises shared ProviderUnavailableError whose exact builtin ConnectionError cause preserves requests ConnectTimeout | Definitely pre-send; compensate event then issue |
| Same preserved chain contains requests ConnectionError wrapping urllib3 MaxRetryError with NewConnectionError reason | Definitely failed to establish a connection; compensate event then issue |
| Generic ConnectionError, read timeout, missing/unrecognized cause chain or unknown shared error | Keep issue/event and uncertain summary; no retry |
| Upload applied but reply was lost | Keep all resources; no automatic retry or summary cleanup |
| Upload confirmed, then any readback failure, including ConnectTimeout or 404 | Keep all resources; a later connection failure cannot undo earlier creation |
| Malformed package metadata or unexpected untyped package exception | Sanitize and preserve uncertainty rather than return an unhandled error without leftovers |

The phase classifier never examines messages. A generic connection exception
whose text says "connection refused" remains uncertain. These rules must be
rechecked when upgrading the provider or SDK/transport. Missing cause information
is not a reason to guess or probe for absence. Operation failures remain 502;
pre-workflow configuration failures remain 503.

Controlled tests exercise both real Team 3 translation layers by injecting SDK
failures. They check event-before-issue cleanup, continued issue cleanup after
event deletion fails, NOT_FOUND treated as absent, unresolved cleanup leftovers,
one upload attempt, no summary deletion/metadata probe, known path retention and
sanitized responses/logs. They also simulate applied-but-lost replies and bad
metadata. This establishes offline behavior; no real network fault, Dropbox
inspection or live controlled-failure evidence is claimed.

## Historical HTTP baseline and original acceptance plan

| Scenario | Current baseline | Required follow-up behavior |
| --- | --- | --- |
| Invalid connection/root settings | 503 before workflow writes | Preserve; no provider request or cleanup |
| Invalid filename/text before create | Definitely not applied | Preserve; compensate any earlier issue/event |
| Valid create conflict or documented permission/input rejection | Definitely rejected | Preserve; compensate event then issue, never touch the existing remote file |
| Creation connection refused before request transmission | All HTTP RequestError values become uncertain ProviderUnavailableError | Close Ka Pui's review item: preserve a trustworthy pre-send classification and allow compensation |
| Connect/pool timeout before the create request is sent | Same conservative treatment | Treat as definite only when the transport establishes the pre-send phase |
| Write timeout, lost reply, read timeout, unknown transport phase | Uncertain | Preserve uncertainty; one create attempt, no compensation |
| Create 5xx, redirect, unexpected status, malformed metadata/error body | Uncertain | Preserve; no retry or fallback write |
| Upload confirmed, then any readback error (including connection refusal/404) | May have applied | Preserve; keep earlier resources and known summary path |
| Readback bytes differ | May have applied | Preserve; report failed verification, not success or an absent file |

The default HTTPX exception definitions distinguish ConnectError (connection
establishment), ConnectTimeout and PoolTimeout from receiving/sending failures
in ReadTimeout/WriteTimeout. A future HTTP fix must use typed transport-phase
information, never message matching or a blanket rule for RequestError. Tests
must establish that the creation request was not sent. Custom transports or
wrappers with unknown semantics remain uncertain. Once create has succeeded,
that earlier fact takes precedence over any subsequent pre-send read failure.

For package implementations, shared ProviderError/ProviderUnavailableError alone
does not prove a write was never sent. Inspect the implementation and preserve
explicit certainty when available; otherwise keep the conservative behavior.
Do not infer absence from an exception name, a generic 503, or one metadata read.
Contract changes, if needed, require coordination with the implementation owners.

The existing storage failure mapping returns 502 at step=summary for operation
failures and 503 for missing configuration. Keep that response mapping unless a
separate change is agreed with Niriti. `path` remains independent of provider ID,
omitted when unknown, and excluded from logs and remote error text.

## Regression test acceptance criteria

| Case | Assertions | Existing coverage and gap |
| --- | --- | --- |
| Configuration rejected before writes | No create calls, no cleanup, 503, step=summary, empty leftovers | Covered by summary/workflow tests |
| Definite storage rejection | One create, no download/retry; event then issue cleanup; existing file untouched | Conflict covered; preserve when changing the transport |
| Confirmed pre-send create failure | No transmitted create; compensate event then issue; no summary leftover | New classification/endpoint regression needed if HTTP remains |
| Pre-send failure with cleanup errors | Still attempt both deletions; report unresolved issue/event; retryable=false | Generic cleanup failure covered; add this classification-specific regression |
| Unknown outcome after create transmission | One create; no automatic retry or cleanup; issue/event plus summary leftovers | Timeout covered; distinguish send/read failure and a server-applied/lost-reply case |
| Upload succeeds, readback connection fails | No compensation; non-retryable; summary destination retained | Readback 404/mismatch covered; add explicit readback ConnectError regression |
| Known/unknown path | Known path separate from id; unknown omitted; OpenAPI field optional; no sensitive logs | Covered at baseline 4cbe546 |
| Cleanup reports NOT_FOUND | Count as already absent; do not report a complete rollback if another deletion failed | Generic NOT_FOUND covered; preserve with the new definite-failure case |
| Final implementation selection | Same workflow outcomes for controlled HTTP/package dependencies | Run for the chosen integration; current HTTP tests do not establish package conformance |

Existing tests: `tests/test_storage_http.py`, `tests/test_summary_storage.py`,
`tests/test_workflow.py`, and `tests/test_verify_storage_live.py`. A test name
such as timeout_before_write in the probe suite does not establish that the
production workflow can distinguish pre-send failures: it currently simulates a
ReadTimeout and tests probe cleanup, not the proposed transport classification.

## Implementation branches and ownership

If HTTP is allowed, Kristie adds pre-send certainty without changing shared
error codes, then verifies transport-to-SummaryStorageError propagation and the
endpoint outcomes above in a focused code commit. Do not merely mark every
ProviderUnavailableError as definite; it can follow an applied write.

If package import is required, Kristie first verifies installation/initialization
and the implementation's failure guarantees, then implements the same workflow
tests through the selected DocumentStorage. HTTP-specific changes can be omitted
if that transport leaves the production path. Either choice retains the known
summary-path handoff already added with Niriti's assumed agreement.

Niriti owns any additional public error/status or orchestration change. Ka Pui
reviews the resulting behavior and incorporates the agreed rules into DESIGN.md.
Mark the connection-failure review item resolved only after the implementation
and its regression tests land; this planning document alone does not resolve it.

## Production recovery versus test probe cleanup

The production workflow preserves uncertain resources for reconciliation. A user
checks the configured provider and known path, contents and references before a
new attempt. There is no automatic resume/idempotency guarantee in this plan.

The opt-in probe intentionally has a different scope: one UUID-named scratch file,
an initial absence check and explicit permission to create/delete test data. It
cleans that file after uncertain outcomes, verifies absence and records failures.
Never copy that test cleanup policy into the production workflow. Controlled
tests, a live storage probe, independent provider inspection and a deployed
three-vertical controlled-failure demonstration are separate evidence items.
