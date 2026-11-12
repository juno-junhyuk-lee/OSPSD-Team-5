import json
from collections.abc import Callable, Iterator

import httpx
import pytest
from issue_tracker_contract import (
    STATUS_FOR_CODE,
    ErrorCode,
    Issue,
    IssueProvider,
    IssueUpdate,
    ServiceError,
)

from app.issue_tracker_client import HttpIssueProvider

Handler = Callable[[httpx.Request], httpx.Response]
ProviderFactory = Callable[[Handler], HttpIssueProvider]
ISSUE_ID = "opaque-team4-id"


@pytest.fixture
def make_provider() -> Iterator[ProviderFactory]:
    clients: list[httpx.Client] = []

    def make(handler: Handler) -> HttpIssueProvider:
        client = httpx.Client(
            base_url="https://issues.example/api/",
            transport=httpx.MockTransport(handler),
            follow_redirects=True,
        )
        clients.append(client)
        return HttpIssueProvider(client)

    yield make
    for client in clients:
        client.close()


def test_create_uses_shared_models_and_exact_http_request(
    make_provider: ProviderFactory,
) -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(201, json={"id": ISSUE_ID, "title": "Stored title"})

    provider: IssueProvider = make_provider(respond)
    result = provider.create_issue("Requested title")

    assert isinstance(provider, IssueProvider)
    assert result == Issue(id=ISSUE_ID, title="Stored title")
    assert len(requests) == 1
    assert requests[0].method == "POST"
    assert str(requests[0].url) == "https://issues.example/api/issues"
    assert json.loads(requests[0].content) == {"title": "Requested title"}
    assert "idempotency-key" not in requests[0].headers


@pytest.mark.parametrize("title", ["", "  \n", "x" * 257])
def test_invalid_title_is_rejected_before_http(
    title: str, make_provider: ProviderFactory
) -> None:
    def unexpected(request: httpx.Request) -> httpx.Response:
        pytest.fail("Invalid input reached the remote service")

    with pytest.raises(ServiceError) as caught:
        make_provider(unexpected).create_issue(title)

    assert caught.value.code == ErrorCode.INVALID_INPUT
    assert not caught.value.provider_involved
    assert not caught.value.may_have_applied


@pytest.mark.parametrize("method", ["GET", "PATCH", "DELETE"])
def test_id_operations_preserve_the_id_and_use_shared_update(
    method: str, make_provider: ProviderFactory
) -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if method == "DELETE":
            return httpx.Response(204)
        return httpx.Response(200, json={"id": ISSUE_ID, "title": "Result title"})

    provider = make_provider(respond)
    if method == "GET":
        assert provider.get_issue(ISSUE_ID).id == ISSUE_ID
    elif method == "PATCH":
        result = provider.update_issue(ISSUE_ID, IssueUpdate(title="New title"))
        assert result.title == "Result title"
    else:
        provider.delete_issue(ISSUE_ID)

    assert len(requests) == 1
    assert requests[0].method == method
    assert requests[0].url.path == f"/api/issues/{ISSUE_ID}"
    if method == "PATCH":
        assert json.loads(requests[0].content) == {"title": "New title"}


def test_update_revalidates_constructed_models(make_provider: ProviderFactory) -> None:
    def unexpected(request: httpx.Request) -> httpx.Response:
        pytest.fail("Invalid update reached the remote service")

    with pytest.raises(ServiceError) as caught:
        make_provider(unexpected).update_issue(
            ISSUE_ID, IssueUpdate.model_construct(title=None)
        )

    assert caught.value.code == ErrorCode.INVALID_INPUT
    assert not caught.value.may_have_applied


@pytest.mark.parametrize("issue_id", ["", ".", "..", "id\n", "id\x7f"])
def test_invalid_ids_do_not_make_http_requests(
    issue_id: str, make_provider: ProviderFactory
) -> None:
    def unexpected(request: httpx.Request) -> httpx.Response:
        pytest.fail("Invalid identifier reached the remote service")

    with pytest.raises(ServiceError) as caught:
        make_provider(unexpected).get_issue(issue_id)

    assert caught.value.code == ErrorCode.NOT_FOUND
    assert not caught.value.provider_involved


def test_opaque_id_is_encoded_as_one_path_segment(
    make_provider: ProviderFactory,
) -> None:
    identifier = "opaque/id?part#fragment%"

    def respond(request: httpx.Request) -> httpx.Response:
        assert request.url.raw_path == b"/api/issues/opaque%2Fid%3Fpart%23fragment%25"
        assert not request.url.query
        assert not request.url.fragment
        return httpx.Response(200, json={"id": identifier, "title": "Title"})

    assert make_provider(respond).get_issue(identifier).id == identifier


def test_fresh_read_limitation_is_explicit_without_http(
    make_provider: ProviderFactory,
) -> None:
    def unexpected(request: httpx.Request) -> httpx.Response:
        pytest.fail("A cached HTTP read cannot implement fresh=True")

    with pytest.raises(ServiceError) as caught:
        make_provider(unexpected).get_issue(ISSUE_ID, fresh=True)

    assert caught.value.code == ErrorCode.SERVICE_NOT_CONFIGURED
    assert caught.value.cause == "fresh_read_unsupported"
    assert not caught.value.provider_involved


@pytest.mark.parametrize("code", list(ErrorCode))
@pytest.mark.parametrize("write", [False, True])
def test_remote_errors_preserve_codes_but_sanitize_details(
    code: ErrorCode, write: bool, make_provider: ProviderFactory
) -> None:
    private = "SECRET-TOKEN private title https://private.example"

    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            STATUS_FOR_CODE[code],
            json={
                "error": {
                    "code": code.value,
                    "message": private,
                    "details": [{"field": private, "message": private}],
                }
            },
            headers={"Retry-After": private},
        )

    provider = make_provider(respond)
    with pytest.raises(ServiceError) as caught:
        if write:
            provider.create_issue("Private title")
        else:
            provider.get_issue(ISSUE_ID)

    error = caught.value
    assert error.code == code
    assert error.provider_involved
    assert private not in str(error)
    assert error.cause == "remote_error"
    assert error.headers is None
    assert error.may_have_applied == (
        write
        and code
        in {
            ErrorCode.PROVIDER_ERROR,
            ErrorCode.INTERNAL_ERROR,
            ErrorCode.REQUEST_IN_PROGRESS,
        }
    )
    assert caught.value.__cause__ is None


@pytest.mark.parametrize(
    ("status", "payload"),
    [
        (502, {"error": {"code": "not_found", "message": "private"}}),
        (404, {"error": {"code": "new_code"}}),
        (422, {"detail": "private"}),
        (500, []),
        (429, {"error": {"code": "provider_error"}}),
    ],
)
def test_unrecognized_error_envelopes_leave_write_outcome_unknown(
    status: int, payload: object, make_provider: ProviderFactory
) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=payload)

    with pytest.raises(ServiceError) as caught:
        make_provider(respond).create_issue("Title")

    assert caught.value.code == ErrorCode.PROVIDER_ERROR
    assert caught.value.may_have_applied
    assert caught.value.cause == "invalid_error_response"


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(201, content=b"not json SECRET"),
        httpx.Response(201, json={"id": ISSUE_ID}),
        httpx.Response(201, json={"id": 123, "title": "Title"}),
        httpx.Response(201, json={"id": "", "title": "Title"}),
        httpx.Response(200, json={"id": ISSUE_ID, "title": "Title"}),
    ],
)
def test_unusable_creation_response_is_not_success_or_safe_to_retry(
    response: httpx.Response, make_provider: ProviderFactory
) -> None:
    calls = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return response

    with pytest.raises(ServiceError) as caught:
        make_provider(respond).create_issue("Title")

    assert caught.value.code == ErrorCode.PROVIDER_ERROR
    assert caught.value.may_have_applied
    assert "SECRET" not in str(caught.value)
    assert calls == 1


@pytest.mark.parametrize("method", ["GET", "PATCH"])
def test_wrong_response_id_is_rejected(
    method: str, make_provider: ProviderFactory
) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": "another-issue", "title": "Title"})

    provider = make_provider(respond)
    with pytest.raises(ServiceError) as caught:
        if method == "GET":
            provider.get_issue(ISSUE_ID)
        else:
            provider.update_issue(ISSUE_ID, IssueUpdate(title="Title"))

    assert caught.value.code == ErrorCode.PROVIDER_ERROR
    assert caught.value.may_have_applied == (method == "PATCH")


@pytest.mark.parametrize("write", [False, True])
@pytest.mark.parametrize(
    "error_type", [httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout]
)
def test_transport_failures_are_sanitized_and_never_retried(
    write: bool,
    error_type: type[httpx.RequestError],
    make_provider: ProviderFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    calls = 0

    def fail(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise error_type("SECRET connection details", request=request)

    provider = make_provider(fail)
    with pytest.raises(ServiceError) as caught:
        if write:
            provider.create_issue("Private title")
        else:
            provider.get_issue(ISSUE_ID)

    assert calls == 1
    assert caught.value.code == ErrorCode.PROVIDER_ERROR
    assert caught.value.may_have_applied == write
    assert "SECRET" not in str(caught.value)
    assert "SECRET" not in caplog.text
    assert caught.value.__suppress_context__


def test_redirect_is_not_followed_even_with_redirecting_client(
    make_provider: ProviderFactory,
) -> None:
    calls: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(307, headers={"Location": "https://another.example"})

    with pytest.raises(ServiceError) as caught:
        make_provider(respond).create_issue("Private title")

    assert calls == ["https://issues.example/api/issues"]
    assert caught.value.may_have_applied


def test_delete_rejects_a_body_on_no_content(make_provider: ProviderFactory) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(204, content=b"unexpected")

    with pytest.raises(ServiceError) as caught:
        make_provider(respond).delete_issue(ISSUE_ID)

    assert caught.value.may_have_applied
