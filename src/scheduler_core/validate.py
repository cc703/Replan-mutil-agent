"""Independent semantic checks for schedules, with half-open interval scans."""

from typing import AbstractSet

from .models import Instance, Plan, ValidationReport
from .validation.execution import check_end_changes, check_neighborhood, check_snapshot
from .validation.index import build_index
from .validation.task_rules import check_deadlines, check_precedences, check_task_references
from .validation.resources import (
    setup_rules,
    collect_occupancy,
    check_overlaps,
    check_calendar,
    check_running_blocks,
)
from .validation.report import ViolationCollector
from .validation_context import (
    ValidationContext,
)


def validate(
    inst: Instance,
    plan: Plan,
    *,
    base: Plan | None = None,
    free: AbstractSet[str] | None = None,
    context: ValidationContext | None = None,
) -> ValidationReport:
    """Check a plan against an instance and optional prior-plan evidence.

    ``inst`` provides the constraints and integer-slot axis; ``plan`` provides
    assignments. Resource intervals are half-open. ``base`` is the optional
    parent plan; ``free=None`` disables neighborhood checks, while an empty set
    allows no non-frozen changes. ``context`` carries optional execution and
    authorization evidence, whose authenticity is the caller's responsibility.

    Inputs are not mutated. Return a report sorted by code, task IDs, device ID
    and detail; ``passed`` is true exactly when there are no violations.
    Semantic failures are reported as violations; incorrect top-level argument
    types raise TypeError.
    """
    if not isinstance(inst, Instance) or not isinstance(plan, Plan):
        raise TypeError("inst and plan must be Instance and Plan")
    if base is not None and not isinstance(base, Plan):
        raise TypeError("base must be a Plan or None")
    if context is not None and not isinstance(context, ValidationContext):
        raise TypeError("context must be a ValidationContext or None")
    if free is not None and not isinstance(free, AbstractSet):
        raise TypeError("free must be a set or None")
    ctx = context if context is not None else ValidationContext()
    collector = ViolationCollector()
    index = build_index(inst, plan, base, ctx, collector)
    check_neighborhood(plan, base, free, index, collector)
    check_snapshot(inst, plan, base, ctx, index, collector)
    setups = setup_rules(inst, index, collector)
    check_task_references(index, collector)
    device_intervals, person_intervals, occupancy = collect_occupancy(
        inst, base, ctx, index, setups, collector
    )
    check_end_changes(inst, plan, base, ctx, index, collector)
    check_deadlines(inst, plan, ctx, index, collector)
    check_precedences(inst, index, collector)
    check_overlaps(index, device_intervals, person_intervals, collector)
    running = check_calendar(inst, index, occupancy, collector)
    check_running_blocks(ctx, index, running, occupancy, collector)
    return collector.report()
