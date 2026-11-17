from scheduler_core.diagnose import diagnose_detailed
from scheduler_core.models import Task
from tests.unit.diagnostics.test_diagnose_cases import instance
from tests.unit.diagnostics.tiny_oracle import feasible


def test_core_has_independent_minimality_proof() -> None:
    inst = instance(duration=2, deadline=3, horizon=5)
    inst.tasks.append(
        Task(id="Y", experiment_id="e", type="t", duration=2, deadline=3, compatible_devices=["D"])
    )
    result = diagnose_detailed(inst, None, None)
    assert result.status == "CORE" and result.minimal and result.core is not None
    core = set(result.core.group_ids)
    assert core == {"deadline:X", "deadline:Y", "capacity:D"}
    assert not feasible(inst, core)
    assert all(feasible(inst, core - {group}) for group in core)
