import pickle

import numpy as np
from simulator.sampling import actual_duration, next_fault_gap, repair_duration, urgent_gap
from simulator.scenarios import Scenario


def test_keyed_independence_and_bounds() -> None:
    s = Scenario(fault_enabled=True, urgent_enabled=True, duration_sigma=0.0, repair_sigma=0.0)
    before = np.random.get_state(legacy=True)
    samples = [actual_duration(42, str(i), 0, 10, s) for i in range(10)]
    assert samples == [10] * 10
    assert samples == [actual_duration(42, str(i), 0, 10, s) for i in reversed(range(10))]
    assert repair_duration(42, 0, 0, s) == 12
    fault = next_fault_gap(42, 0, 0, s)
    urgent_gap(42, 0, s)
    assert next_fault_gap(42, 0, 0, s) == fault
    assert next_fault_gap(42, 0, 0, Scenario()) is None
    assert urgent_gap(42, 0, Scenario()) is None
    after = np.random.get_state(legacy=True)
    assert pickle.dumps(before) == pickle.dumps(after)


def test_urgent_content_collision_and_immutability() -> None:
    from datetime import datetime, timezone
    from scheduler_core.axis import TimeAxis
    from scheduler_core.models import Device, Instance, Task
    from simulator.sampling import urgent_content

    task = Task(id="u0-t0", experiment_id="u0", type="x", duration=4, compatible_devices=["d"])
    inst = Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=100),
        devices=[Device(id="d", type="x")],
        tasks=[task],
    )
    original = inst.model_copy(deep=True)
    s = Scenario(urgent_task_range=(2, 2), urgent_slack=2.0)
    event = urgent_content(1, 0, 5, inst, s)
    assert [t.id for t in event.tasks] == ["u0~-t0", "u0~-t1"]
    assert [t.deadline for t in event.tasks] == [21, 21]
    assert [(p.pred, p.succ) for p in event.precedences] == [("u0~-t0", "u0~-t1")]
    assert event == urgent_content(1, 0, 5, inst, s)
    assert inst == original


def test_streams_and_order_are_independent() -> None:
    s = Scenario(fault_enabled=True, urgent_enabled=True)
    keys = list(range(30))
    first = {
        k: (
            actual_duration(4, str(k), 0, 10, s),
            next_fault_gap(4, 2, k, s),
            repair_duration(4, 2, k, s),
            urgent_gap(4, k, s),
        )
        for k in keys
    }
    changed = s.model_copy(update={"urgent_rate_per_day": 10.0, "repair_sigma": 1.2})
    second = {
        k: (actual_duration(4, str(k), 0, 10, changed), next_fault_gap(4, 2, k, changed))
        for k in reversed(keys)
    }
    assert second == {k: first[k][:2] for k in keys}
    assert len({first[k][1] for k in keys}) > 1
    assert len({first[k][2] for k in keys}) > 1


def test_duration_clipping_rounding_and_minimum() -> None:
    low = Scenario(duration_sigma=0.0, duration_factor_min=0.2, duration_factor_max=0.5)
    high = Scenario(duration_sigma=0.0, duration_factor_min=1.5, duration_factor_max=2.0)
    assert actual_duration(1, "a", 0, 3, low) == 2
    assert actual_duration(1, "a", 0, 1, low) == 1
    assert actual_duration(1, "a", 0, 3, high) == 5
