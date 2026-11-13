"""Select the providers the scheduled-issue workflow composes.

Each dependency fails with a public ServiceError before any write when its
integration is not configured, so the workflow never starts half-wired.
"""

from collections.abc import Generator
from typing import Annotated

from calendar_contract import CalendarService
from fastapi import Depends
from issue_tracker_contract import IssueProvider
from issue_tracker_contract import ServiceError as IssueServiceError

from app.calendar_service_dependencies import get_calendar_service
from app.errors import ErrorCode, ServiceError
from app.issue_tracker_dependencies import get_issue_provider
from app.summary_storage import SummaryStore
from app.workflow import OPERATION, ScheduledIssueWorkflow


def _not_configured(integration: str) -> ServiceError:
    return ServiceError(
        ErrorCode.PROVIDER_UNAVAILABLE,
        f"The {integration} is not configured or unavailable.",
        operation=OPERATION,
        retryable=False,
        provider=False,
    )


def get_workflow_issue_provider() -> Generator[IssueProvider, None, None]:
    """Reuse Member 3's factory; translate its configuration error."""
    dependency = get_issue_provider()
    try:
        provider = next(dependency)
    except IssueServiceError:
        raise _not_configured("issue tracker") from None
    try:
        yield provider
    finally:
        dependency.close()


def get_summary_store() -> SummaryStore:
    """Member 4 replaces this with the storage adapter."""
    raise _not_configured("summary storage")


def get_scheduled_issue_workflow(
    issues: Annotated[IssueProvider, Depends(get_workflow_issue_provider)],
    calendar: Annotated[CalendarService, Depends(get_calendar_service)],
    summaries: Annotated[SummaryStore, Depends(get_summary_store)],
) -> ScheduledIssueWorkflow:
    return ScheduledIssueWorkflow(issues=issues, calendar=calendar, summaries=summaries)
