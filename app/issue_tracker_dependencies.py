"""Configure issue access only when a workflow requests it."""

import math
import os
from collections.abc import Generator
from dataclasses import dataclass
from ipaddress import ip_address
from urllib.parse import urlsplit

import httpx
from issue_tracker_contract import ErrorCode, IssueProvider, ServiceError

from app.issue_tracker_client import HttpIssueProvider


@dataclass(frozen=True)
class IssueTrackerSettings:
    base_url: str
    timeout_seconds: float

    @classmethod
    def from_environment(cls) -> "IssueTrackerSettings":
        try:
            raw_url = os.environ["ISSUE_TRACKER_BASE_URL"]
            parsed = urlsplit(raw_url)
            url = httpx.URL(raw_url)
            timeout = float(os.getenv("ISSUE_TRACKER_TIMEOUT_SECONDS", "30"))
            loopback = url.host == "localhost"
            try:
                loopback = loopback or ip_address(url.host).is_loopback
            except ValueError:
                pass
            if (
                not url.host
                or any(character.isspace() for character in raw_url)
                or parsed.port == 0
                or url.scheme not in {"http", "https"}
                or (url.scheme == "http" and not loopback)
                or url.userinfo
                or url.query
                or url.fragment
                or not math.isfinite(timeout)
                or not 0 < timeout <= 120
            ):
                raise ValueError
        except KeyError, ValueError, httpx.InvalidURL:
            raise ServiceError(
                ErrorCode.SERVICE_NOT_CONFIGURED,
                "Set ISSUE_TRACKER_BASE_URL and a valid "
                "ISSUE_TRACKER_TIMEOUT_SECONDS (greater than 0, at most 120).",
                cause="invalid_configuration",
                may_have_applied=False,
            ) from None
        return cls(str(url).rstrip("/") + "/", timeout)


def get_issue_provider() -> Generator[IssueProvider, None, None]:
    """Supply the shared interface and close its client after the request."""
    settings = IssueTrackerSettings.from_environment()
    with httpx.Client(
        base_url=settings.base_url,
        timeout=settings.timeout_seconds,
        follow_redirects=False,
        trust_env=False,
    ) as client:
        yield HttpIssueProvider(client)
