import io
import json
from email.message import Message
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from issue_tracker_contract import (
    ErrorCode,
    Issue,
    IssueProvider,
    IssueUpdate,
    ServiceError,
)
from team_4_issue_tracker_trello import TrelloIssueProvider

from app.issue_tracker_dependencies import get_issue_provider

CARD_ID = "a" * 24
LIST_ID = "b" * 24
TRANSPORT = "team_4_issue_tracker_trello.provider.urlopen"


@pytest.fixture(autouse=True)
def configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRELLO_API_KEY", "controlled-key")
    monkeypatch.setenv("TRELLO_TOKEN", "controlled-token")
    monkeypatch.setenv("TRELLO_LIST_ID", LIST_ID)
    monkeypatch.delenv("ISSUE_TRACKER_IMPLEMENTATION", raising=False)


@pytest.mark.parametrize("selection", [None, "team4_trello"])
def test_factory_supplies_the_imported_shared_implementation(
    selection: str | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    if selection is not None:
        monkeypatch.setenv("ISSUE_TRACKER_IMPLEMENTATION", selection)
    with patch.object(TrelloIssueProvider, "close") as close:
        dependency = get_issue_provider()
        provider = next(dependency)
        assert isinstance(provider, TrelloIssueProvider)
        assert isinstance(provider, IssueProvider)
        dependency.close()
        close.assert_called_once_with()


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("TRELLO_API_KEY", None),
        ("TRELLO_TOKEN", None),
        ("TRELLO_LIST_ID", None),
        ("TRELLO_API_KEY", ""),
        ("TRELLO_TOKEN", "private\nsecret"),
        ("TRELLO_LIST_ID", "not-a-list-id"),
        ("ISSUE_TRACKER_IMPLEMENTATION", "http-private-secret"),
    ],
)
def test_configuration_fails_before_construction_or_transport(
    name: str, value: str | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    if value is None:
        monkeypatch.delenv(name, raising=False)
    else:
        monkeypatch.setenv(name, value)
    with (
        patch("app.issue_tracker_dependencies.TrelloIssueProvider") as build,
        patch(TRANSPORT) as send,
        pytest.raises(ServiceError) as caught,
    ):
        next(get_issue_provider())
    assert caught.value.code == ErrorCode.SERVICE_NOT_CONFIGURED
    assert not caught.value.provider_involved
    assert not caught.value.may_have_applied
    assert "private" not in str(caught.value)
    build.assert_not_called()
    send.assert_not_called()


def test_factory_closes_provider_on_workflow_failure() -> None:
    with patch.object(TrelloIssueProvider, "close") as close:
        dependency = get_issue_provider()
        next(dependency)
        with pytest.raises(RuntimeError, match="workflow failure"):
            dependency.throw(RuntimeError("workflow failure"))
    close.assert_called_once_with()


def test_imported_provider_crud_fresh_reads_and_listing_without_network() -> None:
    calls: list[Request] = []
    state: dict[str, str] = {}

    def respond(request: Request, *, timeout: float) -> io.BytesIO:
        calls.append(request)
        url = urlsplit(request.full_url)
        params = parse_qs(url.query)
        assert url.hostname == "api.trello.com"
        assert "controlled-token" not in request.full_url
        assert "controlled-key" in str(request.get_header("Authorization"))
        assert timeout > 0
        method = request.get_method()
        if method == "POST":
            assert params["idList"] == [LIST_ID]
            state[CARD_ID] = params["name"][0]
        elif method == "PUT":
            state[CARD_ID] = params["name"][0]
        elif method == "DELETE":
            state.pop(CARD_ID)
            return io.BytesIO(b"")
        elif url.path.endswith("/cards"):
            return io.BytesIO(
                json.dumps(
                    [{"id": key, "name": title} for key, title in state.items()]
                ).encode()
            )
        elif CARD_ID not in state:
            raise HTTPError(request.full_url, 404, "missing", Message(), io.BytesIO())
        return io.BytesIO(json.dumps({"id": CARD_ID, "name": state[CARD_ID]}).encode())

    with patch(TRANSPORT, side_effect=respond):
        dependency = get_issue_provider()
        provider = next(dependency)
        try:
            assert provider.create_issue("team5-controlled") == Issue(
                id=CARD_ID, title="team5-controlled"
            )
            assert provider.get_issue(CARD_ID).title == "team5-controlled"
            state[CARD_ID] = "Externally changed"
            assert provider.get_issue(CARD_ID, fresh=True).title == "Externally changed"
            assert (
                provider.update_issue(CARD_ID, IssueUpdate(title="Updated")).title
                == "Updated"
            )
            assert provider.list_issues(limit=1) == [Issue(id=CARD_ID, title="Updated")]
            provider.delete_issue(CARD_ID)
            with pytest.raises(ServiceError) as caught:
                provider.get_issue(CARD_ID, fresh=True)
            assert caught.value.code == ErrorCode.NOT_FOUND
        finally:
            dependency.close()
    assert not state
    assert [request.get_method() for request in calls] == [
        "POST",
        "GET",
        "GET",
        "PUT",
        "GET",
        "DELETE",
        "GET",
    ]


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (401, ErrorCode.ACCESS_DENIED),
        (403, ErrorCode.ACCESS_DENIED),
        (429, ErrorCode.PROVIDER_ERROR),
        (500, ErrorCode.PROVIDER_ERROR),
    ],
)
def test_imported_provider_preserves_rejections_and_write_certainty(
    status: int, code: ErrorCode
) -> None:
    error = HTTPError(
        "https://private.example",
        status,
        "private-secret",
        Message(),
        io.BytesIO(b"private-secret"),
    )
    with patch(TRANSPORT, side_effect=error) as send:
        dependency = get_issue_provider()
        provider = next(dependency)
        try:
            with pytest.raises(ServiceError) as caught:
                provider.create_issue("Private title")
        finally:
            dependency.close()
    assert caught.value.code == code
    assert caught.value.may_have_applied == (status >= 500)
    assert "private-secret" not in str(caught.value)
    send.assert_called_once()


@pytest.mark.parametrize(
    "error",
    [
        TimeoutError("private-secret"),
        URLError(ConnectionRefusedError("private-secret")),
    ],
)
def test_imported_provider_does_not_retry_uncertain_creation(error: Exception) -> None:
    with patch(TRANSPORT, side_effect=error) as send:
        dependency = get_issue_provider()
        provider = next(dependency)
        try:
            with pytest.raises(ServiceError) as caught:
                provider.create_issue("Private title")
        finally:
            dependency.close()
    assert caught.value.code == ErrorCode.PROVIDER_ERROR
    assert caught.value.may_have_applied == isinstance(error, TimeoutError)
    assert "private-secret" not in str(caught.value)
    send.assert_called_once()


def test_malformed_create_result_is_uncertain() -> None:
    with patch(TRANSPORT, return_value=io.BytesIO(b'{"id":"not-valid"}')) as send:
        dependency = get_issue_provider()
        provider = next(dependency)
        try:
            with pytest.raises(ServiceError) as caught:
                provider.create_issue("Title")
        finally:
            dependency.close()
    assert caught.value.code == ErrorCode.PROVIDER_ERROR
    assert caught.value.may_have_applied
    send.assert_called_once()


def test_fastapi_dependency_can_be_overridden_without_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TRELLO_TOKEN")
    application = FastAPI()

    @application.post("/controlled-issue")
    def create(provider: IssueProvider = Depends(get_issue_provider)) -> Issue:
        return provider.create_issue("Controlled")

    def controlled() -> IssueProvider:
        return TrelloIssueProvider()

    previous = application.dependency_overrides.copy()
    application.dependency_overrides[get_issue_provider] = controlled
    try:
        with patch.object(
            TrelloIssueProvider,
            "create_issue",
            return_value=Issue(id=CARD_ID, title="Controlled"),
        ):
            with TestClient(application) as client:
                response = client.post("/controlled-issue")
        assert response.status_code == 200
        assert response.json() == {"id": CARD_ID, "title": "Controlled"}
    finally:
        application.dependency_overrides.clear()
        application.dependency_overrides.update(previous)
