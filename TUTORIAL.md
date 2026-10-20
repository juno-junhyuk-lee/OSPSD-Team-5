# Calendar service tutorial

This walkthrough shows the full **Create → Read → Update → Delete** workflow
against a running local server, plus a few failure responses that use the shared
Level 5 error shape. It is the team demo path for reviewers and teammates.

Use a unique title each run so leftover events are easy to find and clean up.

## 0. One-time setup

From the repository root:

```sh
uv sync --frozen
```

Authorize Google Calendar (creates local `token.json`; do not commit it):

```sh
uv run python scripts/google_calendar_auth.py
```

Team members use the shared test account. Reviewers outside the team should
follow [External reviewers](README.md#external-reviewers) in the README.

Start the server in one terminal (leave it running):

```sh
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Interactive API docs: http://127.0.0.1:8000/docs

The `curl` examples below assume another terminal in the same repo. On Windows
PowerShell you can paste the same commands if `curl` is available, or use
Swagger UI and match the bodies.

## 1. Create (POST)

```sh
curl -sS -i -X POST http://127.0.0.1:8000/events \
  -H "Content-Type: application/json" \
  -d "{
    \"title\": \"Team 5 tutorial event\",
    \"start_time\": \"2026-10-22T10:00:00-04:00\",
    \"end_time\": \"2026-10-22T11:00:00-04:00\"
  }"
```

Expected: **201** with Google’s event ID and the four public fields. Example
shape (your `id` will differ):

```http
HTTP/1.1 201 Created
Content-Type: application/json
```

```json
{
  "id": "dnmuq3jlnvb8v1cfh5aej2ou10",
  "title": "Team 5 tutorial event",
  "start_time": "2026-10-22T10:00:00-04:00",
  "end_time": "2026-10-22T11:00:00-04:00"
}
```

Save the `id` for the next steps. In bash:

```sh
EVENT_ID=dnmuq3jlnvb8v1cfh5aej2ou10
```

## 2. Read (GET)

Calendar metadata:

```sh
curl -sS -i http://127.0.0.1:8000/calendars/primary
```

Expected: **200** with `id`, `title`, and `time_zone`.

The event you just created:

```sh
curl -sS -i "http://127.0.0.1:8000/events/$EVENT_ID"
```

Expected: **200** with the same four fields as the POST response.

## 3. Update (PATCH)

```sh
curl -sS -i -X PATCH "http://127.0.0.1:8000/events/$EVENT_ID" \
  -H "Content-Type: application/json" \
  -d "{
    \"title\": \"Team 5 tutorial event (updated)\",
    \"start_time\": \"2026-10-22T10:00:00-04:00\",
    \"end_time\": \"2026-10-22T11:30:00-04:00\"
  }"
```

Expected: **200** with the same `id` and refreshed title/times.

Confirm with GET again; the body should match the PATCH response.

## 4. Delete (DELETE)

```sh
curl -sS -i -X DELETE "http://127.0.0.1:8000/events/$EVENT_ID"
```

Expected: **204** with an empty body.

Repeat DELETE (or GET / PATCH the same ID):

```sh
curl -sS -i -X DELETE "http://127.0.0.1:8000/events/$EVENT_ID"
curl -sS -i "http://127.0.0.1:8000/events/$EVENT_ID"
curl -sS -i -X PATCH "http://127.0.0.1:8000/events/$EVENT_ID" \
  -H "Content-Type: application/json" \
  -d "{
    \"title\": \"should fail\",
    \"start_time\": \"2026-10-22T10:00:00-04:00\",
    \"end_time\": \"2026-10-22T11:00:00-04:00\"
  }"
```

Expected: **404** each time, shared error shape:

```json
{
  "error": {
    "code": "not_found",
    "message": "Event not found.",
    "retryable": false
  }
}
```

## 5. Error handling examples

Failures use one public shape:

```json
{"error": {"code": "...", "message": "...", "retryable": false}}
```

| `code` | Typical status | Meaning |
| --- | --- | --- |
| `invalid_input` | 422 | Bad ID, body, or field values |
| `not_found` | 404 | Missing or already deleted |
| `access_denied` | 403 | Provider refused access |
| `provider_unavailable` | 503 | Auth missing or rejected |
| `provider_error` | 502 | Provider failed or result uncertain |

### Invalid create body (end before start)

```sh
curl -sS -i -X POST http://127.0.0.1:8000/events \
  -H "Content-Type: application/json" \
  -d "{
    \"title\": \"bad times\",
    \"start_time\": \"2026-10-22T11:00:00-04:00\",
    \"end_time\": \"2026-10-22T10:00:00-04:00\"
  }"
```

Expected: **422** / `invalid_input` / `retryable: false`. No new Google event.

### Invalid event ID

```sh
curl -sS -i "http://127.0.0.1:8000/events/bad%20id!"
```

Expected: **422** / `invalid_input` before any Google call.

### Unknown calendar

```sh
curl -sS -i http://127.0.0.1:8000/calendars/secondary
```

Expected: **404** / `not_found`.

Successful requests do not write a failure log. Each failure should produce one
sanitized JSON log line on the `calendar_service` logger (operation, error code,
provider flag, status) with no tokens or request bodies.

## 6. Cleanup and stop

If a create succeeded but you stopped early, delete that event ID with DELETE.
Then stop the server with Ctrl+C.

## Related docs

- Setup, contracts, and auth: [README.md](README.md)
- Shared error format: README “Error format”
- Per-operation Level 5 evidence: `docs/*_LEVEL5_VERIFICATION.md`
