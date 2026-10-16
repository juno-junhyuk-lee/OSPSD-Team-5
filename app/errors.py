"""Shared service error format and failure logging for every operation."""

import json
import logging
from enum import StrEnum

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("calendar_service")


class ErrorCode(StrEnum):
    """Public error codes; each has one HTTP status."""

    INVALID_INPUT = "invalid_input"
    NOT_FOUND = "not_found"
    ACCESS_DENIED = "access_denied"
    PROVIDER_ERROR = "provider_error"
    PROVIDER_UNAVAILABLE = "provider_unavailable"


STATUS_BY_CODE = {
    ErrorCode.INVALID_INPUT: 422,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.ACCESS_DENIED: 403,
    ErrorCode.PROVIDER_ERROR: 502,
    ErrorCode.PROVIDER_UNAVAILABLE: 503,
}


class ServiceError(Exception):
    """A failure returned to callers as {"error": {code, message, retryable}}."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        operation: str,
        retryable: bool,
        provider: bool,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.operation = operation
        self.retryable = retryable
        # provider = the provider was called or caused the failure
        self.provider = provider

    @property
    def status(self) -> int:
        return STATUS_BY_CODE[self.code]


def log_failure(error: ServiceError) -> None:
    """Write one sanitized JSON line; never includes provider details or secrets."""
    level = logging.ERROR if error.status >= 500 else logging.WARNING
    logger.log(
        level,
        json.dumps(
            {
                "operation": error.operation,
                "error": error.code.value,
                "provider": error.provider,
                "status": error.status,
            }
        ),
    )


def service_error_handler(_request: Request, error: Exception) -> JSONResponse:
    """Render a ServiceError in the shared shape and log it."""
    assert isinstance(error, ServiceError)
    log_failure(error)
    return JSONResponse(
        status_code=error.status,
        content={
            "error": {
                "code": error.code.value,
                "message": error.message,
                "retryable": error.retryable,
            }
        },
    )
