"""Shared storage operations checked against controlled HTTP responses."""

from email import policy
from email.parser import BytesParser

import httpx
import pytest
from cloud_storage_api import (
    ConflictError,
    DocumentStorage,
    InvalidOperationError,
    InvalidRequestError,
    NotFoundError,
    ProviderError,
    ProviderUnavailableError,
)

from app.storage_client import HttpDocumentStorage

PATH = "/team5/summary.md"
CONTENT = "# 일정\nIssue: 123\n".encode()


def metadata(path: str = PATH, **changes: object) -> dict[str, object]:
    return {
        "id": "file-id",
        "name": path.rsplit("/", 1)[1],
        "path": path,
        "size": len(CONTENT),
        "modified_at": "2026-11-15T12:00:00Z",
        "etag": "revision-1",
        **changes,
    }


@pytest.mark.parametrize("method", ["POST", "PUT"])
def test_upload_uses_shared_multipart_and_exact_bytes(method: str) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        assert request.method == method
        assert str(request.url) == "https://storage.example/api/files"
        message = BytesParser(policy=policy.default).parsebytes(
            b"Content-Type: "
            + request.headers["content-type"].encode()
            + b"\r\n\r\n"
            + request.content
        )
        parts = {
            part.get_param("name", header="content-disposition"): part
            for part in message.iter_parts()
        }
        assert set(parts) == {"path", "file"}
        assert parts["path"].get_payload(decode=True) == PATH.encode()
        assert parts["file"].get_filename() == "summary.md"
        assert parts["file"].get_payload(decode=True) == CONTENT
        return httpx.Response(201 if method == "POST" else 200, json=metadata(id=None))

    with httpx.Client(
        base_url="https://storage.example/api/", transport=httpx.MockTransport(respond)
    ) as client:
        adapter = HttpDocumentStorage(client)
        assert isinstance(adapter, DocumentStorage)
        info = (
            adapter.create(PATH, CONTENT)
            if method == "POST"
            else adapter.replace(PATH, CONTENT)
        )
    assert info.id is None and info.size == len(CONTENT) and info.path == PATH


def test_metadata_download_list_move_delete_and_health_routes() -> None:
    calls: list[tuple[str, str]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.url.path.endswith("/health/provider"):
            return httpx.Response(200, json={"status": "ok"})
        if request.method == "DELETE":
            assert request.url.params["path"] == PATH
            return httpx.Response(204)
        if request.method == "PATCH":
            assert request.url.params["path"] == PATH
            assert request.content == b'{"new_path":"/team5/new.md"}'
            return httpx.Response(200, json=metadata("/team5/new.md"))
        if request.url.path.endswith("/files"):
            assert request.url.params["path"] == "/team5"
            return httpx.Response(
                200,
                json=[
                    metadata("/team5/z.md", type="file"),
                    metadata("/team5/a.md", type="file"),
                ],
            )
        assert request.url.params["path"] == PATH
        if request.url.path.endswith("/download"):
            return httpx.Response(200, content=CONTENT)
        return httpx.Response(200, json=metadata())

    with httpx.Client(
        base_url="https://storage.example/", transport=httpx.MockTransport(respond)
    ) as client:
        adapter = HttpDocumentStorage(client)
        assert adapter.get_metadata("team5/summary.md").id == "file-id"
        assert adapter.download(PATH) == CONTENT
        assert [entry.name for entry in adapter.list_files("/team5")] == [
            "a.md",
            "z.md",
        ]
        assert adapter.move(PATH, "/team5/new.md").path == "/team5/new.md"
        adapter.delete(PATH)
        adapter.check_health()
    assert calls == [
        ("GET", "/files/metadata"),
        ("GET", "/files/download"),
        ("GET", "/files"),
        ("PATCH", "/files"),
        ("DELETE", "/files"),
        ("GET", "/health/provider"),
    ]


@pytest.mark.parametrize(
    "method,status,code,error_type",
    [
        ("POST", 409, "conflict", ConflictError),
        ("PUT", 404, "not_found", NotFoundError),
    ],
)
def test_rejected_upload_does_not_fall_back_or_retry(
    method: str, status: int, code: str, error_type: type[Exception]
) -> None:
    calls: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        calls.append(request.method)
        return httpx.Response(status, json={"error": {"code": code}})

    with httpx.Client(
        base_url="https://storage.example/", transport=httpx.MockTransport(respond)
    ) as client:
        adapter = HttpDocumentStorage(client)
        with pytest.raises(error_type):
            if method == "POST":
                adapter.create(PATH, CONTENT)
            else:
                adapter.replace(PATH, CONTENT)
    assert calls == [method]


@pytest.mark.parametrize(
    "changes",
    [
        {"id": 5},
        {"name": "wrong.md"},
        {"path": "/other/summary.md"},
        {"size": -1},
        {"size": True},
        {"modified_at": "bad"},
        {"modified_at": "2026-11-15T12:00:00+00:00"},
        {"type": "invalid"},
    ],
)
def test_metadata_validation_rejects_unusable_results(
    changes: dict[str, object],
) -> None:
    with httpx.Client(
        base_url="https://storage.example/",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={**metadata(), **changes})
        ),
    ) as client:
        with pytest.raises(ProviderError):
            HttpDocumentStorage(client).get_metadata(PATH)


@pytest.mark.parametrize(
    "mode", ["wrong_size", "invalid_json", "missing_fields", "folder", "wrong_status"]
)
def test_unusable_upload_response_is_a_provider_error(mode: str) -> None:
    calls = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if mode == "invalid_json":
            return httpx.Response(201, content=b"SECRET")
        payload = {
            "wrong_size": metadata(size=999),
            "folder": metadata(type="folder"),
            "missing_fields": {},
            "wrong_status": metadata(),
        }[mode]
        return httpx.Response(200 if mode == "wrong_status" else 201, json=payload)

    with httpx.Client(
        base_url="https://storage.example/", transport=httpx.MockTransport(respond)
    ) as client:
        with pytest.raises(ProviderError) as caught:
            HttpDocumentStorage(client).create(PATH, CONTENT)
    assert "SECRET" not in str(caught.value)
    assert calls == 1


@pytest.mark.parametrize(
    "path",
    ["/", "../escape", "/a//b", "//a/b", "/a/../b", "/a/", "bad\x00name", "a\\b"],
)
def test_invalid_paths_never_make_http_calls(path: str) -> None:
    def unexpected(request: httpx.Request) -> httpx.Response:
        raise AssertionError("unexpected HTTP")

    with httpx.Client(
        base_url="https://storage.example/", transport=httpx.MockTransport(unexpected)
    ) as client:
        with pytest.raises(InvalidRequestError):
            HttpDocumentStorage(client).create(path, CONTENT)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        [metadata("/other/file.md", type="file")],
        [metadata(type="file"), metadata(type="file")],
        [metadata()],
        [metadata("/team5/nested/file.md", type="file")],
    ],
)
def test_invalid_listings_are_not_returned_as_success(payload: object) -> None:
    with httpx.Client(
        base_url="https://storage.example/",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=payload)
        ),
    ) as client:
        with pytest.raises(ProviderError):
            HttpDocumentStorage(client).list_files("/team5")


def test_root_listing_is_allowed_but_root_deletion_is_not() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET" and request.url.params["path"] == "/"
        return httpx.Response(200, json=[])

    with httpx.Client(
        base_url="https://storage.example/", transport=httpx.MockTransport(respond)
    ) as client:
        adapter = HttpDocumentStorage(client)
        assert adapter.list_files("") == []
        with pytest.raises(InvalidOperationError):
            adapter.delete("/")


def test_nonempty_deletion_response_and_failed_health_are_errors() -> None:
    with httpx.Client(
        base_url="https://storage.example/",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(204, content=b"SECRET")
        ),
    ) as client:
        adapter = HttpDocumentStorage(client)
        with pytest.raises(ProviderError):
            adapter.delete(PATH)
        with pytest.raises(ProviderUnavailableError):
            adapter.check_health()
