# DELETE Level 2 verification

Ka Pui Cheung owns `DELETE /events/{event_id}`. This walkthrough checks the real
HTTP-to-Google path separately from the offline suite. It uses the same setup
and local token as [POST Level 2 verification](POST_LEVEL2_VERIFICATION.md).
On Windows, replace `.venv/bin/python` with `./.venv/Scripts/python.exe` and
use `curl.exe`.

## Steps

1. Authorize once with `.venv/bin/python scripts/google_calendar_auth.py`.
2. Start one worker: `.venv/bin/python -m uvicorn app.main:app --port 8765`.
3. In another terminal, create a uniquely named event and copy its `id`:

   ```sh
   curl -i http://127.0.0.1:8765/events \
     -H 'Content-Type: application/json' \
     -d '{"title":"DELETE Level 2 check UNIQUE_RUN","start_time":"2026-10-06T10:00:00-04:00","end_time":"2026-10-06T11:00:00-04:00"}'
   ```

4. Confirm Google has it: `.venv/bin/python scripts/google_calendar_auth.py --event-id RETURNED_ID`.
5. Delete it, then repeat the same request:

   ```sh
   curl -i -X DELETE http://127.0.0.1:8765/events/RETURNED_ID
   curl -i -X DELETE http://127.0.0.1:8765/events/RETURNED_ID
   curl -i -X DELETE http://127.0.0.1:8765/events/not-a-real-id
   ```

## Expected results

| Step | Expected |
| --- | --- |
| 3 | `201` with a Google-assigned `id` |
| 4 | The script finds the event |
| 5, first DELETE | `204` with an empty body; the event is gone from Google Calendar |
| 5, repeated DELETE | `404` `{"detail": "Event not found"}` (Google answers 410 Gone) |
| 5, unknown ID | `404` `{"detail": "Event not found"}` |
| Step 4 again | The script still finds the event but Google marks it `cancelled`; it no longer appears in calendar listings |

This verification cleans up after itself: the only event it creates is the one
it deletes. To check the `503` path, temporarily rename `token.json` and send a
DELETE; restore the file afterwards.

## Evidence

| Date | Verifier | Revision | Result |
| --- | --- | --- | --- |
| 2026-10-05 | Ka Pui Cheung | `993b27b` + uncommitted DELETE patch | POST `201`; event confirmed in Google; DELETE `204` (empty body); repeat DELETE `404`; unknown ID `404`; GET mirror then `404`; Google `events.get` returns `status: cancelled` and `events.list` no longer shows it |
| 2026-10-05 | Ka Pui Cheung | rebased onto `1670d55` (PR #10) | POST `201`; DELETE `204`; repeat DELETE `404`; unknown ID `404`. `GET /events/{id}` afterwards still returns `200`, because event GET does not treat Google's `cancelled` status as missing (outside this PR) |
| _pending_ | second teammate | | |
