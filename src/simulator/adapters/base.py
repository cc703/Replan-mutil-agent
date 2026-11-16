"""Adapter contracts. Real device integration is reserved for a future stage."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

from scheduler_core.models import BlockedWindow, Device, Event
from simulator.events import SimEvent, StatusChange


@dataclass(frozen=True)
class CalendarWindow:
    """A half-open interval of device unavailability or occupation."""

    start: int
    end: int
    kind: Literal["CLOSED", "MAINT", "FAULT", "RUNNING"]


class AdapterCallbackError(RuntimeError):
    """A subscriber failed while a simulation event was processed."""


@runtime_checkable
class DeviceAdapter(Protocol):
    """Read device state and subscribe to processed simulation events."""

    def list_devices(self) -> list[Device]: ...
    def get_status(self, device_id: str) -> str: ...
    def subscribe(self, cb: Callable[[SimEvent], None]) -> None: ...


@runtime_checkable
class ControllableAdapter(DeviceAdapter, Protocol):
    """Read device calendars and confirm a planned start."""

    def get_calendar(self, device_id: str, start: int, end: int) -> list[CalendarWindow]: ...
    def start_task(self, device_id: str, task_id: str, at: int) -> None: ...


@runtime_checkable
class RuntimeView(Protocol):
    """Simulator operations consumed by adapter facades."""

    def list_devices(self) -> list[Device]: ...
    def device_status(self, device_id: str) -> str: ...
    def calendar(self, device_id: str, start: int, end: int) -> list[BlockedWindow]: ...
    def add_status_listener(self, callback: Callable[[StatusChange], None]) -> None: ...
    def add_event_listener(self, callback: Callable[[SimEvent], None]) -> None: ...
    def inject(self, event: Event, at: int) -> None: ...
    def confirm_start(self, device_id: str, task_id: str, at: int) -> None: ...
