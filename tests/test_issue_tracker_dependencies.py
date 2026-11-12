from collections.abc import Iterator
from unittest.mock import patch

import httpx
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from issue_tracker_contract import ErrorCode, Issue, IssueProvider, ServiceError

from app.issue_tracker_client import HttpIssueProvider
from app.issue_tracker_dependencies import IssueTrackerSettings, get_issue_provider


@pytest.fixture(autouse=True)
def isolated_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ISSUE_TRACKER_BASE_URL", raising=False)
    monkeypatch.delenv("ISSUE_TRACKER_TIMEOUT_SECONDS", raising=False)


@pytest.mark.parametrize(
    ("base_url", "expected"),
    [
        ("https://issues.example", "https://issues.example/"),
        ("https://issues.example/api/", "https://issues.example/api/"),
        ("http://127.0.0.1:8123", "http://127.0.0.1:8123/"),
        ("http://localhost:8123", "http://localhost:8123/"),
        ("http://[::1]:8123", "http://[::1]:8123/"),
    ],
)
def test_base_url_is_configurable(
    base_url: str, expected: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ISSUE_TRACKER_BASE_URL", base_url)

    settings = IssueTrackerSettings.from_environment()

    assert settings.base_url == expected
    assert settings.timeout_seconds == 30


@pytest.mark.parametrize(
    "value",
    [
        "",
        "not a URL",
        "ftp://issues.example",
        "http://issues.example",
        "https://user:SECRET@issues.example",
        "https://issues.example?token=SECRET",
        "https://issues.example#SECRET",
        "https://[invalid",
        "https://issues.example:0",
        "https://issues.example:99999",
        "https://issues.example/\nSECRET",
    ],
)
def test_invalid_configuration_is_sanitized(
    value: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ISSUE_TRACKER_BASE_URL", value)

    with pytest.raises(ServiceError) as caught:
        IssueTrackerSettings.from_environment()

    assert caught.value.code == ErrorCode.SERVICE_NOT_CONFIGURED
    assert not caught.value.provider_involved
    assert not caught.value.may_have_applied
    assert "SECRET" not in str(caught.value)


@pytest.mark.parametrize("value", ["", "bad", "0", "-1", "nan", "inf", "121"])
def test_timeout_must_be_finite_and_bounded(
    value: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ISSUE_TRACKER_BASE_URL", "https://issues.example")
    monkeypatch.setenv("ISSUE_TRACKER_TIMEOUT_SECONDS", value)

    with pytest.raises(ServiceError) as caught:
        IssueTrackerSettings.from_environment()

    assert caught.value.code == ErrorCode.SERVICE_NOT_CONFIGURED


def test_missing_configuration_is_an_issue_error() -> None:
    dependency = get_issue_provider()
    with pytest.raises(ServiceError) as caught:
        next(dependency)

    assert caught.value.code == ErrorCode.SERVICE_NOT_CONFIGURED


def test_factory_configures_and_closes_the_http_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ISSUE_TRACKER_BASE_URL", "https://another-team.example/api")
    monkeypatch.setenv("ISSUE_TRACKER_TIMEOUT_SECONDS", "12.5")

    def respond(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://another-team.example/api/issues"
        assert request.extensions["timeout"] == {
            "connect": 12.5,
            "read": 12.5,
            "write": 12.5,
            "pool": 12.5,
        }
        return httpx.Response(201, json={"id": "remote-id", "title": "Title"})

    client = httpx.Client(
        base_url="https://another-team.example/api/",
        timeout=12.5,
        transport=httpx.MockTransport(respond),
    )
    with patch(
        "app.issue_tracker_dependencies.httpx.Client", return_value=client
    ) as build:
        dependency = get_issue_provider()
        provider = next(dependency)
        assert isinstance(provider, HttpIssueProvider)
        assert provider.create_issue("Title").id == "remote-id"
        assert not client.is_closed
        dependency.close()

    assert client.is_closed
    build.assert_called_once_with(
        base_url="https://another-team.example/api/",
        timeout=12.5,
        follow_redirects=False,
        trust_env=False,
    )


def test_factory_closes_client_when_workflow_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ISSUE_TRACKER_BASE_URL", "https://issues.example")
    client = httpx.Client()
    with patch("app.issue_tracker_dependencies.httpx.Client", return_value=client):
        dependency = get_issue_provider()
        next(dependency)
        with pytest.raises(RuntimeError, match="workflow failure"):
            dependency.throw(RuntimeError("workflow failure"))

    assert client.is_closed


def test_fastapi_can_override_shared_dependency_without_issue_configuration() -> None:
    application = FastAPI()

    @application.post("/controlled-issue")
    def create(provider: IssueProvider = Depends(get_issue_provider)) -> Issue:
        return provider.create_issue("Controlled title")

    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(201, json={"id": "controlled-id", "title": "Controlled"})

    def controlled() -> Iterator[IssueProvider]:
        with httpx.Client(
            base_url="https://controlled.example",
            transport=httpx.MockTransport(respond),
        ) as client:
            yield HttpIssueProvider(client)

    previous = application.dependency_overrides.copy()
    application.dependency_overrides[get_issue_provider] = controlled
    try:
        with TestClient(application) as client:
            response = client.post("/controlled-issue")
        assert response.status_code == 200
        assert response.json() == {"id": "controlled-id", "title": "Controlled"}
    finally:
        application.dependency_overrides.clear()
        application.dependency_overrides.update(previous)
