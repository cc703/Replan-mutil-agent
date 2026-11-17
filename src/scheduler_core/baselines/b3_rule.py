"""Public rule-based repair baseline."""

from collections.abc import Sequence
from scheduler_core.impact import EventType
from scheduler_core.models import Instance, Plan, ReplanParams
from scheduler_core.replanning.events import prepare_raw
from scheduler_core.validation_context import ExecutionSnapshot, ValidationContext
from .b3 import b3


def b3_rule_repair(
    inst: Instance,
    plan0: Plan,
    events: Sequence[EventType],
    *,
    context: ValidationContext | None = None,
    post_applied: bool = False,
    params: ReplanParams | None = None,
) -> Plan | None:
    """Apply raw events once or consume a post-event instance, then repair."""
    context = context or ValidationContext(
        snapshot=ExecutionSnapshot(plan_id=plan0.id, as_of=inst.now, base_as_of=inst.now)
    )
    post = inst
    if not post_applied:
        post, context = prepare_raw(inst, plan0, events, context)
    return b3(post, plan0, events, context, params)
