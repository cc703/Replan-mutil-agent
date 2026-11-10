"""Acceptance checks for independent schedule validation."""

from scheduler_core.models import (
    Assignment,
    BlockedWindow,
    Plan,
    Task,
)
from scheduler_core.validate import validate
from scheduler_core.validation_context import (
    RunningBlockBinding,
)
import pytest


from .validation_helpers import execution_case, instance, reasons


@pytest.mark.parametrize("capacity", [1, 4])
def test_running_unbound_windows(capacity: int) -> None:
    inst = instance()
    inst.devices[0].capacity = capacity
    inst.blocked = [BlockedWindow(device_id="d", start=5, end=8, kind="RUNNING")]
    plan = Plan(
        id="p",
        assignments={
            "a": Assignment(task_id="a", device_id="d", start=0, end=4),
            "b": Assignment(task_id="b", device_id="d", start=8, end=12),
        },
    )
    assert not reasons(validate(inst, plan), "V2", "RUNNING_BLOCK_UNBOUND")
    plan.assignments["b"] = plan.assignments["b"].model_copy(update={"start": 7, "end": 11})
    assert reasons(validate(inst, plan), "V2", "RUNNING_BLOCK_UNBOUND") == [["b"]]


def test_running_binding_capacity_and_deduplication() -> None:
    inst, plan, base, ctx = execution_case("RUNNING", 10, remaining=0)
    inst.devices[0].capacity = 4
    inst.blocked = [BlockedWindow(device_id="d", start=5, end=10, kind="RUNNING")]
    ctx.running_block_bindings = [RunningBlockBinding(device_id="d", start=5, end=10, task_id="a")]
    for i in range(3):
        tid = str(i)
        inst.tasks.append(
            Task(id=tid, experiment_id="e", type="x", duration=2, compatible_devices=["d"])
        )
        plan.assignments[tid] = Assignment(task_id=tid, device_id="d", start=10, end=12)
    # Move snapshot and now so simultaneous tasks are non-frozen and legal.
    inst.now = 5
    assert ctx.snapshot is not None
    ctx.snapshot.as_of = 5
    for tid in ("0", "1", "2"):
        plan.assignments[tid] = plan.assignments[tid].model_copy(update={"start": 5, "end": 7})
    assert validate(inst, plan, base=base, context=ctx).passed
    inst.tasks.append(
        Task(id="3", experiment_id="e", type="x", duration=2, compatible_devices=["d"])
    )
    plan.assignments["3"] = Assignment(task_id="3", device_id="d", start=5, end=7)
    report = validate(inst, plan, base=base, context=ctx)
    assert reasons(report, "V9", "CAPACITY_EXCEEDED") == [["0", "1", "2", "3", "a"]]
    assert not reasons(report, "V2", "RUNNING_BLOCK_UNBOUND")
    inst.devices[0].capacity = 1
    inst.tasks = inst.tasks[:2]
    plan.assignments = {k: v for k, v in plan.assignments.items() if k in ("a", "0")}
    report = validate(inst, plan, base=base, context=ctx)
    assert reasons(report, "V2", "DEVICE_OVERLAP") == [["0", "a"]]
    assert not reasons(report, "V2", "RUNNING_BLOCK_UNBOUND")


@pytest.mark.parametrize(
    "case",
    [
        "no_record",
        "not_running",
        "no_assignment",
        "device",
        "end",
        "start",
        "no_window",
        "duplicate",
    ],
)
def test_invalid_running_bindings(case: str) -> None:
    inst, plan, base, ctx = execution_case("RUNNING", 10, remaining=0)
    inst.blocked = [BlockedWindow(device_id="d", start=5, end=10, kind="RUNNING")]
    binding = RunningBlockBinding(device_id="d", start=5, end=10, task_id="a")
    assert ctx.snapshot is not None
    if case == "no_record":
        ctx.snapshot.records.clear()
    elif case == "not_running":
        inst.tasks[0].status = "PENDING"
    elif case == "no_assignment":
        plan.assignments.clear()
    elif case == "device":
        binding.device_id = "other"
        inst.blocked[0].device_id = "other"
    elif case == "end":
        binding.end = 9
        inst.blocked[0].end = 9
    elif case == "start":
        binding.start = 11
        binding.end = 12
        inst.blocked[0].start = 11
        inst.blocked[0].end = 12
    elif case == "no_window":
        inst.blocked.clear()
    ctx.running_block_bindings = [binding, binding] if case == "duplicate" else [binding]
    assert reasons(
        validate(inst, plan, base=base, context=ctx), "V2", "RUNNING_BLOCK_BINDING_INVALID"
    ) == [["a"]]
    ctx.running_block_bindings = []
    assert not reasons(
        validate(inst, plan, base=base, context=ctx), "V2", "RUNNING_BLOCK_BINDING_INVALID"
    )
