"""Authorize the team test account and verify a read-only Calendar request."""

import argparse
import sys
from pathlib import Path

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.calendars.readonly",
]
ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--event-id", help="Verify a specific event instead of listing."
    )
    args = parser.parse_args()
    credentials_path = ROOT / "credentials.json"
    token_path = ROOT / "token.json"
    credentials = None
    if token_path.exists():
        credentials = Credentials.from_authorized_user_file(str(token_path))
        if not credentials.has_scopes(SCOPES):
            print("Stored token lacks required scopes; requesting authorization again.")
            credentials = None
    if credentials is None or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(Request())
            except RefreshError:
                print("Stored authorization expired or was revoked; sign in again.")
                credentials = None
        if credentials is None or not credentials.valid:
            if not credentials_path.exists():
                print("Place credentials.json in the repository root.", file=sys.stderr)
                return 1
            flow = InstalledAppFlow.from_client_secrets_file(
                str(credentials_path), SCOPES
            )
            print("Sign in with the shared test account and approve event access.")
            credentials = flow.run_local_server(
                port=0, timeout_seconds=300, authorization_prompt_message=""
            )
        if not credentials.has_scopes(SCOPES):
            print("Required event access was not granted.", file=sys.stderr)
            return 1
        token_path.write_text(credentials.to_json(), encoding="utf-8")
    print("Authentication succeeded; token stored locally.")
    try:
        service = build("calendar", "v3", credentials=credentials)
        if args.event_id:
            event = (
                service.events()
                .get(calendarId="primary", eventId=args.event_id)
                .execute()
            )
            events = [event]
        else:
            result = (
                service.events()
                .list(
                    calendarId="primary",
                    maxResults=10,
                    singleEvents=True,
                    showDeleted=False,
                )
                .execute()
            )
            events = result.get("items", [])
        print("Calendar request succeeded (primary calendar, read-only request).")
        if not events:
            print("No events returned. Create a timed test event and rerun.")
        for event in events:
            print(f"Event: {event.get('summary', '(untitled)')}")
            print(f"Event ID: {event['id']}")
    except HttpError as error:
        print(f"Calendar request failed: HTTP {error.resp.status}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
