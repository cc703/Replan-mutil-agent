"""HTTP errors shared by scheduler endpoints."""

from typing import Any

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any]
    trace_id: str


class ErrorEnvelope(BaseModel):
    error: ErrorDetail


class ServiceError(Exception):
    def __init__(self, code: str, message: str, status: int = 400, **details: Any) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.details = details

    def envelope(self, trace: str) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": str(self),
                "details": self.details,
                "trace_id": trace,
            }
        }
