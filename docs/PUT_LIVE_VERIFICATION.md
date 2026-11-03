# PUT live verification

Ran `uv run python -m scripts.verify_put_live` on 2026-11-02 at commit `b8fba90` (same code as the run) against the shared test account's `primary` Google Calendar. The script creates one temporary event, adds a Google-only `description`, replaces the event through PUT, reads it back, deletes it, and checks that a repeated GET returns 404. Event IDs and calendar data are not recorded.

```json
{"step": "post", "status": 201}
{"step": "seed_description", "done": true}
{"step": "put", "status": 200, "same_id": true, "title_replaced": true, "start_replaced": true, "end_replaced": true}
{"step": "get_after_put", "status": 200, "matches_put": true}
{"step": "google_fields_kept", "description_kept": true}
{"step": "delete", "status": 204}
{"step": "get_after_delete", "status": 404}
```

Results: PUT returned 200 with the same ID and the replaced title and times; GET returned the same event; the Google-only description was kept; cleanup deleted the event and the final GET returned 404 (logged once as `get_event` `not_found`). This run uses Team 5's current field names (`start_time`, `end_time`); rerun it after the shared package is adopted.
