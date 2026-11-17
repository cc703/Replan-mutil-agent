"""In-memory world, candidate evidence and independently guarded versions."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Sequence
from datetime import datetime, timezone
import json
from threading import RLock
from typing import Any, Literal

from scheduler_core.models import Instance, Plan
from scheduler_core.impact import EventType, analyze_impact, neighborhoods
from scheduler_core.models import ReplanParams, ReplanResult
from scheduler_core.validate import validate
from scheduler_core.validation_context import ValidationContext

from .permits import Binding, PermitStore, payload_digest


@dataclass(frozen=True)
class Evidence:
    """The exact instance, parent, neighborhood and evidence of a CP-SAT result."""

    instance: Instance
    plan: Plan
    base: Plan | None
    free: frozenset[str] | None
    context: ValidationContext | None
    revision: int

    def checked(self) -> None:
        if not validate(
            self.instance, self.plan, base=self.base, free=self.free, context=self.context
        ).passed:
            raise ValueError("plan failed independent validation")


class WorldStore:
    """Single-process session state; persisted application history is out of scope."""

    def __init__(
        self,
        session: str,
        instance: Instance,
        initial: Evidence,
        aliases: dict[str, set[str]] | None = None,
    ) -> None:
        if initial.revision != 0 or initial.base is not None:
            raise ValueError("initial plan requires initial validation semantics")
        if initial.instance != instance:
            raise ValueError("initial instance mismatch")
        initial.checked()
        self.session = session
        self._aliases = {key: frozenset(value) for key, value in (aliases or {}).items()}
        self._instance = instance.model_copy(deep=True)
        self._revision = 0
        self._active = initial.plan.id
        self._versions: dict[str, Evidence] = {initial.plan.id: self._copy(initial)}
        self._candidates: dict[str, Evidence] = {}
        self._audit: list[dict[str, Any]] = []
        self._rejections: set[str] = set()
        self._permits = PermitStore()
        self._lock = RLock()

    @property
    def aliases(self) -> dict[str, frozenset[str]]:
        return dict(self._aliases)

    @property
    def instance(self) -> Instance:
        with self._lock:
            return self._instance.model_copy(deep=True)

    @property
    def revision(self) -> int:
        with self._lock:
            return self._revision

    @property
    def active(self) -> str:
        with self._lock:
            return self._active

    @property
    def versions(self) -> dict[str, Evidence]:
        with self._lock:
            return {key: self._copy(value) for key, value in self._versions.items()}

    @property
    def audit(self) -> list[dict[str, Any]]:
        with self._lock:
            import copy

            return copy.deepcopy(self._audit)

    @property
    def rejections(self) -> set[str]:
        with self._lock:
            return set(self._rejections)

    @staticmethod
    def _copy(value: Evidence) -> Evidence:
        return Evidence(
            value.instance.model_copy(deep=True),
            value.plan.model_copy(deep=True),
            value.base.model_copy(deep=True) if value.base else None,
            value.free,
            value.context.model_copy(deep=True) if value.context else None,
            value.revision,
        )

    def _binding(self, level: Literal["L1", "L2"], action: str, payload: object) -> Binding:
        return Binding(level, action, self.session, self._revision, payload_digest(payload))

    def authorize(self, level: Literal["L1", "L2"], action: str, payload: object) -> str:
        """Called solely by trusted UI after a human confirmation."""
        with self._lock:
            return self._permits.issue(self._binding(level, action, payload))

    def apply_world(
        self,
        token: str,
        payload: object,
        post: Instance,
        actor: str,
        expected_revision: int,
        context: ValidationContext,
    ) -> None:
        """Apply a validated L1 world change once, atomically with its approval."""
        with self._lock:
            binding = self._binding(
                "L1",
                "change",
                {
                    "proposal": payload,
                    "post": post.model_dump(mode="json"),
                    "revision": expected_revision,
                    "context": context.model_dump(mode="json"),
                },
            )

            def apply() -> None:
                if self._revision != expected_revision:
                    raise ValueError("world changed; refresh and reconfirm")
                from .changes import prepare_change
                from .ir import proposal_adapter

                proposal = proposal_adapter.validate_json(json.dumps(payload))
                expected, _, _ = prepare_change(
                    proposal,
                    self._instance,
                    self._versions[self._active].plan,
                    context,
                    self._aliases,
                )
                if expected != post:
                    raise ValueError("world differs from approved proposal")
                self._instance = post.model_copy(deep=True)
                self._revision += 1
                self._candidates.clear()
                self._record("change", actor, payload)

            self._permits.apply(token, binding, apply)

    def _add_candidate(self, evidence: Evidence) -> None:
        """Internal solver registration, with independent validation."""
        with self._lock:
            if evidence.revision != self._revision or evidence.instance != self._instance:
                raise ValueError("candidate belongs to a stale world")
            if evidence.plan.id in self._candidates:
                raise ValueError("candidate ID already exists")
            evidence.checked()
            self._candidates[evidence.plan.id] = self._copy(evidence)

    def solve(
        self,
        events: Sequence[EventType],
        context: ValidationContext,
        *,
        full: bool = False,
        params: ReplanParams | None = None,
    ) -> ReplanResult:
        """Run CP-SAT against the current world and register its evidence atomically."""
        from .solver import replan

        with self._lock:
            _, result, evidence = replan(
                self._instance,
                self._versions[self._active].plan,
                events,
                context,
                self._revision,
                params,
                post_applied=True,
                full=full,
            )
            for item in evidence:
                self._add_candidate(item)
            return result

    def show(self, candidate_id: str) -> Plan:
        with self._lock:
            evidence = self._candidates[candidate_id]
            if evidence.revision != self._revision or evidence.instance != self._instance:
                raise ValueError("candidate belongs to a stale world")
            evidence.checked()
            return evidence.plan.model_copy(deep=True)

    def commit(self, token: str, candidate_id: str, actor: str) -> None:
        with self._lock:
            evidence = self._candidates[candidate_id]
            payload = evidence.plan.model_dump(mode="json")
            binding = self._binding("L2", "commit", payload)

            def apply() -> None:
                self.show(candidate_id)
                version_id = f"{self._revision + 1}:{candidate_id}"
                self._versions[version_id] = self._copy(evidence)
                self._active = version_id
                self._revision += 1
                self._candidates.clear()
                self._record(
                    "commit", actor, {"version": version_id, "parent": evidence.plan.parent_id}
                )

            self._permits.apply(token, binding, apply)

    def rollback_payload(self, version_id: str, context: ValidationContext) -> dict[str, Any]:
        """Bind target, current parent and the trusted execution facts for L2."""
        with self._lock:
            base = self._versions[self._active].plan
            snapshot = context.snapshot
            if (
                snapshot is None
                or snapshot.plan_id != base.id
                or snapshot.as_of != self._instance.now
            ):
                raise ValueError("current execution snapshot required")
            observed = {record.task_id for record in snapshot.records}
            if any(
                task.status in {"RUNNING", "DONE"} and task.id not in observed
                for task in self._instance.tasks
            ):
                raise ValueError("incomplete execution snapshot")
            return {
                "target": version_id,
                "plan": self._versions[version_id].plan.model_dump(mode="json"),
                "parent": base.model_dump(mode="json"),
                "context": context.model_dump(mode="json"),
                "revision": self._revision,
                "now": self._instance.now,
            }

    def rollback(self, token: str, version_id: str, actor: str, context: ValidationContext) -> None:
        """Revalidate an older plan against the current physical world before L2."""
        with self._lock:
            evidence = self._versions[version_id]
            payload = self.rollback_payload(version_id, context)
            binding = self._binding("L2", "rollback", payload)

            def apply() -> None:
                base = self._versions[self._active].plan
                impact = analyze_impact(self._instance, base, [], context=context)
                free = neighborhoods(self._instance, base, impact, 48)[3]
                target = evidence.plan.model_copy(deep=True, update={"parent_id": base.id})
                if not validate(
                    self._instance, target, base=base, free=free, context=context
                ).passed:
                    raise ValueError("rollback failed current-world validation")
                new_id = f"{self._revision + 1}:rollback:{version_id}"
                self._versions[new_id] = Evidence(
                    self._instance.model_copy(deep=True),
                    target,
                    base.model_copy(deep=True),
                    frozenset(free),
                    context.model_copy(deep=True),
                    self._revision,
                )
                self._active = new_id
                self._revision += 1
                self._candidates.clear()
                self._record("rollback", actor, {"target": version_id})

            self._permits.apply(token, binding, apply)

    def _record(self, action: str, actor: str, payload: object = None) -> None:
        import copy

        self._audit.append(
            {
                "action": action,
                "actor": actor,
                "revision": self._revision,
                "at": datetime.now(timezone.utc).isoformat(),
                "payload": copy.deepcopy(payload),
            }
        )

    def record_rejection(self, action: str, actor: str, payload: object = None) -> None:
        with self._lock:
            if payload is not None:
                self._rejections.add(payload_digest(payload))
            self._record(f"reject:{action}", actor)
