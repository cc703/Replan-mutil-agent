"""Declared tool permissions and read-only helpers for model-facing suggestions."""

from datetime import datetime
from collections.abc import Sequence
from typing import Literal

from scheduler_core.models import Instance, Plan, ReplanResult
from scheduler_core.impact import EventType, analyze_impact as analyze_impact
from scheduler_core.diagnose import diagnose_detailed as diagnose_infeasibility
from scheduler_core.plan_diff import TaskPlanDiff, diff_plans
from scheduler_core.relax import suggest_relaxations_detailed as suggest_relaxation
from scheduler_core.solve_initial import solve_initial_detailed as solve_initial
from scheduler_core.validate import validate
from scheduler_core.validation_context import ValidationContext

from .ir import Proposal, check_proposal
from .store import WorldStore

__all__ = [
    "PERMISSIONS",
    "model_tool_allowed",
    "resolve_entity",
    "parse_time",
    "validate_ir",
    "get_plan",
    "get_schedule_view",
    "replay",
    "analyze_impact",
    "solve_initial",
    "replan",
    "diagnose_infeasibility",
    "suggest_relaxation",
    "compare_plans",
    "verify_plan",
    "commit_ir",
    "commit_plan",
    "rollback_plan",
]

PERMISSIONS: dict[str, Literal["L0", "L1", "L2"]] = {
    "get_plan": "L0",
    "get_schedule_view": "L0",
    "resolve_entity": "L0",
    "parse_time": "L0",
    "validate_ir": "L0",
    "analyze_impact": "L0",
    "solve_initial": "L0",
    "replan": "L0",
    "diagnose_infeasibility": "L0",
    "suggest_relaxation": "L0",
    "compare_plans": "L0",
    "verify_plan": "L0",
    "commit_ir": "L1",
    "commit_plan": "L2",
    "rollback_plan": "L2",
    "replay": "L0",
}


def model_tool_allowed(name: str) -> bool:
    """Model suggestions may invoke read-only operations, never approval-bearing writes."""
    return PERMISSIONS.get(name) == "L0"


def resolve_entity(text: str, ids: set[str], aliases: dict[str, set[str]]) -> list[str]:
    """Return matching existing IDs; do not guess when aliases are ambiguous."""
    matches = ({text} if text in ids else set()) | (aliases.get(text, set()) & ids)
    return sorted(matches)


def parse_time(instance: Instance, value: datetime) -> int:
    """Require an aware, in-range, aligned absolute instant."""
    return instance.axis.to_slot(value)


def validate_ir(instance: Instance, proposal: Proposal) -> None:
    check_proposal(proposal, instance)


def get_plan(store: WorldStore) -> Plan:
    evidence = store.versions[store.active]
    if evidence.instance != store.instance:
        raise ValueError("active plan is stale in the current world")
    evidence.checked()
    return evidence.plan.model_copy(deep=True)


def get_schedule_view(store: WorldStore) -> list[dict[str, object]]:
    return [
        assignment.model_dump(mode="json") for assignment in get_plan(store).assignments.values()
    ]


def replay(store: WorldStore) -> list[dict[str, object]]:
    """Return a session-local copy of the human decision audit."""
    return store.audit


def replan(
    store: WorldStore, events: Sequence[EventType], context: ValidationContext
) -> ReplanResult:
    return store.solve(events, context)


def commit_ir(
    store: WorldStore,
    token: str,
    payload: object,
    post: Instance,
    actor: str,
    revision: int,
    context: ValidationContext,
) -> None:
    store.apply_world(token, payload, post, actor, revision, context)


def commit_plan(store: WorldStore, token: str, candidate_id: str, actor: str) -> None:
    store.commit(token, candidate_id, actor)


def rollback_plan(
    store: WorldStore, token: str, version_id: str, actor: str, context: ValidationContext
) -> None:
    store.rollback(token, version_id, actor, context)


def compare_plans(store: WorldStore, candidate_id: str) -> list[TaskPlanDiff]:
    base = store.versions[store.active].plan
    return diff_plans(store.instance, base, store.show(candidate_id))


def verify_plan(instance: Instance, plan: Plan) -> bool:
    """Initial-plan validation only; replans require retained evidence via store.show."""
    return validate(instance, plan).passed
