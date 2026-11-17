"""Read-only routing suggestions for natural language requests."""

import re
from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel, ConfigDict

from .state import GraphState


class RouteSuggestion(BaseModel):
    """Untrusted routing output; a route never grants write permission."""

    model_config = ConfigDict(extra="forbid", strict=True)
    action: Literal["change", "query", "rollback"]
    target: str = ""


def route(state: GraphState, router: Callable[[str], dict[str, str]] | None) -> GraphState:
    text = state.get("text", "").strip()
    if re.search(r"回滚|rollback", text, re.IGNORECASE):
        match = re.search(r"(?:回滚|rollback)\s+([^\s]+)", text, re.IGNORECASE)
        return {"action": "rollback", "target": match.group(1) if match else ""}
    if re.search(r"查询|查看|当前计划|\bstatus\b", text, re.IGNORECASE):
        return {"action": "query"}
    if router:
        try:
            result = RouteSuggestion.model_validate(router(text))
            return {"action": result.action, "target": result.target.strip()}
        except (ValueError, TypeError, RuntimeError):
            pass
    return {"action": "change"}
