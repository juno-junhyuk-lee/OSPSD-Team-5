"""Shared service error format and failure logging for every operation."""

import json
import logging

from calendar_contract import CalendarError
from calendar_contract import ErrorCode as ErrorCode
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.observability import record_failure

logger = logging.getLogger("calendar_service")


class ErrorDetails(BaseModel):
    code: ErrorCode
    message: str
    retryable: bool


class ErrorResponse(BaseModel):
    error: ErrorDetails


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
        status: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.operation = operation
        self.retryable = retryable
        # provider = the provider was called or caused the failure
        self.provider = provider
        self.http_status = STATUS_BY_CODE[code] if status is None else status

    @property
    def status(self) -> int:
        return self.http_status


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


def service_error_handler(request: Request, error: Exception) -> JSONResponse:
    """Render the shared error and pass safe context to the request log."""
    assert isinstance(error, ServiceError)
    if not record_failure(request.scope, error.code, error.provider):
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


def calendar_error_handler(request: Request, error: Exception) -> JSONResponse:
    """Add HTTP/log context to an already sanitized shared operation failure."""
    assert isinstance(error, CalendarError)
    operation = getattr(request.scope.get("route"), "name", "calendar_operation")
    provider = error.code != ErrorCode.INVALID_INPUT
    if error.details is not None and isinstance(error.details.get("provider"), bool):
        provider = bool(error.details["provider"])
    return service_error_handler(
        request,
        ServiceError(
            error.code,
            error.message,
            operation=operation,
            retryable=error.retryable,
            provider=provider,
            status=(
                400
                if error.code == ErrorCode.INVALID_INPUT
                and error.details is not None
                and error.details.get("reason") == "unsupported_event_shape"
                else None
            ),
        ),
    )


async def request_validation_handler(
    request: Request, _error: Exception
) -> JSONResponse:
    """Reject invalid requests without exposing validation inputs or bodies."""
    assert isinstance(_error, RequestValidationError)
    operation = getattr(request.scope.get("route"), "name", "request_validation")
    errors = _error.errors()
    malformed_json = any(error["type"] == "json_invalid" for error in errors)
    if any(error["loc"] == ("body",) for error in errors):
        malformed_json = malformed_json or not (await request.body()).strip()
    return service_error_handler(
        request,
        ServiceError(
            ErrorCode.INVALID_INPUT,
            "Invalid request. Check required fields, types, and values.",
            operation=operation,
            retryable=False,
            provider=False,
            status=400 if malformed_json else 422,
        ),
    )
