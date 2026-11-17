import json
from unittest.mock import MagicMock

import httpx
import pytest
from issue_tracker_contract import ErrorCode, Issue, IssueProvider, ServiceError

from scripts.verify_issue_tracker_live import main, verify

CARD_ID = "a" * 24
LIST_ID = "b" * 24
MARKER = "controlled-marker"


@pytest.mark.parametrize(
    "failure", [None, "read", "uncertain-create", "delete", "wrong-list"]
)
def test_verification_and_cleanup_paths_are_offline(
    failure: str | None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("TRELLO_LIST_ID", LIST_ID)
    issues = MagicMock(spec=IssueProvider)
    issue = Issue(id=CARD_ID, title=f"team5-hw3-{MARKER}")
    issues.create_issue.return_value = issue
    issues.get_issue.return_value = issue
    if failure == "read":
        issues.get_issue.side_effect = ServiceError(ErrorCode.PROVIDER_ERROR, "PRIVATE")
    elif failure == "uncertain-create":
        issues.create_issue.side_effect = ServiceError(
            ErrorCode.PROVIDER_ERROR, "PRIVATE", may_have_applied=True
        )
    elif failure == "delete":
        issues.delete_issue.side_effect = ServiceError(
            ErrorCode.PROVIDER_ERROR, "PRIVATE"
        )
    reads: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        reads.append(request.url.path)
        if request.url.path == f"/1/lists/{LIST_ID}":
            return httpx.Response(
                200,
                json={
                    "id": "wrong" if failure == "wrong-list" else LIST_ID,
                    "closed": False,
                },
            )
        if "fields" in request.url.params:
            return httpx.Response(
                200, json={"id": CARD_ID, "name": issue.title, "idList": LIST_ID}
            )
        return httpx.Response(404)

    with httpx.Client(
        base_url="https://api.trello.com/1/", transport=httpx.MockTransport(respond)
    ) as direct:
        assert verify(issues, direct, MARKER) == (failure is None)
    if failure == "wrong-list":
        issues.create_issue.assert_not_called()
        issues.delete_issue.assert_not_called()
    elif failure == "uncertain-create":
        issues.create_issue.assert_called_once_with(issue.title)
        issues.delete_issue.assert_not_called()
    else:
        issues.create_issue.assert_called_once_with(issue.title)
        issues.get_issue.assert_called_once_with(CARD_ID, fresh=True)
        issues.delete_issue.assert_called_once_with(CARD_ID)
        assert reads[-1] == f"/1/cards/{CARD_ID}"
    output = capsys.readouterr().out
    assert "PRIVATE" not in output
    assert CARD_ID not in output
    assert LIST_ID not in output
    records = [json.loads(line) for line in output.splitlines()]
    if failure in {"uncertain-create", "delete"}:
        assert any(record.get("inspection_required") for record in records)


def test_writes_require_explicit_opt_in() -> None:
    with pytest.raises(SystemExit) as caught:
        main([])
    assert caught.value.code == 2
