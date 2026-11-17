"""Validation of P4 search control parameters."""

from math import isfinite

from scheduler_core.models import ReplanParams


def validate_params(params: ReplanParams) -> None:
    """Reject invalid budgets and CP-SAT search controls before doing work."""
    budget = params.total_budget_s
    if (
        isinstance(budget, bool)
        or not isinstance(budget, (int, float))
        or not isfinite(budget)
        or budget <= 0
    ):
        raise ValueError("total_budget_s must be positive and finite")
    for name, value, minimum, maximum in (
        ("num_workers", params.num_workers, 1, 2147483647),
        ("seed", params.seed, 0, 2147483647),
        ("max_level", params.max_level, 0, 3),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
            raise ValueError(f"invalid {name}")
    window = params.window_slots
    if isinstance(window, bool) or not isinstance(window, int) or window < 0:
        raise ValueError("invalid window_slots")
