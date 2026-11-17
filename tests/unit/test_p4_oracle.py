from datetime import datetime, timezone
from itertools import product

from scheduler_core.axis import TimeAxis
from scheduler_core.models import (
    Assignment,
    BlockedWindow,
    Device,
    Instance,
    Plan,
    ReplanParams,
    Task,
)
from scheduler_core.replanning.model import solve_neighborhood
from scheduler_core.validation_context import ExecutionSnapshot, ValidationContext


def test_three_task_objective_matches_finite_enumeration() -> None:
    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=10),
        devices=[Device(id="d", type="x")],
        tasks=[
            Task(
                id=x,
                experiment_id="e",
                type="x",
                duration=1,
                compatible_devices=["d"],
                deadline=9,
                weight=i + 1,
            )
            for i, x in enumerate("abc")
        ],
        blocked=[BlockedWindow(device_id="d", start=2, end=4, kind="FAULT")],
    )
    base = Plan(
        id="p",
        assignments={
            x: Assignment(task_id=x, device_id="d", start=i + 2, end=i + 3)
            for i, x in enumerate("abc")
        },
    )
    ctx = ValidationContext(snapshot=ExecutionSnapshot(plan_id="p", as_of=0, base_as_of=0))
    p = ReplanParams(alpha=1, beta_moved=2, beta_switched=5, beta_shift=1, gamma=3, num_workers=1)
    raw = solve_neighborhood(inst, base, set("abc"), set(), ctx, {"c"}, p, 5)
    assert raw.status == "OPTIMAL"
    values = []
    for starts in product(range(9), repeat=3):
        if len(set(starts)) != 3 or any(2 <= s < 4 for s in starts):
            continue
        moved = sum(s != i + 2 for i, s in enumerate(starts))
        shift = sum(abs(s - (i + 2)) for i, s in enumerate(starts))
        values.append(2 * moved + shift / 10 + 3 * (starts[2] + 1))
    assert raw.objective == min(values)
