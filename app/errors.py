from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class RembgError(Exception):
    def __init__(
        self,
        message: str,
        *,
        type: str = "invalid_request_error",
        code: str | None = None,
        status: int = 400,
        param: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.type = type
        self.code = code
        self.status = status
        self.param = param

    def to_body(self) -> dict[str, Any]:
        err: dict[str, Any] = {
            "message": self.message,
            "type": self.type,
            "code": self.code,
            "param": self.param,
        }
        return {"error": err}


async def rembg_error_handler(_request: Request, exc: RembgError) -> JSONResponse:
    return JSONResponse(status_code=exc.status, content=exc.to_body())


async def validation_error_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = exc.errors()
    first = errors[0] if errors else {}
    loc = first.get("loc") or ()
    param = str(loc[-1]) if loc else None
    message = str(first.get("msg") or "validation error")
    body = {
        "error": {
            "message": message,
            "type": "invalid_request_error",
            "code": "invalid_request",
            "param": param,
        }
    }
    return JSONResponse(status_code=400, content=body)
