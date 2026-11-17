"""Task-level differences between two plans."""

from dataclasses import dataclass

from scheduler_core.models import Assignment, Instance, Plan


@dataclass(frozen=True)
class TaskPlanDiff:
    """A changed task's assignments and individual change flags."""

    task_id: str
    before: Assignment | None
    after: Assignment | None
    added: bool
    removed: bool
    moved: bool
    device_changed: bool
    person_changed: bool
    start_delta: int | None


def diff_plans(inst: Instance, base: Plan, plan: Plan) -> list[TaskPlanDiff]:
    """Return changed assignments in task-ID order without mutating inputs.

    Assignments may include removed tasks, which need not appear in the new instance.
    """
    del inst  # Kept in the public interface for callers with instance context.
    result = []
    for tid in sorted(base.assignments.keys() | plan.assignments.keys()):
        old, new = base.assignments.get(tid), plan.assignments.get(tid)
        if old == new:
            continue
        result.append(
            TaskPlanDiff(
                task_id=tid,
                before=old.model_copy(deep=True) if old else None,
                after=new.model_copy(deep=True) if new else None,
                added=old is None,
                removed=new is None,
                moved=old is not None and new is not None and old.start != new.start,
                device_changed=old is not None
                and new is not None
                and old.device_id != new.device_id,
                person_changed=old is not None
                and new is not None
                and old.person_id != new.person_id,
                start_delta=new.start - old.start if old is not None and new is not None else None,
            )
        )
    return result
