from typing import Any

from datetime import datetime, timezone

from scheduler_core.axis import TimeAxis
from scheduler_core.models import Assignment, Device, Instance, Plan, Task
from simulator.engine import Simulator
from simulator.scenarios import Scenario


def test_uncontended_overrun_extends_plan_without_callback() -> None:
    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=30),
        devices=[Device(id="d", type="x")],
        tasks=[Task(id="a", experiment_id="e", type="x", duration=3, compatible_devices=["d"])],
    )
    plan = Plan(id="p", assignments={"a": Assignment(task_id="a", device_id="d", start=0, end=3)})
    simulator = Simulator(
        inst,
        plan,
        Scenario(duration_sigma=0.0, duration_factor_min=1.5, duration_factor_max=1.5),
        lambda *_: None,
        1,
    )
    result = simulator.run(7)
    assert result.final_plan.id == "p.ov1"
    assert result.final_plan.parent_id == "p"
    assert result.final_plan.assignments["a"].end == 5
    assert result.final_instance.tasks[0].status == "DONE"
    assert result.counters.get("replan_calls", 0) == 0


def test_overrun_conflict_triggers_replanning_and_blocks_successor() -> None:
    from simulator.replay import replay

    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=30),
        devices=[Device(id="d", type="x")],
        tasks=[
            Task(id="a", experiment_id="e", type="x", duration=3, compatible_devices=["d"]),
            Task(id="b", experiment_id="e", type="x", duration=2, compatible_devices=["d"]),
        ],
    )
    plan = Plan(
        id="p",
        assignments={
            "a": Assignment(task_id="a", device_id="d", start=0, end=3),
            "b": Assignment(task_id="b", device_id="d", start=3, end=5),
        },
    )
    calls = []

    def callback(post: Any, base: Any, batch: Any) -> Any:
        calls.append((post, base, batch))
        return None

    scenario = Scenario(duration_sigma=0.0, duration_factor_min=1.5, duration_factor_max=1.5)
    result = Simulator(inst, plan, scenario, callback, 1).run(5)
    assert result.final_plan.id == "p"
    assert result.final_instance.tasks[1].status == "SCHEDULED"
    assert len(calls) == 1
    assert len(calls[0][2]) == 2
    assert calls[0][2][0].payload.new_end == 5
    assert replay(result.log) == result


def test_overrun_deadline_precedence_and_person_conflicts_trigger() -> None:
    from scheduler_core.models import Person, Precedence

    for conflict in ("deadline", "precedence", "person"):
        a = Task(
            id="a",
            experiment_id="e",
            type="x",
            duration=3,
            compatible_devices=["d1"],
            deadline=3 if conflict == "deadline" else None,
            requires_person=conflict == "person",
        )
        tasks = [a]
        assignments = {
            "a": Assignment(
                task_id="a",
                device_id="d1",
                start=0,
                end=3,
                person_id="p" if conflict == "person" else None,
            )
        }
        precedences = []
        persons = [Person(id="p")] if conflict == "person" else []
        if conflict != "deadline":
            tasks.append(
                Task(
                    id="b",
                    experiment_id="e",
                    type="x",
                    duration=2,
                    compatible_devices=["d2"],
                    requires_person=conflict == "person",
                )
            )
            assignments["b"] = Assignment(
                task_id="b",
                device_id="d2",
                start=3,
                end=5,
                person_id="p" if conflict == "person" else None,
            )
        if conflict == "precedence":
            precedences.append(Precedence(pred="a", succ="b"))
        inst = Instance(
            axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=30),
            devices=[Device(id="d1", type="x"), Device(id="d2", type="x")],
            tasks=tasks,
            persons=persons,
            precedences=precedences,
        )
        scenario = Scenario(duration_sigma=0.0, duration_factor_min=1.5, duration_factor_max=1.5)
        result = Simulator(
            inst, Plan(id="p", assignments=assignments), scenario, lambda *_: None, 1
        ).run(5)
        assert result.final_plan.id == "p", conflict
        assert result.counters["replan_calls"] == 1, conflict
