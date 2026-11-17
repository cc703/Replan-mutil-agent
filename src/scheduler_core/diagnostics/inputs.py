"""Input and execution-evidence preparation shared by diagnostic APIs."""

from scheduler_core.models import Instance, Plan
from scheduler_core.validate import validate
from scheduler_core.validation.execution import check_snapshot
from scheduler_core.validation.index import build_index
from scheduler_core.validation.report import ViolationCollector
from scheduler_core.validation_context import ValidationContext


def prepare(
    inst: Instance,
    base: Plan | None,
    free: set[str] | None,
    context: ValidationContext | None,
) -> tuple[set[str], set[str], ValidationContext]:
    """Reject inconsistent evidence and derive frozen and free task sets."""
    if not isinstance(inst, Instance):
        raise TypeError("inst must be an Instance")
    if base is not None and not isinstance(base, Plan):
        raise TypeError("base must be a Plan or None")
    if free is not None and not isinstance(free, set):
        raise TypeError("free must be a set or None")
    if context is not None and not isinstance(context, ValidationContext):
        raise TypeError("context must be ValidationContext or None")
    ctx = context.model_copy(deep=True) if context else ValidationContext()
    active = {t.id for t in inst.tasks if t.status in ("PENDING", "SCHEDULED", "RUNNING", "DONE")}
    if base is None:
        if any(t.status != "PENDING" for t in inst.tasks):
            raise ValueError("initial scheduling requires pending tasks")
        check = validate(inst, Plan(id="precheck", assignments={}))
        if any(v.detail != "reason=MISSING_ASSIGNMENT;" for v in check.violations):
            raise ValueError("invalid initial instance")
        selected = active if free is None else set(free)
        if selected != active:
            raise ValueError("initial free set must contain all tasks")
        return selected, set(), ctx
    if ctx.snapshot is None or ctx.snapshot.plan_id != base.id or ctx.snapshot.as_of != inst.now:
        raise ValueError("matching execution snapshot required")
    ctx.deadline_authorizations = [a for a in ctx.deadline_authorizations if a.plan_id == base.id]
    ctx.end_changes = [c for c in ctx.end_changes if c.plan_id == base.id]
    tasks = {task.id: task for task in inst.tasks}
    seen: set[str] = set()
    for auth in ctx.deadline_authorizations:
        task = tasks.get(auth.task_id)
        if (
            auth.task_id in seen
            or task is None
            or task.deadline is None
            or task.deadline_level != "NEGOTIABLE"
            or auth.original_deadline != task.deadline
            or auth.acted_at > inst.now
            or (auth.valid_until is not None and auth.valid_until < inst.now)
        ):
            raise ValueError("invalid deadline authorization")
        seen.add(auth.task_id)
    collector = ViolationCollector()
    idx = build_index(inst, base, base, ctx, collector)
    check_snapshot(inst, base, base, ctx, idx, collector)
    if collector.report().violations:
        raise ValueError("invalid execution evidence")
    for task in inst.tasks:
        if task.status not in ("RUNNING", "DONE"):
            continue
        record, old = idx.records.get(task.id), base.assignments.get(task.id)
        if (
            record is None
            or old is None
            or record.status != task.status
            or record.start != old.start
            or record.device_id != old.device_id
            or record.person_id != old.person_id
        ):
            raise ValueError(f"missing or conflicting execution evidence for {task.id}")
    selected = active - idx.frozen if free is None else set(free)
    if selected & idx.frozen or not selected <= active:
        raise ValueError("invalid free set")
    if any(tid not in base.assignments for tid in active - selected):
        raise ValueError("missing fixed assignment")
    return selected, idx.frozen, ctx
