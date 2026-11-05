"""Load authorized credentials without starting browser login during requests."""

import json
import os
from functools import lru_cache, partial
from pathlib import Path
from threading import Lock
from typing import Any

from google.auth.exceptions import GoogleAuthError, TransportError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build  # type: ignore[import-untyped]

from app.event_provider import CalendarAuthenticationError

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
HOSTED_SCOPES = [*SCOPES, "https://www.googleapis.com/auth/calendar.calendars.readonly"]
ROOT = Path(__file__).resolve().parents[1]
_refresh_lock = Lock()


def hosted() -> bool:
    return bool(os.getenv("K_SERVICE")) or os.getenv("CALENDAR_MODE") == "hosted"


@lru_cache(maxsize=1)
def hosted_authorization() -> Credentials:
    try:
        path = Path(os.environ["CALENDAR_TOKEN_FILE"])
        info = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(info, dict):
            raise ValueError
        required = ("client_id", "client_secret", "refresh_token")
        if not all(isinstance(info.get(key), str) and info[key] for key in required):
            raise ValueError
        scopes = info.get("scopes")
        if isinstance(scopes, str):
            scopes = scopes.split()
        if not isinstance(scopes, list) or not all(
            isinstance(scope, str) for scope in scopes
        ):
            raise ValueError
        # Access tokens are refreshed in memory on each new instance.
        credentials: Credentials = Credentials.from_authorized_user_info(
            {key: info[key] for key in required}, scopes=scopes
        )
        if not credentials.has_scopes(HOSTED_SCOPES):
            raise ValueError
        return credentials
    except KeyError, OSError, TypeError, ValueError, GoogleAuthError:
        raise CalendarAuthenticationError from None


def load_hosted_credentials() -> Credentials:
    credentials = hosted_authorization()
    with _refresh_lock:
        if not credentials.valid:
            try:
                credentials.refresh(partial(Request(), timeout=10))
            except TransportError:
                raise
            except GoogleAuthError:
                raise CalendarAuthenticationError(provider=True) from None
            if not credentials.valid or not credentials.has_scopes(HOSTED_SCOPES):
                raise CalendarAuthenticationError(provider=True)
    return credentials


def load_credentials(token_path: Path = ROOT / "token.json") -> Any:
    if hosted():
        return load_hosted_credentials()
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
    except TransportError:
        raise
    except (OSError, ValueError, GoogleAuthError) as error:
        raise CalendarAuthenticationError(provider=provider_involved) from error


def calendar_client() -> Any:
    return build("calendar", "v3", credentials=load_credentials())
