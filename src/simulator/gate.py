"""Independent plan adoption gate and execution evidence construction."""

from dataclasses import dataclass
from typing import Any

from . import log as records
from .events import EventKind, SimEvent
from scheduler_core.models import Instance, Plan, TaskOverrun, ValidationReport
from scheduler_core.validate import validate
from scheduler_core.validation_context import (
    ExecutionRecord,
    ExecutionSnapshot,
    FrozenEndChange,
    NotStartedEvidence,
    ValidationContext,
)


class SchedulerFailure(Exception):
    """Carry a callback exception to the event loop for transactional retry."""

    def __init__(self, original: Exception) -> None:
        self.original = original


@dataclass(frozen=True)
class ExecutionEvidence:
    """Observed execution facts, including a reported overrun where applicable."""

    task_id: str
    status: str
    device_id: str
    person_id: str | None
    start: int
    event_id: str
    actual_end: int | None = None
    reported_end: int | None = None
    overrun_event_id: str | None = None
    overrun_at: int | None = None


def context_for_plan(
    base: Plan,
    candidate: Plan,
    clock: int,
    base_as_of: int,
    evidence: list[ExecutionEvidence],
    not_started: list[NotStartedEvidence] | None = None,
) -> ValidationContext:
    """Build a validator snapshot from observed execution, without mutating inputs."""
    records: list[ExecutionRecord] = []
    changes: list[FrozenEndChange] = []
    for item in evidence:
        assignment = base.assignments[item.task_id]
        if item.status == "DONE":
            records.append(
                ExecutionRecord(
                    task_id=item.task_id,
                    status="DONE",
                    device_id=item.device_id,
                    person_id=item.person_id,
                    start=item.start,
                    actual_end=item.actual_end,
                    event_id=item.event_id,
                )
            )
        elif item.status == "RUNNING":
            known_end = item.reported_end if item.reported_end is not None else assignment.end
            records.append(
                ExecutionRecord(
                    task_id=item.task_id,
                    status="RUNNING",
                    device_id=item.device_id,
                    person_id=item.person_id,
                    start=item.start,
                    planned_end=assignment.end,
                    remaining_estimate=max(0, known_end - clock),
                    event_id=item.event_id,
                )
            )
            proposed = candidate.assignments.get(item.task_id)
            if (
                proposed is not None
                and proposed.end > assignment.end
                and item.reported_end is not None
                and item.overrun_event_id is not None
                and item.overrun_at is not None
            ):
                changes.append(
                    FrozenEndChange(
                        task_id=item.task_id,
                        plan_id=candidate.id,
                        base_plan_id=base.id,
                        old_end=assignment.end,
                        new_end=proposed.end,
                        event_id=item.overrun_event_id,
                        acted_at=item.overrun_at,
                    )
                )
        else:
            raise ValueError("evidence must describe RUNNING or DONE")
    return ValidationContext(
        snapshot=ExecutionSnapshot(
            plan_id=base.id, as_of=clock, base_as_of=base_as_of, records=records
        ),
        end_changes=changes,
        not_started=not_started or [],
    )


def check_candidate(
    inst: Instance, base: Plan, candidate: Plan, context: ValidationContext
) -> tuple[bool, str | None, str | None]:
    """Require parent linkage and independent semantic validation for adoption."""
    if candidate.parent_id != base.id:
        return False, "PARENT", "candidate parent does not match current plan"
    report: ValidationReport = validate(inst, candidate, base=base, free=None, context=context)
    if not report.passed:
        first = report.violations[0]
        return False, first.code, first.detail
    return True, None, None


class PlanHandling:
    """Plan updates, independent acceptance and retry behavior for the engine."""

    def _evidence(self: Any) -> list[ExecutionEvidence]:
        result: list[ExecutionEvidence] = []
        for tid, (start, _, seq) in self.running.items():
            a = self.plan.assignments[tid]
            overrun = self.known_overruns.get(tid)
            result.append(
                ExecutionEvidence(
                    task_id=tid,
                    status="RUNNING",
                    device_id=a.device_id,
                    person_id=a.person_id,
                    start=start,
                    event_id=f"start:{seq}",
                    reported_end=overrun[0] if overrun else None,
                    overrun_event_id=overrun[1] if overrun else None,
                    overrun_at=overrun[2] if overrun else None,
                )
            )
        for tid, (start, end, seq) in self.done.items():
            a = self.plan.assignments[tid]
            result.append(
                ExecutionEvidence(
                    task_id=tid,
                    status="DONE",
                    device_id=a.device_id,
                    person_id=a.person_id,
                    start=start,
                    actual_end=end,
                    event_id=f"end:{seq}",
                )
            )
        return result

    def _adopt(self: Any, candidate: Plan) -> None:
        old = self.plan
        changed = {
            tid
            for tid in set(old.assignments) | set(candidate.assignments)
            if old.assignments.get(tid) != candidate.assignments.get(tid)
        }
        cleared_devices = set()
        for tid in changed & self.setups:
            cleared_devices.add(old.assignments[tid].device_id)
            self._setup_remove(tid)
        for tid, fact in list(self.not_started.items()):
            if (
                tid in changed
                or tid not in self.tasks
                or self.tasks[tid].status not in {"PENDING", "SCHEDULED"}
            ):
                self._tx.item(self.not_started, tid)
                self.not_started.pop(tid, None)
            else:
                self._tx.item(self.not_started, tid)
                self.not_started[tid] = fact.model_copy(
                    update={"base_plan_id": candidate.id, "observed_at": self.clock}
                )
        self._tx.attr(self, "plan")
        self.plan = candidate.model_copy(deep=True)
        for device_id in sorted(cleared_devices):
            self._state(device_id)
        self._tx.attr(self, "base_as_of")
        self.base_as_of = self.clock
        for tid in changed:
            if (
                tid in self.tasks
                and tid in candidate.assignments
                and self._task(tid).status == "PENDING"
            ):
                self._task_state(tid, "SCHEDULED")
            if tid not in self.running:
                self._tx.member(self.blocked_starts, tid)
                self.blocked_starts.discard(tid)
                self._tx.item(self.epochs, tid)
                self.epochs[tid] = self.epochs.get(tid, 0) + 1
                self.queue.set_epoch(tid, self.epochs[tid])
        self._enqueue_assignments(changed - self.running.keys())
        self._record(
            records.ReplanResultRecord,
            result="adopted",
            plan_json=records.canonical_json(candidate),
            plan_hash=records.content_hash(candidate),
        )

    def _flush(self: Any) -> None:
        if self.window.due is None or self.window.due > self.clock:
            return
        batch = self.window.batch()
        post = self.instance.model_copy(deep=True, update={"now": self.clock})
        evidence = self._evidence()
        facts = [fact.model_copy(deep=True) for fact in self.not_started.values()]
        snapshot = context_for_plan(
            self.plan, self.plan, self.clock, self.base_as_of, evidence, facts
        )
        try:
            args = (
                post.model_copy(deep=True),
                self.plan.model_copy(deep=True),
                [event.model_copy(deep=True) for event in batch],
            )
            if self.scheduler_with_context is not None:
                candidate = self.scheduler_with_context(*args, snapshot.model_copy(deep=True))
            else:
                candidate = self.scheduler(*args)
        except Exception as exc:
            raise SchedulerFailure(exc) from exc
        for name in ("events", "due", "last_call", "failures"):
            self._tx.attr(self.window, name)
        self.window.called(self.clock)
        self._record(records.ReplanCalled, events_json=records.canonical_json(batch))
        self._tx.item(self.counters, "replan_calls")
        self.counters["replan_calls"] += 1
        if candidate is None:
            self._record(records.ReplanResultRecord, result="none")
            self._retry()
            return
        context = context_for_plan(
            self.plan, candidate, self.clock, self.base_as_of, evidence, facts
        )
        accepted, code, reason = check_candidate(post, self.plan, candidate, context)
        self._tx.item(self.counters, "validations")
        self.counters["validations"] += 1
        if not accepted:
            self._record(
                records.ReplanResultRecord,
                result="rejected",
                code=code,
                reason=reason,
                plan_json=records.canonical_json(candidate),
                plan_hash=records.content_hash(candidate),
            )
            self._retry()
            return
        self._adopt(candidate)
        for name in ("events", "due", "last_call", "failures"):
            self._tx.attr(self.window, name)
        self.window.success()

    def _retry(self: Any) -> None:
        for name in ("events", "due", "last_call", "failures"):
            self._tx.attr(self.window, name)
        due = self.window.failed(self.clock)
        if due is None:
            self._record(records.ReplanAbandoned, reason="consecutive failures exceeded limit")
        else:
            self._push(SimEvent(time=due, kind=EventKind.REPLAN_FLUSH))

    def _overrun(self: Any, event: SimEvent) -> None:
        assert event.task_id
        tid = event.task_id
        if tid not in self.running:
            return
        if tid in self.known_overruns:
            return
        if isinstance(event.payload, TaskOverrun):
            start, old_end, seq = self.running[tid]
            if event.payload.new_end > old_end:
                self._tx.item(self.running, tid)
                self.running[tid] = (start, event.payload.new_end, seq)
                assignment = self.plan.assignments[tid]
                self._push(
                    SimEvent(
                        time=event.payload.new_end,
                        kind=EventKind.TASK_END,
                        device_id=assignment.device_id,
                        task_id=tid,
                        plan_epoch=self.epochs.get(tid, 0),
                    )
                )
        end = (
            event.payload.new_end
            if isinstance(event.payload, TaskOverrun)
            else self.running[tid][1]
        )
        if end <= self.plan.assignments[tid].end:
            return
        self._tx.item(self.known_overruns, tid)
        self.known_overruns[tid] = (end, f"overrun:{event.seq}", self.clock)
        self._record(records.TaskOverrunRecord, task_id=tid, new_end=end)
        assignment = self.plan.assignments[tid].model_copy(update={"end": end})
        assignments = dict(self.plan.assignments)
        assignments[tid] = assignment
        candidate = self.plan.model_copy(
            deep=True,
            update={
                "id": f"{self.plan.id}.ov{self.counters['overrun_plans'] + 1}",
                "parent_id": self.plan.id,
                "assignments": assignments,
            },
        )
        post = self.instance.model_copy(deep=True, update={"now": self.clock})
        context = context_for_plan(
            self.plan,
            candidate,
            self.clock,
            self.base_as_of,
            self._evidence(),
            list(self.not_started.values()),
        )
        report = validate(post, candidate, base=self.plan, context=context)
        self._tx.item(self.counters, "validations")
        self.counters["validations"] += 1
        reported = event.model_copy(update={"payload": TaskOverrun(task_id=tid, new_end=end)})
        if any(v.code in {"V2", "V3", "V5", "V6", "V7", "V9"} for v in report.violations):
            self._trigger(reported, "TASK_OVERRUN")
        elif report.passed:
            self._tx.item(self.counters, "overrun_plans")
            self.counters["overrun_plans"] += 1
            self._adopt(candidate)
        else:
            self._trigger(reported, "TASK_OVERRUN")
