"""Storage boundary for workflow Markdown summaries.

Member 4 supplies the real storage adapter. Until then the workflow depends only
on this protocol, so tests and the endpoint use controlled implementations.
"""

from typing import Protocol

from pydantic import BaseModel


class StoredSummary(BaseModel):
    """Where a saved summary can be found; the ID is opaque to the workflow."""

    id: str


class SummaryStorageError(Exception):
    """A sanitized storage failure; adapters must not include provider details.

    may_have_applied = the summary might have been saved despite the failure.
    """

    def __init__(
        self,
        message: str,
        *,
        may_have_applied: bool,
        retryable: bool = False,
        configured: bool = True,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.may_have_applied = may_have_applied
        self.retryable = retryable
        self.configured = configured


class SummaryStore(Protocol):
    def save_summary(self, name: str, markdown: str) -> StoredSummary:
        """Save one Markdown document; raise SummaryStorageError on failure."""
        ...
