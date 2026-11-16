"""Pure runtime instance transformations for external disruptions."""

from dataclasses import dataclass
import heapq
from typing import Any, Literal, cast

from scheduler_core.models import (
    BlockedWindow,
    DeviceOutage,
    Instance,
    Precedence,
    Task,
    UrgentInsert,
)

from scheduler_core.validation_context import NotStartedEvidence

from . import log as records
from .events import EventKind, SimEvent, StatusChange
from .queue import EventQueue
from .sampling import actual_duration
from .states import derive_device_state


class ListenerFailure(Exception):
    """Wrap a listener exception so the engine can restore its event boundary."""

    def __init__(self, original: Exception) -> None:
        self.original = original


@dataclass
class _QueueTransaction:
    next_seq: int
    stale_skipped: int
    popped: list[tuple[int, int, int, SimEvent]]
    epochs: dict[str, int | None]


class TransactionalEventQueue(EventQueue):
    """Queue with nested mutation journals; rollback work is paid only on failure."""

    def __init__(self) -> None:
        super().__init__()
        self._transactions: list[_QueueTransaction] = []

    def begin(self) -> None:
        self._transactions.append(_QueueTransaction(self._next_seq, self.stale_skipped, [], {}))

    def set_epoch(self, task_id: str, epoch: int) -> None:
        if self._transactions:
            journal = self._transactions[-1]
            if task_id not in journal.epochs:
                journal.epochs[task_id] = self._epochs.get(task_id)
        super().set_epoch(task_id, epoch)

    def pop_before(self, t_end: int) -> SimEvent | None:
        if type(t_end) is not int or t_end < 0:
            raise ValueError("cutoff must be a nonnegative integer")
        while self._heap and self._heap[0][0] < t_end:
            item = heapq.heappop(self._heap)
            if self._transactions:
                self._transactions[-1].popped.append(item)
            event = item[3]
            if (
                event.plan_epoch is not None
                and event.task_id is not None
                and self._epochs.get(event.task_id, event.plan_epoch) != event.plan_epoch
            ):
                self.stale_skipped += 1
                continue
            return event
        return None

    def commit(self) -> None:
        journal = self._transactions.pop()
        if self._transactions:
            parent = self._transactions[-1]
            parent.popped.extend(journal.popped)
            for task_id, old_epoch in journal.epochs.items():
                parent.epochs.setdefault(task_id, old_epoch)

    def rollback(self) -> None:
        journal = self._transactions.pop()
        self._heap = [item for item in self._heap if item[2] < journal.next_seq]
        self._heap.extend(item for item in journal.popped if item[2] < journal.next_seq)
        heapq.heapify(self._heap)
        self._next_seq = journal.next_seq
        self.stale_skipped = journal.stale_skipped
        for task_id, old_epoch in journal.epochs.items():
            if old_epoch is None:
                self._epochs.pop(task_id, None)
            else:
                self._epochs[task_id] = old_epoch


@dataclass
class _WindowNode:
    key: tuple[int, int]
    left: "_WindowNode | None" = None
    right: "_WindowNode | None" = None
    height: int = 1
    max_end: int = 0

    def __post_init__(self) -> None:
        self.max_end = self.key[1]


def _height(node: _WindowNode | None) -> int:
    return node.height if node else 0


def _refresh(node: _WindowNode) -> None:
    node.height = 1 + max(_height(node.left), _height(node.right))
    node.max_end = max(
        node.key[1], node.left.max_end if node.left else 0, node.right.max_end if node.right else 0
    )


def _rotate_right(node: _WindowNode) -> _WindowNode:
    pivot = node.left
    assert pivot is not None
    pivot = _WindowNode(pivot.key, pivot.left, pivot.right, pivot.height, pivot.max_end)
    node.left, pivot.right = pivot.right, node
    _refresh(node)
    _refresh(pivot)
    return pivot


def _rotate_left(node: _WindowNode) -> _WindowNode:
    pivot = node.right
    assert pivot is not None
    pivot = _WindowNode(pivot.key, pivot.left, pivot.right, pivot.height, pivot.max_end)
    node.right, pivot.left = pivot.left, node
    _refresh(node)
    _refresh(pivot)
    return pivot


def _insert(node: _WindowNode | None, key: tuple[int, int]) -> _WindowNode:
    if node is None:
        return _WindowNode(key)
    node = _WindowNode(node.key, node.left, node.right, node.height, node.max_end)
    if key < node.key:
        node.left = _insert(node.left, key)
    elif key > node.key:
        node.right = _insert(node.right, key)
    else:
        return node
    _refresh(node)
    balance = _height(node.left) - _height(node.right)
    if balance > 1:
        assert node.left is not None
        if key > node.left.key:
            node.left = _rotate_left(node.left)
        return _rotate_right(node)
    if balance < -1:
        assert node.right is not None
        if key < node.right.key:
            node.right = _rotate_right(node.right)
        return _rotate_left(node)
    return node


class WindowIndex:
    """AVL interval tree; insertion and overlap queries are logarithmic."""

    def __init__(self, intervals: list[tuple[int, int]]) -> None:
        self.root: _WindowNode | None = None
        for start, end in intervals:
            self.add(start, end)

    def add(self, start: int, end: int) -> None:
        """Insert a half-open interval without rebuilding existing entries."""
        if start < 0 or end <= start:
            raise ValueError("invalid window")
        self.root = _insert(self.root, (start, end))

    def overlaps(self, start: int, end: int) -> bool:
        """Return whether a half-open query intersects an indexed window."""
        node = self.root
        while node is not None:
            if node.left is not None and node.left.max_end > start:
                node = node.left
            elif node.key[0] < end and node.key[1] > start:
                return True
            elif node.key[0] >= end:
                return False
            else:
                node = node.right
        return False


def apply_outage(inst: Instance, outage: DeviceOutage) -> Instance:
    """Return a copy with the newly reported fault window appended."""
    if outage.device_id not in {device.id for device in inst.devices}:
        raise ValueError("unknown device")
    data = inst.model_dump(mode="python")
    data["blocked"].append(
        BlockedWindow(device_id=outage.device_id, start=outage.start, end=outage.end, kind="FAULT")
    )
    return Instance.model_validate(data)


def apply_urgent(inst: Instance, event: UrgentInsert, at: int) -> Instance:
    """Append urgent tasks and edges, enforcing release at or after arrival."""
    tasks = [
        task.model_copy(deep=True, update={"release": max(task.release, at)})
        for task in event.tasks
    ]
    data = inst.model_dump(mode="python")
    data["tasks"] = [*inst.tasks, *tasks]
    data["precedences"] = [*inst.precedences, *event.precedences]
    return Instance.model_validate(data)


def interrupt_task(inst: Instance, task_id: str, at: int, executed: int) -> tuple[Instance, Task]:
    """Mark a running task interrupted and append a collision-free restart and edges."""
    tasks = {task.id: task for task in inst.tasks}
    task = tasks.get(task_id)
    if task is None or task.status != "RUNNING" or executed < 0:
        raise ValueError("interruption requires a running task and nonnegative execution")
    parts = task_id.rsplit("~r", 1)
    root = parts[0] if len(parts) == 2 and parts[1].isdigit() else task_id
    index = 1
    while f"{root}~r{index}" in tasks:
        index += 1
    new_id = f"{root}~r{index}"
    duration = max(1, task.duration - executed) if task.preemptible else task.duration
    restart = task.model_copy(
        deep=True, update={"id": new_id, "status": "PENDING", "release": at, "duration": duration}
    )
    updated = [
        t.model_copy(deep=True, update={"status": "INTERRUPTED"})
        if t.id == task_id
        else t.model_copy(deep=True)
        for t in inst.tasks
    ]
    edges = [edge.model_copy(deep=True) for edge in inst.precedences]
    for edge in inst.precedences:
        if edge.pred == task_id or edge.succ == task_id:
            edges.append(
                Precedence(
                    pred=new_id if edge.pred == task_id else edge.pred,
                    succ=new_id if edge.succ == task_id else edge.succ,
                    lag_min=edge.lag_min,
                    lag_max=edge.lag_max,
                )
            )
    data = inst.model_dump(mode="python")
    data.update(tasks=[*updated, restart], precedences=edges)
    return Instance.model_validate(data), restart


class RuntimeHandling:
    """Execution and disruption handling for the event loop."""

    def _task(self: Any, tid: str) -> Any:
        return self.tasks[tid]

    def _task_state(
        self: Any, tid: str, state: str, start: int | None = None, end: int | None = None
    ) -> None:
        task = self._task(tid)
        old = task.status
        updated = task.model_copy(deep=True, update={"status": state})
        self._tx.index(self.instance.tasks, self.task_positions[tid])
        self.instance.tasks[self.task_positions[tid]] = updated
        self._tx.item(self.tasks, tid)
        self.tasks[tid] = updated
        self._record(
            records.TaskStateRecord,
            task_id=tid,
            old=old,
            new=state,
            actual_start=start,
            actual_end=end,
        )

    def _state(self: Any, device_id: str) -> None:
        demand = self.running_demand[device_id]
        setup_count = len(self.setups_by_device[device_id])
        causes = cast(list[Literal["FAULT", "OFFLINE", "MAINT"]], list(self.down[device_id]))
        state = derive_device_state(demand, setup_count, causes)
        old = self.states[device_id]
        if old != state:
            change = StatusChange(time=self.clock, entity_id=device_id, old=old, new=state)
            self._tx.item(self.states, device_id)
            self.states[device_id] = state
            self._record(
                records.DeviceStateRecord, device_id=device_id, old=old.value, new=state.value
            )
            self._pending_status[-1].append((change, tuple(self.listeners)))

    def _ready(self: Any, tid: str, *, setup: bool = False) -> bool:
        assignment = self.plan.assignments[tid]
        device = self.devices_by_id[assignment.device_id]
        if self.down[device.id] or self.device_windows[device.id].overlaps(
            self.clock, assignment.end
        ):
            return False
        used = self.running_demand[device.id] + self.setup_demand[device.id]
        if tid in self.setups:
            used -= self._task(tid).demand
        if used + self._task(tid).demand > device.capacity:
            return False
        if assignment.person_id and not setup:
            person_id = assignment.person_id
            if self.person_windows[person_id].overlaps(self.clock, assignment.end):
                return False
            if person_id in self.running_by_person:
                return False
        return True

    def _setup_add(self: Any, tid: str) -> None:
        assignment = self.plan.assignments[tid]
        self._tx.member(self.setups, tid)
        self.setups.add(tid)
        self._tx.member(self.setups_by_device[assignment.device_id], tid)
        self.setups_by_device[assignment.device_id].add(tid)
        self._tx.item(self.setup_demand, assignment.device_id)
        self.setup_demand[assignment.device_id] += self._task(tid).demand
        if assignment.person_id is not None:
            self._tx.item(self.setups_by_person, assignment.person_id)
            if assignment.person_id in self.setups_by_person:
                self._tx.member(self.setups_by_person[assignment.person_id], tid)
            self.setups_by_person.setdefault(assignment.person_id, set()).add(tid)

    def _setup_remove(self: Any, tid: str) -> None:
        if tid not in self.setups:
            return
        assignment = self.plan.assignments[tid]
        self._tx.member(self.setups, tid)
        self.setups.remove(tid)
        self._tx.member(self.setups_by_device[assignment.device_id], tid)
        self.setups_by_device[assignment.device_id].remove(tid)
        self._tx.item(self.setup_demand, assignment.device_id)
        self.setup_demand[assignment.device_id] -= self._task(tid).demand
        if assignment.person_id is not None:
            self._tx.member(self.setups_by_person[assignment.person_id], tid)
            self.setups_by_person[assignment.person_id].remove(tid)

    def _running_remove(self: Any, tid: str, device_id: str) -> None:
        self._tx.member(self.running_by_device[device_id], tid)
        self.running_by_device[device_id].remove(tid)
        self._tx.item(self.running_demand, device_id)
        self.running_demand[device_id] -= self._task(tid).demand
        if not self.running_by_device[device_id]:
            self._tx.item(self.busy_slots, device_id)
            self._tx.item(self.busy_since, device_id)
            self.busy_slots[device_id] += self.clock - self.busy_since.pop(device_id)

    def _trigger(self: Any, event: SimEvent, reason: str) -> None:
        existing = self.window.due
        for name in ("events", "due", "last_call", "failures"):
            self._tx.attr(self.window, name)
        due = self.window.add(event)
        self._record(
            records.ReplanTriggered, reason=reason, event_json=records.canonical_json(event)
        )
        if existing is None:
            self._push(SimEvent(time=due, kind=EventKind.REPLAN_FLUSH))

    def _blocked(self: Any, event: SimEvent) -> None:
        assert event.device_id and event.task_id
        self._setup_remove(event.task_id)
        self._tx.member(self.blocked_starts, event.task_id)
        self.blocked_starts.add(event.task_id)
        assignment = self.plan.assignments[event.task_id]
        self._tx.item(self.not_started, event.task_id)
        self.not_started[event.task_id] = NotStartedEvidence(
            task_id=event.task_id,
            base_plan_id=self.plan.id,
            planned_device_id=assignment.device_id,
            planned_start=assignment.start,
            planned_end=assignment.end,
            planned_person_id=assignment.person_id,
            blocked_at=self.clock,
            observed_at=self.clock,
            event_id=f"blocked:{event.seq}",
        )
        self._record(
            records.StartBlocked,
            device_id=event.device_id,
            task_id=event.task_id,
            reason="resource unavailable",
        )
        self._trigger(event, "START_BLOCKED")
        self._state(event.device_id)

    def _start(self: Any, event: SimEvent) -> None:
        assert event.task_id and event.device_id
        tid = event.task_id
        if tid in self.blocked_starts:
            return
        if not self._ready(tid):
            self._blocked(event)
            return
        self._tx.item(self.not_started, tid)
        self.not_started.pop(tid, None)
        task = self._task(tid)
        self._tx.item(self.remaining, tid)
        duration = self.remaining.pop(tid, None)
        if duration is None:
            key = (tid, self.attempts[tid])
            if self.replay_samples is not None and key in self.replay_samples:
                duration = self.replay_samples[key]
            elif self.replay_exact:
                raise records.ReplayMismatch(len(self.history), "recorded duration", key)
            else:
                duration = actual_duration(
                    self.seed, tid, self.attempts[tid], task.duration, self.scenario
                )
            self._record(
                records.DurationSampled,
                task_id=tid,
                attempt=self.attempts[tid],
                planned=task.duration,
                actual=duration,
                source="sampled",
            )
        self._tx.item(self.running, tid)
        self.running[tid] = (self.clock, self.clock + duration, event.seq)
        self._tx.attr(self, "start_deviation_sum")
        self.start_deviation_sum += abs(self.clock - self.plan.assignments[tid].start)
        self._tx.attr(self, "start_deviation_count")
        self.start_deviation_count += 1
        if not self.running_by_device[event.device_id]:
            self._tx.item(self.busy_since, event.device_id)
            self.busy_since[event.device_id] = self.clock
        self._tx.member(self.running_by_device[event.device_id], tid)
        self.running_by_device[event.device_id].add(tid)
        self._tx.item(self.running_demand, event.device_id)
        self.running_demand[event.device_id] += task.demand
        person_id = self.plan.assignments[tid].person_id
        if person_id is not None:
            self._tx.item(self.running_by_person, person_id)
            self.running_by_person[person_id] = tid
        self._task_state(tid, "RUNNING", self.clock)
        self._state(event.device_id)
        self._push(
            SimEvent(
                time=self.clock + duration,
                kind=EventKind.TASK_END,
                device_id=event.device_id,
                task_id=tid,
                plan_epoch=self.epochs.get(tid, 0),
            )
        )
        end = self.plan.assignments[tid].end
        if self.clock + duration > end:
            self._push(
                SimEvent(
                    time=end,
                    kind=EventKind.TASK_OVERRUN,
                    task_id=tid,
                    plan_epoch=self.epochs.get(tid, 0),
                )
            )

    def _end(self: Any, event: SimEvent) -> None:
        assert event.task_id and event.device_id
        if event.task_id not in self.running:
            return
        if self.running[event.task_id][1] != event.time:
            return
        self._tx.item(self.running, event.task_id)
        start, end, _ = self.running.pop(event.task_id)
        self._running_remove(event.task_id, event.device_id)
        person_id = self.plan.assignments[event.task_id].person_id
        if person_id is not None:
            self._tx.item(self.running_by_person, person_id)
            self.running_by_person.pop(person_id, None)
        self._tx.item(self.done, event.task_id)
        self.done[event.task_id] = (start, end, event.seq)
        self._task_state(event.task_id, "DONE", start, end)
        self._state(event.device_id)

    def _interrupt(self: Any, device_id: str) -> bool:
        affected = sorted(self.running_by_device[device_id])
        for tid in affected:
            self._tx.item(self.running, tid)
            start, actual_end, _ = self.running.pop(tid)
            self._running_remove(tid, device_id)
            person_id = self.plan.assignments[tid].person_id
            if person_id is not None:
                self._tx.item(self.running_by_person, person_id)
                self.running_by_person.pop(person_id, None)
            task = self._task(tid)
            self._task_state(tid, "INTERRUPTED", start)
            # interrupt_task accepts RUNNING; restore only in a temporary copy.
            temp = self.instance.model_copy(deep=True)
            temp.tasks = [
                t.model_copy(update={"status": "RUNNING"}) if t.id == tid else t for t in temp.tasks
            ]
            self._tx.attr(self, "instance")
            self.instance, restart = interrupt_task(temp, tid, self.clock, self.clock - start)
            self._tx.attr(self, "tasks")
            self.tasks = {task.id: task for task in self.instance.tasks}
            self._tx.attr(self, "task_positions")
            self.task_positions = {task.id: i for i, task in enumerate(self.instance.tasks)}
            self._tx.item(self.epochs, tid)
            self.epochs[tid] = self.epochs.get(tid, 0) + 1
            self.queue.set_epoch(tid, self.epochs[tid])
            if task.preemptible:
                self._tx.item(self.remaining, restart.id)
                self.remaining[restart.id] = max(1, actual_end - self.clock)
            else:
                self._tx.item(self.attempts, restart.id)
                self.attempts[restart.id] = self.attempts[tid] + 1
        return bool(affected)

    def _dispatch(self: Any, event: SimEvent) -> None:
        kind, tid, did = event.kind, event.task_id, event.device_id
        if kind == EventKind.TASK_START:
            self._start(event)
        elif kind == EventKind.TASK_END:
            self._end(event)
        elif kind == EventKind.SETUP_START:
            assert tid and did
            if self._ready(tid, setup=True):
                self._setup_add(tid)
                self._state(did)
            else:
                self._blocked(event)
        elif kind == EventKind.SETUP_END:
            assert tid and did
            self._setup_remove(tid)
            self._state(did)
        elif kind == EventKind.TASK_OVERRUN:
            self._overrun(event)
        elif kind == EventKind.REPLAN_FLUSH:
            if event.seq in self.periodic_events:
                self._trigger(event, "PERIODIC")
                assert self.scenario.periodic_slots is not None
                self._schedule_periodic(self.clock + self.scenario.periodic_slots)
            else:
                self._flush()
        elif kind in (EventKind.DEVICE_FAULT, EventKind.MAINT_START):
            assert did
            cause = "FAULT" if kind == EventKind.DEVICE_FAULT else "MAINT"
            if kind == EventKind.DEVICE_FAULT:
                assert isinstance(event.payload, DeviceOutage)
                self._tx.attr(self, "instance")
                self.instance = apply_outage(self.instance, event.payload)
                self._tx.attr(self.device_windows[did], "root")
                self.device_windows[did].add(event.payload.start, event.payload.end)
                source = "generated" if event.seq in self.generated else "injected"
                self._record(
                    records.DeviceFault, device_id=did, end=event.payload.end, source=source
                )
                self._push(
                    SimEvent(time=event.payload.end, kind=EventKind.DEVICE_RECOVER, device_id=did)
                )
                if source == "generated":
                    self._schedule_fault(did)
            else:
                end = self.maintenance_ends[event.seq]
                self._record(records.MaintenanceStart, device_id=did, end=end)
            interrupted = self._interrupt(did)
            self._tx.item(self.down[did], cause)
            self.down[did][cause] += 1
            self._state(did)
            if kind == EventKind.DEVICE_FAULT or interrupted:
                self._trigger(event, cause)
        elif kind in (EventKind.DEVICE_RECOVER, EventKind.MAINT_END):
            assert did
            cause = "FAULT" if kind == EventKind.DEVICE_RECOVER else "MAINT"
            self._tx.item(self.down[did], cause)
            self.down[did][cause] -= 1
            if not self.down[did][cause]:
                self._tx.item(self.down[did], cause)
                del self.down[did][cause]
            self._record(
                records.DeviceRecover if cause == "FAULT" else records.MaintenanceEnd, device_id=did
            )
            self._state(did)
        elif kind == EventKind.URGENT_ARRIVAL:
            assert isinstance(event.payload, UrgentInsert)
            self._tx.attr(self, "instance")
            self.instance = apply_urgent(self.instance, event.payload, self.clock)
            self._tx.attr(self, "tasks")
            self.tasks = {task.id: task for task in self.instance.tasks}
            self._tx.attr(self, "task_positions")
            self.task_positions = {task.id: i for i, task in enumerate(self.instance.tasks)}
            source = "generated" if event.seq in self.generated else "injected"
            self._record(
                records.UrgentArrival,
                event_json=records.canonical_json(event.payload),
                source=source,
            )
            self._trigger(event, "URGENT_ARRIVAL")
            if source == "generated":
                self._schedule_urgent()
