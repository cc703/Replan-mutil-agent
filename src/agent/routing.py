"""Read-only routing suggestions for natural language requests."""

import re
from collections.abc import Callable
from .state import GraphState


def route(state: GraphState, router: Callable[[str], dict[str, str]] | None) -> GraphState:
    text = state.get("text", "").strip()
    if re.search(r"回滚|rollback", text, re.IGNORECASE):
        match = re.search(r"(?:回滚|rollback)\s+([^\s]+)", text, re.IGNORECASE)
        return {"action": "rollback", "target": match.group(1) if match else ""}
    if re.search(r"查询|查看|当前计划|\bstatus\b", text, re.IGNORECASE):
        return {"action": "query"}
    if router:
        try:
            result = router(text)
            if result.get("action") in {"change", "query", "rollback"}:
                return {"action": result["action"], "target": result.get("target", "")}
        except (ValueError, TypeError, RuntimeError):
            pass
    return {"action": "change"}
