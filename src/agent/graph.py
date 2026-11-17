"""A resumable human-in-the-loop graph for one scheduling change."""

from collections.abc import Callable
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from scheduler_core.validation_context import ValidationContext

from .explain import Claim, Explanation, Fact, explain
from .routing import route
from .change_nodes import change_nodes
from .view_nodes import view_nodes
from .permits import payload_digest
from .store import WorldStore
from .trace import Trace


from .state import GraphState
from .negotiation import diagnose, negotiate, negotiation_facts


def build_graph(
    store: WorldStore,
    extractor: Callable[[str], dict[str, Any]],
    context: ValidationContext,
    trace: Trace | None = None,
    explainer: Callable[[dict[str, Fact]], list[Claim]] | None = None,
    router: Callable[[str], dict[str, str]] | None = None,
) -> Any:
    """Compile a graph with process-local checkpoints; resume by the same thread id."""

    explanation_cache: dict[tuple[int, str, str], Explanation] = {}

    def route_node(state: GraphState) -> GraphState:
        return route(state, router)

    changes = change_nodes(store, extractor, context)

    def diagnose_node(state: GraphState) -> GraphState:
        return diagnose(state, store)

    def negotiate_node(state: GraphState) -> GraphState:
        facts = negotiation_facts(state)
        fact_payload = {
            key: {"kind": value.kind, "value": value.value, "unit": value.unit}
            for key, value in facts.items()
        }
        key = (store.revision, "negotiation", payload_digest(fact_payload))
        if key not in explanation_cache:
            explanation_cache[key] = explain(
                facts, lambda: explainer(dict(facts)) if explainer else []
            )
        explanation = explanation_cache[key]
        result = negotiate(state, store, explanation)
        if trace:
            trace.explanation(explanation.correct, explanation.total, explanation.fallback)
        return result

    views = view_nodes(store, context, trace, explainer, explanation_cache)

    builder = StateGraph(GraphState)

    def instrument(
        name: str, node: Callable[[GraphState], GraphState]
    ) -> Callable[[GraphState], GraphState]:
        import time

        def run(state: GraphState) -> GraphState:
            started = time.perf_counter()
            status = "unknown"
            valid = False
            try:
                result = node(state)
                valid = not bool(result.get("error"))
                status = "ok" if valid else "failed"
                return result
            finally:
                if trace:
                    category = {
                        "prepare": "extract",
                        "confirm_change": "change",
                        "advance": "route",
                        "select": "commit",
                        "query": "route",
                        "rollback": "commit",
                        "diagnose": "solve",
                        "negotiate": "clarify",
                    }.get(name, name)
                    trace.record(
                        category,
                        elapsed_ms=(time.perf_counter() - started) * 1000,
                        tokens=None,
                        schema_ok=valid,
                        status=status,
                    )

        return run

    nodes = {
        "route": route_node,
        "diagnose": diagnose_node,
        "negotiate": negotiate_node,
        **changes,
        **views,
    }
    for name, node in nodes.items():
        # LangGraph generic TypedDict bounds are not understood by mypy 1.15.
        builder.add_node(name, instrument(name, node), input_schema=GraphState)  # type: ignore[call-overload]
    builder.add_edge(START, "route")
    builder.add_conditional_edges(
        "route",
        lambda s: s.get("action", "change"),
        {"change": "extract", "query": "query", "rollback": "rollback"},
    )
    builder.add_edge("extract", "prepare")
    builder.add_conditional_edges(
        "prepare", lambda s: "clarify" if s.get("error") else "confirm_change"
    )
    builder.add_conditional_edges("clarify", lambda s: END if s.get("outcome") else "prepare")
    builder.add_conditional_edges(
        "confirm_change",
        lambda s: END if s.get("outcome") else ("advance" if s.get("remaining") else "solve"),
    )
    builder.add_edge("advance", "prepare")
    builder.add_conditional_edges(
        "solve",
        lambda s: "select"
        if s.get("candidates")
        else (
            "diagnose"
            if s.get("outcome") == "INFEASIBLE" and s.get("negotiation_count", 0) < 3
            else END
        ),
    )
    builder.add_edge("diagnose", "negotiate")
    builder.add_conditional_edges("negotiate", lambda s: END if s.get("outcome") else "prepare")
    builder.add_edge("select", END)
    builder.add_edge("query", END)
    builder.add_edge("rollback", END)
    return builder.compile(checkpointer=InMemorySaver())
