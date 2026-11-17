"""CP-SAT calls with the exact validation evidence retained for each candidate."""

from collections.abc import Sequence

from scheduler_core.impact import EventType, analyze_impact, neighborhoods
from scheduler_core.models import Instance, Plan, ReplanParams, ReplanResult
from scheduler_core.replanning.events import prepare_raw
from scheduler_core.replanning.pool import _candidate_context, replan_candidates
from scheduler_core.solve_initial import SolveInitialResult, solve_initial_detailed
from scheduler_core.validation_context import ValidationContext

from .store import Evidence


def initial(instance: Instance) -> tuple[SolveInitialResult, Evidence | None]:
    result = solve_initial_detailed(instance)
    evidence = None if result.plan is None else Evidence(instance, result.plan, None, None, None, 0)
    return result, evidence


def replan(
    instance: Instance,
    base: Plan,
    events: Sequence[EventType],
    context: ValidationContext,
    revision: int,
    params: ReplanParams | None = None,
    *,
    post_applied: bool = False,
    full: bool = False,
) -> tuple[Instance, ReplanResult, list[Evidence]]:
    """Solve once and retain post-world, candidate-level free set and real context."""
    p = params or ReplanParams()
    if post_applied:
        post, effective = instance.model_copy(deep=True), context.model_copy(deep=True)
    else:
        post, effective = prepare_raw(instance, base, events, context)
    result = replan_candidates(
        post, base, events, p, context=effective, post_applied=True, full=full
    )
    impact = analyze_impact(post, base, events, p.window_slots, context=effective)
    levels = neighborhoods(post, base, impact, p.window_slots)
    evidence = []
    for candidate in result.candidates:
        candidate_context = _candidate_context(effective, candidate.plan.id, base, post, events)
        item = Evidence(
            post,
            candidate.plan,
            base,
            frozenset(levels[candidate.level]),
            candidate_context,
            revision,
        )
        item.checked()
        evidence.append(item)
    return post, result, evidence
