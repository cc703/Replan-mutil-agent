"""Convert validated IR to explicit core changes without mutating the world."""

from collections.abc import Mapping, Set

from scheduler_core.models import DeviceOutage, Instance, Plan, TaskOverrun, UrgentInsert
from scheduler_core.replanning.events import prepare_raw
from scheduler_core.validation_context import ValidationContext

from .ir import Deadline, Outage, Overrun, Proposal, Urgent, check_proposal, urgent_core


def prepare_change(
    proposal: Proposal,
    instance: Instance,
    base: Plan,
    context: ValidationContext,
    aliases: Mapping[str, Set[str]] | None = None,
) -> tuple[Instance, list[DeviceOutage | TaskOverrun | UrgentInsert], ValidationContext]:
    """Return a new world and its authentic context; never apply an event twice."""
    check_proposal(proposal, instance, aliases)
    if isinstance(proposal, Deadline):
        slot = instance.axis.to_slot(proposal.deadline)
        tasks = [
            task.model_copy(
                deep=True,
                update={
                    "deadline": slot,
                    "deadline_level": proposal.level,
                    "weight": proposal.weight,
                },
            )
            if task.id == proposal.task.resolved_id
            else task.model_copy(deep=True)
            for task in instance.tasks
        ]
        data = instance.model_dump()
        data["tasks"] = tasks
        return Instance.model_validate(data), [], context.model_copy(deep=True)
    if isinstance(proposal, Outage):
        assert proposal.device.resolved_id is not None
        event: DeviceOutage | TaskOverrun | UrgentInsert = DeviceOutage(
            device_id=proposal.device.resolved_id,
            start=instance.axis.to_slot(proposal.start),
            end=instance.axis.to_slot(proposal.end),
        )
    elif isinstance(proposal, Overrun):
        assert proposal.task.resolved_id is not None
        event = TaskOverrun(
            task_id=proposal.task.resolved_id, new_end=instance.axis.to_slot(proposal.end)
        )
    else:
        assert isinstance(proposal, Urgent)
        event = UrgentInsert(
            tasks=[urgent_core(task, instance) for task in proposal.tasks],
            precedences=proposal.precedences,
        )
    post, effective = prepare_raw(instance, base, [event], context)
    return post, [event], effective
