"""Acceptance checks for independent schedule validation."""

from scheduler_core.models import (
    Assignment,
    BlockedWindow,
    Device,
    Person,
    PersonBlockedWindow,
    Plan,
    SetupRule,
)
from scheduler_core.validate import validate
import pytest


from .validation_helpers import instance, reasons


def test_overlap_and_half_open_boundary() -> None:
    inst = instance()
    plan = Plan(
        id="p",
        assignments={
            "a": Assignment(task_id="a", device_id="d", start=0, end=4),
            "b": Assignment(task_id="b", device_id="d", start=3, end=7),
        },
    )
    report = validate(inst, plan)
    assert any(
        v.code == "V2" and "reason=DEVICE_OVERLAP;" in v.detail and v.task_ids == ["a", "b"]
        for v in report.violations
    )
    plan.assignments["b"] = Assignment(task_id="b", device_id="d", start=4, end=8)
    assert validate(inst, plan).passed


def test_single_demand_above_capacity_only_v9() -> None:
    inst = instance()
    inst.tasks = inst.tasks[:1]
    inst.tasks[0].demand = 2
    plan = Plan(id="p", assignments={"a": Assignment(task_id="a", device_id="d", start=0, end=4)})
    report = validate(inst, plan)
    assert reasons(report, "V9", "DEMAND_EXCEEDS_CAPACITY") == [["a"]]
    assert not reasons(report, "V2", "DEVICE_OVERLAP")
    inst.tasks[0].demand = 1
    assert validate(inst, plan).passed


def test_setup_calendar_and_half_open() -> None:
    inst = instance()
    inst.tasks = inst.tasks[:1]
    inst.setups = [SetupRule(device_id="d", task_type="x", slots=2)]
    plan = Plan(id="p", assignments={"a": Assignment(task_id="a", device_id="d", start=0, end=4)})
    report = validate(inst, plan)
    assert reasons(report, "V6", "SETUP_BEFORE_ORIGIN") == [["a"]]
    assert not reasons(report, "V2", "DEVICE_OVERLAP")
    plan.assignments["a"] = plan.assignments["a"].model_copy(update={"start": 3, "end": 7})
    inst.blocked = [
        BlockedWindow(device_id="d", kind="FAULT", start=0, end=2),
        BlockedWindow(device_id="d", kind="MAINT", start=1, end=2),
    ]
    assert reasons(validate(inst, plan), "V6", "CALENDAR_BLOCKED") == [["a"]]
    plan.assignments["a"] = plan.assignments["a"].model_copy(update={"start": 4, "end": 8})
    assert validate(inst, plan).passed


def test_person_skill_and_calendar() -> None:
    inst = instance()
    inst.tasks = inst.tasks[:1]
    inst.tasks[0].required_skills = {"x", "y"}
    inst.persons = [Person(id="p", skills={"x"}, blocked=[PersonBlockedWindow(start=4, end=6)])]
    plan = Plan(id="p", assignments={"a": Assignment(task_id="a", device_id="d", start=0, end=4)})
    assert reasons(validate(inst, plan), "V7", "MISSING_PERSON") == [["a"]]
    plan.assignments["a"].person_id = "missing"
    assert reasons(validate(inst, plan), "V7", "UNKNOWN_PERSON") == [["a"]]
    plan.assignments["a"].person_id = "p"
    assert reasons(validate(inst, plan), "V7", "SKILL_MISSING") == [["a"]]
    inst.persons[0].skills.add("y")
    assert validate(inst, plan).passed
    plan.assignments["a"] = plan.assignments["a"].model_copy(update={"start": 1, "end": 5})
    assert reasons(validate(inst, plan), "V7", "PERSON_UNAVAILABLE") == [["a"]]
    inst.persons[0].blocked.clear()
    assert validate(inst, plan).passed


@pytest.mark.parametrize(
    "token",
    [
        "RELEASE_VIOLATED",
        "START_BEFORE_NOW",
        "HORIZON_EXCEEDED",
        "DURATION_MISMATCH",
        "SETUP_RULE_CONFLICT",
    ],
)
def test_time_and_setup_reason_matrix(token: str) -> None:
    inst = instance()
    inst.tasks = inst.tasks[:1]
    plan = Plan(id="p", assignments={"a": Assignment(task_id="a", device_id="d", start=2, end=6)})
    code = {
        "RELEASE_VIOLATED": "V4",
        "START_BEFORE_NOW": "V4",
        "HORIZON_EXCEEDED": "V6",
        "DURATION_MISMATCH": "V10",
        "SETUP_RULE_CONFLICT": "V2",
    }[token]
    assert not reasons(validate(inst, plan), code, token)
    if token == "RELEASE_VIOLATED":
        inst.tasks[0].release = 3
    elif token == "START_BEFORE_NOW":
        inst.now = 3
    elif token == "HORIZON_EXCEEDED":
        inst.axis.horizon_slots = 5
    elif token == "DURATION_MISMATCH":
        inst.tasks[0].duration = 5
    else:
        inst.setups = [
            SetupRule(device_id="d", task_type="x", slots=1),
            SetupRule(device_id="d", task_type="x", slots=2),
        ]
    assert reasons(validate(inst, plan), code, token) == (
        [[]] if token == "SETUP_RULE_CONFLICT" else [["a"]]
    )


def test_capacity_includes_setup_and_touching_boundary() -> None:
    inst = instance()
    inst.devices[0].capacity = 2
    inst.setups = [SetupRule(device_id="d", task_type="x", slots=1)]
    inst.tasks[0].demand = 2
    plan = Plan(
        id="p",
        assignments={
            "a": Assignment(task_id="a", device_id="d", start=1, end=5),
            "b": Assignment(task_id="b", device_id="d", start=5, end=9),
        },
    )
    assert reasons(validate(inst, plan), "V9", "CAPACITY_EXCEEDED") == [["a", "b"]]
    plan.assignments["b"] = plan.assignments["b"].model_copy(update={"start": 6, "end": 10})
    assert validate(inst, plan).passed


def test_optional_person_still_checked() -> None:
    inst = instance()
    inst.devices.append(Device(id="e", type="x"))
    inst.tasks[1].compatible_devices.append("e")
    inst.persons = [Person(id="p", blocked=[PersonBlockedWindow(start=0, end=1)])]
    plan = Plan(
        id="p",
        assignments={
            "a": Assignment(task_id="a", device_id="d", start=0, end=4, person_id="p"),
            "b": Assignment(task_id="b", device_id="e", start=1, end=5, person_id="p"),
        },
    )
    report = validate(inst, plan)
    assert reasons(report, "V7", "PERSON_UNAVAILABLE") == [["a"]]
    assert reasons(report, "V7", "PERSON_OVERLAP") == [["a", "b"]]
    plan.assignments["a"].person_id = None
    assert validate(inst, plan).passed
