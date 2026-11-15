"""Storage connection settings and an explicitly scoped HTTP client.

STORAGE_BASE_URL is required; STORAGE_TIMEOUT_SECONDS defaults to 30 (0 < n <=
120). STORAGE_BEARER_TOKEN is optional and must be supplied outside the repository.
Configuration is read only when requested, not when this module is imported.
"""

import math
import os
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from ipaddress import ip_address
from urllib.parse import urlsplit

import httpx


class StorageConfigurationError(ValueError):
    """Invalid local settings, before any provider request has been attempted."""


@dataclass(frozen=True)
class StorageSettings:
    base_url: str
    timeout_seconds: float
    bearer_token: str | None = field(default=None, repr=False)

    @classmethod
    def from_environment(cls) -> "StorageSettings":
        try:
            raw_url = os.environ["STORAGE_BASE_URL"]
            parsed = urlsplit(raw_url)
            url = httpx.URL(raw_url)
            timeout = float(os.getenv("STORAGE_TIMEOUT_SECONDS", "30"))
            token = os.getenv("STORAGE_BEARER_TOKEN")
            loopback = url.host == "localhost"
            try:
                loopback = loopback or ip_address(url.host).is_loopback
            except ValueError:
                pass
            if (
                not url.host
                or any(c.isspace() for c in raw_url)
                or parsed.port == 0
                or url.scheme not in {"http", "https"}
                or (url.scheme == "http" and not loopback)
                or url.userinfo
                or url.query
                or url.fragment
                or not math.isfinite(timeout)
                or not 0 < timeout <= 120
                or (
                    token is not None
                    and (not token or any(not 33 <= ord(c) <= 126 for c in token))
                )
            ):
                raise ValueError
        except KeyError, ValueError, httpx.InvalidURL:
            raise StorageConfigurationError(
                "Set STORAGE_BASE_URL and valid storage connection settings."
            ) from None
        return cls(str(url).rstrip("/") + "/", timeout, token)


@contextmanager
def storage_http_client(settings: StorageSettings) -> Iterator[httpx.Client]:
    """Close the client on success or failure; keep tokens off redirected hosts."""
    headers = (
        {"Authorization": f"Bearer {settings.bearer_token}"}
        if settings.bearer_token
        else {}
    )
    with httpx.Client(
        base_url=settings.base_url,
        timeout=settings.timeout_seconds,
        headers=headers,
        follow_redirects=False,
        trust_env=False,
    ) as client:
        yield client
