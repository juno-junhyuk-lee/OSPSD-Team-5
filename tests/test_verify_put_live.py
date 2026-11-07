import json
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, Mock

import pytest
from fastapi.testclient import TestClient
from googleapiclient.errors import HttpError  # type: ignore[import-untyped]
from httpx import Client, MockTransport, ReadTimeout, Request, Response

from scripts import verify_put_live as verification


@pytest.fixture
def script_google(
    client: TestClient, google_service: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> MagicMock:
    monkeypatch.setattr(verification, "load_credentials", Mock())
    build = MagicMock()
    build.return_value.__enter__.return_value = google_service
    monkeypatch.setattr(verification, "build", build)
    return google_service


def evidence(capsys: pytest.CaptureFixture[str]) -> dict[str, dict[str, object]]:
    output = capsys.readouterr()
    assert "private" not in output.out + output.err
    assert "google-event-" not in output.out
    return {item["step"]: item for item in map(json.loads, output.out.splitlines())}


def test_live_script_workflow_and_cleanup_with_controlled_google(
    script_google: MagicMock,
    provider_events: dict[str, dict[str, object]],
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert verification.main() == 0

    steps = evidence(capsys)
    assert set(steps) == {
        "package",
        "run",
        "health",
        "ready",
        "post",
        "get_after_post",
        "seed_description",
        "put",
        "get_after_put",
        "google_fields_kept",
        "delete",
        "get_after_delete",
        "repeat_delete",
    }
    assert all(step["passed"] is True for step in steps.values())
    assert provider_events["google-event-1"]["status"] == "cancelled"
    script_google.events.return_value.insert.assert_called_once()


@pytest.mark.parametrize("defect", ["wrong-time", "lost-description", "exception"])
def test_failed_workflow_checks_return_nonzero_and_still_delete(
    script_google: MagicMock,
    provider_events: dict[str, dict[str, object]],
    capsys: pytest.CaptureFixture[str],
    defect: str,
) -> None:
    patch = script_google.events.return_value.patch
    original: Callable[..., dict[str, object]] = patch.return_value.execute.side_effect

    def execute(*, num_retries: int = 0) -> dict[str, object]:
        result = original(num_retries=num_retries)
        if "summary" in patch.call_args.kwargs["body"]:
            if defect == "wrong-time":
                result["start"] = {"dateTime": "2000-01-01T00:00:00Z"}
            elif defect == "lost-description":
                del provider_events["google-event-1"]["description"]
            else:
                raise TypeError("private-provider-data")
        return result

    patch.return_value.execute.side_effect = execute

    assert verification.main() == 1

    steps = evidence(capsys)
    failed = {
        "wrong-time": "put",
        "lost-description": "google_fields_kept",
        "exception": "workflow",
    }
    assert steps[failed[defect]]["passed"] is False
    assert steps["delete"]["passed"] is True
    assert steps["get_after_delete"]["passed"] is True
    assert steps["repeat_delete"]["passed"] is True
    assert provider_events["google-event-1"]["status"] == "cancelled"


@pytest.mark.parametrize("failure", ["response", "exception"])
def test_cleanup_failure_is_reported_and_later_cleanup_requests_still_run(
    script_google: MagicMock,
    provider_events: dict[str, dict[str, object]],
    capsys: pytest.CaptureFixture[str],
    failure: str,
) -> None:
    execute = script_google.events.return_value.delete.return_value.execute
    original: Callable[..., str] = execute.side_effect
    attempts = 0

    def delete(*, num_retries: int = 0) -> str:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            if failure == "response":
                raise HttpError(Mock(status=503), b"private-provider-data")
            raise TypeError("private-provider-data")
        return original(num_retries=num_retries)

    execute.side_effect = delete

    assert verification.main() == 1

    steps = evidence(capsys)
    assert steps["delete"]["passed"] is False
    assert "get_after_delete" in steps and "repeat_delete" in steps
    assert attempts == 2
    assert provider_events["google-event-1"]["status"] == "cancelled"


@pytest.mark.parametrize(
    ("version", "commit"),
    [("0.2.0", verification.PACKAGE_COMMIT), ("0.1.0", "wrong-commit")],
)
def test_wrong_package_fails_before_credentials_or_google_are_used(
    script_google: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    version: str,
    commit: str,
) -> None:
    package = Mock(version=version)
    package.read_text.return_value = json.dumps({"vcs_info": {"commit_id": commit}})
    monkeypatch.setattr(verification, "distribution", Mock(return_value=package))

    assert verification.main() == 1

    assert evidence(capsys)["package"]["passed"] is False
    assert script_google.mock_calls == []
    assert verification.load_credentials.call_count == 0  # type: ignore[attr-defined]
    assert verification.build.call_count == 0  # type: ignore[attr-defined]


def test_known_id_is_cleaned_up_even_when_post_response_is_invalid(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = Mock(spec=TestClient)
    client.post.return_value = Response(
        201, json={"id": "known-event", "title": "private"}
    )
    client.request.side_effect = [Response(204), Response(404), Response(404)]
    google = Mock()
    result = verification.Verification()

    verification.verify_workflow(client, google, result, "controlled-run")

    assert result.finish() == 1
    steps = evidence(capsys)
    assert steps["post"]["passed"] is False
    assert steps["delete"]["passed"] is True
    assert steps["get_after_delete"]["passed"] is True
    assert steps["repeat_delete"]["passed"] is True
    assert google.mock_calls == []


def test_first_delete_must_succeed_even_if_event_is_already_gone(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = Mock(spec=TestClient)
    client.request.side_effect = [Response(404), Response(404), Response(404)]
    result = verification.Verification()

    verification.clean_up(client, "known-event", result)

    assert result.finish() == 1
    steps = evidence(capsys)
    assert steps["delete"]["passed"] is False
    assert steps["get_after_delete"]["passed"] is True
    assert steps["repeat_delete"]["passed"] is True


def test_uncertain_post_without_id_requires_inspection_and_is_not_retried(
    script_google: MagicMock,
    provider_events: dict[str, dict[str, object]],
    capsys: pytest.CaptureFixture[str],
) -> None:
    execute = script_google.events.return_value.insert.return_value.execute
    original: Callable[..., dict[str, object]] = execute.side_effect

    def lose_response(*, num_retries: int = 0) -> None:
        original(num_retries=num_retries)
        raise TimeoutError("private-provider-data")

    execute.side_effect = lose_response

    assert verification.main() == 1

    steps = evidence(capsys)
    assert steps["post"]["passed"] is False
    assert steps["cleanup_id_known"]["passed"] is False
    assert steps["cleanup_id_known"]["manual_inspection_required"] is True
    assert "status" not in provider_events["google-event-1"]
    execute.assert_called_once_with(num_retries=0)
    script_google.events.return_value.delete.assert_not_called()


def test_equivalent_offset_formatting_does_not_fail_verification(
    script_google: MagicMock,
    capsys: pytest.CaptureFixture[str],
) -> None:
    patch = script_google.events.return_value.patch
    original: Callable[..., dict[str, object]] = patch.return_value.execute.side_effect

    def execute(*, num_retries: int = 0) -> dict[str, object]:
        result = original(num_retries=num_retries)
        if "summary" in patch.call_args.kwargs["body"]:
            for field in ("start", "end"):
                value = result[field]
                assert isinstance(value, dict)
                value["dateTime"] = value["dateTime"].replace("+00:00", "Z")
        return result

    patch.return_value.execute.side_effect = execute

    assert verification.main() == 0
    assert all(step["passed"] is True for step in evidence(capsys).values())


@pytest.fixture
def remote_requests(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> list[Request]:
    bearer = tmp_path / "bearer"
    bearer.write_text("private-smoke-bearer", encoding="utf-8")
    monkeypatch.setenv("CALENDAR_VERIFY_URL", "https://calendar.example.test")
    monkeypatch.setenv("CALENDAR_VERIFY_BEARER_FILE", str(bearer))
    requests: list[Request] = []

    def respond(request: Request) -> Response:
        assert request.url.host == "calendar.example.test"
        assert request.headers["Authorization"] == "Bearer private-smoke-bearer"
        requests.append(request)
        result = client.request(
            request.method,
            request.url.path,
            content=request.content,
            headers={"Content-Type": "application/json"},
        )
        return Response(
            result.status_code, content=result.content, headers=result.headers
        )

    def remote_client(**options: Any) -> Client:
        assert options["trust_env"] is False
        assert options["follow_redirects"] is False
        return Client(transport=MockTransport(respond), **options)

    monkeypatch.setattr(verification, "Client", remote_client)
    monkeypatch.setattr(
        verification, "TestClient", Mock(side_effect=AssertionError("Local fallback"))
    )
    return requests


def test_deployed_smoke_uses_remote_http_and_cleans_up(
    script_google: MagicMock,
    remote_requests: list[Request],
    provider_events: dict[str, dict[str, object]],
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert verification.main() == 0
    assert [(request.method, request.url.path) for request in remote_requests] == [
        ("GET", "/health"),
        ("GET", "/ready"),
        ("POST", "/events"),
        ("GET", "/events/google-event-1"),
        ("PUT", "/events/google-event-1"),
        ("GET", "/events/google-event-1"),
        ("DELETE", "/events/google-event-1"),
        ("GET", "/events/google-event-1"),
        ("DELETE", "/events/google-event-1"),
    ]
    assert provider_events["google-event-1"]["status"] == "cancelled"
    assert all(step["passed"] is True for step in evidence(capsys).values())


def test_deployed_smoke_detects_broken_put_and_still_cleans_up(
    script_google: MagicMock,
    remote_requests: list[Request],
    provider_events: dict[str, dict[str, object]],
    capsys: pytest.CaptureFixture[str],
) -> None:
    patch = script_google.events.return_value.patch
    original: Callable[..., dict[str, object]] = patch.return_value.execute.side_effect

    def broken_put(*, num_retries: int = 0) -> dict[str, object]:
        result = original(num_retries=num_retries)
        if "summary" in patch.call_args.kwargs["body"]:
            result["start"] = {"dateTime": "2000-01-01T00:00:00Z"}
        return result

    patch.return_value.execute.side_effect = broken_put
    assert verification.main() == 1
    steps = evidence(capsys)
    assert steps["put"]["passed"] is False
    assert steps["delete"]["passed"] is True
    assert provider_events["google-event-1"]["status"] == "cancelled"
    assert sum(request.method == "POST" for request in remote_requests) == 1


@pytest.mark.parametrize("failed_path", ["/health", "/ready"])
def test_unready_service_fails_before_creating_events(
    script_google: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    failed_path: str,
) -> None:
    client = MagicMock(spec=Client)
    client.__enter__.return_value = client
    client.get.side_effect = lambda path: Response(
        503 if path == failed_path else {"/health": 200, "/ready": 204}[path]
    )
    monkeypatch.setattr(verification, "verification_client", lambda: client)
    assert verification.main() == 1
    assert evidence(capsys)[failed_path[1:]]["passed"] is False
    client.post.assert_not_called()
    script_google.events.return_value.insert.assert_not_called()


def test_readiness_transport_error_is_sanitized(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = Mock(spec=Client)
    client.get.side_effect = [ReadTimeout("private-response"), Response(204)]
    result = verification.Verification()
    assert verification.check_readiness(client, result) is False
    steps = evidence(capsys)
    assert steps["health"]["passed"] is False
    assert steps["ready"]["passed"] is True


def test_uncertain_http_create_is_not_retried(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = Mock(spec=Client)
    client.post.side_effect = ReadTimeout("private-response")
    result = verification.Verification()
    verification.verify_workflow(client, Mock(), result, "controlled-run")
    assert result.finish() == 1
    steps = evidence(capsys)
    assert steps["cleanup_id_known"]["manual_inspection_required"] is True
    client.post.assert_called_once()
    client.put.assert_not_called()
    client.request.assert_not_called()


@pytest.mark.parametrize(
    "url",
    [
        "http://calendar.example.test",
        "https://calendar.example.test/events",
        "https://user@calendar.example.test",
        "https://calendar.example.test?x=1",
        "https://calendar.example.test#fragment",
        "",
    ],
)
def test_rejects_unsafe_deployed_origins(
    monkeypatch: pytest.MonkeyPatch, url: str
) -> None:
    monkeypatch.setenv("CALENDAR_VERIFY_URL", url)
    with pytest.raises(ValueError, match="HTTPS service origin"):
        verification.verification_client()


def test_bearer_without_url_cannot_fall_back_to_local(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CALENDAR_VERIFY_URL", raising=False)
    monkeypatch.setenv("CALENDAR_VERIFY_BEARER_FILE", "private-file")
    with pytest.raises(ValueError, match="Set CALENDAR_VERIFY_URL"):
        verification.verification_client()
