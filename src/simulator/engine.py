"""Discrete event simulator, with independent validation on every plan adoption."""

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
import heapq
from typing import Any

from scheduler_core.models import (
    BlockedWindow,
    Device,
    DeviceOutage,
    Event,
    Instance,
    Plan,
    TaskOverrun,
    UrgentInsert,
)
from scheduler_core.validate import validate

from . import log as records
from .events import EventKind, SimEvent, StatusChange
from .gate import PlanHandling, SchedulerFailure
from .metrics import calculate_metrics
from .runtime import (
    ListenerFailure,
    RuntimeHandling,
    TransactionalEventQueue,
    WindowIndex,
    apply_urgent,
)
from .sampling import next_fault_gap, repair_duration, urgent_content, urgent_gap
from .scenarios import Scenario
from .states import DeviceState
from .transaction import JournalList, UndoJournal
from .trigger import TriggerWindow

Scheduler = Callable[[Instance, Plan, list[SimEvent]], Plan | None]


@dataclass(frozen=True)
class SimResult:
    """Snapshot of a simulation at a run cutoff."""

    log: bytes
    metrics: dict[str, Any]
    final_plan: Plan
    final_instance: Instance
    stale_skipped: int
    counters: dict[str, int]


class Simulator(PlanHandling, RuntimeHandling):
    """Run an event-driven simulation without altering caller-owned models."""

    def __init__(
        self,
        inst: Instance,
        plan: Plan,
        scenario: Scenario,
        scheduler: Scheduler | None,
        seed: int,
        *,
        replay_external: list[records.SimEventRecord] | None = None,
        scheduler_with_context: Callable[..., Plan | None] | None = None,
    ) -> None:
        if not validate(inst, plan).passed:
            raise ValueError("initial plan failed validation")
        if any(task.status not in ("PENDING", "SCHEDULED") for task in inst.tasks):
            raise ValueError("initial task must be pending or scheduled")
        self.instance = inst.model_copy(deep=True)
        self.tasks = {task.id: task for task in self.instance.tasks}
        self.task_positions = {task.id: index for index, task in enumerate(self.instance.tasks)}
        self.plan = plan.model_copy(deep=True)
        self.scenario = scenario
        if (scheduler is None) == (scheduler_with_context is None):
            raise ValueError("provide exactly one scheduler callback")
        self.scheduler = scheduler
        self.scheduler_with_context = scheduler_with_context
        self.not_started: dict[str, Any] = {}
        self.seed = seed
        self.clock = inst.now
        self.start_time = inst.now
        self.busy_slots: Counter[str] = Counter({device.id: 0 for device in inst.devices})
        self.busy_since: dict[str, int] = {}
        self.start_deviation_sum = 0
        self.start_deviation_count = 0
        self.base_as_of = self.clock
        self._tx = UndoJournal()
        self.queue = TransactionalEventQueue()
        self._held_events: list[tuple[int, int, int, SimEvent]] = []
        self.epochs: dict[str, int] = {}
        self.history: list[records.SimEventRecord] = []
        self.counters: Counter[str] = Counter()
        self.window = TriggerWindow(
            scenario.delta_slots, scenario.cooldown_slots, scenario.max_consecutive_failures
        )
        self.running: dict[str, tuple[int, int, int]] = {}
        self.running_by_device: dict[str, set[str]] = {d.id: set() for d in inst.devices}
        self.running_by_person: dict[str, str] = {}
        self.running_demand: Counter[str] = Counter()
        self.setup_demand: Counter[str] = Counter()
        self.setups_by_device: dict[str, set[str]] = {d.id: set() for d in inst.devices}
        self.setups_by_person: dict[str, set[str]] = {}
        self.devices_by_id = {device.id: device for device in self.instance.devices}
        self.device_indices = {
            device.id: index for index, device in enumerate(self.instance.devices)
        }
        self.done: dict[str, tuple[int, int, int]] = {}
        self.known_overruns: dict[str, tuple[int, str, int]] = {}
        self.attempts: Counter[str] = Counter()
        self.remaining: dict[str, int] = {}
        self.replay_samples: dict[tuple[str, int], int] | None = None
        self.replay_exact = False
        self.setups: set[str] = set()
        self.blocked_starts: set[str] = set()
        self.down: dict[str, Counter[str]] = {d.id: Counter() for d in inst.devices}
        self.device_windows = {
            d.id: WindowIndex([(w.start, w.end) for w in inst.blocked if w.device_id == d.id])
            for d in inst.devices
        }
        self.person_windows = {
            p.id: WindowIndex([(w.start, w.end) for w in p.blocked]) for p in inst.persons
        }
        self.states = {d.id: DeviceState.IDLE for d in inst.devices}
        self._listeners: list[Callable[[StatusChange], None]] = JournalList(self._tx)
        self._event_listeners: list[Callable[[SimEvent], None]] = JournalList(self._tx)
        self._pending_status: list[
            list[tuple[StatusChange, tuple[Callable[[StatusChange], None], ...]]]
        ] = []
        self.generated: set[int] = set()
        self.periodic_events: set[int] = set()
        self.maintenance_ends: dict[int, int] = {}
        self.fault_occurrences: Counter[str] = Counter()
        self.urgent_occurrences = 0
        self.replay_external = replay_external
        self.replay_faults: dict[str, list[SimEvent]] = {}
        self.replay_arrivals: list[SimEvent] = []
        if replay_external is not None:
            for item in replay_external:
                if isinstance(item, records.EventEnqueued) and item.source == "generated":
                    saved = SimEvent.model_validate_json(item.event_json)
                    if saved.kind == EventKind.DEVICE_FAULT and saved.device_id is not None:
                        self.replay_faults.setdefault(saved.device_id, []).append(saved)
                    elif saved.kind == EventKind.URGENT_ARRIVAL:
                        self.replay_arrivals.append(saved)
        self.prototypes = inst.model_copy(deep=True)
        self._current = SimEvent(time=self.clock, kind=EventKind.REPLAN_FLUSH)
        self._record(
            records.Header,
            seed=seed,
            version="p3-v1",
            scene_json=records.canonical_json(scenario),
            instance_json=records.canonical_json(inst),
            plan_json=records.canonical_json(plan),
            scene_hash=records.content_hash(scenario),
            instance_hash=records.content_hash(inst),
            plan_hash=records.content_hash(plan),
        )
        for task in list(self.instance.tasks):
            if task.id in plan.assignments and task.status == "PENDING":
                self._task_state(task.id, "SCHEDULED")
        self._enqueue_assignments(set(plan.assignments))
        for window in self.instance.blocked:
            if window.kind == "MAINT" and window.end > self.clock:
                seq = self._push(
                    SimEvent(
                        time=max(window.start, self.clock),
                        kind=EventKind.MAINT_START,
                        device_id=window.device_id,
                    )
                )
                self.maintenance_ends[seq] = window.end
                self._push(
                    SimEvent(time=window.end, kind=EventKind.MAINT_END, device_id=window.device_id)
                )
        for device in self.instance.devices:
            self._schedule_fault(device.id)
        self._schedule_urgent()
        if scenario.periodic_slots is not None:
            self._schedule_periodic(self.clock + scenario.periodic_slots)

    def _record(self, cls: Any, **kwargs: Any) -> None:
        event = self._current
        self._tx.record(lambda: self.history.pop())
        self.history.append(
            cls(
                index=len(self.history),
                time=self.clock,
                priority=event.priority,
                seq=event.seq,
                **kwargs,
            )
        )

    def _push(self, event: SimEvent, source: str = "internal") -> int:
        assigned = self.queue.push(event)
        self._tx.item(self.counters, "enqueued")
        self.counters["enqueued"] += 1
        self._record(
            records.EventEnqueued, event_json=records.canonical_json(assigned), source=source
        )
        return assigned.seq

    def _schedule_fault(self, device_id: str) -> None:
        if not self.scenario.fault_enabled:
            return
        occurrence = self.fault_occurrences[device_id]
        device_index = self.device_indices[device_id]
        if self.replay_external is None:
            gap = next_fault_gap(self.seed, device_index, occurrence, self.scenario)
            assert gap is not None
            time = self.clock + gap
            end = time + repair_duration(self.seed, device_index, occurrence, self.scenario)
        else:
            faults = self.replay_faults.get(device_id, [])
            if occurrence >= len(faults):
                return
            saved = faults[occurrence]
            assert isinstance(saved.payload, DeviceOutage)
            time, end = saved.time, saved.payload.end
        self._tx.item(self.fault_occurrences, device_id)
        self.fault_occurrences[device_id] += 1
        if time >= self.instance.axis.horizon_slots:
            return
        event = DeviceOutage(device_id=device_id, start=time, end=end)
        seq = self._push(
            SimEvent(time=time, kind=EventKind.DEVICE_FAULT, device_id=device_id, payload=event),
            "generated",
        )
        self._tx.member(self.generated, seq)
        self.generated.add(seq)

    def _schedule_periodic(self, time: int) -> None:
        if time < self.instance.axis.horizon_slots:
            seq = self._push(SimEvent(time=time, kind=EventKind.REPLAN_FLUSH))
            self._tx.member(self.periodic_events, seq)
            self.periodic_events.add(seq)

    def _schedule_urgent(self) -> None:
        if not self.scenario.urgent_enabled:
            return
        occurrence = self.urgent_occurrences
        if self.replay_external is None:
            gap = urgent_gap(self.seed, occurrence, self.scenario, self.instance.axis.slot_minutes)
            assert gap is not None
            time = self.clock + gap
            if time >= self.instance.axis.horizon_slots:
                return
            event = urgent_content(self.seed, occurrence, time, self.prototypes, self.scenario)
        else:
            arrivals = self.replay_arrivals
            if occurrence >= len(arrivals):
                return
            time = arrivals[occurrence].time
            payload = arrivals[occurrence].payload
            assert isinstance(payload, UrgentInsert)
            event = payload
        self._tx.attr(self, "urgent_occurrences")
        self.urgent_occurrences += 1
        seq = self._push(
            SimEvent(time=time, kind=EventKind.URGENT_ARRIVAL, payload=event), "generated"
        )
        self._tx.member(self.generated, seq)
        self.generated.add(seq)

    def _enqueue_assignments(self, ids: set[str]) -> None:
        events: list[SimEvent] = []
        tasks = {task.id: task for task in self.instance.tasks}
        for tid in ids:
            if tid not in self.plan.assignments or tid not in tasks:
                continue
            assignment = self.plan.assignments[tid]
            task = tasks[tid]
            if task.status not in ("PENDING", "SCHEDULED"):
                continue
            epoch = self.epochs.get(tid, 0)
            self.queue.set_epoch(tid, epoch)
            setup = next(
                (
                    r.slots
                    for r in self.instance.setups
                    if r.device_id == assignment.device_id and r.task_type == task.type
                ),
                0,
            )
            if setup and assignment.start - setup >= self.clock:
                events.append(
                    SimEvent(
                        time=assignment.start - setup,
                        kind=EventKind.SETUP_START,
                        device_id=assignment.device_id,
                        task_id=tid,
                        plan_epoch=epoch,
                    )
                )
                events.append(
                    SimEvent(
                        time=assignment.start,
                        kind=EventKind.SETUP_END,
                        device_id=assignment.device_id,
                        task_id=tid,
                        plan_epoch=epoch,
                    )
                )
            if assignment.start >= self.clock:
                events.append(
                    SimEvent(
                        time=assignment.start,
                        kind=EventKind.TASK_START,
                        device_id=assignment.device_id,
                        task_id=tid,
                        plan_epoch=epoch,
                    )
                )
        assigned = self.queue.push_plan_batch(events)
        for event in assigned:
            self._record(
                records.EventEnqueued, event_json=records.canonical_json(event), source="plan"
            )
        self._tx.item(self.counters, "enqueued")
        self.counters["enqueued"] += len(events)

    def inject(self, event: Event, at: int) -> None:
        """Schedule a validated external event without applying it before its time."""
        if type(at) is not int or at < self.clock:
            raise ValueError("injection time precedes clock")
        if isinstance(event, DeviceOutage):
            if event.start != at or event.device_id not in self.down:
                raise ValueError("invalid outage")
            sim = SimEvent(
                time=at, kind=EventKind.DEVICE_FAULT, device_id=event.device_id, payload=event
            )
        elif isinstance(event, UrgentInsert):
            apply_urgent(self.instance, event, at)
            sim = SimEvent(time=at, kind=EventKind.URGENT_ARRIVAL, payload=event)
        elif isinstance(event, TaskOverrun):
            if (
                event.task_id not in self.running
                or event.task_id in self.known_overruns
                or at >= self.running[event.task_id][1]
                or event.new_end <= self.running[event.task_id][1]
            ):
                raise ValueError("overrun requires a running task and a later end")
            sim = SimEvent(
                time=at, kind=EventKind.TASK_OVERRUN, task_id=event.task_id, payload=event
            )
        else:
            raise ValueError("unsupported event")
        self._record(records.Injected, event_json=records.canonical_json(event), at=at)
        self._push(sim, "injected")

    def run(self, t_end: int) -> SimResult:
        """Process events before cutoff; nested runs may advance the returned cutoff."""
        if type(t_end) is not int or t_end < self.clock or t_end > self.instance.axis.horizon_slots:
            raise ValueError("invalid run cutoff")
        while True:
            transactional = bool(self.listeners or self.event_listeners or self._tx.active)
            if transactional:
                self.queue.begin()
                self._tx.begin()
                self._tx.attr(self, "clock")
                self._tx.attr(self, "_current")
                held = self._held_events.copy()
                self._tx.record(partial(setattr, self, "_held_events", held))
            candidate = self.queue.pop_before(t_end)
            if candidate is not None:
                heapq.heappush(
                    self._held_events,
                    (candidate.time, candidate.priority, candidate.seq, candidate),
                )
            if not self._held_events or self._held_events[0][0] >= t_end:
                if transactional:
                    self.queue.commit()
                    self._tx.commit()
                break
            event = heapq.heappop(self._held_events)[3]
            previous_event = self._current
            self.clock = event.time
            self._current = event
            self._tx.item(self.counters, "events")
            self.counters["events"] += 1
            try:
                self._pending_status.append([])
                try:
                    self._dispatch(event)
                finally:
                    notifications = self._pending_status.pop()
                for change, listeners in notifications:
                    for status_callback in listeners:
                        try:
                            status_callback(change)
                        except Exception as error:
                            raise ListenerFailure(error) from error
                for callback in tuple(self.event_listeners):
                    try:
                        callback(event.model_copy(deep=True))
                    except Exception as error:
                        raise ListenerFailure(error) from error
            except SchedulerFailure as exc:
                if transactional:
                    self.queue.commit()
                    self._tx.commit()
                heapq.heappush(self._held_events, (event.time, event.priority, event.seq, event))
                self.counters["events"] -= 1
                self._current = previous_event
                raise exc.original
            except ListenerFailure as exc:
                if transactional:
                    self.queue.rollback()
                    self._tx.rollback()
                raise exc.original
            except BaseException:
                if transactional:
                    self.queue.rollback()
                    self._tx.rollback()
                raise
            if transactional:
                self.queue.commit()
                self._tx.commit()
        # A listener may have completed a nested run beyond this call's cutoff.
        t_end = max(t_end, self.clock)
        self._tx.attr(self, "clock")
        self.clock = t_end
        end = records.EndRun(index=len(self.history), time=t_end, priority=0, seq=0, t_end=t_end)
        snapshot = [*self.history, end]
        busy = dict(self.busy_slots)
        for device_id, since in self.busy_since.items():
            busy[device_id] += t_end - since
        metrics = calculate_metrics(
            self.instance, self.plan, self.history, self.start_time, t_end, busy
        )
        metrics["events"] = self.counters["events"]
        metrics["plan_deviation_mean"] = (
            self.start_deviation_sum / self.start_deviation_count
            if self.start_deviation_count
            else 0.0
        )
        return SimResult(
            log=records.serialize_log(snapshot),
            metrics=metrics,
            final_plan=self.plan.model_copy(deep=True),
            final_instance=self.instance.model_copy(deep=True, update={"now": t_end}),
            stale_skipped=self.queue.stale_skipped,
            counters=dict(self.counters),
        )

    def list_devices(self) -> list[Device]:
        """Return independent device copies."""
        return [device.model_copy(deep=True) for device in self.instance.devices]

    def device_status(self, device_id: str) -> str:
        """Return the current aggregate device state."""
        if device_id not in self.states:
            raise ValueError("unknown device")
        return self.states[device_id].value

    def calendar(self, device_id: str, start: int, end: int) -> list[Any]:
        """Return clipped blocked windows for an existing device."""
        if device_id not in self.states or start < 0 or end <= start:
            raise ValueError("invalid calendar request")
        windows = [
            window.model_copy(
                deep=True, update={"start": max(start, window.start), "end": min(end, window.end)}
            )
            for window in self.instance.blocked
            if window.device_id == device_id and window.start < end and window.end > start
        ]
        for tid in self.running_by_device[device_id]:
            begin, finish, _ = self.running[tid]
            if begin < end and finish > start:
                windows.append(
                    BlockedWindow(
                        device_id=device_id,
                        start=max(start, begin),
                        end=min(end, finish),
                        kind="RUNNING",
                    )
                )
        return sorted(windows, key=lambda window: (window.start, window.end, window.kind))

    @property
    def listeners(self) -> list[Callable[[StatusChange], None]]:
        """Mutable status subscriptions, including transactional replacement."""
        return self._listeners

    @listeners.setter
    def listeners(self, callbacks: list[Callable[[StatusChange], None]]) -> None:
        if callbacks is self._listeners:
            return
        replacement = JournalList(self._tx)
        list.extend(replacement, callbacks)
        self._tx.attr(self, "_listeners")
        self._listeners = replacement

    @property
    def event_listeners(self) -> list[Callable[[SimEvent], None]]:
        """Mutable event subscriptions, including transactional replacement."""
        return self._event_listeners

    @event_listeners.setter
    def event_listeners(self, callbacks: list[Callable[[SimEvent], None]]) -> None:
        if callbacks is self._event_listeners:
            return
        replacement = JournalList(self._tx)
        list.extend(replacement, callbacks)
        self._tx.attr(self, "_event_listeners")
        self._event_listeners = replacement

    def add_status_listener(self, callback: Callable[[StatusChange], None]) -> None:
        """Subscribe to device state transitions."""
        self.listeners.append(callback)

    def add_event_listener(self, callback: Callable[[SimEvent], None]) -> None:
        """Notify once after each applied event, restoring its boundary on failure."""
        self.event_listeners.append(callback)

    def confirm_start(self, device_id: str, task_id: str, at: int) -> None:
        """Check that a start request exactly matches the current plan."""
        assignment = self.plan.assignments.get(task_id)
        if assignment is None or assignment.device_id != device_id or assignment.start != at:
            raise ValueError("start does not match current plan")
