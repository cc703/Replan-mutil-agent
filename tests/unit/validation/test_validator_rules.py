"""Acceptance checks for independent schedule validation."""

from scheduler_core.models import (
    Assignment,
    Device,
    Person,
    Plan,
    Precedence,
)
from scheduler_core.validate import validate
from scheduler_core.validation_context import (
    DeadlineAuthorization,
    ValidationContext,
)
import pytest


from .validation_helpers import instance, reasons


def test_missing_assignment() -> None:
    report = validate(instance(), Plan(id="p", assignments={}))
    assert any(
        v.code == "V1" and "reason=MISSING_ASSIGNMENT;" in v.detail and v.task_ids == ["a"]
        for v in report.violations
    )


@pytest.mark.parametrize(
    "token",
    [
        "MISSING_ASSIGNMENT",
        "UNKNOWN_TASK",
        "UNKNOWN_DEVICE",
        "DEVICE_NOT_COMPATIBLE",
        "EMPTY_COMPATIBLE_LIST",
        "UNKNOWN_DEVICE_REF",
        "TASK_NOT_SCHEDULABLE",
    ],
)
def test_v1_reason_matrix(token: str) -> None:
    inst = instance()
    inst.tasks = inst.tasks[:1]
    plan = Plan(id="p", assignments={"a": Assignment(task_id="a", device_id="d", start=0, end=4)})
    assert not reasons(validate(inst, plan), "V1", token)
    if token == "MISSING_ASSIGNMENT":
        plan.assignments.clear()
        ids = ["a"]
    elif token == "UNKNOWN_TASK":
        plan.assignments["z"] = Assignment(task_id="z", device_id="d", start=5, end=9)
        ids = ["z"]
    elif token == "UNKNOWN_DEVICE":
        plan.assignments["a"].device_id = "z"
        ids = ["a"]
    elif token == "DEVICE_NOT_COMPATIBLE":
        inst.devices.append(Device(id="z", type="x"))
        plan.assignments["a"].device_id = "z"
        ids = ["a"]
    elif token == "EMPTY_COMPATIBLE_LIST":
        inst.tasks[0].compatible_devices = []
        ids = ["a"]
    elif token == "UNKNOWN_DEVICE_REF":
        inst.tasks[0].compatible_devices.append("z")
        ids = ["a"]
    else:
        inst.tasks[0].status = "FAILED"
        ids = ["a"]
    assert reasons(validate(inst, plan), "V1", token) == [ids]


@pytest.mark.parametrize("status", ["FAILED", "CANCELLED", "INTERRUPTED"])
def test_unschedulable_statuses(status: str) -> None:
    inst = instance()
    inst.tasks = inst.tasks[:1]
    inst.tasks[0].status = status  # type: ignore[assignment]
    plan = Plan(id="p", assignments={})
    assert validate(inst, plan).passed
    plan.assignments["a"] = Assignment(task_id="a", device_id="d", start=0, end=4)
    assert reasons(validate(inst, plan), "V1", "TASK_NOT_SCHEDULABLE") == [["a"]]


@pytest.mark.parametrize(
    "token",
    ["PRECEDENCE_MIN_LAG", "PRECEDENCE_MAX_LAG", "PRECEDENCE_UNKNOWN_TASK", "PRECEDENCE_CYCLE"],
)
def test_precedence_reasons_and_boundaries(token: str) -> None:
    inst = instance()
    inst.devices.append(Device(id="e", type="x"))
    inst.tasks[1].compatible_devices.append("e")
    plan = Plan(
        id="p",
        assignments={
            "a": Assignment(task_id="a", device_id="d", start=0, end=4),
            "b": Assignment(task_id="b", device_id="e", start=5, end=9),
        },
    )
    inst.precedences = [Precedence(pred="a", succ="b", lag_min=1, lag_max=1)]
    assert validate(inst, plan).passed
    if token == "PRECEDENCE_MIN_LAG":
        plan.assignments["b"] = plan.assignments["b"].model_copy(update={"start": 4, "end": 8})
    elif token == "PRECEDENCE_MAX_LAG":
        plan.assignments["b"] = plan.assignments["b"].model_copy(update={"start": 6, "end": 10})
    elif token == "PRECEDENCE_UNKNOWN_TASK":
        inst.precedences.append(Precedence(pred="a", succ="z"))
    else:
        inst.precedences.append(Precedence(pred="b", succ="a"))
    ids = ["a", "z"] if token == "PRECEDENCE_UNKNOWN_TASK" else ["a", "b"]
    assert reasons(validate(inst, plan), "V3", token) == [ids]


@pytest.mark.parametrize(
    "token",
    [
        "DEADLINE_EXCEEDED",
        "AUTH_NOT_APPLICABLE",
        "AUTH_EXPIRED",
        "AUTH_FUTURE",
        "AUTH_OUT_OF_SCOPE",
        "AUTH_DUPLICATE",
    ],
)
def test_deadline_authorization_matrix(token: str) -> None:
    inst = instance()
    inst.tasks = inst.tasks[:1]
    inst.now = 2
    inst.tasks[0].deadline = 5
    plan = Plan(id="p", assignments={"a": Assignment(task_id="a", device_id="d", start=2, end=6)})
    auth = DeadlineAuthorization(
        task_id="a",
        plan_id="p",
        original_deadline=5,
        relaxed_deadline=6,
        confirmation_id="human",
        acted_at=1,
        valid_until=3,
    )
    ctx = ValidationContext(deadline_authorizations=[auth])
    assert validate(inst, plan, context=ctx).passed
    if token == "DEADLINE_EXCEEDED":
        ctx.deadline_authorizations = []
    elif token == "AUTH_NOT_APPLICABLE":
        inst.tasks[0].deadline_level = "HARD"
    elif token == "AUTH_EXPIRED":
        auth.valid_until = 1
    elif token == "AUTH_FUTURE":
        auth.acted_at = 3
    elif token == "AUTH_OUT_OF_SCOPE":
        auth.plan_id = "wrong"
    else:
        ctx.deadline_authorizations.append(auth.model_copy())
    assert reasons(validate(inst, plan, context=ctx), "V5", token) == [["a"]]


def test_authorization_unknown_wrong_original_and_hard() -> None:
    inst = instance()
    inst.tasks = inst.tasks[:1]
    inst.tasks[0].deadline = 4
    plan = Plan(id="p", assignments={"a": Assignment(task_id="a", device_id="d", start=0, end=4)})
    auth = DeadlineAuthorization(
        task_id="z",
        plan_id="p",
        original_deadline=4,
        relaxed_deadline=6,
        confirmation_id="c",
        acted_at=0,
    )
    ctx = ValidationContext(deadline_authorizations=[auth])
    assert reasons(validate(inst, plan, context=ctx), "V5", "AUTH_NOT_APPLICABLE") == [["z"]]
    auth.task_id = "a"
    auth.original_deadline = 3
    assert reasons(validate(inst, plan, context=ctx), "V5", "AUTH_OUT_OF_SCOPE") == [["a"]]
    auth.original_deadline = 4
    assert validate(inst, plan, context=ctx).passed


@pytest.mark.parametrize("source", ["plan", "base"])
def test_assignment_key_mismatch_after_mutation(source: str) -> None:
    inst = instance()
    plan = Plan(
        id="p",
        assignments={
            "a": Assignment(task_id="a", device_id="d", start=0, end=4),
            "b": Assignment(task_id="b", device_id="d", start=4, end=8),
        },
    )
    base = plan.model_copy(deep=True)
    base.id = "base"
    plan.parent_id = "base"
    assert not reasons(validate(inst, plan, base=base), "V1", "ASSIGNMENT_KEY_MISMATCH")
    target = plan if source == "plan" else base
    target.assignments["a"].task_id = "b"
    report = validate(inst, plan, base=base)
    assert reasons(report, "V1", "ASSIGNMENT_KEY_MISMATCH") == [["a", "b"]]
    assert any(
        f"source={source};" in v.detail
        for v in report.violations
        if "reason=ASSIGNMENT_KEY_MISMATCH;" in v.detail
    )


@pytest.mark.parametrize(
    "token",
    [
        "PARENT_MISMATCH",
        "BASE_REQUIRED",
        "FREE_UNKNOWN_TASK",
        "FREE_CONTAINS_FROZEN",
        "ADDED_NOT_FREE",
        "REMOVED_NOT_FREE",
        "BASE_TASK_UNKNOWN",
        "NONFREE_CHANGED",
    ],
)
def test_neighborhood_reasons(token: str) -> None:
    inst = instance()
    plan = Plan(
        id="p",
        parent_id="base",
        assignments={
            "a": Assignment(task_id="a", device_id="d", start=0, end=4),
            "b": Assignment(task_id="b", device_id="d", start=4, end=8),
        },
    )
    base = plan.model_copy(deep=True)
    base.id = "base"
    assert validate(inst, plan, base=base, free=set()).passed
    free: set[str] | None = set()
    effective_base: Plan | None = base
    ids: list[str] = []
    if token == "PARENT_MISMATCH":
        plan.parent_id = "wrong"
    elif token == "BASE_REQUIRED":
        effective_base = None
    elif token == "FREE_UNKNOWN_TASK":
        free = {"z"}
        ids = ["z"]
    elif token == "FREE_CONTAINS_FROZEN":
        inst.now = 1
        free = {"a"}
        ids = ["a"]
    elif token == "ADDED_NOT_FREE":
        del base.assignments["b"]
        ids = ["b"]
    elif token == "REMOVED_NOT_FREE":
        del plan.assignments["b"]
        ids = ["b"]
    elif token == "BASE_TASK_UNKNOWN":
        base.assignments["z"] = Assignment(task_id="z", device_id="d", start=9, end=10)
        ids = ["z"]
    else:
        plan.assignments["b"] = plan.assignments["b"].model_copy(update={"start": 5, "end": 9})
        ids = ["b"]
    assert reasons(validate(inst, plan, base=effective_base, free=free), "V11", token) == [ids]
    if token == "NONFREE_CHANGED":
        assert not reasons(validate(inst, plan, base=base, free=None), "V11", token)
        assert not reasons(validate(inst, plan, base=base, free={"b"}), "V11", token)


@pytest.mark.parametrize(
    "kind,code,token,ids",
    [
        ("task", "V1", "DUPLICATE_TASK_ID", ["a"]),
        ("device", "V1", "DUPLICATE_DEVICE_ID", []),
        ("person", "V7", "DUPLICATE_PERSON_ID", []),
    ],
)
def test_duplicate_ids_after_mutation(kind: str, code: str, token: str, ids: list[str]) -> None:
    inst = instance()
    inst.persons = [Person(id="p")]
    plan = Plan(
        id="p",
        assignments={
            "a": Assignment(task_id="a", device_id="d", start=0, end=4),
            "b": Assignment(task_id="b", device_id="d", start=4, end=8),
        },
    )
    assert not reasons(validate(inst, plan), code, token)
    if kind == "task":
        inst.tasks.append(inst.tasks[0].model_copy(deep=True))
    elif kind == "device":
        inst.devices.append(inst.devices[0].model_copy(deep=True))
    else:
        inst.persons.append(inst.persons[0].model_copy(deep=True))
    report = validate(inst, plan)
    assert reasons(report, code, token) == [ids]
    violation = next(v for v in report.violations if f"reason={token};" in v.detail)
    if kind == "device":
        assert violation.device_id == "d"
    if kind == "person":
        assert "person_id=p;" in violation.detail
    inst.tasks.reverse()
    inst.devices.reverse()
    inst.persons.reverse()
    assert validate(inst, plan) == report


def test_model_construct_invalid_references_and_cycle() -> None:
    inst = instance()
    inst.tasks[0].compatible_devices = []
    inst.precedences = [
        Precedence.model_construct(pred="a", succ="z", lag_min=0, lag_max=None),
        Precedence(pred="a", succ="b"),
        Precedence(pred="b", succ="a"),
    ]
    plan = Plan(
        id="p",
        assignments={
            "a": Assignment(task_id="a", device_id="d", start=0, end=4),
            "b": Assignment(task_id="b", device_id="d", start=4, end=8),
        },
    )
    report = validate(inst, plan)
    assert reasons(report, "V1", "EMPTY_COMPATIBLE_LIST") == [["a"]]
    assert reasons(report, "V3", "PRECEDENCE_UNKNOWN_TASK") == [["a", "z"]]
    assert reasons(report, "V3", "PRECEDENCE_CYCLE") == [["a", "b"]]
    inst.tasks[0].compatible_devices = ["d"]
    inst.precedences = []
    assert validate(inst, plan).passed
