"""Validated candidate presentation, query and rollback nodes."""

from collections.abc import Callable
from langgraph.types import interrupt
from scheduler_core.validation_context import ValidationContext
from .evidence import candidate_facts
from .explain import Claim, Explanation, Fact, explain
from .permits import payload_digest
from .state import GraphState
from .store import WorldStore
from .trace import Trace


def view_nodes(
    store: WorldStore,
    context: ValidationContext,
    trace: Trace | None,
    explainer: Callable[[dict[str, Fact]], list[Claim]] | None,
    explanation_cache: dict[tuple[int, str, str], Explanation],
) -> dict[str, Callable[[GraphState], GraphState]]:
    def select(state: GraphState) -> GraphState:
        plans = [store.show(candidate).model_dump(mode="json") for candidate in state["candidates"]]
        base = store.versions[store.active].plan
        explanations = []
        measures = []
        verified_claims = []
        for candidate in state["candidates"]:
            plan = store.show(candidate)
            facts = candidate_facts(
                store.instance,
                base,
                plan,
                state.get("impact", {}),
                state.get("candidate_metrics", {}).get(candidate, {}),
            )
            fact_payload = {
                key: {"kind": value.kind, "value": value.value, "unit": value.unit}
                for key, value in facts.items()
            }
            cache_key = (store.revision, candidate, payload_digest(fact_payload))
            if cache_key not in explanation_cache:
                explanation_cache[cache_key] = explain(
                    facts, lambda: explainer(dict(facts)) if explainer else []
                )
            explanation = explanation_cache[cache_key]
            explanations.append(explanation.text)
            verified_claims.append([claim.model_dump(mode="json") for claim in explanation.claims])
            measures.append((explanation.correct, explanation.total, explanation.fallback))
        response = interrupt(
            {"kind": "L2", "plans": plans, "explanations": explanations, "claims": verified_claims}
        )
        if trace:
            for correct, total, fallback in measures:
                trace.explanation(correct, total, fallback)
        if not isinstance(response, dict):
            store.record_rejection("commit", "human")
            return {"outcome": "rejected"}
        store.commit(response["token"], response["candidate_id"], "human")
        return {"outcome": "committed"}

    def query(state: GraphState) -> GraphState:
        stale = store.versions[store.active].instance != store.instance
        detail = f"active={store.active}; revision={store.revision}; stale={stale}"
        if not stale:
            evidence = store.versions[store.active]
            evidence.checked()
            detail += "; plan=" + evidence.plan.model_dump_json()
        return {"outcome": detail}

    def rollback(state: GraphState) -> GraphState:
        target = state.get("target", "")
        if not target:
            answer = interrupt({"kind": "ROLLBACK_TARGET", "versions": list(store.versions)})
            if not isinstance(answer, str) or answer not in store.versions:
                return {"outcome": "cancelled"}
            target = answer
        payload = store.rollback_payload(target, context)
        token = interrupt({"kind": "L2_ROLLBACK", "binding": payload})
        if not isinstance(token, str):
            store.record_rejection("rollback", "human", payload)
            return {"outcome": "rejected"}
        store.rollback(token, target, "human", context)
        return {"outcome": "rolled_back"}

    return {"select": select, "query": query, "rollback": rollback}
