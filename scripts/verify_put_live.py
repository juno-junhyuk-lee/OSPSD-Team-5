"""Verify PUT against the shared account's real Google Calendar, then clean up.

Creates one temporary event through POST, adds a description directly in Google,
replaces the event through PUT, reads it back through GET and Google, deletes it,
and confirms a repeated GET returns 404. Prints one JSON line per step with
statuses and checks only; event IDs and calendar data are not printed. Exits
non-zero when any check fails, including cleanup, and always attempts cleanup
once the event exists.
Run `scripts/google_calendar_auth.py` first, then from the repository root:
`uv run python -m scripts.verify_put_live`.
"""

import json
import sys
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from googleapiclient.discovery import build  # type: ignore[import-untyped]

from app.google_create_events import load_credentials
from app.main import app

DESCRIPTION = "Non-shared field kept by PUT"


class Verification:
    """Collects the names of failed steps while reporting every step."""

    def __init__(self) -> None:
        self.failed_steps: list[str] = []

    def check(self, step: str, passed: bool, **fields: object) -> None:
        """Print one sanitized evidence line for `step` and record it if not `passed`."""
        print(json.dumps({"step": step, "passed": passed, **fields}))
        if not passed:
            self.failed_steps.append(step)


def same_instant(value: object, expected: str) -> bool:
    """Return whether `value` is a timestamp equal to the `expected` timestamp."""
    if not isinstance(value, str):
        return False
    return datetime.fromisoformat(value) == datetime.fromisoformat(expected)


def clean_up(client: TestClient, event_id: str, verification: Verification) -> None:
    """Delete `event_id`, confirm it is gone, and report any cleanup failure."""
    try:
        deleted = client.delete(f"/events/{event_id}")
        verification.check(
            "delete", deleted.status_code == 204, status=deleted.status_code
        )
        gone = client.get(f"/events/{event_id}")
        verification.check(
            "get_after_delete", gone.status_code == 404, status=gone.status_code
        )
    except Exception as error:
        verification.check("cleanup", False, error=type(error).__name__)


def main() -> int:
    """Run POST, PUT, GET, DELETE, and GET against Google and return the exit status."""
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
    verification = Verification()
    credentials = load_credentials()
    with (
        TestClient(app) as client,
        build("calendar", "v3", credentials=credentials) as google,
    ):
        created = client.post("/events", json=created_body)
        verification.check(
            "post", created.status_code == 201, status=created.status_code
        )
        if created.status_code != 201:
            print("verification failed: post", file=sys.stderr)
            return 1
        event_id = created.json()["id"]
        try:
            google.events().patch(
                calendarId="primary",
                eventId=event_id,
                body={"description": DESCRIPTION},
            ).execute(num_retries=0)
            verification.check("seed_description", True)

            replaced = client.put(f"/events/{event_id}", json=replacement)
            body = replaced.json()
            same_id = body.get("id") == event_id
            title_replaced = body.get("title") == replacement["title"]
            start_replaced = same_instant(
                body.get("start_time"), replacement["start_time"]
            )
            end_replaced = same_instant(body.get("end_time"), replacement["end_time"])
            verification.check(
                "put",
                replaced.status_code == 200
                and same_id
                and title_replaced
                and start_replaced
                and end_replaced,
                status=replaced.status_code,
                same_id=same_id,
                title_replaced=title_replaced,
                start_replaced=start_replaced,
                end_replaced=end_replaced,
            )

            read_back = client.get(f"/events/{event_id}")
            matches_put = read_back.json() == body
            verification.check(
                "get_after_put",
                read_back.status_code == 200 and matches_put,
                status=read_back.status_code,
                matches_put=matches_put,
            )

            stored = (
                google.events()
                .get(calendarId="primary", eventId=event_id)
                .execute(num_retries=0)
            )
            description_kept = stored.get("description") == DESCRIPTION
            verification.check(
                "google_fields_kept",
                description_kept,
                description_kept=description_kept,
            )
        except Exception as error:
            verification.check("verification", False, error=type(error).__name__)
        finally:
            clean_up(client, event_id, verification)

    if verification.failed_steps:
        print(
            f"verification failed: {', '.join(verification.failed_steps)}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
