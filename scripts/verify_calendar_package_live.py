"""Verify the installed public Calendar factory with disposable real Google data."""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from calendar_contract import (
    CalendarError,
    CalendarService,
    CreateEvent,
    ErrorCode,
    ReplaceEvent,
)
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build  # type: ignore[import-untyped]
from team5_calendar import create_calendar_service


def record(step: str, passed: bool, **fields: object) -> bool:
    print(json.dumps({"step": step, "passed": passed, **fields}), flush=True)
    return passed


def matching_events(google: Any, marker: str) -> int:
    count = 0
    page = None
    while True:
        result = (
            google.events()
            .list(
                calendarId="primary",
                q=marker,
                showDeleted=False,
                maxResults=2500,
                pageToken=page,
            )
            .execute(num_retries=0)
        )
        count += len(result.get("items", []))
        page = result.get("nextPageToken")
        if not page:
            return count


def verify(service: CalendarService, google: Any, marker: str) -> bool:
    passed = record("google_before", matching_events(google, marker) == 0)
    if not passed:
        return False
    event_id = None
    request = CreateEvent(
        title=marker, start="2030-01-07T15:00:00Z", end="2030-01-07T15:30:00Z"
    )
    try:
        created = service.create(request)
        event_id = created.id
        passed &= record("create", bool(event_id) and created.title == marker)
        read = service.get(event_id)
        passed &= record("read", read == created)
        stored = (
            google.events()
            .get(calendarId="primary", eventId=event_id)
            .execute(num_retries=0)
        )
        passed &= record(
            "independent_google_read",
            stored.get("id") == event_id
            and stored.get("summary") == marker
            and datetime.fromisoformat(stored["start"]["dateTime"])
            == datetime.fromisoformat(request.start)
            and datetime.fromisoformat(stored["end"]["dateTime"])
            == datetime.fromisoformat(request.end),
        )
        replacement = ReplaceEvent(
            title=marker + " updated",
            start="2030-01-07T16:00:00Z",
            end="2030-01-07T16:30:00Z",
        )
        updated = service.replace(event_id, replacement)
        observed = service.get(event_id)
        passed &= record(
            "replace_and_read",
            updated.id == event_id
            and observed == updated
            and updated.title == replacement.title
            and datetime.fromisoformat(updated.start)
            == datetime.fromisoformat(replacement.start)
            and datetime.fromisoformat(updated.end)
            == datetime.fromisoformat(replacement.end),
        )
    except Exception as error:
        passed = record("operation", False, error_type=type(error).__name__)
    finally:
        if event_id is not None:
            try:
                service.delete(event_id)
                passed &= record("delete", True)
            except Exception as error:
                passed = record("delete", False, error_type=type(error).__name__)
            for name, operation in (
                ("read_after_delete", service.get),
                ("repeat_delete", service.delete),
            ):
                try:
                    operation(event_id)
                    passed = record(name, False)
                except CalendarError as error:
                    passed &= record(name, error.code == ErrorCode.NOT_FOUND)
                except Exception as error:
                    passed = record(name, False, error_type=type(error).__name__)
        else:
            passed = record("cleanup_id_known", False, inspect_marker_before_retry=True)
        remaining = matching_events(google, marker)
        passed &= record(
            "independent_google_cleanup", remaining == 0, active_matches=remaining
        )
    return bool(passed)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--token-file", type=Path, required=True)
    parser.add_argument("--allow-writes", action="store_true")
    args = parser.parse_args()
    if not args.allow_writes:
        parser.error(
            "--allow-writes is required to create and delete disposable events"
        )
    marker = "team5-package-" + uuid4().hex[:12]
    print(
        json.dumps(
            {
                "step": "run",
                "marker": marker,
                "started_utc": datetime.now(UTC).isoformat(),
            }
        ),
        flush=True,
    )
    try:
        initial = hashlib.sha256(args.token_file.read_bytes()).digest()
        credentials = Credentials.from_authorized_user_file(str(args.token_file))
        if not credentials.valid:
            credentials.refresh(Request())
        with build("calendar", "v3", credentials=credentials) as google:
            passed = verify(
                create_calendar_service(token_file=args.token_file), google, marker
            )
        passed &= record(
            "external_token_unchanged",
            hashlib.sha256(args.token_file.read_bytes()).digest() == initial,
        )
        return 0 if passed else 1
    except Exception as error:
        record("verification", False, error_type=type(error).__name__)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
