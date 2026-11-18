# HW3 Member 1: scheduled-issue workflow

## Status

Endpoint structure, orchestration, Markdown generation, and failure handling are
implemented and tested offline with controlled dependencies. The local FastAPI
route also passed a real Trello -> Google Calendar -> Dropbox run, followed by
provider readback and cleanup. This is local composition evidence, not deployed
verification or independent human inspection.

| Integration | Owner | State |
| --- | --- | --- |
| Issue tracker (`IssueProvider`) | Member 3 | Imported Team 4 provider; local composed create, fresh read and cleanup passed |
| Calendar (`CalendarService`) | Member 2 | Wired via existing `get_calendar_service` |
| Summary storage (`SummaryStore`) | Kristie (Member 4) | Imported Team 3/Team 1 selected by configuration; local paired composition/readback/cleanup passed; independent inspection and hosted verification pending |

## Local real-provider workflow evidence

Kristie (Member 4) executed the commands with Codex assistance at application
commit `e2616dd52a7aef6803896c48661f0464800ef71b` on November 16, 2026:

- [Creation](evidence/HW3_WORKFLOW_LOCAL_5ef8b3616f30459a83bfc0f94463e0e3.json):
  21:52:58–21:53:04 America/New_York, local FastAPI TestClient using normal
  dependencies and real provider accounts, no dependency overrides. One request
  returned 201 with issue, event and Markdown summary references.
- [Readback and cleanup](evidence/HW3_WORKFLOW_LOCAL_5ef8b3616f30459a83bfc0f94463e0e3_READBACK_CLEANUP.json):
  21:54:19–21:54:24 America/New_York. The imported issue provider's fresh read
  matched; the Calendar package's read matched ID/title/time instants; the storage
  package's metadata and downloaded UTF-8 bytes matched the response summary.
  Cleanup ran summary -> event -> issue and confirmed each absent afterward.

Review checked evidence linkage, response titles, UTC/local time equivalence,
summary path derived from the issue/event IDs, and downloaded-content SHA-256
against response Markdown. Keep creation's original `cleanup=not performed`:
the separate later record establishes cleanup. These ad-hoc execution records
do not include the storage probe's full source-hash/package-provenance manifest;
they identify the application commit and reported readback results. No credentials
are recorded, no new test was rerun to create this documentation, and no deployed
run, independent teammate inspection or live failure injection is claimed.

See the [storage package transition plan](HW3_STORAGE_PACKAGE_TRANSITION.md) for
the active decision and proposed file ownership with Niriti and Ka Pui. This
plan does not claim their agreement. Task 4 now wires `get_summary_store` to the
scoped package factory and maps local initialization failures to a sanitized
503 with `step=summary` and empty leftovers before issue/event writes. Runtime
package configuration is documented in that plan; `STORAGE_BASE_URL` is no
longer used by this workflow.

## Endpoint

### Paired implementation-swap verification

At `bf66e7f`, Kristie also ran the local composed route with Team 3 then Team 1,
changing only the implementation selector between runs. Both returned 201 with
real providers; issue/Calendar/summary readbacks and summary/event/issue cleanup
absence checks passed. Commit/source manifests were unchanged. See
[paired swap evidence and limitations](HW3_STORAGE_TEAM1_INTEGRATION.md#step-6-local-configuration-only-swap-evidence).
These successful normal requests do not resolve #53's validation-precedence issue or establish
deployed/independently inspected verification; the evidence explicitly records
the pending final #53 fix.

### Integrated candidate prerequisites

Kristie (Member 4), with Codex assistance, reconciled upstream milestone commit
`a4da568` with storage branch base `2a11f60`. Keep Team 4's implementation and
issue contract 1.1.0, Calendar's stable contract/local implementation package,
and Team 3's approved storage pin. The workflow fake now includes `list_issues`;
the unconfigured issue test checks `TRELLO_API_KEY`, not the retired HTTP URL.
The OAuth test checks the requested exclusive `0600` open on all platforms and
actual POSIX mode bits only on POSIX. Frozen sync, Ruff lint/format, strict mypy
and the full offline suite passed: **948 passed, 58 skipped**, with the existing
Starlette TestClient warning. Merge staging/commit is left to Kristie.

Before a real run, the operator must configure the same terminal with
`TRELLO_API_KEY`, `TRELLO_TOKEN`, and a permitted 24-character `TRELLO_LIST_ID`;
authorize the intended Google account (`token.json` exists locally but its
validity/account was not checked during this merge); and supply the
[Dropbox package configuration](HW3_STORAGE_AUTH.md). No credential contents
were opened, no live workflow was executed, and prior storage evidence remains
historical to its recorded commit/hash set. Use one uniquely marked workflow
request and preserve response IDs before any cleanup; never blindly repeat an
uncertain request. Live request/readback/cleanup evidence is a separate scope.

`POST /workflows/scheduled-issues`

```json
{"title": "Fix login bug", "start": "2030-01-07T15:00:00Z", "end": "2030-01-07T15:30:00Z"}
```

Success is `201`:

```json
{
  "issue": {"id": "...", "title": "Fix login bug"},
  "event": {"id": "...", "title": "Fix login bug", "start": "...", "end": "..."},
  "summary": {"id": "...", "markdown": "# Fix login bug\n..."}
}
```

## Steps

1. **Validate** the title against both shared contracts (issue 1–256 chars with a
   non-space character; Calendar non-blank) and the times against the Calendar
   rules. Nothing is written if any input is invalid.
2. **Create the issue** through `IssueProvider.create_issue`.
3. **Create the event** through `CalendarService.create` with the same title.
4. **Render Markdown** from provider-confirmed values (`render_summary`). Titles
   are escaped and collapsed to one line; IDs stay inside code spans.
5. **Store the summary** through `SummaryStore.save_summary(name, markdown)`.
   The name is placed under STORAGE_ROOT_PATH; storage verifies exact UTF-8 bytes
   through download before returning its opaque reference.

## Failure handling

Errors keep the existing shape (`code`, `message`, `retryable`) and add `step`
(`validate`, `issue`, `event`, `summary`) and `leftovers`, the resources that may
still exist. Messages are fixed text; remote messages are never forwarded.
Every error from this endpoint (400, 403, 422, 502, 503) has all five fields and
matches `WorkflowErrorResponse` in OpenAPI, including request-body validation and
configuration failures.

An uncertain summary includes its optional storage `path` when the store knows
the destination. The provider `id` remains `null` when it is not reported; a path
is not substituted for an ID in leftovers. Unknown paths are omitted, preserving
the existing shape for controlled stores and other integrations. For example:

```json
{"kind": "summary", "id": null, "state": "uncertain", "path": "/team5/summary.md"}
```

This locator helps manual reconciliation; it does not prove the file exists or
make retrying safe. Retry and compensation behavior are unchanged.

The [storage failure certainty plan](HW3_STORAGE_FAILURE_POLICY.md) distinguishes
current behavior from proposed pre-send failure handling and its acceptance tests.

| Failure | Action | Leftovers |
| --- | --- | --- |
| Malformed or empty JSON | None (400, step `validate`) | none |
| Invalid input | None (422, step `validate`) | none |
| Integration not configured | None (503, step of that integration) | none |
| Issue fails definitively | Stop | none |
| Issue creation uncertain | Stop; no retry | issue `uncertain` |
| Event fails definitively | Delete the issue | none, or issue if deletion failed |
| Event creation uncertain | Keep the issue | issue `created`, event `uncertain` |
| Storage fails definitively | Delete event, then issue | any that could not be deleted |
| Storage uncertain | Keep both | issue, event `created`; summary `uncertain` |

Decisions:

- **No automatic retries of writes.** Both shared contracts forbid retrying
  uncertain writes, and there is no idempotency support to rely on.
- **Compensate only after a definite failure.** If a later step definitely did
  nothing, earlier writes are deleted newest first. A `not_found` during cleanup
  counts as already removed.
- **Never compensate after an uncertain write.** Deleting the issue while the
  event may exist would hide the link a person needs to reconcile.
- **`retryable` is true only when the failed step allows a retry and nothing from
  this attempt remains**, so a client retry cannot create duplicates.

Code mapping: issue `access_denied` → 403, `invalid_input` → 422,
`service_not_configured` → 503 `provider_unavailable`, everything else → 502
`provider_error`. Calendar codes pass through, except an uncertain create, which
is reported as a 502 with leftovers. An unconfigured integration fails during
dependency resolution with 503 `provider_unavailable`, before any write; `step`
names it (`issue` = issue tracker, `event` = Calendar, `summary` = storage).
`WorkflowRoute` gives request-body validation errors and the shared Calendar
dependency's configuration error this shape; other routes keep the shared
three-field error.

## Code

- `app/workflow.py`: request/response models, Markdown rendering, orchestration,
  error translation, compensation, `WorkflowRoute`, and the error handler.
- `app/workflow_dependencies.py`: selects the three providers; translates issue
  and storage configuration errors; supplies the scoped storage client.
- `app/summary_storage.py`: `SummaryStore` protocol, `StoredSummary`, and
  `SummaryStorageError(may_have_applied, retryable, configured, path=None)`.
- `tests/test_workflow.py`: offline orchestration, Markdown, failure, logging,
  and dependency tests with fakes for all three providers.

## Storage handoff for Kristie (Member 4)

`DocumentSummaryStore` now bridges to tagged `DocumentStorage` through
the imported Team 3 package; `get_summary_store` validates configuration before writes
and closes its SDK afterward. It raises sanitized `SummaryStorageError`
for operation failures and a 503 `WorkflowError` with `step=summary` and no
leftovers for bad configuration. See [storage setup and remaining evidence](HW3_STORAGE.md).

## Remaining work

- Independently verify each integration in its provider and complete the real
  configuration-only storage swap; the storage adapter is connected locally.
- Run the full workflow against deployed services, including cleanup, and record
  evidence.
- Deploy the endpoint (bearer authentication already covers all non-health paths).
- Member 5: fold this into the HW3 `DESIGN.md` and the end-to-end test plan.
