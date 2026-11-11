# DELETE Level 4 verification

Ka Pui Cheung owns `DELETE /events/{event_id}` and its provider injection. This
record covers implementation commit `8057588`.

## Wiring to review

- The DELETE route receives the provider-independent `CalendarService` through
  `Depends(get_calendar_service)` in `app/main.py`; the route does not construct
  or import the concrete event provider.
- `get_calendar_service()` supplies `GoogleCalendarService` and composes the
  operation providers. `get_event_deleter()` in
  `app/event_deletion_dependencies.py` selects `GoogleEventDeleter` for normal
  requests. Google SDK calls and SDK error translation stay behind that adapter.
- `tests/test_shared_calendar_http.py` replaces the route's `CalendarService`
  dependency with a `ControlledCalendarService`. The DELETE-specific
  `tests/test_delete_event_contract.py` replaces `get_event_deleter` with a
  `ControlledEventDeleter` and verifies that the normal factory selects Google.
  These controlled tests do not need Google credentials or network access, and
  restore dependency overrides after each test.
- Replacing the service implementation leaves the route unchanged. Replacing
  only the DELETE provider requires a new `EventDeleter` implementation and a
  change to `get_event_deleter()`.

## Offline evidence

Commit `8057588` passed Ruff lint/format, strict mypy, `git diff --check`, and
132 tests on Linux with Python 3.14.6. The six controlled tests also passed with
`socket.connect` and `load_credentials` replaced by functions that fail the
test; calling `GoogleEventDeleter` directly under the same block failed, which
confirms the block was active.

At PR head `6446fb3`, GitHub CI also passed the full application test job,
including the shared-service and DELETE controlled-provider tests. This is
offline evidence, not a live Google verification.

## Real-provider verification

The earlier Level 2 live run verified DELETE against Google on older
revisions. Repeat that verification through normal dependency wiring at the
current branch head before recording Level 4 as complete. Expected results
remain `204` for the first delete, then `404` for a repeated delete and an
unknown ID.

| Date | Verifier | Revision | Result |
| --- | --- | --- | --- |
| _pending_ | Ka Pui Cheung | `6446fb3` | |
| _pending_ | second teammate | | |

Another teammate must review both the real wiring and the test substitution.
