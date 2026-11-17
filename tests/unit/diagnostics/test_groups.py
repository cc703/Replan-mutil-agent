import pytest
from scheduler_core.diagnose import diagnose_detailed
from scheduler_core.models import Assignment, Plan
from scheduler_core.validation_context import ExecutionSnapshot, ValidationContext
from tests.unit.diagnostics.test_diagnose_cases import instance


def test_past_assignment_is_frozen_and_not_releasable() -> None:
    inst = instance(duration=2, deadline=5)
    inst.now = 2
    base = Plan(id="p", assignments={"X": Assignment(task_id="X", device_id="D", start=0, end=2)})
    context = ValidationContext(snapshot=ExecutionSnapshot(plan_id="p", as_of=2, base_as_of=0))
    assert diagnose_detailed(inst, base, None, context=context).status == "FEASIBLE"
    with pytest.raises(ValueError, match="free"):
        diagnose_detailed(inst, base, {"X"}, context=context)


def test_missing_execution_record_is_input_error() -> None:
    inst = instance(duration=2, deadline=5)
    inst.now = 2
    inst.tasks[0].status = "RUNNING"
    base = Plan(id="p", assignments={"X": Assignment(task_id="X", device_id="D", start=1, end=3)})
    context = ValidationContext(snapshot=ExecutionSnapshot(plan_id="p", as_of=2, base_as_of=0))
    with pytest.raises(ValueError, match="execution evidence"):
        diagnose_detailed(inst, base, None, context=context)


def test_done_early_keeps_observed_duration_when_unfrozen() -> None:
    from scheduler_core.models import ReplanParams
    from scheduler_core.replanning.model import solve_neighborhood
    from scheduler_core.validation_context import ExecutionRecord

    inst = instance(duration=4, deadline=2)
    inst.now = 2
    inst.tasks[0].status = "DONE"
    base = Plan(id="p", assignments={"X": Assignment(task_id="X", device_id="D", start=0, end=2)})
    record = ExecutionRecord(
        task_id="X", status="DONE", device_id="D", start=0, actual_end=2, event_id="done"
    )
    ctx = ValidationContext(
        snapshot=ExecutionSnapshot(plan_id="p", as_of=2, base_as_of=2, records=[record])
    )
    groups = {"frozen:X", "deadline:X", "capacity:D"}
    for enabled in (groups, groups - {"frozen:X"}, set()):
        result = solve_neighborhood(
            inst,
            base,
            set(),
            {"X"},
            ctx,
            set(),
            ReplanParams(num_workers=1),
            2,
            enabled_groups=enabled,
        )
        assert result.status == "OPTIMAL" and result.assignments is not None
        assignment = result.assignments["X"]
        assert assignment.end - assignment.start == 2
    assert diagnose_detailed(inst, base, None, context=ctx).status == "FEASIBLE"


def test_running_overrun_keeps_expected_duration_when_unfrozen() -> None:
    from scheduler_core.models import ReplanParams
    from scheduler_core.replanning.model import solve_neighborhood
    from scheduler_core.validation_context import ExecutionRecord

    inst = instance(duration=2, deadline=5)
    inst.now = 2
    inst.tasks[0].status = "RUNNING"
    base = Plan(id="p", assignments={"X": Assignment(task_id="X", device_id="D", start=1, end=3)})
    record = ExecutionRecord(
        task_id="X",
        status="RUNNING",
        device_id="D",
        start=1,
        planned_end=3,
        remaining_estimate=4,
        event_id="overrun",
    )
    ctx = ValidationContext(
        snapshot=ExecutionSnapshot(plan_id="p", as_of=2, base_as_of=0, records=[record])
    )
    groups = {"frozen:X", "deadline:X", "capacity:D"}
    fixed = solve_neighborhood(
        inst, base, set(), {"X"}, ctx, set(), ReplanParams(num_workers=1), 2, enabled_groups=groups
    )
    assert fixed.status == "INFEASIBLE"
    released = solve_neighborhood(
        inst,
        base,
        set(),
        {"X"},
        ctx,
        set(),
        ReplanParams(num_workers=1),
        2,
        enabled_groups=groups - {"frozen:X"},
    )
    assert released.status == "OPTIMAL" and released.assignments is not None
    assignment = released.assignments["X"]
    assert assignment.end - assignment.start == 5
    result = diagnose_detailed(inst, base, None, context=ctx)
    assert result.status == "CORE" and result.minimal and result.core is not None
    assert set(result.core.group_ids) == {"deadline:X", "frozen:X"}
