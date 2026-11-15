"""Consumer-facing Calendar factory checks with controlled Google transport."""

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from unittest.mock import MagicMock, Mock

import pytest
from calendar_contract import (
    CalendarError,
    CalendarService,
    CreateEvent,
    ErrorCode,
    Event,
    ReplaceEvent,
)
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore[import-untyped]
from team5_calendar import (
    authorization,
    authorize,
    create_calendar_service,
    google_auth,
    google_events,
)

from tests.test_shared_conformance import (
    TestGoogleCalendarServiceConformance as _GoogleConformance,
)

PAYLOAD = {
    "title": "Package consumer check",
    "start": "2030-01-07T15:00:00Z",
    "end": "2030-01-07T15:30:00Z",
}


def test_factory_is_lazy_and_does_not_need_a_team5_app(tmp_path: Path) -> None:
    service = create_calendar_service(token_file=tmp_path / "not-yet-authorized.json")
    assert callable(service.create)
    assert callable(service.get)
    assert callable(service.replace)
    assert callable(service.delete)
    assert list(tmp_path.iterdir()) == []


def test_factory_runs_existing_google_crud_and_cleans_up(
    google_service: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(google_events, "calendar_client", lambda: google_service)
    service = create_calendar_service(token_file=tmp_path / "unused-test-token.json")

    created = service.create(CreateEvent(**PAYLOAD))
    assert created.model_dump() == {"id": "google-event-1", **PAYLOAD}
    assert service.get(created.id) == created
    replacement = ReplaceEvent(**{**PAYLOAD, "title": "Updated package event"})
    updated = service.replace(created.id, replacement)
    assert updated.id == created.id
    assert updated.title == replacement.title
    assert service.get(created.id) == updated
    service.delete(created.id)
    with pytest.raises(CalendarError) as caught:
        service.get(created.id)
    assert caught.value.code == ErrorCode.NOT_FOUND
    with pytest.raises(CalendarError) as caught:
        service.delete(created.id)
    assert caught.value.code == ErrorCode.NOT_FOUND
    google_service.events.return_value.insert.return_value.execute.assert_called_once_with(
        num_retries=0
    )


def test_factory_preserves_uncertain_create_without_retry(
    google_service: MagicMock, tmp_path: Path
) -> None:
    execute = google_service.events.return_value.insert.return_value.execute
    execute.side_effect = TimeoutError("private provider detail")
    service = create_calendar_service(token_file=tmp_path / "unused-test-token.json")
    with pytest.raises(CalendarError) as caught:
        service.create(CreateEvent(**PAYLOAD))
    assert caught.value.code == ErrorCode.PROVIDER_ERROR
    assert caught.value.retryable is False
    assert "private provider detail" not in caught.value.message
    execute.assert_called_once_with(num_retries=0)
    google_service.events.return_value.delete.assert_not_called()


def test_missing_external_token_uses_shared_error(tmp_path: Path) -> None:
    service = create_calendar_service(token_file=tmp_path / "missing.json")
    with pytest.raises(CalendarError) as caught:
        service.get("event-1")
    assert caught.value.code == ErrorCode.PROVIDER_UNAVAILABLE
    assert caught.value.retryable is False
    assert str(tmp_path) not in caught.value.message
    assert authorization.active_authorization.get() is None


def test_explicit_token_paths_are_isolated_and_override_host_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    paths = [tmp_path / "account-a.json", tmp_path / "account-b.json"]
    for path in paths:
        path.write_text("{}", encoding="utf-8")
    credentials = [Mock(valid=True), Mock(valid=True)]
    for credential in credentials:
        credential.has_scopes.return_value = True
    load = Mock(side_effect=credentials)
    monkeypatch.setattr(Credentials, "from_authorized_user_file", load)
    monkeypatch.setenv("K_SERVICE", "another-teams-service")
    monkeypatch.setenv("CALENDAR_MODE", "hosted")
    monkeypatch.setenv("CALENDAR_TOKEN_FILE", str(tmp_path / "wrong-account.json"))

    selected: list[object] = []
    sdk = MagicMock()
    sdk.events.return_value.get.return_value.execute.return_value = {
        "id": "event-1",
        "summary": PAYLOAD["title"],
        "start": {"dateTime": PAYLOAD["start"]},
        "end": {"dateTime": PAYLOAD["end"]},
    }

    def build(api: str, version: str, *, credentials: object) -> MagicMock:
        assert (api, version) == ("calendar", "v3")
        selected.append(credentials)
        return sdk

    monkeypatch.setattr(google_auth, "build", build)
    first = create_calendar_service(token_file=paths[0])
    second = create_calendar_service(token_file=paths[1])
    assert first.get("event-1").id == "event-1"
    assert second.get("event-1").id == "event-1"
    assert first.get("event-1").id == "event-1"
    assert selected == [credentials[0], credentials[1], credentials[0]]
    assert [call.args[0] for call in load.call_args_list] == [str(p) for p in paths]


def test_external_refresh_stays_in_memory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "token.json"
    path.write_text("unchanged private fixture", encoding="utf-8")
    credential = Mock(valid=False, expired=True, refresh_token="private-refresh")
    credential.has_scopes.return_value = True

    def refresh(request: object) -> None:
        credential.valid = True

    credential.refresh.side_effect = refresh
    monkeypatch.setattr(
        Credentials,
        "from_authorized_user_file",
        Mock(return_value=credential),
    )
    configured = authorization.TokenAuthorization(path)
    assert configured.load() is credential
    assert configured.load() is credential
    credential.refresh.assert_called_once()
    credential.to_json.assert_not_called()
    assert path.read_text(encoding="utf-8") == "unchanged private fixture"


def test_factory_context_is_isolated_between_concurrent_consumers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    barrier = Barrier(2)
    paths = [tmp_path / "a.json", tmp_path / "b.json"]

    def read(self: object, event_id: str) -> Event:
        barrier.wait(timeout=5)
        configured = authorization.active_authorization.get()
        assert configured is not None
        return Event(id=event_id, **{**PAYLOAD, "title": configured.path.name})

    monkeypatch.setattr(google_events.GoogleEventReader, "get_event", read)
    services = [create_calendar_service(token_file=path) for path in paths]
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda service: service.get("event"), services))
    assert [event.title for event in results] == [path.name for path in paths]
    assert authorization.active_authorization.get() is None


def test_explicit_authorize_command_writes_private_external_token(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    destination = tmp_path / "external-token.json"
    client = tmp_path / "client.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "authorize",
            "--client-secrets",
            str(client),
            "--token-file",
            str(destination),
        ],
    )
    flow = Mock()
    flow.run_local_server.return_value.has_scopes.return_value = True
    flow.run_local_server.return_value.to_json.return_value = '{"token":"synthetic"}'
    create = Mock(return_value=flow)
    monkeypatch.setattr(InstalledAppFlow, "from_client_secrets_file", create)
    assert authorize.main() == 0
    create.assert_called_once_with(str(client), authorization.SCOPES)
    flow.run_local_server.assert_called_once_with(
        port=0, timeout_seconds=300, authorization_prompt_message=""
    )
    assert destination.read_text(encoding="utf-8") == '{"token":"synthetic"}'
    assert destination.stat().st_mode & 0o777 == 0o600


def test_authorize_command_does_not_replace_an_existing_token(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    destination = tmp_path / "external-token.json"
    destination.write_text("existing grant", encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "authorize",
            "--client-secrets",
            str(tmp_path / "client.json"),
            "--token-file",
            str(destination),
        ],
    )
    flow = Mock()
    flow.run_local_server.return_value.has_scopes.return_value = True
    monkeypatch.setattr(
        InstalledAppFlow, "from_client_secrets_file", Mock(return_value=flow)
    )
    assert authorize.main() == 1
    assert destination.read_text(encoding="utf-8") == "existing grant"


def test_authorize_command_sanitizes_setup_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    destination = tmp_path / "external-token.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "authorize",
            "--client-secrets",
            str(tmp_path / "client.json"),
            "--token-file",
            str(destination),
        ],
    )
    monkeypatch.setattr(
        InstalledAppFlow,
        "from_client_secrets_file",
        Mock(side_effect=ValueError("SECRET client details")),
    )
    assert authorize.main() == 1
    assert not destination.exists()
    assert "SECRET" not in capsys.readouterr().out


class TestPackageConformance(_GoogleConformance):
    """Run the unchanged shared suite through the public consumer factory."""

    @pytest.fixture
    def service(
        self,
        google_service: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> CalendarService:
        monkeypatch.setattr(google_events, "calendar_client", lambda: google_service)
        return create_calendar_service(token_file=tmp_path / "controlled-token.json")


@pytest.mark.parametrize("contents", ["[]", "null", "42", '"private-token"', "{bad"])
def test_malformed_token_is_a_sanitized_shared_error(
    tmp_path: Path, contents: str
) -> None:
    token = tmp_path / "token.json"
    token.write_text(contents)
    service = create_calendar_service(token_file=token)
    with pytest.raises(CalendarError) as raised:
        service.get("synthetic-event-id")
    assert raised.value.code == ErrorCode.PROVIDER_UNAVAILABLE
    assert raised.value.retryable is False
    assert "private-token" not in str(raised.value)
    assert "team5_calendar.authorize" in str(raised.value)
