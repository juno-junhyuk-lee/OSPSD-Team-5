"""The live probe's cleanup behavior is tested without provider access."""

from email import policy
from email.parser import BytesParser
from unittest.mock import patch

import httpx
import pytest

from app.storage_settings import StorageSettings
from scripts.verify_storage_live import main, verify


@pytest.mark.parametrize(
    "mode",
    [
        "success",
        "existing",
        "conflict",
        "lost_response",
        "timeout_before_write",
        "read_mismatch",
        "cleanup_failure",
    ],
)
def test_probe_records_failures_and_only_cleans_its_own_file(mode: str) -> None:
    exists = mode == "existing"
    content = b""
    calls: list[str] = []

    def info(path: str) -> dict[str, object]:
        return {
            "id": "file-id",
            "name": path.rsplit("/", 1)[1],
            "path": path,
            "size": len(content),
            "modified_at": None,
            "etag": None,
        }

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal exists, content
        calls.append(request.method)
        if request.url.path == "/health/provider":
            return httpx.Response(200, json={"status": "ok"})
        if request.method == "POST":
            if exists or mode == "conflict":
                return httpx.Response(409, json={"error": {"code": "conflict"}})
            message = BytesParser(policy=policy.default).parsebytes(
                b"Content-Type: "
                + request.headers["content-type"].encode()
                + b"\r\n\r\n"
                + request.content
            )
            parts = {
                part.get_param("name", header="content-disposition"): part.get_payload(
                    decode=True
                )
                for part in message.iter_parts()
            }
            path, uploaded = parts["path"], parts["file"]
            assert isinstance(path, bytes) and isinstance(uploaded, bytes)
            content = uploaded
            if mode != "timeout_before_write":
                exists = True
            if mode in {"lost_response", "timeout_before_write"}:
                raise httpx.ReadTimeout("SECRET", request=request)
            return httpx.Response(201, json=info(path.decode()))
        if request.method == "DELETE":
            if mode == "cleanup_failure":
                return httpx.Response(
                    503, json={"error": {"code": "provider_unavailable"}}
                )
            if not exists:
                return httpx.Response(404, json={"error": {"code": "not_found"}})
            exists = False
            return httpx.Response(204)
        if not exists:
            return httpx.Response(404, json={"error": {"code": "not_found"}})
        if request.url.path.endswith("download"):
            return httpx.Response(
                200, content=b"wrong" if mode == "read_mismatch" else content
            )
        return httpx.Response(200, json=info(request.url.params["path"]))

    client = httpx.Client(
        base_url="https://storage.example/", transport=httpx.MockTransport(respond)
    )
    settings = StorageSettings("https://storage.example/", 30)
    with patch("scripts.verify_storage_live.storage_http_client", return_value=client):
        result = verify(settings, "/team5-test")
    assert client.is_closed
    assert "SECRET" not in str(result)
    assert result["direct_provider_verification"] == "pending"
    assert result["deployed_composed_workflow"] == "not exercised"
    if mode == "success":
        assert result["result"] == "passed"
        assert result["create_and_download_compare"] == "passed"
        assert result["create_conflict"] == "passed"
        assert result["conflict_preserved_bytes"] == "passed"
        assert result["cleanup"] == "confirmed absent" and not exists
    elif mode in {"existing", "conflict"}:
        assert result["result"] == "failed"
        assert "DELETE" not in calls
        if mode == "existing":
            assert "POST" not in calls and exists
    elif mode == "cleanup_failure":
        assert result["result"] == "failed" and result["cleanup"] == "failed"
        assert exists
    else:
        assert result["result"] == "failed"
        assert result["cleanup"] == "confirmed absent"
        assert not exists and calls.count("POST") == 1


def test_cli_requires_explicit_execute_flag() -> None:
    with patch("sys.argv", ["verify_storage_live", "--output", "unused.json"]):
        with patch("scripts.verify_storage_live.verify") as run:
            with pytest.raises(SystemExit) as caught:
                main()
    assert caught.value.code == 2
    run.assert_not_called()
