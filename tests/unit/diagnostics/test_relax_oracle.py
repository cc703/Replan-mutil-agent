from scheduler_core.models import ConflictCore, Task
from scheduler_core.relax import suggest_relaxations_detailed
from scheduler_core.validate import validate
from tests.unit.diagnostics.test_diagnose_cases import instance


def test_exact_cost_incomparable_supports_and_double_validation() -> None:
    inst = instance(duration=2, deadline=3, horizon=5)
    inst.tasks[0].deadline_level = "NEGOTIABLE"
    inst.tasks[0].weight = 2
    inst.tasks.append(
        Task(
            id="Y",
            experiment_id="e",
            type="t",
            duration=2,
            deadline=3,
            compatible_devices=["D"],
            weight=1,
        )
    )
    result = suggest_relaxations_detailed(
        inst,
        None,
        None,
        ConflictCore(group_ids=["capacity:D", "deadline:X", "deadline:Y"], descriptions=[]),
    )
    assert len(result.proposals) == 2
    assert [(p.deltas, p.option.cost) for p in result.proposals] == [({"Y": 1}, 1), ({"X": 1}, 2)]
    for proposal in result.proposals:
        modified = inst.model_copy(deep=True)
        for task in modified.tasks:
            if task.id in proposal.deltas:
                assert task.deadline is not None
                task.deadline += proposal.deltas[task.id]
        assert validate(modified, proposal.plan).passed
        report = validate(inst, proposal.plan)
        assert not report.passed and all(v.code == "V5" for v in report.violations)
