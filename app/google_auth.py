"""Load authorized credentials without starting browser login during requests."""

from pathlib import Path
from typing import Any

from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build  # type: ignore[import-untyped]

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
ROOT = Path(__file__).resolve().parents[1]


class CalendarAuthenticationError(Exception):
    """Local authorization is unavailable; run the authentication script."""


def load_credentials(token_path: Path = ROOT / "token.json") -> Any:
    try:
        credentials = Credentials.from_authorized_user_file(str(token_path))  # type: ignore[no-untyped-call]
        if not credentials.has_scopes(SCOPES):
            raise CalendarAuthenticationError
        if not credentials.valid:
            if not credentials.expired or not credentials.refresh_token:
                raise CalendarAuthenticationError
            credentials.refresh(Request())
            token_path.write_text(credentials.to_json(), encoding="utf-8")
        return credentials
    except (OSError, ValueError, GoogleAuthError) as error:
        raise CalendarAuthenticationError from error


def calendar_client() -> Any:
    return build("calendar", "v3", credentials=load_credentials())
