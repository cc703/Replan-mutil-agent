"""Public full-release solver baseline."""

from collections.abc import Sequence
from scheduler_core.impact import EventType
from scheduler_core.models import Instance, Plan, ReplanParams
from scheduler_core.replan import replan
from scheduler_core.validation_context import ValidationContext


def b2_full_replan(
    inst: Instance,
    plan0: Plan,
    events: Sequence[EventType],
    params: ReplanParams,
    *,
    with_stability: bool = False,
    context: ValidationContext | None = None,
    post_applied: bool = False,
) -> Plan | None:
    """Solve full release, returning a validated plan or None."""
    result = replan(
        inst,
        plan0,
        events,
        params,
        context=context,
        post_applied=post_applied,
        full=True,
        tardiness_only=not with_stability,
    )
    return result.candidates[0].plan if result.candidates else None
