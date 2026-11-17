"""Budgeted neighborhood replanning with independent candidate validation."""

import time
from collections.abc import Sequence
from typing import Literal

from scheduler_core.impact import EventType, analyze_impact, neighborhoods
from scheduler_core.models import (
    Candidate,
    Instance,
    Plan,
    PlanMetrics,
    ReplanParams,
    ReplanResult,
    TaskOverrun,
    UrgentInsert,
)
from scheduler_core.replanning.events import prepare_post, prepare_raw
from scheduler_core.replanning.model import solve_neighborhood
from scheduler_core.replanning.params import validate_params
from scheduler_core.validate import validate
from scheduler_core.validation_context import ExecutionSnapshot, FrozenEndChange, ValidationContext


def replan(
    inst: Instance,
    base: Plan,
    events: Sequence[EventType],
    params: ReplanParams | None = None,
    *,
    context: ValidationContext | None = None,
    post_applied: bool = False,
    full: bool = False,
    tardiness_only: bool = False,
) -> ReplanResult:
    """Replan a post-event instance using a shared wall-clock budget."""
    started = time.perf_counter()
    p = params or ReplanParams()
    validate_params(p)
    context = context or ValidationContext(
        snapshot=ExecutionSnapshot(plan_id=base.id, as_of=inst.now, base_as_of=inst.now)
    )
    if post_applied:
        post = prepare_post(inst, base, events, context)
    else:
        post, context = prepare_raw(inst, base, events, context)
        # Bind the caller's execution evidence to this candidate, not a fabricated event ID.
        assert context.snapshot is not None
        for event in events:
            if not isinstance(event, TaskOverrun):
                continue
            record = next((r for r in context.snapshot.records if r.task_id == event.task_id), None)
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
            if not any(c.task_id == event.task_id for c in context.end_changes):
                context.end_changes.append(
                    FrozenEndChange(
                        task_id=event.task_id,
                        plan_id=f"{base.id}.replan",
                        base_plan_id=base.id,
                        old_end=old.end,
                        new_end=event.new_end,
                        event_id=record.event_id,
                        acted_at=context.snapshot.as_of,
                    )
                )
    impact = analyze_impact(post, base, events, p.window_slots, context=context)
    levels = neighborhoods(post, base, impact, p.window_slots)
    urgent = {t.id for e in events if isinstance(e, UrgentInsert) for t in e.tasks}
    selected_levels = [3] if full else list(range(p.max_level + 1))
    reached = None
    last_status = "UNKNOWN"
    exhausted = False
    for level in selected_levels:
        remaining = p.total_budget_s - (time.perf_counter() - started)
        if remaining <= 0:
            exhausted = True
            break
        allocations = sum(2**k for k in selected_levels if k >= level)
        allocation = remaining * 2**level / allocations
        raw = solve_neighborhood(
            post,
            base,
            levels[level],
            impact.frozen,
            context,
            urgent,
            p,
            allocation,
            tardiness_only=tardiness_only,
        )
        reached, last_status = level, raw.status
        if time.perf_counter() - started > p.total_budget_s:
            exhausted = True
            break
        if raw.status == "MODEL_INVALID":
            raise RuntimeError("invalid CP-SAT model")
        if raw.assignments is None:
            continue
        tasks = {t.id: t for t in post.tasks}
        comparable = set(raw.assignments) & base.assignments.keys()
        moved = sum(raw.assignments[t].start != base.assignments[t].start for t in comparable)
        switched = sum(
            raw.assignments[t].device_id != base.assignments[t].device_id for t in comparable
        )
        shift = sum(abs(raw.assignments[t].start - base.assignments[t].start) for t in comparable)
        tard = sum(
            tasks[t].weight * max(0, a.end - (tasks[t].deadline or 0))
            for t, a in raw.assignments.items()
            if tasks[t].deadline is not None
        )
        urgent_value = sum(raw.assignments[t].end for t in urgent if t in raw.assignments)
        metrics = PlanMetrics(
            tardiness=tard,
            makespan=max((a.end for a in raw.assignments.values()), default=0),
            moved=moved,
            switched=switched,
            shift_total=shift,
            urgent_delay=urgent_value,
            solve_seconds=time.perf_counter() - started,
        )
        candidate = Plan(
            id=f"{base.id}.replan", parent_id=base.id, assignments=raw.assignments, metrics=metrics
        )
        report = validate(post, candidate, base=base, free=levels[level], context=context)
        if not report.passed:
            raise RuntimeError(f"CP-SAT candidate failed independent validation: {report}")
        if time.perf_counter() - started > p.total_budget_s:
            exhausted = True
            break
        return ReplanResult(
            status="OK",
            impact=impact,
            level_reached=level,
            candidates=[
                Candidate(
                    plan=candidate,
                    level=level,
                    weights=(p.alpha, p.beta_moved),
                    f1=tard,
                    f2=p.beta_moved * moved
                    + p.beta_switched * switched
                    + p.beta_shift * shift / post.axis.horizon_slots,
                    f3=float(urgent_value),
                    validation=report,
                )
            ],
        )
    status: Literal["INFEASIBLE", "TIMEOUT"] = (
        "INFEASIBLE"
        if not exhausted and reached == 3 and last_status == "INFEASIBLE"
        else "TIMEOUT"
    )
    return ReplanResult(status=status, impact=impact, level_reached=reached)
