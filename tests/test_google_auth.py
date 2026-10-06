from pathlib import Path
from unittest.mock import Mock

import pytest
from google.auth.exceptions import RefreshError

from app.google_auth import SCOPES, CalendarAuthenticationError, load_credentials


@pytest.mark.parametrize("contents", [None, "not-json", "{}"])
def test_missing_or_invalid_token_requires_authentication(
    tmp_path: Path, contents: str | None
) -> None:
    token = tmp_path / "token.json"
    if contents is not None:
        token.write_text(contents, encoding="utf-8")

    with pytest.raises(CalendarAuthenticationError):
        load_credentials(token)


@pytest.fixture
def credentials(monkeypatch: pytest.MonkeyPatch) -> Mock:
    stored = Mock(valid=True)
    stored.has_scopes.return_value = True
    monkeypatch.setattr(
        "app.google_auth.Credentials.from_authorized_user_file",
        Mock(return_value=stored),
    )
    return stored


def test_valid_token_is_reused(tmp_path: Path, credentials: Mock) -> None:
    token = tmp_path / "token.json"

    assert load_credentials(token) is credentials
    credentials.has_scopes.assert_called_once_with(SCOPES)
    credentials.refresh.assert_not_called()
    assert not token.exists()


def test_insufficient_scope_requires_authentication(
    tmp_path: Path, credentials: Mock
) -> None:
    credentials.has_scopes.return_value = False

    with pytest.raises(CalendarAuthenticationError):
        load_credentials(tmp_path / "token.json")
    credentials.refresh.assert_not_called()


def test_expired_token_is_refreshed_and_saved(
    tmp_path: Path, credentials: Mock
) -> None:
    credentials.valid = False
    credentials.expired = True
    credentials.refresh_token = "fake-refresh-token"
    credentials.to_json.return_value = '{"fake": "refreshed"}'
    token = tmp_path / "token.json"

    assert load_credentials(token) is credentials
    credentials.refresh.assert_called_once()
    assert token.read_text(encoding="utf-8") == '{"fake": "refreshed"}'


def test_revoked_token_requires_authentication(
    tmp_path: Path, credentials: Mock
) -> None:
    credentials.valid = False
    credentials.expired = True
    credentials.refresh_token = "fake-refresh-token"
    credentials.refresh.side_effect = RefreshError("revoked")  # type: ignore[no-untyped-call]
    token = tmp_path / "token.json"

    with pytest.raises(CalendarAuthenticationError):
        load_credentials(token)
    assert not token.exists()


def test_expired_token_without_refresh_requires_authentication(
    tmp_path: Path, credentials: Mock
) -> None:
    credentials.valid = False
    credentials.expired = True
    credentials.refresh_token = None

    with pytest.raises(CalendarAuthenticationError):
        load_credentials(tmp_path / "token.json")
    credentials.refresh.assert_not_called()
