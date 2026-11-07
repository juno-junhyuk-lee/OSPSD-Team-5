# PUT live verification

Ran `uv run python -m scripts.verify_put_live` on 2026-11-03 at commit `46a9723` (same code as the run) against the shared test account's `primary` Google Calendar. The script creates one temporary event, adds a Google-only `description`, replaces the event through PUT, reads it back, deletes it, and checks that a repeated GET returns 404. Each step reports `passed`; the script exits 1 and names the failed steps when any check fails, and cleanup still runs and reports its own failures. Event IDs and calendar data are not recorded.

```json
{"step": "post", "passed": true, "status": 201}
{"step": "seed_description", "passed": true}
{"step": "put", "passed": true, "status": 200, "same_id": true, "title_replaced": true, "start_replaced": true, "end_replaced": true}
{"step": "get_after_put", "passed": true, "status": 200, "matches_put": true}
{"step": "google_fields_kept", "passed": true, "description_kept": true}
{"step": "delete", "passed": true, "status": 204}
{"step": "get_after_delete", "passed": true, "status": 404}
```

Results: the script exited 0. PUT returned 200 with the same ID and the replaced title and times; GET returned the same event; the Google-only description was kept; cleanup deleted the event and the final GET returned 404 (logged once as `get_event` `not_found`). A run with the time check forced to fail exited 1 with `verification failed: put` and still deleted the event. This run uses Team 5's current field names (`start_time`, `end_time`); rerun it after the shared package is adopted.
