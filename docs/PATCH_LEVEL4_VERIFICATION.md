# PATCH Level 4 verification

Niriti Pahadi owns `PATCH /events/{event_id}` and FastAPI injection of
`EventUpdater`. This record verifies the Level 4 wiring. It does not verify a
release tag or another teammate's checkout.

## Boundary to review

- `get_event_updater` in `app/event_update_dependencies.py` selects
  `GoogleEventUpdater` for normal requests.
- The PATCH handler receives an `EventUpdater` through `Depends` and does not
  construct Google clients itself.
- `tests/test_update_event_contract.py` substitutes a controlled updater through
  dependency overrides and checks HTTP mapping without Google credentials.
- Existing Google-backed offline tests in `tests/test_update_events.py` still
  exercise the real adapter through the injected Google updater.

## Reproduce the real workflow

Follow the README installation and shared Google authorization instructions.
Use the [PATCH Level 2 walkthrough](PATCH_LEVEL2_VERIFICATION.md):

1. Start one Uvicorn worker without reload (normal injection selects Google).
2. POST → PATCH → GET; expect the same public contract as Level 2/3.
3. DELETE then PATCH the same ID; expect 404.
4. Delete only this run's events and stop the server.

Offline: `uv run pytest tests/test_update_event_contract.py tests/test_update_events.py -q`

## Evidence

| Date | Verifier | Revision | Result |
| --- | --- | --- | --- |
| 2026-10-13 | Niriti Pahadi | Level 4 branch | Controlled updater contract tests; Google-backed offline PATCH suite; public contract unchanged |
| _pending_ | teammate review | | |
