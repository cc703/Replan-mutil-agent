"""Evidence-bounded infeasibility diagnosis and human negotiation."""

from typing import Any
from langgraph.types import interrupt
from scheduler_core.models import DeviceOutage, TaskOverrun, UrgentInsert
from scheduler_core.diagnose import diagnose_detailed
from scheduler_core.impact import analyze_impact, neighborhoods
from scheduler_core.relax import suggest_relaxations_detailed
from scheduler_core.validation_context import ValidationContext
from .permits import payload_digest
from .state import GraphState
from .store import WorldStore
from .explain import Explanation, Fact


def diagnose(state: GraphState, store: WorldStore) -> GraphState:
    event_types: dict[str, type[DeviceOutage] | type[TaskOverrun] | type[UrgentInsert]] = {
        "DEVICE_OUTAGE": DeviceOutage,
        "TASK_OVERRUN": TaskOverrun,
        "URGENT_INSERT": UrgentInsert,
    }
    events = [
        event_types[item["type"]].model_validate(item) for item in state.get("applied_events", [])
    ]
    ctx = ValidationContext.model_validate(state["context"])
    base = store.versions[store.active].plan
    impact = analyze_impact(store.instance, base, events, context=ctx)
    free = neighborhoods(store.instance, base, impact, 48)[3]
    diagnosis = diagnose_detailed(store.instance, base, free, context=ctx)
    summary: dict[str, Any] = {"status": diagnosis.status, "minimal": diagnosis.minimal}
    summary.update(
        {
            "solves": diagnosis.solves,
            "groups_total": diagnosis.groups_total,
            "reasons": list(diagnosis.reasons),
        }
    )
    proposals: list[dict[str, Any]] = []
    if diagnosis.core is not None:
        summary["groups"] = diagnosis.core.group_ids
        summary["descriptions"] = diagnosis.core.descriptions
        result = suggest_relaxations_detailed(
            store.instance, base, free, diagnosis.core, k=3, context=ctx
        )
        proposals = [
            {
                "deltas": item.deltas,
                "cost": item.option.cost,
                "optimal": item.optimal,
                "groups": item.option.relaxed_groups,
                "description": item.option.description,
            }
            for item in result.proposals
            if item.verified
        ]
        proposals = [
            item for item in proposals if payload_digest(item["deltas"]) not in store.rejections
        ]
    return {"diagnosis": summary, "proposals": proposals}


def negotiation_facts(state: GraphState) -> dict[str, Fact]:
    """Expose only facts directly returned by diagnosis and hypothetical relaxation."""
    summary = state["diagnosis"]
    facts = {
        "诊断状态": Fact("text", str(summary["status"]), ""),
        "不可约性": Fact("text", "已证明" if summary["minimal"] else "未证明", ""),
        "诊断求解次数": Fact("number", summary["solves"], "次"),
        "约束组总数": Fact("number", summary["groups_total"], "个"),
    }
    for index, group in enumerate(summary.get("groups", [])):
        facts[f"冲突组 {index}"] = Fact("text", group, "")
    for index, description in enumerate(summary.get("descriptions", [])):
        facts[f"冲突描述 {index}"] = Fact("text", description, "")
    for index, reason in enumerate(summary.get("reasons", [])):
        facts[f"诊断原因 {index}"] = Fact("text", reason, "")
    for index, proposal in enumerate(state["proposals"]):
        facts[f"假设方案 {index} 代价"] = Fact("number", proposal["cost"], "加权槽")
        facts[f"假设方案 {index} 最优性"] = Fact(
            "text", "已证明" if proposal["optimal"] else "未证明", ""
        )
        facts[f"假设方案 {index} 描述"] = Fact("text", proposal["description"], "")
        for task, delta in proposal["deltas"].items():
            facts[f"假设方案 {index} 任务 {task} 延后"] = Fact("number", delta, "槽")
        for group in proposal["groups"]:
            facts[f"假设方案 {index} 约束组 {group}"] = Fact("text", group, "")
    return facts


def negotiate(state: GraphState, store: WorldStore, explanation: Explanation) -> GraphState:
    response = interrupt(
        {
            "kind": "NEGOTIATION",
            "diagnosis": state["diagnosis"],
            "proposals": state["proposals"],
            "notice": "假设方案不授权超期，修改截止须另行确认",
            "explanation": explanation.text,
            "claims": [claim.model_dump(mode="json") for claim in explanation.claims],
        }
    )
    if (
        not isinstance(response, int)
        or isinstance(response, bool)
        or not 0 <= response < len(state["proposals"])
    ):
        for item in state["proposals"]:
            store.record_rejection("negotiation", "human", item["deltas"])
        if not state["proposals"]:
            store.record_rejection("negotiation", "human")
        return {"outcome": "rejected"}
    proposal = state["proposals"][response]
    tasks = {task.id: task for task in store.instance.tasks}
    drafts = []
    for task_id, delta in sorted(proposal["deltas"].items()):
        task = tasks[task_id]
        if task.deadline is None or task.deadline_level != "NEGOTIABLE":
            raise ValueError("proposal is not a negotiable deadline")
        drafts.append(
            {
                "kind": "DEADLINE",
                "strength": "HARD",
                "task": {"original": task_id, "resolved_id": task_id, "confidence": 1.0},
                "deadline": store.instance.axis.to_dt(task.deadline + delta).isoformat(),
                "level": task.deadline_level,
                "weight": task.weight,
            }
        )
    if not drafts:
        return {"outcome": "rejected"}
    return {
        "draft": drafts[0],
        "remaining": drafts[1:],
        "outcome": "",
        "negotiation_count": state.get("negotiation_count", 0) + 1,
    }
