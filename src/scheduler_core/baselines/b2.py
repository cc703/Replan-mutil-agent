"""Full-release CP-SAT baselines."""

from collections.abc import Sequence

from scheduler_core.impact import EventType
from scheduler_core.models import Instance, Plan, ReplanParams, ReplanResult
from scheduler_core.replan import replan
from scheduler_core.validation_context import ValidationContext


def b2(
    inst: Instance,
    base: Plan,
    events: Sequence[EventType],
    context: ValidationContext,
    params: ReplanParams | None = None,
) -> ReplanResult:
    """Full release, weighted tardiness only."""
    return replan(
        inst,
        base,
        events,
        params,
        context=context,
        post_applied=True,
        full=True,
        tardiness_only=True,
    )


def b2s(
    inst: Instance,
    base: Plan,
    events: Sequence[EventType],
    context: ValidationContext,
    params: ReplanParams | None = None,
) -> ReplanResult:
    """Full release, full stability and urgency objective."""
    return replan(inst, base, events, params, context=context, post_applied=True, full=True)
