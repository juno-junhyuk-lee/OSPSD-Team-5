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
| Summary storage (`SummaryStore`) | Member 4 | Placeholder: `get_summary_store` returns 503 until the adapter lands |

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
   The suggested name is path-safe; storage may assign its own ID.

## Failure handling

Errors keep the existing shape (`code`, `message`, `retryable`) and add `step`
(`validate`, `issue`, `event`, `summary`) and `leftovers`, the resources that may
still exist. Messages are fixed text; remote messages are never forwarded.

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
  configuration errors; storage placeholder.
- `app/summary_storage.py`: `SummaryStore` protocol, `StoredSummary`, and
  `SummaryStorageError(may_have_applied, retryable, configured)`.
- `tests/test_workflow.py`: offline orchestration, Markdown, failure, logging,
  and dependency tests with fakes for all three providers.

## Handoff for Member 4 (storage)

Implement `SummaryStore` and replace `get_summary_store` in
`app/workflow_dependencies.py`. Raise `SummaryStorageError` only, with
`may_have_applied=True` whenever the write might have happened (for example, a lost
response), and `configured=False` for missing configuration. Do not include
provider bodies or credentials in messages.

## Remaining work

- Connect Member 4's storage adapter and verify each integration live.
- Run the full workflow against deployed services, including cleanup, and record
  evidence.
- Deploy the endpoint (bearer authentication already covers all non-health paths).
- Member 5: fold this into the HW3 `DESIGN.md` and the end-to-end test plan.
