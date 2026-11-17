"""Hypothetical, independently validated negotiable-deadline proposals."""

from dataclasses import dataclass
from fractions import Fraction
from math import lcm, isfinite
import time

from ortools.sat.python import cp_model

from scheduler_core.diagnostics.inputs import prepare
from scheduler_core.diagnostics.relax_model import set_objective
from scheduler_core.models import ConflictCore, Instance, Plan, RelaxationOption, ReplanParams
from scheduler_core.replanning.model import solve_neighborhood
from scheduler_core.solving.run import _build_model
from scheduler_core.validate import validate
from scheduler_core.validation_context import ValidationContext


@dataclass(frozen=True)
class RelaxationProposal:
    option: RelaxationOption
    deltas: dict[str, int]
    plan: Plan
    optimal: bool
    verified: bool
    moved_count: int


@dataclass(frozen=True)
class RelaxResult:
    status: str
    proposals: list[RelaxationProposal]
    notes: tuple[str, ...]


def suggest_relaxations_detailed(
    inst: Instance,
    plan0: Plan | None,
    free: set[str] | None,
    core: ConflictCore,
    *,
    k: int = 3,
    time_limit_s: float = 5.0,
    context: ValidationContext | None = None,
) -> RelaxResult:
    """Find incomparable deadline supports and verify both hypothetical and original instances."""
    started = time.perf_counter()
    if isinstance(k, bool) or not isinstance(k, int):
        raise TypeError("k must be an integer")
    if not 1 <= k <= 10:
        raise ValueError("k outside [1, 10]")
    if isinstance(time_limit_s, bool) or not isinstance(time_limit_s, (int, float)):
        raise TypeError("time_limit_s must be a number")
    if not isfinite(time_limit_s) or not 0 < time_limit_s <= 3600:
        raise ValueError("invalid time limit")
    end_time = started + time_limit_s
    selected, frozen, ctx = prepare(inst, plan0, free, context)
    tasks = {t.id: t for t in inst.tasks}
    limits = {
        t.id: inst.axis.horizon_slots - t.deadline
        for t in inst.tasks
        if t.id in selected
        and t.deadline is not None
        and t.deadline_level == "NEGOTIABLE"
        and t.deadline < inst.axis.horizon_slots
    }
    if not any(f"deadline:{tid}" in core.group_ids for tid in limits):
        return RelaxResult("NO_OPTIONS", [], ("冲突不在可协商截止期上",))
    fractions = {tid: Fraction(str(tasks[tid].weight)) for tid in limits}
    scale = lcm(*(value.denominator for value in fractions.values()))
    costs = {tid: int(value * scale) for tid, value in fractions.items()}
    if (
        scale > (1 << 50)
        or sum(costs[t] * limits[t] for t in limits) * (sum(limits.values()) + 1) >= 1 << 60
    ):
        raise ValueError("relaxation objective exceeds safe integer bounds")
    proposals: list[RelaxationProposal] = []
    excluded: list[set[str]] = []
    status = "UNKNOWN"
    for _ in range(min(k, 16)):
        remaining = end_time - time.perf_counter()
        if remaining <= 0:
            break
        if plan0 is None:
            h = inst.axis.horizon_slots
            load = sum(t.duration * t.demand for t in inst.tasks)
            deltas: dict[str, cp_model.IntVar] = {}
            model, starts, ends, devices, people, *_ = _build_model(
                inst, h, load, 1, 0, relax_deltas=deltas, relax_limits=limits
            )
            bits = {tid: model.new_bool_var(f"support:{tid}") for tid in limits}
            for tid, bit in bits.items():
                model.add(deltas[tid] >= 1).only_enforce_if(bit)
                model.add(deltas[tid] == 0).only_enforce_if(bit.Not())
            set_objective(model, deltas, bits, costs, excluded, limits)
            remaining = end_time - time.perf_counter()
            if remaining <= 0:
                break
            solver = cp_model.CpSolver()
            solver.parameters.num_search_workers = 1
            solver.parameters.max_time_in_seconds = remaining
            result = solver.solve(model)
            status = solver.status_name(result)
            if result not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                if result == cp_model.MODEL_INVALID:
                    raise RuntimeError("invalid relaxation model")
                break
            from scheduler_core.models import Assignment

            assignments = {
                t.id: Assignment(
                    task_id=t.id,
                    device_id=next(
                        d for (tid, d), b in devices.items() if tid == t.id and solver.value(b)
                    ),
                    person_id=next(
                        (p for (tid, p), b in people.items() if tid == t.id and solver.value(b)),
                        None,
                    ),
                    start=solver.value(starts[t.id]),
                    end=solver.value(ends[t.id]),
                )
                for t in inst.tasks
            }
            values = {tid: solver.value(delta) for tid, delta in deltas.items()}
        else:
            raw = solve_neighborhood(
                inst,
                plan0,
                selected,
                frozen,
                ctx,
                set(),
                ReplanParams(num_workers=1),
                remaining,
                relax_limits=limits,
                relax_costs=costs,
                excluded_supports=excluded,
            )
            status = raw.status
            if status == "MODEL_INVALID":
                raise RuntimeError("invalid relaxation model")
            if raw.assignments is None or raw.deltas is None:
                break
            assignments, values = raw.assignments, raw.deltas
        positive = {tid: delta for tid, delta in values.items() if delta > 0}
        if not positive:
            break
        plan = Plan(
            id=plan0.id if plan0 else "relaxation",
            parent_id=plan0.id if plan0 else None,
            assignments=assignments,
        )
        hypothetical = inst.model_copy(deep=True)
        for task in hypothetical.tasks:
            if task.id in positive:
                assert task.deadline is not None
                task.deadline += positive[task.id]
        assumed_report = validate(
            hypothetical, plan, base=plan0, free=selected if plan0 else None, context=ctx
        )
        original_report = validate(
            inst, plan, base=plan0, free=selected if plan0 else None, context=ctx
        )
        if time.perf_counter() >= end_time:
            break
        if (
            not assumed_report.passed
            or original_report.passed
            or any(
                v.code != "V5" or not set(v.task_ids) <= positive.keys()
                for v in original_report.violations
            )
        ):
            break
        cost = sum(fractions[tid] * delta for tid, delta in positive.items())
        moved = sum(
            a.start != plan0.assignments[tid].start
            for tid, a in assignments.items()
            if plan0 and tid in plan0.assignments
        )
        option = RelaxationOption(
            description=f"若获授权，截止期延后 {positive} 槽",
            cost=float(cost),
            relaxed_groups=[f"deadline:{tid}" for tid in sorted(positive)],
        )
        proposals.append(
            RelaxationProposal(option, positive, plan, status == "OPTIMAL", True, moved)
        )
        excluded.append(set(positive))
    return RelaxResult(status, proposals, ())


def suggest_relaxations(
    inst: Instance,
    plan0: Plan | None,
    free: set[str] | None,
    core: ConflictCore,
    *,
    k: int = 3,
    time_limit_s: float = 5.0,
    context: ValidationContext | None = None,
) -> list[RelaxationOption]:
    """Return only hypothetical options, without adopting any plan."""
    return [
        p.option
        for p in suggest_relaxations_detailed(
            inst, plan0, free, core, k=k, time_limit_s=time_limit_s, context=context
        ).proposals
    ]
