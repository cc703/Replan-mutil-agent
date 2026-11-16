"""Manual external event injection through the simulator's validation."""

from scheduler_core.models import DeviceOutage, TaskOverrun, UrgentInsert

from .simulated import SimulatedAdapter


class ManualAdapter(SimulatedAdapter):
    """A simulated adapter that can schedule validated external events."""

    def inject_outage(self, event: DeviceOutage, at: int) -> None:
        """Schedule an outage beginning at at."""
        if not isinstance(event, DeviceOutage):
            raise ValueError("expected DeviceOutage")
        self._runtime.inject(event, at)

    def inject_urgent(self, event: UrgentInsert, at: int) -> None:
        """Schedule an urgent insertion."""
        if not isinstance(event, UrgentInsert):
            raise ValueError("expected UrgentInsert")
        self._runtime.inject(event, at)

    def inject_overrun(self, event: TaskOverrun, at: int) -> None:
        """Schedule an overrun for an already running task."""
        if not isinstance(event, TaskOverrun):
            raise ValueError("expected TaskOverrun")
        self._runtime.inject(event, at)
