"""Per-service OAuth state; token refresh never writes into installed files."""

from contextvars import ContextVar
from functools import partial
from pathlib import Path
from threading import Lock

from google.auth.exceptions import GoogleAuthError, TransportError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from .event_provider import CalendarAuthenticationError

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


class TokenAuthorization:
    def __init__(self, token_file: str | Path) -> None:
        self.path = Path(token_file).expanduser().resolve()
        self._credentials: Credentials | None = None
        self._lock = Lock()

    def load(self) -> Credentials:
        with self._lock:
            if self._credentials is None:
                try:
                    credentials = Credentials.from_authorized_user_file(str(self.path))
                    if not credentials.has_scopes(SCOPES):
                        raise ValueError
                except OSError, ValueError, AttributeError, TypeError, GoogleAuthError:
                    raise CalendarAuthenticationError from None
                self._credentials = credentials
            credentials = self._credentials
            if not credentials.valid:
                if not credentials.expired or not credentials.refresh_token:
                    raise CalendarAuthenticationError
                try:
                    credentials.refresh(partial(Request(), timeout=10))
                except TransportError:
                    raise
                except GoogleAuthError:
                    raise CalendarAuthenticationError(provider=True) from None
                if not credentials.valid or not credentials.has_scopes(SCOPES):
                    raise CalendarAuthenticationError(provider=True)
            return credentials


active_authorization: ContextVar[TokenAuthorization | None] = ContextVar(
    "team5_calendar_authorization", default=None
)
