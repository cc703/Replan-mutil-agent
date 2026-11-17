"""Stable identifiers for independently removable scheduling constraints."""

from dataclasses import dataclass
from datetime import timedelta

from scheduler_core.models import Instance, Plan
from scheduler_core.validation_context import ValidationContext


@dataclass(frozen=True)
class Group:
    id: str
    description: str
    relaxable: bool = False


def list_groups(
    inst: Instance,
    base: Plan | None,
    free: set[str],
    context: ValidationContext,
    frozen: set[str] | None = None,
) -> list[Group]:
    """List constraint groups in deterministic order, excluding bound running windows."""

    def instant(slot: int) -> str:
        return (inst.axis.t0 + timedelta(minutes=slot * inst.axis.slot_minutes)).isoformat()

    groups: list[Group] = []
    for task in inst.tasks:
        if task.deadline is not None:
            groups.append(
                Group(
                    f"deadline:{task.id}",
                    f"Task {task.id} deadline {task.deadline}",
                    task.deadline_level == "NEGOTIABLE" and task.id in free,
                )
            )
        if base is not None:
            if task.id in (frozen or set()) or task.status in ("RUNNING", "DONE"):
                groups.append(Group(f"frozen:{task.id}", f"Frozen task {task.id}"))
            elif task.id not in free and task.id in base.assignments:
                groups.append(Group(f"pinned:{task.id}", f"Pinned task {task.id}"))
    bound = {(b.device_id, b.start, b.end) for b in context.running_block_bindings}
    for w in inst.blocked:
        if w.kind == "RUNNING" and (w.device_id, w.start, w.end) in bound:
            continue
        gid = f"window:{w.device_id}:{w.start}:{w.end}:{w.kind}"
        groups.append(
            Group(gid, f"Device {w.device_id} {w.kind} window {instant(w.start)}–{instant(w.end)}")
        )
    for edge in inst.precedences:
        groups.append(
            Group(f"precedence:{edge.pred}>{edge.succ}", f"{edge.pred} precedes {edge.succ}")
        )
    for device in inst.devices:
        groups.append(Group(f"capacity:{device.id}", f"Device {device.id} capacity"))
    for person in inst.persons:
        groups.append(Group(f"person:{person.id}", f"Person {person.id} availability"))
        for pw in person.blocked:
            groups.append(
                Group(
                    f"person_window:{person.id}:{pw.start}:{pw.end}",
                    f"Person {person.id} window {instant(pw.start)}–{instant(pw.end)}",
                )
            )
    return sorted({g.id: g for g in groups}.values(), key=lambda g: g.id)
