"""Anonymous miniature world for the offline CLI and smoke evaluation."""

from datetime import datetime, timezone

from scheduler_core.axis import TimeAxis
from scheduler_core.models import Device, Instance, Task


def miniature() -> Instance:
    return Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 1, tzinfo=timezone.utc), horizon_slots=48),
        devices=[Device(id="d1", type="generic")],
        tasks=[
            Task(
                id="t1",
                experiment_id="e1",
                type="generic",
                duration=2,
                compatible_devices=["d1"],
                deadline=30,
            )
        ],
    )
