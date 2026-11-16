"""Stable heap queue with per-task epoch invalidation."""

import heapq
from collections.abc import Iterable
from .events import SimEvent


class EventQueue:
    """Assign monotonic sequence numbers and lazily discard stale events."""

    def __init__(self) -> None:
        self._heap: list[tuple[int, int, int, SimEvent]] = []
        self._next_seq = 0
        self._epochs: dict[str, int] = {}
        self.stale_skipped = 0

    def set_epoch(self, task_id: str, epoch: int) -> None:
        """Set the current plan epoch for one changed task."""
        if type(epoch) is not int or epoch < 0:
            raise ValueError("epoch must be a nonnegative integer")
        self._epochs[task_id] = epoch

    def push(self, event: SimEvent) -> SimEvent:
        """Enqueue an event with a newly assigned global sequence."""
        assigned = event.model_copy(deep=True, update={"seq": self._next_seq})
        self._next_seq += 1
        heapq.heappush(self._heap, (assigned.time, assigned.priority, assigned.seq, assigned))
        return assigned.model_copy(deep=True)

    def push_plan_batch(self, events: Iterable[SimEvent]) -> list[SimEvent]:
        """Enqueue plan events sorted by time, device and task."""
        batch = list(events)
        if any(e.device_id is None or e.task_id is None or e.plan_epoch is None for e in batch):
            raise ValueError("plan events require device, task and epoch")
        return [
            self.push(e)
            for e in sorted(batch, key=lambda e: (e.time, e.device_id or "", e.task_id or ""))
        ]

    def pop_before(self, t_end: int) -> SimEvent | None:
        """Return next live event strictly before cutoff, leaving later entries untouched."""
        if type(t_end) is not int or t_end < 0:
            raise ValueError("cutoff must be a nonnegative integer")
        while self._heap and self._heap[0][0] < t_end:
            event = heapq.heappop(self._heap)[3]
            if (
                event.plan_epoch is not None
                and event.task_id is not None
                and self._epochs.get(event.task_id, event.plan_epoch) != event.plan_epoch
            ):
                self.stale_skipped += 1
                continue
            return event
        return None

    def pop(self) -> SimEvent:
        """Pop the next live event, counting stale events skipped."""
        while self._heap:
            event = heapq.heappop(self._heap)[3]
            if (
                event.plan_epoch is not None
                and event.task_id is not None
                and self._epochs.get(event.task_id, event.plan_epoch) != event.plan_epoch
            ):
                self.stale_skipped += 1
                continue
            return event
        raise IndexError("pop from empty event queue")

    def __len__(self) -> int:
        """Return heap size, including entries not yet checked for staleness."""
        return len(self._heap)
