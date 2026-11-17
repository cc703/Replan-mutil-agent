"""Serializable state shared by graph nodes."""

from typing import Any
from typing_extensions import TypedDict


class GraphState(TypedDict, total=False):
    action: str
    target: str
    text: str
    draft: dict[str, Any]
    error: str
    post: dict[str, Any]
    events: list[dict[str, Any]]
    context: dict[str, Any]
    prior_context: dict[str, Any]
    outcome: str
    candidates: list[str]
    prepared_revision: int
    remaining: list[dict[str, Any]]
    applied_events: list[dict[str, Any]]
    full_replan: bool
    diagnosis: dict[str, Any]
    proposals: list[dict[str, Any]]
    negotiation_count: int
    impact: dict[str, Any]
    candidate_metrics: dict[str, dict[str, float]]
