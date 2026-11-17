# HW3 Member 1: scheduled-issue workflow

## Status

Endpoint structure, orchestration, Markdown generation, and failure handling are
implemented and tested offline with controlled dependencies. Live issue, Calendar,
and storage integrations are connected as they become available. No deployed or
live end-to-end evidence is claimed yet.

| Integration | Owner | State |
| --- | --- | --- |
| Issue tracker (`IssueProvider`) | Member 3 | Wired via `get_issue_provider` (PR #52); live verification pending |
| Calendar (`CalendarService`) | Member 2 | Wired via existing `get_calendar_service` |
| Summary storage (`SummaryStore`) | Kristie (Member 4) | HTTP currently wired; mandatory package transition planned; package CRUD and swap pending |

See the [storage package transition plan](HW3_STORAGE_PACKAGE_TRANSITION.md) for
the active decision and proposed file ownership with Niriti and Ka Pui. This
documentation update does not change workflow wiring or claim their agreement.

## Endpoint

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
| Invalid input | None | none |
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
dependency resolution with 503, before any write.

## Code

- `app/workflow.py`: request/response models, Markdown rendering, orchestration,
  error translation, compensation, and the error handler.
- `app/workflow_dependencies.py`: selects the three providers; translates issue
  configuration errors; supplies the scoped storage client.
- `app/summary_storage.py`: `SummaryStore` protocol, `StoredSummary`, and
  `SummaryStorageError(may_have_applied, retryable, configured, path=None)`.
- `tests/test_workflow.py`: offline orchestration, Markdown, failure, logging,
  and dependency tests with fakes for all three providers.

## Storage handoff for Kristie (Member 4)

`DocumentSummaryStore` now bridges to tagged `DocumentStorage` through
`HttpDocumentStorage`; `get_summary_store` validates configuration before writes
and closes its HTTP client afterward. It raises sanitized `SummaryStorageError`
for operation failures and a 503 `WorkflowError` with `step=summary` and no
leftovers for bad configuration. See [storage setup and remaining evidence](HW3_STORAGE.md).

## Remaining work

- Independently verify each integration in its provider and complete the real
  configuration-only storage swap; the storage adapter is connected locally.
- Run the full workflow against deployed services, including cleanup, and record
  evidence.
- Deploy the endpoint (bearer authentication already covers all non-health paths).
- Member 5: fold this into the HW3 `DESIGN.md` and the end-to-end test plan.
