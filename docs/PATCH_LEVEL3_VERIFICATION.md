# PATCH Level 3 verification

Niriti Pahadi owns `PATCH /events/{event_id}`, the `EventUpdater` contract, and
its Google implementation. This record verifies the Level 3 refactor. It does
not verify a release tag or another teammate's checkout.

## Boundary to review

- `app/event_update_provider.py` defines the typed update operation using
  `UpdateEventRequest` and `Event`, plus three service errors.
- `GoogleEventUpdater` in `app/google_update_events.py` keeps Google get/patch,
  cancelled checks, response translation, and known failure translation behind
  that contract.
- The PATCH handler calls an `EventUpdater` and maps service errors to the
  existing 404, 503, and 502 responses. Request validation still happens before
  a write.
- `app/main.py` still selects Google directly for Level 3. External injection
  and controlled updater substitution are Level 4 work.
- The shared `load_credentials` helper remains compatible with POST and DELETE.

## Reproduce the real workflow

Follow the README installation and shared Google authorization instructions.
Use the [PATCH Level 2 walkthrough](PATCH_LEVEL2_VERIFICATION.md) at this
revision:

1. Start one Uvicorn worker without reload.
2. POST one uniquely named timed event; expect 201.
3. PATCH it with a new title and times; expect 200, the same ID, and updated
   fields. GET the ID and confirm with an independent Google read.
4. DELETE the event; PATCH the same ID again and expect 404 (cancelled).
5. Submit invalid equal start/end times; expect 422 with no provider change.
6. Delete only this run's events and stop the server.

Keep credentials and tokens local and ignored.

## Evidence

| Date | Verifier | Revision | Result |
| --- | --- | --- | --- |
| 2026-10-13 | Niriti Pahadi | Level 3 branch | Offline suite including `tests/test_google_update_events.py`; public PATCH contract unchanged; real-provider walkthrough follows Level 2 steps against the refactored boundary |
