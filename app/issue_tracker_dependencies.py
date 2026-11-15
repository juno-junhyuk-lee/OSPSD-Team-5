"""Supply Team 4's implementation with our test-account configuration."""

import os
import re
from collections.abc import Generator

from issue_tracker_contract import ErrorCode, IssueProvider, ServiceError
from team_4_issue_tracker_trello import TrelloIssueProvider


def validate_issue_configuration() -> None:
    """Reject missing settings before the composed workflow can write."""
    settings = [os.getenv(name, "") for name in ("TRELLO_API_KEY", "TRELLO_TOKEN")]
    if (
        os.getenv("ISSUE_TRACKER_IMPLEMENTATION", "team4_trello") != "team4_trello"
        or any(not value or any(char.isspace() for char in value) for value in settings)
        or not re.fullmatch(r"[0-9a-f]{24}", os.getenv("TRELLO_LIST_ID", ""))
    ):
        raise ServiceError(
            ErrorCode.SERVICE_NOT_CONFIGURED,
            "Configure ISSUE_TRACKER_IMPLEMENTATION=team4_trello and valid "
            "TRELLO_API_KEY, TRELLO_TOKEN, and TRELLO_LIST_ID settings.",
            cause="invalid_configuration",
            may_have_applied=False,
        )


def get_issue_provider() -> Generator[IssueProvider, None, None]:
    """Keep the shared dependency entry point and close the imported provider."""
    validate_issue_configuration()
    provider = TrelloIssueProvider()
    try:
        yield provider
    finally:
        provider.close()
