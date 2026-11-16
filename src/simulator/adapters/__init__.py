"""Device adapter protocols and simulator-backed implementations."""

from .base import (
    AdapterCallbackError,
    CalendarWindow,
    ControllableAdapter,
    DeviceAdapter,
    RuntimeView,
)
from .manual import ManualAdapter
from .simulated import SimulatedAdapter

__all__ = [
    "AdapterCallbackError",
    "CalendarWindow",
    "ControllableAdapter",
    "DeviceAdapter",
    "RuntimeView",
    "ManualAdapter",
    "SimulatedAdapter",
]
