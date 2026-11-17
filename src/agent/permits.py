"""Single-use human approvals bound to a session, revision and payload."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import hashlib
import json
import secrets
from threading import RLock
from typing import Any, Literal, TypeVar

Level = Literal["L1", "L2"]
T = TypeVar("T")


def payload_digest(payload: Any) -> str:
    """Return a canonical digest for a JSON-compatible operation payload."""
    data = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Binding:
    """Exact action approved by the trusted human interface."""

    level: Level
    action: str
    session: str
    revision: int
    digest: str


class PermitStore:
    """Serialize authorization and mutations; tokens never come from model output."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._permits: dict[str, Binding] = {}

    def issue(self, binding: Binding) -> str:
        """Issue a token after the trusted interface has obtained approval."""
        with self._lock:
            token = secrets.token_urlsafe(32)
            self._permits[token] = binding
            return token

    def apply(self, token: str, binding: Binding, operation: Callable[[], T]) -> T:
        """Consume an exact token and execute the mutation under the same lock.

        Failed operations still consume the token, requiring a fresh approval.
        The caller must perform revision checks and the mutation in operation.
        """
        with self._lock:
            if self._permits.get(token) != binding:
                raise PermissionError("invalid or expired approval")
            del self._permits[token]
            return operation()
