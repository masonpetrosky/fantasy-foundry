from __future__ import annotations

import logging
from collections.abc import Mapping
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def _request_id_from_request(request: Request) -> str:
    request_id = str(getattr(request.state, "request_id", "") or "").strip()
    if request_id:
        return request_id
    request_id = str(request.headers.get("x-request-id") or "").strip()
    return request_id or "unknown"


def _route_group(path: str) -> str:
    if not str(path).startswith("/api/"):
        return "non_api"
    parts = str(path).split("/")
    return parts[2] if len(parts) > 2 else "unknown"


def _message_from_detail(detail: object, *, default: str) -> str:
    if isinstance(detail, str) and detail.strip():
        return detail.strip()
    if isinstance(detail, Mapping):
        for key in ("message", "detail", "msg"):
            value = detail.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    if isinstance(detail, list):
        for item in detail:
            if isinstance(item, Mapping):
                msg = item.get("msg")
                if isinstance(msg, str) and msg.strip():
                    return msg.strip()
    return default


def _sanitize_detail(detail: object) -> object:
    if isinstance(detail, BaseException):
        return str(detail)
    if isinstance(detail, Mapping):
        return {str(key): _sanitize_detail(value) for key, value in detail.items()}
    if isinstance(detail, (list, tuple, set)):
        return [_sanitize_detail(item) for item in detail]
    return detail


def _error_code_for_status(status_code: int) -> str:
    if status_code == 400:
        return "bad_request"
    if status_code == 401:
        return "unauthorized"
    if status_code == 403:
        return "forbidden"
    if status_code == 404:
        return "not_found"
    if status_code == 405:
        return "method_not_allowed"
    if status_code == 408:
        return "request_timeout"
    if status_code == 409:
        return "conflict"
    if status_code == 413:
        return "payload_too_large"
    if status_code == 415:
        return "unsupported_media_type"
    if status_code == 422:
        return "validation_error"
    if status_code == 429:
        return "rate_limited"
    if status_code == 503:
        return "service_unavailable"
    if 500 <= status_code <= 599:
        return "internal_error"
    return "http_error"


def _json_error_payload(
    *,
    status_code: int,
    detail: object,
    message_default: str,
    request_id: str,
) -> dict[str, Any]:
    safe_detail = _sanitize_detail(detail)
    message = _message_from_detail(safe_detail, default=message_default)
    return {
        "error_code": _error_code_for_status(status_code),
        "message": message,
        "request_id": request_id,
        # Preserve legacy field for existing clients while standardizing envelope keys.
        "detail": safe_detail,
    }


def register_exception_handlers(app: FastAPI) -> None:
    error_logger = logging.getLogger("fantasy_foundry.errors")

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        status_code = int(exc.status_code or 500)
        status_phrase = HTTPStatus(status_code).phrase if status_code in HTTPStatus._value2member_map_ else "Request failed"
        request_id = _request_id_from_request(request)
        payload = _json_error_payload(
            status_code=status_code,
            detail=exc.detail,
            message_default=status_phrase,
            request_id=request_id,
        )
        headers = dict(exc.headers or {})
        headers.setdefault("X-Request-Id", request_id)
        return JSONResponse(status_code=status_code, content=payload, headers=headers)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        request_id = _request_id_from_request(request)
        payload = _json_error_payload(
            status_code=422,
            detail=exc.errors(),
            message_default="Request validation failed.",
            request_id=request_id,
        )
        return JSONResponse(status_code=422, content=payload, headers={"X-Request-Id": request_id})

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        request_id = _request_id_from_request(request)
        error_logger.exception(
            "api_exception request_id=%s method=%s path=%s route_group=%s exception_class=%s",
            request_id,
            request.method,
            request.url.path,
            _route_group(request.url.path),
            exc.__class__.__name__,
        )
        payload = _json_error_payload(
            status_code=500,
            detail="Internal server error.",
            message_default="Internal server error.",
            request_id=request_id,
        )
        return JSONResponse(status_code=500, content=payload, headers={"X-Request-Id": request_id})
