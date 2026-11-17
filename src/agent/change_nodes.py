"""Extraction, confirmation and CP-SAT graph nodes."""

import json
from collections.abc import Callable
from typing import Any
from langgraph.types import interrupt
from pydantic import ValidationError
from scheduler_core.models import DeviceOutage, TaskOverrun, UrgentInsert
from scheduler_core.validation_context import ValidationContext
from .changes import prepare_change
from .ir import normalize_relative, parse_draft, proposal_adapter
from .state import GraphState
from .store import WorldStore


def change_nodes(
    store: WorldStore, extractor: Callable[[str], dict[str, Any]], context: ValidationContext
) -> dict[str, Callable[[GraphState], GraphState]]:
    def extract(state: GraphState) -> GraphState:
        for _ in range(3):
            try:
                raw = extractor(state["text"])
                changes = raw.get("changes")
                drafts = changes if isinstance(changes, list) and changes else [raw]
                if not all(isinstance(item, dict) for item in drafts):
                    raise ValueError("invalid changes")
                for item in drafts:
                    proposal_adapter.validate_json(
                        json.dumps(normalize_relative(item, store.instance))
                    )
                return {
                    "draft": drafts[0],
                    "remaining": drafts[1:],
                    "applied_events": [],
                    "full_replan": False,
                    "error": "",
                }
            except RuntimeError:
                break
            except (ValueError, TypeError):
                continue
        return {"draft": {}, "error": "请输入结构化变更表单"}

    def prepare(state: GraphState) -> GraphState:
        try:
            draft, proposal = parse_draft(state["draft"], store.instance, store.aliases)
            base = store.versions[store.active].plan
            effective_context = (
                ValidationContext.model_validate(state["context"])
                if state.get("context")
                else context
            )
            post, events, effective = prepare_change(
                proposal, store.instance, base, effective_context, store.aliases
            )
            return {
                "draft": draft,
                "post": post.model_dump(mode="json"),
                "prepared_revision": store.revision,
                "events": [event.model_dump(mode="json") for event in events],
                "context": effective.model_dump(mode="json"),
                "prior_context": effective_context.model_dump(mode="json"),
                "error": "",
            }
        except ValidationError as exc:
            loc = exc.errors()[0]["loc"]
            field = str(loc[-1]) if loc else "kind"
            allowed = {
                "kind",
                "device",
                "task",
                "start",
                "end",
                "deadline",
                "level",
                "weight",
                "tasks",
                "duration",
                "compatible_devices",
            }
            return {"error": f"请补充或修正字段：{field if field in allowed else '变更类型'}"}
        except (ValueError, TypeError, KeyError) as exc:
            message = str(exc)
            if "soft preference" in message:
                question = "软偏好当前不支持执行；请修改或退出"
            elif "entity needs" in message:
                question = "请明确唯一的设备或任务 ID"
            elif "evidence" in message or "snapshot" in message:
                question = "请提供匹配的真实运行证据"
            else:
                question = "请核对时间、任务字段及当前约束"
            return {"error": question}

    def clarify(state: GraphState) -> GraphState:
        response = interrupt({"kind": "form", "error": state["error"], "draft": state["draft"]})
        if not isinstance(response, dict):
            return {"outcome": "cancelled"}
        return {"draft": response, "error": ""}

    def confirm_change(state: GraphState) -> GraphState:
        from scheduler_core.models import Instance

        payload = {
            "proposal": state["draft"],
            "post": state["post"],
            "revision": state["prepared_revision"],
            "context": state["prior_context"],
        }
        token = interrupt({"kind": "L1", "proposal": state["draft"], "binding": payload})
        if not isinstance(token, str):
            store.record_rejection("change", "human", state["draft"])
            return {"outcome": "rejected"}
        store.apply_world(
            token,
            state["draft"],
            Instance.model_validate(state["post"]),
            "human",
            state["prepared_revision"],
            ValidationContext.model_validate(state["prior_context"]),
        )
        return {
            "applied_events": state.get("applied_events", []) + state["events"],
            "full_replan": state.get("full_replan", False)
            or state["draft"].get("kind") == "DEADLINE",
        }

    def advance(state: GraphState) -> GraphState:
        remaining = state.get("remaining", [])
        return {"draft": remaining[0], "remaining": remaining[1:]}

    def solve(state: GraphState) -> GraphState:
        event_types: dict[str, type[DeviceOutage] | type[TaskOverrun] | type[UrgentInsert]] = {
            "DEVICE_OUTAGE": DeviceOutage,
            "TASK_OVERRUN": TaskOverrun,
            "URGENT_INSERT": UrgentInsert,
        }
        events = [
            event_types[event["type"]].model_validate(event)
            for event in state.get("applied_events", [])
        ]
        effective = ValidationContext.model_validate(state["context"])
        result = store.solve(events, effective, full=state.get("full_replan", False))
        return {
            "outcome": result.status,
            "candidates": [candidate.plan.id for candidate in result.candidates],
            "impact": result.impact.model_dump(mode="json") if result.impact else {},
            "candidate_metrics": {
                c.plan.id: {"f1": c.f1, "f2": c.f2, "f3": c.f3} for c in result.candidates
            },
        }

    return {
        "extract": extract,
        "prepare": prepare,
        "clarify": clarify,
        "confirm_change": confirm_change,
        "advance": advance,
        "solve": solve,
    }
