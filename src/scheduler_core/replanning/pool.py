"""Generate validated alternatives across neighborhoods and weight settings."""

import math
import time
from collections.abc import Sequence

from scheduler_core.impact import EventType, analyze_impact, neighborhoods
from scheduler_core.models import (
    Assignment,
    Candidate,
    Instance,
    Plan,
    PlanMetrics,
    ReplanParams,
    ReplanResult,
    TaskOverrun,
    UrgentInsert,
)
from scheduler_core.pareto import select_candidates
from scheduler_core.replanning.events import prepare_post, prepare_raw
from scheduler_core.replanning.model import solve_neighborhood
from scheduler_core.replanning.params import validate_params
from scheduler_core.validate import validate
from scheduler_core.validation_context import ExecutionSnapshot, FrozenEndChange, ValidationContext


def _validate_grid(params: ReplanParams) -> None:
    validate_params(params)
    if params.total_budget_s > 3600:
        raise ValueError("total_budget_s must not exceed 3600")
    values = (
        params.alpha,
        params.beta_moved,
        params.beta_switched,
        params.beta_shift,
        params.gamma,
    )
    if any(not math.isfinite(v) or v < 0 for v in values):
        raise ValueError("objective weights must be finite and nonnegative")
    if not 1 <= len(params.weight_grid) <= 4:
        raise ValueError("weight_grid must have one to four pairs")
    for pair in params.weight_grid:
        if len(pair) != 2 or any(not math.isfinite(v) or v < 0 for v in pair) or not any(pair):
            raise ValueError("invalid weight_grid pair")


def _candidate_context(
    context: ValidationContext,
    candidate_id: str,
    base: Plan,
    post: Instance,
    events: Sequence[EventType],
) -> ValidationContext:
    ctx = context.model_copy(deep=True)
    ctx.deadline_authorizations = [
        a for a in ctx.deadline_authorizations if a.plan_id == candidate_id
    ]
    ctx.end_changes = [c for c in ctx.end_changes if c.plan_id == candidate_id]
    assert ctx.snapshot is not None
    for event in events:
        if not isinstance(event, TaskOverrun):
            continue
        record = next((r for r in ctx.snapshot.records if r.task_id == event.task_id), None)
        old = base.assignments.get(event.task_id)
        task = next((t for t in post.tasks if t.id == event.task_id), None)
        if (
            record is None
            or old is None
            or task is None
            or task.status != "RUNNING"
            or record.status != "RUNNING"
            or record.start != old.start
            or record.device_id != old.device_id
            or record.person_id != old.person_id
            or record.planned_end != old.end
            or event.new_end <= old.end
        ):
            raise ValueError("inconsistent overrun execution evidence")
        if not any(c.task_id == event.task_id for c in ctx.end_changes):
            ctx.end_changes.append(
                FrozenEndChange(
                    task_id=event.task_id,
                    plan_id=candidate_id,
                    base_plan_id=base.id,
                    old_end=old.end,
                    new_end=event.new_end,
                    event_id=record.event_id,
                    acted_at=ctx.snapshot.as_of,
                )
            )
    return ctx


def _make_candidate(
    post: Instance,
    base: Plan,
    assignments: dict[str, Assignment],
    level: int,
    grid: tuple[float, float],
    params: ReplanParams,
    urgent: set[str],
    candidate_id: str,
    elapsed: float,
    free: set[str],
    context: ValidationContext,
) -> Candidate:
    tasks = {t.id: t for t in post.tasks}
    comparable = assignments.keys() & base.assignments.keys()
    moved = sum(assignments[t].start != base.assignments[t].start for t in comparable)
    switched = sum(assignments[t].device_id != base.assignments[t].device_id for t in comparable)
    shift = sum(abs(assignments[t].start - base.assignments[t].start) for t in comparable)
    tard = sum(
        tasks[t].weight * max(0, a.end - (tasks[t].deadline or 0))
        for t, a in assignments.items()
        if tasks[t].deadline is not None
    )
    urgent_value = sum(assignments[t].end for t in urgent if t in assignments)
    metrics = PlanMetrics(
        tardiness=tard,
        makespan=max((a.end for a in assignments.values()), default=0),
        moved=moved,
        switched=switched,
        shift_total=shift,
        urgent_delay=urgent_value,
        solve_seconds=elapsed,
    )
    plan = Plan(id=candidate_id, parent_id=base.id, assignments=assignments, metrics=metrics)
    report = validate(post, plan, base=base, free=free, context=context)
    if not report.passed:
        raise RuntimeError(f"CP-SAT candidate failed independent validation: {report}")
    return Candidate(
        plan=plan,
        level=level,
        weights=grid,
        f1=tard,
        f2=params.beta_moved * moved
        + params.beta_switched * switched
        + params.beta_shift * shift / post.axis.horizon_slots,
        f3=float(urgent_value),
        validation=report,
    )


def replan_candidates(
    inst: Instance,
    base: Plan,
    events: Sequence[EventType],
    params: ReplanParams | None = None,
    *,
    context: ValidationContext | None = None,
    post_applied: bool = False,
    full: bool = False,
    max_candidates: int = 5,
    diagnose_on_infeasible: bool = True,
) -> ReplanResult:
    """Produce independently validated candidates within one shared time budget."""
    started = time.perf_counter()
    p = params or ReplanParams()
    _validate_grid(p)
    select_candidates([], max_n=max_candidates)
    ctx = context or ValidationContext(
        snapshot=ExecutionSnapshot(plan_id=base.id, as_of=inst.now, base_as_of=inst.now)
    )
    if post_applied:
        post = prepare_post(inst, base, events, ctx)
        ctx = ctx.model_copy(deep=True)
    else:
        post, ctx = prepare_raw(inst, base, events, ctx)
    impact = analyze_impact(post, base, events, p.window_slots, context=ctx)
    levels = neighborhoods(post, base, impact, p.window_slots)
    urgent = {t.id for e in events if isinstance(e, UrgentInsert) for t in e.tasks}
    selected_levels = [3] if full else list(range(p.max_level + 1))
    jobs = [(level, i, pair) for level in selected_levels for i, pair in enumerate(p.weight_grid)]
    pool: list[Candidate] = []
    reached: int | None = None
    level3_statuses: list[str] = []
    ids = {base.id}
    for index, (level, grid_index, pair) in enumerate(jobs):
        remaining = p.total_budget_s - (time.perf_counter() - started)
        if remaining <= 0:
            break
        candidate_id = f"{base.id}.replan.l{level}.w{grid_index}"
        if candidate_id in ids:
            raise ValueError("candidate ID collision")
        ids.add(candidate_id)
        candidate_ctx = _candidate_context(ctx, candidate_id, base, post, events)
        adjusted = p.model_copy(
            update={
                "alpha": pair[0],
                "beta_moved": p.beta_moved * pair[1],
                "beta_switched": p.beta_switched * pair[1],
                "beta_shift": p.beta_shift * pair[1],
            }
        )
        remaining = p.total_budget_s - (time.perf_counter() - started)
        if remaining <= 0:
            break
        raw = solve_neighborhood(
            post,
            base,
            levels[level],
            impact.frozen,
            candidate_ctx,
            urgent,
            adjusted,
            remaining / (len(jobs) - index),
        )
        reached = level
        if raw.status == "MODEL_INVALID":
            raise RuntimeError("invalid CP-SAT model")
        if level == 3:
            level3_statuses.append(raw.status)
        if raw.assignments is not None:
            if time.perf_counter() - started >= p.total_budget_s:
                break
            pool.append(
                _make_candidate(
                    post,
                    base,
                    raw.assignments,
                    level,
                    pair,
                    p,
                    urgent,
                    candidate_id,
                    time.perf_counter() - started,
                    levels[level],
                    candidate_ctx,
                )
            )
    if pool:
        return ReplanResult(
            status="OK",
            candidates=select_candidates(pool, max_n=max_candidates),
            impact=impact,
            level_reached=reached,
        )
    level3_infeasible = len(level3_statuses) == len(p.weight_grid) and all(
        status == "INFEASIBLE" for status in level3_statuses
    )
    result = ReplanResult(
        status="INFEASIBLE" if level3_infeasible else "TIMEOUT",
        impact=impact,
        level_reached=reached,
    )
    if level3_infeasible and diagnose_on_infeasible and not ctx.deadline_authorizations:
        remaining = p.total_budget_s - (time.perf_counter() - started)
        if remaining > 0:
            from scheduler_core.diagnose import diagnose_detailed
            from scheduler_core.relax import suggest_relaxations

            diagnosis = diagnose_detailed(
                post, base, levels[3], time_limit_s=remaining, context=ctx
            )
            if diagnosis.status in ("CORE", "BACKGROUND") and diagnosis.core is not None:
                result.conflict = diagnosis.core
                remaining = p.total_budget_s - (time.perf_counter() - started)
                if remaining > 0:
                    result.relaxations = suggest_relaxations(
                        post, base, levels[3], diagnosis.core, time_limit_s=remaining, context=ctx
                    )
    return result
