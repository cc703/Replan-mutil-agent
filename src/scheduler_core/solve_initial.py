"""Initial scheduling and its independent validation boundary."""

from dataclasses import dataclass
import math

from .models import Instance, Plan, PlanMetrics
from .solving.run import run_model
from .validate import validate


@dataclass(frozen=True)
class SolveInitialResult:
    """Solver status, validated plan, and diagnostics in unscaled units."""

    status: str
    plan: Plan | None
    objective: float | None
    best_bound: float | None
    gap: float | None
    wall_seconds: float
    reasons: tuple[str, ...]


def solve_initial_detailed(
    inst: Instance,
    *,
    time_limit_s: float = 30,
    num_workers: int = 8,
    seed: int = 0,
    objective_weights: dict[str, float] | None = None,
) -> SolveInitialResult:
    """Solve PENDING tasks and validate every returned plan independently.

    Default weights are tardiness=1, makespan=1, imbalance=0.1 and
    preference=0. Missing keys use defaults; explicit zero is preserved.
    Nonzero preference is unsupported. Invalid inputs raise ValueError.
    INFEASIBLE, UNKNOWN and MODEL_INVALID carry no plan.
    """
    if not isinstance(inst, Instance):
        raise TypeError("inst must be an Instance")
    if isinstance(time_limit_s, bool) or not isinstance(time_limit_s, (int, float)):
        raise ValueError("time_limit_s must be a positive finite number")
    if time_limit_s <= 0 or time_limit_s > 1e100 or not math.isfinite(time_limit_s):
        raise ValueError("time_limit_s must be a positive finite number")
    if (
        isinstance(num_workers, bool)
        or not isinstance(num_workers, int)
        or not 1 <= num_workers <= 2147483647
    ):
        raise ValueError("num_workers must be a positive integer")
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= 2147483647:
        raise ValueError("seed must be an integer between 0 and 2147483647")
    if any(task.status != "PENDING" for task in inst.tasks):
        raise ValueError("initial scheduling accepts only PENDING tasks")
    report = validate(inst, Plan(id="initial-precheck", assignments={}))
    ignored = {"reason=MISSING_ASSIGNMENT;"}
    invalid = [v for v in report.violations if v.detail not in ignored]
    if invalid:
        raise ValueError(f"invalid instance: {invalid}")
    # Keep all numeric inputs safely within CP-SAT's signed integer domain.
    limit = (1 << 60) - 1
    values = [inst.axis.horizon_slots, inst.now]
    values.extend(x for t in inst.tasks for x in (t.duration, t.demand, t.release))
    values.extend(t.deadline for t in inst.tasks if t.deadline is not None)
    values.extend(d.capacity for d in inst.devices)
    values.extend(s.slots for s in inst.setups)
    values.extend(x for p in inst.precedences for x in (p.lag_min, p.lag_max) if x is not None)
    if any(abs(x) > limit for x in values):
        raise ValueError("instance exceeds safe integer bounds")
    raw = run_model(inst, time_limit_s, num_workers, seed, objective_weights)
    plan = None
    if raw.status in ("OPTIMAL", "FEASIBLE"):
        if raw.assignments is None:
            raise RuntimeError("solver returned a successful status without assignments")
        plan = Plan(
            id="initial",
            assignments=raw.assignments,
            metrics=PlanMetrics(makespan=raw.makespan, solve_seconds=raw.wall_seconds, gap=raw.gap),
        )
        final_report = validate(inst, plan)
        if not final_report.passed:
            raise RuntimeError(f"solver returned an invalid plan: {final_report}")
    elif raw.status not in ("INFEASIBLE", "UNKNOWN", "MODEL_INVALID"):
        raise RuntimeError(f"unrecognized solver status: {raw.status}")
    return SolveInitialResult(
        raw.status, plan, raw.objective, raw.best_bound, raw.gap, raw.wall_seconds, raw.reasons
    )


def solve_initial(
    inst: Instance,
    *,
    time_limit_s: float = 30,
    num_workers: int = 8,
    seed: int = 0,
    objective_weights: dict[str, float] | None = None,
) -> Plan | None:
    """Return a validated plan, or None when infeasible or unknown."""
    result = solve_initial_detailed(
        inst,
        time_limit_s=time_limit_s,
        num_workers=num_workers,
        seed=seed,
        objective_weights=objective_weights,
    )
    if result.status == "MODEL_INVALID":
        raise RuntimeError(f"invalid solver model: {result.reasons}")
    return result.plan
