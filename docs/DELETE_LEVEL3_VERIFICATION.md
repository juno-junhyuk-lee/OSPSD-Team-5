# DELETE Level 3 verification

Ka Pui Cheung owns `DELETE /events/{event_id}`, the `EventDeleter` contract, and
its Google implementation. This record covers implementation commit `89fb596`.

## Boundary to review

- `app/event_deletion_provider.py` defines `delete_event(event_id) -> None`
  plus three service errors: not found, unavailable, and unconfirmed.
- `GoogleEventDeleter` in `app/google_delete_events.py` keeps `events.delete`,
  the `primary` calendar, `sendUpdates="none"`, and Google 404/410 handling
  behind that contract and translates known failures into service errors.
- The DELETE handler calls an `EventDeleter` and maps service errors to the
  existing 404, 503, and 502 responses without importing SDK exceptions.
- `app/main.py` still selects Google directly for Level 3. Injection and
  controlled deleter tests are Level 4 work.
- `GoogleEventNotFoundError` and `delete_google_event` keep their names because
  PATCH imports the error.

## Offline evidence

Commit `89fb596` passed Ruff lint/format, strict mypy, `git diff --check`, and
126 tests on Linux with Python 3.14.6. The 11 new tests in
`tests/test_google_delete_events.py` check one non-retried `events.delete`
call, 404/410 to not found, setup failure to unavailable without a provider
call, and seven SDK/transport failures to unconfirmed. Removing 410 from the
not-found statuses made three tests fail; restoring it made them pass.

## Real-provider verification

Repeat the [DELETE Level 2 walkthrough](DELETE_LEVEL2_VERIFICATION.md) at this
commit. The expected results are unchanged.

| Date | Verifier | Revision | Result |
| --- | --- | --- | --- |
| _pending_ | Ka Pui Cheung | `89fb596` | |
| _pending_ | second teammate | | |

Teammate review of the boundary and matching PR CI are also pending.
