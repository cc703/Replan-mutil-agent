from typing import Any

from datetime import datetime, timezone

from scheduler_core.axis import TimeAxis
from scheduler_core.models import Assignment, Device, Instance, Plan, Task
from simulator.gate import ExecutionEvidence, check_candidate, context_for_plan


def test_running_extension_evidence_and_parent_gate() -> None:
    task = Task(
        id="a", experiment_id="e", type="x", duration=5, compatible_devices=["d"], status="RUNNING"
    )
    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=100),
        now=5,
        devices=[Device(id="d", type="x")],
        tasks=[task],
    )
    base = Plan(
        id="base", assignments={"a": Assignment(task_id="a", device_id="d", start=1, end=6)}
    )
    candidate = Plan(
        id="next",
        parent_id="base",
        assignments={"a": Assignment(task_id="a", device_id="d", start=1, end=9)},
    )
    evidence = ExecutionEvidence(
        task_id="a",
        status="RUNNING",
        device_id="d",
        person_id=None,
        start=1,
        event_id="start",
        reported_end=9,
        overrun_event_id="overrun",
        overrun_at=5,
    )
    ctx = context_for_plan(base, candidate, 5, 0, [evidence])
    assert ctx.snapshot is not None
    assert (ctx.snapshot.plan_id, ctx.snapshot.as_of, ctx.snapshot.base_as_of) == ("base", 5, 0)
    record = ctx.snapshot.records[0]
    assert (
        record.status,
        record.device_id,
        record.person_id,
        record.start,
        record.planned_end,
        record.remaining_estimate,
        record.event_id,
    ) == ("RUNNING", "d", None, 1, 6, 4, "start")
    change = ctx.end_changes[0]
    assert (
        change.task_id,
        change.plan_id,
        change.base_plan_id,
        change.old_end,
        change.new_end,
        change.event_id,
        change.acted_at,
    ) == ("a", "next", "base", 6, 9, "overrun", 5)
    assert check_candidate(inst, base, candidate, ctx) == (True, None, None)
    bad = candidate.model_copy(update={"parent_id": "other"})
    assert check_candidate(inst, base, bad, ctx)[1] == "PARENT"


def test_urgent_replan_is_independently_validated_and_adopted() -> None:
    from scheduler_core.models import UrgentInsert
    from simulator.engine import Simulator
    from simulator.scenarios import Scenario

    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=30),
        devices=[Device(id="d", type="x")],
        tasks=[Task(id="a", experiment_id="e", type="x", duration=2, compatible_devices=["d"])],
    )
    plan = Plan(id="p", assignments={"a": Assignment(task_id="a", device_id="d", start=0, end=2)})
    urgent = Task(id="u", experiment_id="u", type="x", duration=2, compatible_devices=["d"])

    def schedule(post: Any, base: Any, _batch: Any) -> Any:
        assert any(t.id == "u" for t in post.tasks)
        assignments = dict(base.assignments)
        assignments["u"] = Assignment(task_id="u", device_id="d", start=post.now, end=post.now + 2)
        return Plan(id="p2", parent_id=base.id, assignments=assignments)

    engine = Simulator(inst, plan, Scenario(duration_sigma=0.0), schedule, 1)
    engine.inject(UrgentInsert(tasks=[urgent]), 3)
    result = engine.run(7)
    assert result.final_plan.id == "p2"
    assert [task.status for task in result.final_instance.tasks] == ["DONE", "DONE"]


def test_gate_rejects_omitted_urgent_task() -> None:
    from simulator.gate import check_candidate
    from scheduler_core.validation_context import ValidationContext

    a = Task(id="a", experiment_id="e", type="x", duration=2, compatible_devices=["d"])
    urgent = Task(id="u", experiment_id="u", type="x", duration=2, compatible_devices=["d"])
    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=30),
        devices=[Device(id="d", type="x")],
        tasks=[a, urgent],
    )
    assignments = {"a": Assignment(task_id="a", device_id="d", start=0, end=2)}
    base = Plan(id="p", assignments=assignments)
    candidate = Plan(id="p2", parent_id="p", assignments=assignments)
    accepted, code, _reason = check_candidate(inst, base, candidate, ValidationContext())
    assert not accepted
    assert code == "V1"


def test_done_snapshot_fields_and_history_rewrite_rejected() -> None:
    task = Task(
        id="a", experiment_id="e", type="x", duration=5, compatible_devices=["d"], status="DONE"
    )
    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=30),
        now=8,
        devices=[Device(id="d", type="x")],
        tasks=[task],
    )
    base = Plan(
        id="base", assignments={"a": Assignment(task_id="a", device_id="d", start=1, end=6)}
    )
    changed = Plan(
        id="next",
        parent_id="base",
        assignments={"a": Assignment(task_id="a", device_id="d", start=2, end=6)},
    )
    evidence = ExecutionEvidence(
        task_id="a",
        status="DONE",
        device_id="d",
        person_id=None,
        start=1,
        event_id="end:13",
        actual_end=6,
    )
    ctx = context_for_plan(base, changed, 8, 7, [evidence])
    assert ctx.snapshot is not None
    record = ctx.snapshot.records[0]
    assert (record.status, record.start, record.actual_end, record.event_id) == (
        "DONE",
        1,
        6,
        "end:13",
    )
    assert not check_candidate(inst, base, changed, ctx)[0]


def test_gate_rejects_device_overlap_and_person_skill() -> None:
    from scheduler_core.models import Person
    from scheduler_core.validation_context import ValidationContext

    tasks = [
        Task(
            id=tid,
            experiment_id="e",
            type="x",
            duration=2,
            compatible_devices=["d"],
            required_skills={"trained"},
        )
        for tid in ("a", "b")
    ]
    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=30),
        devices=[Device(id="d", type="x")],
        persons=[Person(id="p", skills={"trained"}), Person(id="untrained")],
        tasks=tasks,
    )
    base = Plan(
        id="base",
        assignments={
            "a": Assignment(task_id="a", device_id="d", person_id="p", start=0, end=2),
            "b": Assignment(task_id="b", device_id="d", person_id="p", start=2, end=4),
        },
    )
    overlap = Plan(
        id="overlap",
        parent_id="base",
        assignments={
            "a": base.assignments["a"],
            "b": Assignment(task_id="b", device_id="d", person_id="p", start=1, end=3),
        },
    )
    assert check_candidate(inst, base, overlap, ValidationContext())[1] == "V2"
    bad_skill = Plan(
        id="skill",
        parent_id="base",
        assignments={
            "a": base.assignments["a"],
            "b": Assignment(task_id="b", device_id="d", person_id="untrained", start=2, end=4),
        },
    )
    assert check_candidate(inst, base, bad_skill, ValidationContext())[1] == "V7"
