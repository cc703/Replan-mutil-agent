"""Batching, cooldown and bounded retry state for replanning."""

from dataclasses import dataclass, field
from .events import SimEvent


@dataclass
class TriggerWindow:
    """Accumulate triggering events until a flush succeeds or is abandoned."""

    delta_slots: int
    cooldown_slots: int
    max_consecutive_failures: int
    events: list[SimEvent] = field(default_factory=list)
    due: int | None = None
    last_call: int | None = None
    failures: int = 0

    def add(self, event: SimEvent) -> int:
        """Add an event and return the existing or newly scheduled flush time."""
        self.events = [*self.events, event.model_copy(deep=True)]
        if self.due is None:
            self.due = event.time + self.delta_slots
            if self.last_call is not None:
                self.due = max(self.due, self.last_call + self.cooldown_slots)
        return self.due

    def batch(self) -> list[SimEvent]:
        """Return independent events ordered by simulation event key."""
        return [
            event.model_copy(deep=True)
            for event in sorted(
                self.events, key=lambda event: (event.time, event.priority, event.seq)
            )
        ]

    def called(self, now: int) -> None:
        """Mark a callback attempt and consume its scheduled flush."""
        if self.due is None or now < self.due:
            raise ValueError("flush is not due")
        self.last_call = now
        self.due = None

    def success(self) -> None:
        """Clear a successfully processed batch and failure streak."""
        self.events = []
        self.due = None
        self.failures = 0

    def failed(self, now: int) -> int | None:
        """Retain batch for retry or discard after exceeding the failure limit."""
        self.failures += 1
        if self.failures > self.max_consecutive_failures:
            self.events = []
            self.due = None
            self.failures = 0
            return None
        self.due = now + self.cooldown_slots
        return self.due
