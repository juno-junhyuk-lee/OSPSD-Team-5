# DELETE Level 4 verification

Ka Pui Cheung owns `DELETE /events/{event_id}` and its provider injection. This
record covers implementation commit `8057588`.

## Wiring to review

- `get_event_deleter()` in `app/event_deletion_dependencies.py` is the only code that
  selects `GoogleEventDeleter`.
- The DELETE route receives an `EventDeleter` through `Depends` and handles only
  the service errors from `app/event_deletion_provider.py`.
- `tests/test_delete_event_contract.py` overrides `get_event_deleter` with a
  `ControlledEventDeleter` and restores prior overrides after each test.
- Swapping providers means a new `EventDeleter` implementation and a one-line
  change in `get_event_deleter`.

## Offline evidence

Commit `8057588` passed Ruff lint/format, strict mypy, `git diff --check`, and
132 tests on Linux with Python 3.14.6. The six controlled tests also passed with
`socket.connect` and `load_credentials` replaced by functions that fail the
test; calling `GoogleEventDeleter` directly under the same block failed, which
confirms the block was active.

## Real-provider verification

Start the server normally (no overrides) and repeat the
[DELETE Level 2 walkthrough](DELETE_LEVEL2_VERIFICATION.md) at this commit.
Expected results are unchanged: `204`, then `404` on repeat, and `404` for an
unknown ID.

No live run was recorded in this Level 4 table. Later completed real-provider
results are in [DELETE Level 5 verification](DELETE_LEVEL5_VERIFICATION.md);
they do not establish a live run at the earlier `8057588` revision.
