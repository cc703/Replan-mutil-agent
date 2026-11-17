"""Budgeted deletion filtering of a proven infeasible constraint set."""

from collections.abc import Callable
from dataclasses import dataclass
import time


@dataclass(frozen=True)
class SearchResult:
    groups: set[str]
    minimal: bool
    solves: int


def reduce_core(
    groups: set[str],
    solve: Callable[[set[str], float], str],
    deadline: float,
    *,
    solves: int = 0,
) -> SearchResult:
    """Keep an established infeasible set, deleting only after an infeasibility proof."""
    current = set(groups)
    minimal = True
    for group in sorted(groups):
        remaining = deadline - time.perf_counter()
        if remaining <= 0 or solves >= 200:
            minimal = False
            break
        status = solve(current - {group}, remaining)
        solves += 1
        if status == "INFEASIBLE":
            current.remove(group)
        elif status == "UNKNOWN":
            minimal = False
        elif status not in ("OPTIMAL", "FEASIBLE"):
            raise RuntimeError(f"unexpected solver status {status}")
    return SearchResult(current, minimal, solves)
