# PATCH Level 2 verification

Niriti Pahadi owns `PATCH /events/{event_id}`. This walkthrough checks the real
HTTP-to-Google update path separately from the offline suite. It uses the same
setup and local token as [POST Level 2 verification](POST_LEVEL2_VERIFICATION.md).
On Windows, replace `.venv/bin/python` with `./.venv/Scripts/python.exe` and
use `curl.exe`.

## Steps

1. Authorize once with `./.venv/Scripts/python.exe scripts/google_calendar_auth.py`.
2. Start one worker: `./.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8765`.
3. Create a uniquely named event and copy its `id`:

   ```sh
   curl.exe -i http://127.0.0.1:8765/events \
     -H "Content-Type: application/json" \
     -d "{\"title\":\"PATCH Level 2 check UNIQUE_RUN\",\"start_time\":\"2026-10-07T10:00:00-04:00\",\"end_time\":\"2026-10-07T11:00:00-04:00\"}"
   ```

4. Update it:

   ```sh
   curl.exe -i -X PATCH http://127.0.0.1:8765/events/RETURNED_ID \
     -H "Content-Type: application/json" \
     -d "{\"title\":\"PATCH Level 2 check UNIQUE_RUN UPDATED\",\"start_time\":\"2026-10-07T11:00:00-04:00\",\"end_time\":\"2026-10-07T12:00:00-04:00\"}"
   ```

5. Confirm local GET and an independent Google read:

   ```sh
   curl.exe -i http://127.0.0.1:8765/events/RETURNED_ID
   ./.venv/Scripts/python.exe scripts/google_calendar_auth.py --event-id RETURNED_ID
   ```

6. Clean up with DELETE, then confirm unknown IDs:

   ```sh
   curl.exe -i -X DELETE http://127.0.0.1:8765/events/RETURNED_ID
   curl.exe -i -X PATCH http://127.0.0.1:8765/events/not-a-real-id \
     -H "Content-Type: application/json" \
     -d "{\"title\":\"x\",\"start_time\":\"2026-10-07T11:00:00-04:00\",\"end_time\":\"2026-10-07T12:00:00-04:00\"}"
   ```

## Expected results

| Step | Expected |
| --- | --- |
| 3 | `201` with a Google-assigned `id` |
| 4 | `200` with the same `id`, updated title/times |
| 5 | Local GET matches PATCH JSON; auth script finds the updated title |
| 6, DELETE | `204` (or `404` if already cancelled) |
| 6, PATCH after DELETE | `404` `{"detail": "Event not found"}` (including Google `status: cancelled`) |
| 6, unknown PATCH | `404` `{"detail": "Event not found"}` |

Keep `credentials.json` and `token.json` local and ignored by Git. Delete only
your own verification events.

## Evidence

| Date | Verifier | Revision | Result |
| --- | --- | --- | --- |
| 2026-10-07 | Niriti Pahadi | `01abd0d` | Auth OK; POST `201` id `f6rrpvrnujaf5369b2emfj8f8k`; PATCH `200` title/times updated; GET matched PATCH; independent Google read showed updated title; event left `cancelled` after cleanup; GET still `200` for cancelled (known GET behavior) |
| _pending_ | second teammate | | |
