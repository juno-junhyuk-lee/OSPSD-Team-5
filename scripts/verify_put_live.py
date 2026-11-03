"""Verify PUT against the shared account's real Google Calendar, then clean up.

Creates one temporary event through POST, adds a description directly in Google,
replaces the event through PUT, reads it back through GET and Google, deletes it,
and confirms a repeated GET returns 404. Prints one JSON line per step with
statuses and checks only; event IDs and calendar data are not printed.
Run `scripts/google_calendar_auth.py` first, then from the repository root:
`uv run python -m scripts.verify_put_live`.
"""

import json
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from googleapiclient.discovery import build  # type: ignore[import-untyped]

from app.google_create_events import load_credentials
from app.main import app

DESCRIPTION = "Non-shared field kept by PUT"


def report(step: str, **fields: object) -> None:
    """Print one sanitized evidence line for `step`."""
    print(json.dumps({"step": step, **fields}))


def main() -> None:
    """Run POST, PUT, GET, DELETE, and GET against Google and report each step."""
    start = datetime.now(UTC).replace(microsecond=0) + timedelta(days=1)
    created_body = {
        "title": "HW2 PUT verification (temporary)",
        "start_time": start.isoformat(),
        "end_time": (start + timedelta(minutes=30)).isoformat(),
    }
    replacement = {
        "title": "HW2 PUT verification (replaced)",
        "start_time": (start + timedelta(hours=1)).isoformat(),
        "end_time": (start + timedelta(hours=2)).isoformat(),
    }
    credentials = load_credentials()
    with (
        TestClient(app) as client,
        build("calendar", "v3", credentials=credentials) as google,
    ):
        created = client.post("/events", json=created_body)
        report("post", status=created.status_code)
        created.raise_for_status()
        event_id = created.json()["id"]
        try:
            google.events().patch(
                calendarId="primary",
                eventId=event_id,
                body={"description": DESCRIPTION},
            ).execute(num_retries=0)
            report("seed_description", done=True)

            replaced = client.put(f"/events/{event_id}", json=replacement)
            body = replaced.json()
            report(
                "put",
                status=replaced.status_code,
                same_id=body.get("id") == event_id,
                title_replaced=body.get("title") == replacement["title"],
                start_replaced=body.get("start_time") is not None
                and datetime.fromisoformat(body["start_time"])
                == datetime.fromisoformat(replacement["start_time"]),
                end_replaced=body.get("end_time") is not None
                and datetime.fromisoformat(body["end_time"])
                == datetime.fromisoformat(replacement["end_time"]),
            )

            read_back = client.get(f"/events/{event_id}")
            report(
                "get_after_put",
                status=read_back.status_code,
                matches_put=read_back.json() == body,
            )

            stored = (
                google.events()
                .get(calendarId="primary", eventId=event_id)
                .execute(num_retries=0)
            )
            report(
                "google_fields_kept",
                description_kept=stored.get("description") == DESCRIPTION,
            )
        finally:
            deleted = client.delete(f"/events/{event_id}")
            report("delete", status=deleted.status_code)
            gone = client.get(f"/events/{event_id}")
            report("get_after_delete", status=gone.status_code)


if __name__ == "__main__":
    main()
