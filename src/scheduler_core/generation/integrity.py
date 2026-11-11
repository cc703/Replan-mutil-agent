"""Independent checks of generated instance structural integrity."""

from datetime import timedelta
from math import isfinite

from scheduler_core.generation.params import SCALES
from scheduler_core.models import Instance


def check_instance_integrity(instance: Instance) -> None:
    """Check a typed Instance for structural integrity; return None on success.

    Revalidates mutable data, UTC whole-second axis, IDs, references, skills,
    compatible capacities, integer-slot bounds, setup uniqueness and DAG.
    Raises ValueError (including Pydantic ValidationError) on invalid data.
    Does not mutate the instance, perform IO, or establish schedule feasibility."""
    # Models are mutable; validate a fresh dump rather than trusting construction-time checks.
    Instance.model_validate(instance.model_dump())
    if instance.axis.t0.utcoffset() != timedelta(0) or instance.axis.t0.microsecond:
        raise ValueError("axis must use UTC whole seconds")
    for entries in (instance.devices, instance.tasks, instance.persons):
        ids = [entry.id for entry in entries]
        if any(not isinstance(i, str) or not i for i in ids) or len(ids) != len(set(ids)):
            raise ValueError("invalid entity ids")
    for device in instance.devices:
        if (
            not isinstance(device.type, str)
            or not device.type
            or any(
                not isinstance(capability, str) or not capability
                for capability in device.capabilities
            )
        ):
            raise ValueError("invalid device type or capability")
    for task in instance.tasks:
        if not isinstance(task.type, str) or not task.type or not task.experiment_id:
            raise ValueError("invalid task type or experiment")
        if not isfinite(task.weight):
            raise ValueError("invalid task weight")
        if any(not isinstance(skill, str) or not skill for skill in task.required_skills):
            raise ValueError("invalid task skill")
    for person in instance.persons:
        if any(not isinstance(skill, str) or not skill for skill in person.skills):
            raise ValueError("invalid person skill")
    devices = {d.id: d for d in instance.devices}
    tasks = {t.id: t for t in instance.tasks}
    horizon = instance.axis.horizon_slots
    for task in instance.tasks:
        if not task.compatible_devices or len(set(task.compatible_devices)) != len(
            task.compatible_devices
        ):
            raise ValueError("invalid compatible devices")
        if any(
            d not in devices or devices[d].capacity < task.demand for d in task.compatible_devices
        ):
            raise ValueError("invalid compatible capacity")
        if task.needs_person and not any(
            task.required_skills <= p.skills for p in instance.persons
        ):
            raise ValueError("uncovered personnel requirements")
        if task.release > horizon or task.deadline is not None and task.deadline > horizon:
            raise ValueError("task outside horizon")
    for window in instance.blocked:
        if window.device_id not in devices or window.end > horizon:
            raise ValueError("invalid device window")
    for person in instance.persons:
        if any(w.end > horizon for w in person.blocked):
            raise ValueError("invalid personnel window")
    if instance.now > horizon or any(
        edge.lag_min > horizon or edge.lag_max is not None and edge.lag_max > horizon
        for edge in instance.precedences
    ):
        raise ValueError("time outside horizon")
    setup_keys = [(s.device_id, s.task_type) for s in instance.setups]
    if len(set(setup_keys)) != len(setup_keys) or any(
        s.device_id not in devices or s.slots > horizon or not s.task_type for s in instance.setups
    ):
        raise ValueError("invalid setup")
    edges = [(p.pred, p.succ) for p in instance.precedences]
    if len(set(edges)) != len(edges):
        raise ValueError("duplicate edge")
    incoming = {t: 0 for t in tasks}
    successors: dict[str, list[str]] = {t: [] for t in tasks}
    for a, b in edges:
        if a not in tasks or b not in tasks or a == b:
            raise ValueError("invalid precedence")
        incoming[b] += 1
        successors[a].append(b)
    pending = [t for t in tasks if incoming[t] == 0]
    visited = 0
    while pending:
        item = pending.pop()
        visited += 1
        for target in successors[item]:
            incoming[target] -= 1
            if incoming[target] == 0:
                pending.append(target)
    if visited != len(tasks):
        raise ValueError("precedence cycle")


def check_generated_profile(instance: Instance, scale: str) -> None:
    """Check an Instance against the S/M/L generated profile; return None.

    Includes check_instance_integrity, scale counts, pending status, now=0,
    allowed windows, task time bounds and connected within-experiment DAGs.
    Raises ValueError on a failed check or unknown scale. Does not mutate input
    or do IO; this does not verify a schedule or prove feasibility."""
    check_instance_integrity(instance)
    if scale not in SCALES:
        raise ValueError("invalid scale")
    expected_tasks, expected_devices, expected_experiments = SCALES[scale]
    if (
        len(instance.tasks),
        len(instance.devices),
        len({t.experiment_id for t in instance.tasks}),
    ) != (expected_tasks, expected_devices, expected_experiments):
        raise ValueError("invalid scale profile")
    if instance.now or any(
        t.status != "PENDING" or t.deadline is None or t.release + t.duration > t.deadline
        for t in instance.tasks
    ):
        raise ValueError("invalid task profile")
    if any(w.kind not in ("CLOSED", "MAINT") for w in instance.blocked):
        raise ValueError("invalid blocked kind")
    tasks = {t.id: t for t in instance.tasks}
    if any(
        tasks[e.pred].experiment_id != tasks[e.succ].experiment_id for e in instance.precedences
    ):
        raise ValueError("cross-experiment edge")
    groups: dict[str, set[str]] = {}
    for task in instance.tasks:
        groups.setdefault(task.experiment_id, set()).add(task.id)
    adjacency: dict[str, set[str]] = {task_id: set() for task_id in tasks}
    for edge in instance.precedences:
        adjacency[edge.pred].add(edge.succ)
        adjacency[edge.succ].add(edge.pred)
    for members in groups.values():
        seen: set[str] = set()
        pending = [min(members)]
        while pending:
            node = pending.pop()
            if node not in seen:
                seen.add(node)
                pending.extend(adjacency[node] - seen)
        if seen != members:
            raise ValueError("disconnected experiment")
