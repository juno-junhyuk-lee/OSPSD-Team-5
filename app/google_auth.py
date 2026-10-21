"""Load authorized credentials without starting browser login during requests."""

from pathlib import Path
from typing import Any

from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build  # type: ignore[import-untyped]

from app.event_provider import CalendarAuthenticationError

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
ROOT = Path(__file__).resolve().parents[1]


def load_credentials(token_path: Path = ROOT / "token.json") -> Any:
    provider_involved = False
    try:
        credentials = Credentials.from_authorized_user_file(str(token_path))
        if not credentials.has_scopes(SCOPES):
            raise CalendarAuthenticationError
        if not credentials.valid:
            if not credentials.expired or not credentials.refresh_token:
                raise CalendarAuthenticationError
            provider_involved = True
            credentials.refresh(Request())
            token_path.write_text(credentials.to_json(), encoding="utf-8")
        return credentials
    except (OSError, ValueError, GoogleAuthError) as error:
        raise CalendarAuthenticationError(provider=provider_involved) from error


def calendar_client() -> Any:
    return build("calendar", "v3", credentials=load_credentials())
