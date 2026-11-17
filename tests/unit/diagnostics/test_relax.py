from tests.unit.diagnostics.test_diagnose_cases import instance
from scheduler_core.models import ConflictCore
from scheduler_core.relax import suggest_relaxations_detailed


def test_simple() -> None:
    inst = instance()
    inst.tasks[0].deadline_level = "NEGOTIABLE"
    result = suggest_relaxations_detailed(
        inst, None, None, ConflictCore(group_ids=["deadline:X"], descriptions=[])
    )
    assert len(result.proposals) == 1
    proposal = result.proposals[0]
    assert proposal.deltas == {"X": 1}
    assert proposal.option.cost == 1
    assert proposal.verified and proposal.optimal


def test_empty_core_still_checks_context_and_free() -> None:
    import pytest
    from scheduler_core.models import Assignment, Plan
    from scheduler_core.validation_context import ExecutionSnapshot, ValidationContext

    inst = instance()
    core = ConflictCore(group_ids=[], descriptions=[])
    base = Plan(id="base", assignments={})
    with pytest.raises(ValueError, match="snapshot"):
        suggest_relaxations_detailed(inst, base, None, core)

    inst.now = 1
    base = Plan(
        id="base", assignments={"X": Assignment(task_id="X", device_id="D", start=0, end=4)}
    )
    ctx = ValidationContext(snapshot=ExecutionSnapshot(plan_id="base", as_of=1, base_as_of=0))
    with pytest.raises(ValueError, match="free"):
        suggest_relaxations_detailed(inst, base, {"X"}, core, context=ctx)
    result = suggest_relaxations_detailed(inst, base, None, core, context=ctx)
    assert result.status == "NO_OPTIONS" and not result.proposals
