import json
import pytest
from pydantic import TypeAdapter, ValidationError
from scheduler_core.models import (
    Assignment,
    Device,
    Event,
    Instance,
    Person,
    Plan,
    PlanMetrics,
    Precedence,
    Task,
    TimeAxis,
)


def task(**kwargs: object) -> Task:
    return Task.model_validate(
        {
            "id": "t",
            "experiment_id": "e",
            "type": "x",
            "duration": 1,
            "compatible_devices": ["missing"],
            **kwargs,
        }
    )


def test_old_json_and_isolated_defaults() -> None:
    raw = {
        "axis": {"t0": "2026-01-01T00:00:00Z", "horizon_slots": 4},
        "devices": [],
        "tasks": [task().model_dump(exclude={"required_skills", "requires_person"})],
    }
    inst = Instance.model_validate_json(json.dumps(raw))
    assert inst.persons == [] and not inst.tasks[0].needs_person
    assert Instance.model_validate_json(inst.model_dump_json()) == inst
    a, b = Person(id="a"), Person(id="b")
    a.skills.add("x")
    assert b.skills == set()


def test_structural_boundaries_and_business_cases() -> None:
    axis = TimeAxis.model_validate({"t0": "2026-01-01T00:00:00Z", "horizon_slots": 10})
    t = task(requires_person=True, deadline=0, release=4)
    inst = Instance(axis=axis, devices=[], tasks=[t], persons=[])
    assert inst.tasks[0].needs_person
    assert (
        Assignment(task_id="t", device_id="missing", person_id="unknown", start=0, end=1).person_id
        == "unknown"
    )
    other = task(id="u")
    assert (
        len(
            Instance(
                axis=axis,
                devices=[],
                tasks=[t, other],
                precedences=[Precedence(pred="t", succ="u"), Precedence(pred="u", succ="t")],
            ).precedences
        )
        == 2
    )
    for data in ({"duration": 0}, {"release": True}, {"release": 1.0}):
        with pytest.raises(ValidationError):
            task(**data)
    with pytest.raises(ValidationError):
        Device(id="x", type="x", capacity=0)
    with pytest.raises(ValidationError):
        Instance(axis=axis, devices=[], tasks=[t, t])
    with pytest.raises(ValidationError):
        Instance(
            axis=axis, devices=[], tasks=[t], precedences=[Precedence(pred="t", succ="missing")]
        )
    with pytest.raises(ValidationError):
        Assignment(task_id="t", device_id="d", start=1, end=1)
    with pytest.raises(ValidationError):
        Plan(id="p", assignments={"wrong": Assignment(task_id="t", device_id="d", start=0, end=1)})
    for number in (-1.0, float("nan"), float("inf")):
        with pytest.raises(ValidationError):
            PlanMetrics(tardiness=number)


def test_discriminated_event() -> None:
    adapter: TypeAdapter[Event] = TypeAdapter(Event)
    assert (
        adapter.validate_python({"type": "TASK_OVERRUN", "task_id": "t", "new_end": 3}).type
        == "TASK_OVERRUN"
    )
    with pytest.raises(ValidationError):
        adapter.validate_python({"type": "UNKNOWN"})


def test_person_fields_reject_empty() -> None:
    with pytest.raises(ValidationError):
        Person(id="")
    with pytest.raises(ValidationError):
        Person(id="p", skills={""})
    with pytest.raises(ValidationError):
        task(required_skills={""})


def test_default_containers_do_not_alias() -> None:
    from scheduler_core.models import RelaxationOption, ReplanParams, ReplanResult, ValidationReport

    x, y = ReplanParams(), ReplanParams()
    x.weight_grid.append((9, 9))
    assert len(y.weight_grid) == 4 and y.num_workers == 8
    a, b = ReplanResult(status="OK"), ReplanResult(status="OK")
    a.relaxations.append(RelaxationOption(description="x", cost=1, relaxed_groups=[]))
    assert b.relaxations == []
    first, second = ValidationReport(passed=True), ValidationReport(passed=True)
    first.violations.clear()
    assert first.violations is not second.violations


def test_export_and_defaults_contract() -> None:
    from scheduler_core import models as m

    expected = {
        "TimeAxis",
        "Device",
        "Task",
        "Precedence",
        "BlockedWindow",
        "SetupRule",
        "Instance",
        "Assignment",
        "PlanMetrics",
        "Plan",
        "DeviceOutage",
        "UrgentInsert",
        "TaskOverrun",
        "Violation",
        "ValidationReport",
        "ReplanParams",
        "ImpactReport",
        "Candidate",
        "ConflictCore",
        "RelaxationOption",
        "ReplanResult",
        "Slot",
        "Event",
        "Person",
        "PersonBlockedWindow",
    }
    assert set(m.__all__) == expected
    assert all(hasattr(m, name) for name in expected)
    assert task().model_dump(
        exclude={"id", "experiment_id", "type", "duration", "compatible_devices"}
    ) == {
        "release": 0,
        "deadline": None,
        "deadline_level": "NEGOTIABLE",
        "weight": 1.0,
        "preemptible": False,
        "status": "PENDING",
        "demand": 1,
        "required_skills": set(),
        "requires_person": False,
    }
    assert m.ReplanParams().model_dump() == {
        "alpha": 1.0,
        "beta_moved": 2.0,
        "beta_switched": 5.0,
        "beta_shift": 0.1,
        "gamma": 5.0,
        "total_budget_s": 10.0,
        "window_slots": 48,
        "max_level": 3,
        "weight_grid": [(1, 0.5), (1, 1), (1, 2), (1, 4)],
        "seed": 0,
        "num_workers": 8,
    }
    assert m.Device(id="d", type="x").model_dump() == {
        "id": "d",
        "type": "x",
        "capacity": 1,
        "capabilities": set(),
    }
    assert m.Precedence(pred="a", succ="b").model_dump() == {
        "pred": "a",
        "succ": "b",
        "lag_min": 0,
        "lag_max": None,
    }
    assert m.Plan(id="p", assignments={}).metrics == m.PlanMetrics()
    assert m.ValidationReport(passed=True).violations == []
    assert m.ReplanResult(status="OK").model_dump() == {
        "status": "OK",
        "candidates": [],
        "impact": None,
        "level_reached": None,
        "conflict": None,
        "relaxations": [],
    }


@pytest.mark.parametrize(
    "field",
    [
        "tardiness",
        "makespan",
        "moved",
        "switched",
        "shift_total",
        "urgent_delay",
        "solve_seconds",
        "gap",
    ],
)
def test_metrics_reject_invalid(field: str) -> None:
    for value in (-1, float("nan"), float("inf")):
        with pytest.raises(ValidationError):
            PlanMetrics.model_validate({field: value})


@pytest.mark.parametrize(
    "payload",
    [
        {"type": "DEVICE_OUTAGE", "device_id": "d", "start": 0, "end": 1},
        {"type": "URGENT_INSERT", "tasks": []},
        {"type": "TASK_OVERRUN", "task_id": "t", "new_end": 1},
    ],
)
def test_each_event(payload: dict[str, object]) -> None:
    adapter: TypeAdapter[Event] = TypeAdapter(Event)
    assert adapter.validate_python(payload).type == payload["type"]


def test_more_default_isolation() -> None:
    from scheduler_core.models import BlockedWindow, PersonBlockedWindow, UrgentInsert

    d1, d2 = Device(id="1", type="x"), Device(id="2", type="x")
    d1.capabilities.add("x")
    assert not d2.capabilities
    t1, t2 = task(), task()
    t1.required_skills.add("x")
    t1.compatible_devices.append("d")
    assert not t2.required_skills and t2.compatible_devices == ["missing"]
    p1, p2 = Person(id="1"), Person(id="2")
    p1.blocked.append(PersonBlockedWindow(start=0, end=1))
    assert not p2.blocked
    axis = TimeAxis.model_validate({"t0": "2026-01-01T00:00:00Z", "horizon_slots": 2})
    i1, i2 = Instance(axis=axis, devices=[], tasks=[]), Instance(axis=axis, devices=[], tasks=[])
    i1.persons.append(p1)
    i1.blocked.append(BlockedWindow(device_id="d", start=0, end=1, kind="FAULT"))
    assert not i2.persons and not i2.blocked
    plan1, plan2 = Plan(id="1", assignments={}), Plan(id="2", assignments={})
    plan1.metrics.moved = 1
    assert plan2.metrics.moved == 0
    e1, e2 = UrgentInsert(tasks=[]), UrgentInsert(tasks=[])
    e1.precedences.append(Precedence(pred="a", succ="b"))
    assert not e2.precedences


def test_all_original_field_defaults() -> None:
    from pydantic_core import PydanticUndefined
    from scheduler_core import models as m

    expected: dict[str, dict[str, object]] = {
        "TimeAxis": {"slot_minutes": 5},
        "Device": {"capacity": 1, "capabilities": set()},
        "Task": {
            "release": 0,
            "deadline": None,
            "deadline_level": "NEGOTIABLE",
            "weight": 1.0,
            "preemptible": False,
            "status": "PENDING",
            "demand": 1,
            "required_skills": set(),
            "requires_person": False,
        },
        "Precedence": {"lag_min": 0, "lag_max": None},
        "BlockedWindow": {},
        "SetupRule": {},
        "Instance": {"now": 0, "precedences": [], "blocked": [], "setups": [], "persons": []},
        "Assignment": {"person_id": None},
        "PlanMetrics": {
            "tardiness": 0.0,
            "makespan": 0,
            "moved": 0,
            "switched": 0,
            "shift_total": 0,
            "urgent_delay": 0.0,
            "solve_seconds": 0.0,
            "gap": None,
        },
        "Plan": {"parent_id": None, "metrics": m.PlanMetrics()},
        "DeviceOutage": {"type": "DEVICE_OUTAGE"},
        "UrgentInsert": {"type": "URGENT_INSERT", "precedences": []},
        "TaskOverrun": {"type": "TASK_OVERRUN"},
        "Violation": {"task_ids": [], "device_id": None},
        "ValidationReport": {"violations": []},
        "ReplanParams": {
            "alpha": 1.0,
            "beta_moved": 2.0,
            "beta_switched": 5.0,
            "beta_shift": 0.1,
            "gamma": 5.0,
            "total_budget_s": 10.0,
            "window_slots": 48,
            "max_level": 3,
            "weight_grid": [(1, 0.5), (1, 1), (1, 2), (1, 4)],
            "seed": 0,
            "num_workers": 8,
        },
        "ImpactReport": {},
        "Candidate": {"label": None},
        "ConflictCore": {},
        "RelaxationOption": {},
        "ReplanResult": {
            "candidates": [],
            "impact": None,
            "level_reached": None,
            "conflict": None,
            "relaxations": [],
        },
        "Person": {"skills": set(), "blocked": []},
        "PersonBlockedWindow": {},
    }
    for name, defaults in expected.items():
        model = getattr(m, name)
        actual = {
            key: field.get_default(call_default_factory=True)
            for key, field in model.model_fields.items()
            if not field.is_required()
        }
        assert PydanticUndefined not in actual.values()
        assert actual == defaults, name
