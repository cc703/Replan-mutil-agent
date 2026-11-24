"""Initial scheduling and CP-SAT replanning with durable validation evidence."""

from importlib.metadata import version
import math
import time
from typing import Any
from uuid import uuid4

from agent.evidence import candidate_facts
from agent.explain import explain
from scheduler_core.diagnose import diagnose_detailed
from scheduler_core.generation.integrity import check_instance_integrity
from scheduler_core.impact import analyze_impact, neighborhoods
from scheduler_core.models import Instance, Plan
from scheduler_core.relax import suggest_relaxations_detailed
from scheduler_core.replanning.pool import _candidate_context, replan_candidates
from scheduler_core.solve_initial import solve_initial_detailed

from .errors import ServiceError
from .hashing import instance_digest
from .plan_evidence import changes, plan_body
from .schemas import Evidence, InitialRequest, ReplanRequest, RollbackRequest
from .schemas_events import apply_facts, execution_context


def check_instance(instance: Instance) -> dict[str, Any]:
    try:
        check_instance_integrity(instance)
        execution_context(instance, Plan(id="import", assignments={}))
    except (ValueError, ServiceError) as exc:
        raise ServiceError("INVALID_INSTANCE", str(exc)) from exc
    return {
        "ok": True,
        "instance_sha256": instance_digest(instance),
        "summary": {
            "tasks": len(instance.tasks),
            "devices": len(instance.devices),
            "persons": len(instance.persons),
        },
    }


def initial(req: InitialRequest) -> dict[str, Any]:
    instance = req.instance
    info = check_instance(instance)
    try:
        solved = solve_initial_detailed(
            instance,
            time_limit_s=req.params.time_limit_s,
            num_workers=req.params.num_workers,
            seed=req.params.seed,
            objective_weights=req.params.objective_weights,
        )
    except ValueError as exc:
        raise ServiceError("INVALID_INSTANCE", str(exc)) from exc
    result: dict[str, Any] = {
        "result_status": "TIMEOUT" if solved.status == "UNKNOWN" else solved.status,
        "instance_post": instance.model_dump(mode="json"),
        "instance_post_sha256": info["instance_sha256"],
        "candidates": [],
        "conflict": None,
        "relaxations": [],
        "solver": {
            "ortools_version": version("ortools"),
            "wall_seconds": solved.wall_seconds,
            "status": solved.status,
            "budget_s": req.params.time_limit_s,
        },
    }
    if solved.status == "MODEL_INVALID":
        raise ServiceError("INVALID_INSTANCE", "The initial CP-SAT model is invalid")
    if solved.plan is not None:
        plan = solved.plan.model_copy(update={"id": uuid4().hex})
        body = plan_body(Evidence(instance=instance, plan=plan, revision=req.revision))
        candidate = {
            **body,
            "candidate_id": plan.id,
            "label": "初始计划",
            "level": 0,
            "weights": [1, 1],
            "f1": plan.metrics.tardiness,
            "f2": 0,
            "f3": 0,
            "diff": [],
            "explanation": None,
        }
        result.update(
            result_status="OK",
            candidates=[candidate],
            plan=plan.model_dump(mode="json"),
            plan_sha256=body["plan_sha256"],
            validation=body["validation"],
            view=body["view"],
        )
    return result


def replan(req: ReplanRequest) -> dict[str, Any]:
    started = time.perf_counter()
    base = req.base_plan
    context = req.context or execution_context(req.instance, base)
    post, events, context = apply_facts(req.instance, base, req.events, context)
    budget = req.budget_s or req.params.total_budget_s
    if not math.isfinite(budget) or not 0 < budget <= 120:
        raise ServiceError("VALIDATION_ERROR", "Replan budget must be in (0,120] seconds")
    params = req.params.model_copy(update={"total_budget_s": budget})
    if params.num_workers < 1 or params.num_workers > 32:
        raise ServiceError("VALIDATION_ERROR", "Replan workers must be in [1,32]")
    try:
        solved = replan_candidates(
            post,
            base,
            events,
            params,
            context=context,
            post_applied=True,
            max_candidates=req.max_candidates,
            diagnose_on_infeasible=False,
        )
        impact = analyze_impact(post, base, events, params.window_slots, context=context)
        free = neighborhoods(post, base, impact, params.window_slots)
    except ValueError as exc:
        raise ServiceError("VALIDATION_ERROR", str(exc)) from exc
    candidates = []
    rejected: list[dict[str, Any]] = []
    warnings: list[str] = []
    for candidate in solved.candidates:
        effective = _candidate_context(context, candidate.plan.id, base, post, events)
        evidence = Evidence(
            instance=post,
            plan=candidate.plan,
            base_plan=base,
            free=free[candidate.level],
            context=effective,
            revision=req.revision,
        )
        try:
            body = plan_body(evidence)
        except ServiceError as exc:
            if exc.code != "VALIDATION_FAILED":
                raise
            rejected.extend(exc.details["violations"])
            warnings.append(f"候选 {candidate.plan.id} 未通过独立校验")
            continue
        metrics = {"f1": candidate.f1, "f2": candidate.f2, "f3": candidate.f3}
        explanation = None
        if req.explain:
            facts = candidate_facts(post, base, candidate.plan, impact.model_dump(), metrics)
            explanation = explain(facts, lambda: [], retries=0).text
        body.update(
            candidate_id=candidate.plan.id,
            label=candidate.label,
            level=candidate.level,
            weights=candidate.weights,
            diff=changes(post, base, candidate.plan),
            explanation=explanation,
            **metrics,
        )
        candidates.append(body)
    if solved.status == "OK" and not candidates:
        raise ServiceError(
            "VALIDATION_FAILED",
            "No candidate passed independent validation",
            422,
            violations=rejected,
        )
    conflict, relaxations = None, []
    remaining = budget - (time.perf_counter() - started)
    if solved.status == "INFEASIBLE" and remaining > 0 and not context.deadline_authorizations:
        diagnosis = diagnose_detailed(post, base, free[3], time_limit_s=remaining, context=context)
        if diagnosis.core:
            conflict = {**diagnosis.core.model_dump(), "minimal": diagnosis.minimal}
            remaining = budget - (time.perf_counter() - started)
            if remaining > 0:
                options = suggest_relaxations_detailed(
                    post, base, free[3], diagnosis.core, time_limit_s=remaining, context=context
                )
                relaxations = [
                    {
                        **proposal.option.model_dump(),
                        "deltas": proposal.deltas,
                        "verified": proposal.verified,
                        "hypothetical": True,
                        "cost_unit": "任务权重×截止期延后槽数",
                    }
                    for proposal in options.proposals
                    if proposal.verified
                ]
    return {
        "result_status": solved.status,
        "instance_post": post.model_dump(mode="json"),
        "instance_post_sha256": instance_digest(post),
        "candidates": candidates,
        "impact": {
            **impact.model_dump(mode="json"),
            "frozen": sorted(impact.frozen),
            "affected": sorted(impact.affected),
            "unaffected": sorted(impact.unaffected),
        },
        "conflict": conflict,
        "relaxations": relaxations,
        "warnings": warnings,
        "solver": {
            "ortools_version": version("ortools"),
            "wall_seconds": time.perf_counter() - started,
            "budget_s": budget,
            "level_reached": solved.level_reached,
        },
    }


def rollback(req: RollbackRequest) -> dict[str, Any]:
    base = req.base_plan
    try:
        context = req.context or execution_context(req.instance, base)
        post, events, context = apply_facts(req.instance, base, req.events, context)
        impact = analyze_impact(post, base, events, context=context)
        free = neighborhoods(post, base, impact, 48)[3]
        target = req.target_plan.model_copy(update={"id": uuid4().hex, "parent_id": base.id})
        evidence = Evidence(
            instance=post,
            plan=target,
            base_plan=base,
            free=free,
            context=context,
            revision=req.revision,
        )
        return {**plan_body(evidence), "changes": changes(post, base, target)}
    except ServiceError as exc:
        raise ServiceError("ROLLBACK_INFEASIBLE", str(exc), 422, **exc.details) from exc
    except ValueError as exc:
        raise ServiceError("ROLLBACK_INFEASIBLE", "Current facts rejected rollback", 422) from exc
