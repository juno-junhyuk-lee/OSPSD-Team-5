from pathlib import Path
from typing import cast

from google.auth.exceptions import GoogleAuthError
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build  # type: ignore[import-untyped]
from googleapiclient.errors import HttpError  # type: ignore[import-untyped]

from app.models import Calendar

TOKEN_PATH = Path(__file__).resolve().parents[1] / "token.json"


class GoogleCalendarReader:
    # Google fields and authorization stay behind the calendar interface.
    def get_primary_calendar(self) -> Calendar:
        """Read Google metadata and translate it into the public calendar model."""
        credentials = Credentials.from_authorized_user_file(str(TOKEN_PATH))
        try:
            with build("calendar", "v3", credentials=credentials) as service:
                data = cast(
                    dict[str, object],
                    service.calendars().get(calendarId="primary").execute(),
                )
        except (HttpError, GoogleAuthError) as error:
            raise RuntimeError("Google Calendar request failed") from error

        title = data.get("summary")
        time_zone = data.get("timeZone")
        if not isinstance(title, str) or not isinstance(time_zone, str):
            raise RuntimeError("Google Calendar metadata is incomplete")
        return Calendar(id="primary", title=title, time_zone=time_zone)
