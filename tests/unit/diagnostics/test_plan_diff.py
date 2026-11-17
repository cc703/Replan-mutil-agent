from datetime import datetime, timezone

from scheduler_core.axis import TimeAxis
from scheduler_core.models import Assignment, Instance, Plan
from scheduler_core.plan_diff import diff_plans


def a(tid: str, device: str, start: int, person: str | None = None) -> Assignment:
    return Assignment(task_id=tid, device_id=device, start=start, end=start + 1, person_id=person)


def test_changes_and_input_isolation() -> None:
    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=20),
        devices=[],
        tasks=[],
    )
    old = Plan(id="old", assignments={"a": a("a", "d", 1, "p"), "r": a("r", "d", 2)})
    new = Plan(id="new", assignments={"a": a("a", "e", 4, "q"), "n": a("n", "d", 0)})
    changes = diff_plans(inst, old, new)
    assert [c.task_id for c in changes] == ["a", "n", "r"]
    assert changes[0].moved and changes[0].device_changed and changes[0].person_changed
    assert changes[0].start_delta == 3
    assert changes[1].added and changes[2].removed
    assert changes[0].before is not old.assignments["a"]
