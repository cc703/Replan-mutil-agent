"""Read-only simulation adapter with planned-start confirmation."""

from collections.abc import Callable

from scheduler_core.models import Device
from simulator.events import SimEvent

from .base import AdapterCallbackError, CalendarWindow, RuntimeView


class SimulatedAdapter:
    """Expose a simulator through the device adapter protocol."""

    def __init__(self, runtime: RuntimeView) -> None:
        self._runtime = runtime

    def list_devices(self) -> list[Device]:
        """Return the runtime's detached device list."""
        return self._runtime.list_devices()

    def get_status(self, device_id: str) -> str:
        """Return current aggregate device state."""
        return self._runtime.device_status(device_id)

    def get_calendar(self, device_id: str, start: int, end: int) -> list[CalendarWindow]:
        """Return clipped runtime windows for the requested half-open interval."""
        if type(start) is not int or type(end) is not int:
            raise ValueError("calendar bounds must be integer slots")
        return [
            CalendarWindow(w.start, w.end, w.kind)
            for w in self._runtime.calendar(device_id, start, end)
        ]

    def start_task(self, device_id: str, task_id: str, at: int) -> None:
        """Confirm the planned start without changing the runtime."""
        if type(at) is not int:
            raise ValueError("start must be an integer slot")
        self._runtime.confirm_start(device_id, task_id, at)

    def subscribe(self, cb: Callable[[SimEvent], None]) -> None:
        """Forward actual runtime events; wrap errors so the run can roll back."""

        def forward(event: SimEvent) -> None:
            try:
                cb(event)
            except Exception as exc:
                raise AdapterCallbackError("adapter subscriber failed") from exc

        self._runtime.add_event_listener(forward)
