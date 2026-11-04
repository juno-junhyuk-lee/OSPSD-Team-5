"""Verify the tagged Calendar workflow against Google, then clean up.

Uses in-process HTTP requests through normal FastAPI dependencies and real Google
adapters. Prints sanitized JSON checks and exits nonzero for any failed check or
cleanup. Run `uv run python scripts/google_calendar_auth.py` first, then
`uv run python -m scripts.verify_put_live`. This command changes the calendar.
"""

import json
import sys
from datetime import UTC, datetime, timedelta
from importlib.metadata import distribution
from typing import Any
from urllib.parse import quote
from uuid import uuid4

from calendar_contract import Event
from fastapi.testclient import TestClient
from googleapiclient.discovery import build  # type: ignore[import-untyped]
from httpx import Response

from app.google_create_events import load_credentials
from app.main import app

DESCRIPTION = "Non-shared field kept by PUT"
PACKAGE_TAG = "v0.1.0-rc.1"
PACKAGE_COMMIT = "1c1cad7a0732ddb242a05400d8833d94e4422424"


class Verification:
    """Collect failed steps while reporting sanitized evidence."""

    def __init__(self) -> None:
        self.failed_steps: list[str] = []

    def check(self, step: str, passed: bool, **fields: object) -> None:
        print(json.dumps({"step": step, "passed": passed, **fields}))
        if not passed:
            self.failed_steps.append(step)

    def finish(self) -> int:
        if self.failed_steps:
            print(
                f"verification failed: {', '.join(self.failed_steps)}", file=sys.stderr
            )
            return 1
        return 0


def same_instant(value: object, expected: str) -> bool:
    """Compare instants without requiring matching timestamp formatting."""
    if not isinstance(value, str):
        return False
    try:
        return datetime.fromisoformat(value) == datetime.fromisoformat(expected)
    except ValueError:
        return False


def check_package(verification: Verification) -> bool:
    """Require the installed dependency to match the agreed tag's commit."""
    package = distribution("calendar-contract")
    source = json.loads(package.read_text("direct_url.json") or "{}")
    commit = source.get("vcs_info", {}).get("commit_id")
    passed = package.version == "0.1.0" and commit == PACKAGE_COMMIT
    verification.check(
        "package", passed, tag=PACKAGE_TAG, version=package.version, commit=commit
    )
    return passed


def event_from_response(response: Response) -> Event | None:
    try:
        return Event.model_validate(response.json())
    except ValueError:
        return None


def check_event(
    verification: Verification,
    step: str,
    response: Response,
    expected_status: int,
    expected: dict[str, str],
    event_id: str | None,
) -> bool:
    event = event_from_response(response)
    checks = {
        "same_id": event is not None
        and bool(event.id)
        and (event_id is None or event.id == event_id),
        "title_matches": event is not None and event.title == expected["title"],
        "start_matches": event is not None
        and same_instant(event.start, expected["start"]),
        "end_matches": event is not None and same_instant(event.end, expected["end"]),
    }
    passed = response.status_code == expected_status and all(checks.values())
    verification.check(step, passed, status=response.status_code, **checks)
    return passed


def clean_up(client: TestClient, event_id: str, verification: Verification) -> None:
    """Attempt every cleanup check even when an earlier request fails."""
    path = f"/events/{quote(event_id, safe='')}"
    for step, method, statuses in (
        ("delete", "DELETE", (204, 404)),
        ("get_after_delete", "GET", (404,)),
        ("repeat_delete", "DELETE", (404,)),
    ):
        try:
            response = client.request(method, path)
            verification.check(
                step, response.status_code in statuses, status=response.status_code
            )
        except Exception as error:
            verification.check(step, False, error=type(error).__name__)


def google_time(value: object) -> object:
    return value.get("dateTime") if isinstance(value, dict) else None


def verify_workflow(
    client: TestClient, google: Any, verification: Verification, run_id: str
) -> None:
    """Use one disposable event; the SDK argument is Google's untyped client."""
    start = datetime.now(UTC).replace(microsecond=0) + timedelta(days=1)
    created_body = {
        "title": f"HW2 contract verification {run_id}",
        "start": start.isoformat(),
        "end": (start + timedelta(minutes=30)).isoformat(),
    }
    replacement = {
        "title": f"HW2 contract verification {run_id} (replaced)",
        "start": (start + timedelta(hours=1)).isoformat(),
        "end": (start + timedelta(hours=2)).isoformat(),
    }
    event_id: str | None = None
    try:
        created = client.post("/events", json=created_body)
        if created.status_code == 201:
            raw: object = created.json()
            if isinstance(raw, dict) and isinstance(raw.get("id"), str) and raw["id"]:
                event_id = raw["id"]
        if not check_event(verification, "post", created, 201, created_body, event_id):
            return
        assert event_id is not None
        path = f"/events/{quote(event_id, safe='')}"
        check_event(
            verification,
            "get_after_post",
            client.get(path),
            200,
            created_body,
            event_id,
        )

        google.events().patch(
            calendarId="primary", eventId=event_id, body={"description": DESCRIPTION}
        ).execute(num_retries=0)
        verification.check("seed_description", True)

        check_event(
            verification,
            "put",
            client.put(path, json=replacement),
            200,
            replacement,
            event_id,
        )
        check_event(
            verification, "get_after_put", client.get(path), 200, replacement, event_id
        )
        stored = (
            google.events()
            .get(calendarId="primary", eventId=event_id)
            .execute(num_retries=0)
        )
        if not isinstance(stored, dict):
            verification.check("google_fields_kept", False)
        else:
            checks = {
                "same_id": stored.get("id") == event_id,
                "title_matches": stored.get("summary") == replacement["title"],
                "start_matches": same_instant(
                    google_time(stored.get("start")), replacement["start"]
                ),
                "end_matches": same_instant(
                    google_time(stored.get("end")), replacement["end"]
                ),
                "description_kept": stored.get("description") == DESCRIPTION,
            }
            verification.check("google_fields_kept", all(checks.values()), **checks)
    except Exception as error:
        verification.check("workflow", False, error=type(error).__name__)
    finally:
        if event_id is not None:
            clean_up(client, event_id, verification)
        else:
            verification.check(
                "cleanup_id_known", False, manual_inspection_required=True
            )


def main() -> int:
    """Verify package provenance and the Google workflow; never authorize interactively."""
    verification = Verification()
    try:
        if not check_package(verification):
            return verification.finish()
        run_id = uuid4().hex[:12]
        verification.check("run", True, run_id=run_id)
        credentials = load_credentials()
        with (
            TestClient(app) as client,
            build("calendar", "v3", credentials=credentials) as google,
        ):
            verify_workflow(client, google, verification, run_id)
    except Exception as error:
        verification.check("setup", False, error=type(error).__name__)
    return verification.finish()


if __name__ == "__main__":
    sys.exit(main())
