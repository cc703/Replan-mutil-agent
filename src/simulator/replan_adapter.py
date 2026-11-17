"""P3 adapter: events have already been applied by the simulation runtime."""

from collections.abc import Sequence
from scheduler_core.models import Instance, Plan, ReplanParams, TaskOverrun
from scheduler_core.replan import replan
from scheduler_core.validation_context import FrozenEndChange, ValidationContext
from .events import SimEvent


def scheduler_with_context(
    inst: Instance,
    base: Plan,
    events: Sequence[SimEvent],
    context: ValidationContext,
    params: ReplanParams | None = None,
) -> Plan | None:
    """Return an independently validated candidate, if one was found."""
    payloads = [event.payload for event in events if event.payload is not None]
    evidence = context.model_copy(deep=True)
    for event in events:
        if isinstance(event.payload, TaskOverrun):
            old = base.assignments.get(event.payload.task_id)
            if old is not None and event.payload.new_end > old.end:
                evidence.end_changes.append(
                    FrozenEndChange(
                        task_id=event.payload.task_id,
                        plan_id=f"{base.id}.replan",
                        base_plan_id=base.id,
                        old_end=old.end,
                        new_end=event.payload.new_end,
                        event_id=f"overrun:{event.seq}",
                        acted_at=event.time,
                    )
                )
    result = replan(inst, base, payloads, params, context=evidence, post_applied=True)
    return result.candidates[0].plan if result.candidates else None
