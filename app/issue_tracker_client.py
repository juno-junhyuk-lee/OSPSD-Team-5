"""HTTP access to the shared issue tracker contract."""

from urllib.parse import quote

import httpx
from issue_tracker_contract import (
    STATUS_FOR_CODE,
    ErrorCode,
    Issue,
    IssueCreate,
    IssueUpdate,
    ServiceError,
)
from pydantic import ValidationError

_MESSAGES = {
    ErrorCode.INVALID_INPUT: "The issue tracker rejected the request.",
    ErrorCode.NOT_FOUND: "Issue not found.",
    ErrorCode.ACCESS_DENIED: "The issue tracker denied access.",
    ErrorCode.SERVICE_NOT_CONFIGURED: "Issue tracker configuration is unavailable.",
    ErrorCode.PRECONDITION_FAILED: "The issue changed before the update.",
    ErrorCode.PROVIDER_ERROR: "The issue tracker request could not be confirmed.",
    ErrorCode.INTERNAL_ERROR: "The issue tracker request could not be confirmed.",
    ErrorCode.IDEMPOTENCY_KEY_REUSED: "The issue tracker rejected the creation key.",
    ErrorCode.REQUEST_IN_PROGRESS: "The issue tracker request is still in progress.",
}


class HttpIssueProvider:
    """Use a caller-owned HTTP client; never retry writes or follow redirects."""

    def __init__(self, client: httpx.Client) -> None:
        self._client = client

    def create_issue(self, title: str) -> Issue:
        try:
            body = IssueCreate(title=title)
        except ValidationError:
            raise self._invalid_input() from None
        return self._issue("POST", "issues", expected=201, body=body.model_dump())

    def get_issue(self, issue_id: str, *, fresh: bool = False) -> Issue:
        if fresh:
            raise ServiceError(
                ErrorCode.SERVICE_NOT_CONFIGURED,
                "The configured HTTP issue API does not support cache-bypass reads.",
                cause="fresh_read_unsupported",
                may_have_applied=False,
            )
        return self._issue(
            "GET", self._issue_path(issue_id), expected=200, expected_id=issue_id
        )

    def update_issue(self, issue_id: str, changes: IssueUpdate) -> Issue:
        try:
            body = IssueUpdate.model_validate(changes.model_dump(exclude_unset=True))
        except ValidationError:
            raise self._invalid_input() from None
        return self._issue(
            "PATCH",
            self._issue_path(issue_id),
            expected=200,
            body=body.model_dump(),
            expected_id=issue_id,
        )

    def delete_issue(self, issue_id: str) -> None:
        response = self._request("DELETE", self._issue_path(issue_id), expected=204)
        if response.content:
            raise self._unconfirmed(write=True, cause="invalid_response")

    @staticmethod
    def _invalid_input() -> ServiceError:
        return ServiceError(
            ErrorCode.INVALID_INPUT,
            "Invalid issue request. Check the title.",
            cause="invalid_request",
            may_have_applied=False,
        )

    @staticmethod
    def _issue_path(issue_id: str) -> str:
        if (
            not issue_id
            or issue_id in {".", ".."}
            or any(
                ord(character) < 32 or ord(character) == 127 for character in issue_id
            )
        ):
            raise ServiceError(
                ErrorCode.NOT_FOUND,
                "Issue not found.",
                cause="invalid_identifier",
                may_have_applied=False,
            )
        return "issues/" + quote(issue_id, safe="")

    def _issue(
        self,
        method: str,
        path: str,
        *,
        expected: int,
        body: dict[str, object] | None = None,
        expected_id: str | None = None,
    ) -> Issue:
        response = self._request(method, path, expected=expected, body=body)
        try:
            issue = Issue.model_validate(response.json(), strict=True)
            if not issue.id or (expected_id is not None and issue.id != expected_id):
                raise ValueError
        except ValueError, ValidationError:
            raise self._unconfirmed(
                write=method != "GET", cause="invalid_response"
            ) from None
        return issue

    def _request(
        self,
        method: str,
        path: str,
        *,
        expected: int,
        body: dict[str, object] | None = None,
    ) -> httpx.Response:
        write = method != "GET"
        try:
            response = self._client.request(
                method, path, json=body, follow_redirects=False
            )
        except httpx.RequestError:
            raise self._unconfirmed(write=write, cause="transport_failure") from None
        if response.status_code != expected:
            raise self._remote_error(response, write=write)
        return response

    @staticmethod
    def _unconfirmed(*, write: bool, cause: str) -> ServiceError:
        return ServiceError(
            ErrorCode.PROVIDER_ERROR,
            _MESSAGES[ErrorCode.PROVIDER_ERROR],
            provider_involved=True,
            cause=cause,
            may_have_applied=write,
        )

    @classmethod
    def _remote_error(cls, response: httpx.Response, *, write: bool) -> ServiceError:
        try:
            payload = response.json()
            code = ErrorCode(payload["error"]["code"])
            if STATUS_FOR_CODE[code] != response.status_code:
                raise ValueError
        except ValueError, KeyError, TypeError:
            return cls._unconfirmed(write=write, cause="invalid_error_response")
        # HTTP errors do not carry the provider's write-certainty flag.
        uncertain = write and (
            response.status_code >= 500
            and code != ErrorCode.SERVICE_NOT_CONFIGURED
            or code == ErrorCode.REQUEST_IN_PROGRESS
        )
        return ServiceError(
            code,
            _MESSAGES[code],
            provider_involved=True,
            cause="remote_error",
            may_have_applied=uncertain,
        )
