"""P6 extraction, semantic verification and draft-only conversation transport."""

from collections import OrderedDict
import json
import os
from pathlib import Path
import re
from threading import Lock
from typing import Any
from uuid import uuid4

from agent import llm
from agent.changes import prepare_change
from agent.ir import Deadline, Outage, Overrun, Proposal, Urgent, parse_draft
from pydantic import Field
from scheduler_core.models import Contract, Instance

from .errors import ServiceError
from .schemas import TurnRequest
from .schemas_events import apply_facts, execution_context


class DraftEnvelope(Contract):
    changes: list[dict[str, object]] = Field(min_length=1, max_length=50)


PROMPTS = Path(llm.__file__).with_name("prompts") / "extract"
HISTORY: OrderedDict[tuple[str, str, int], str] = OrderedDict()
HISTORY_LOCK = Lock()
HISTORY_LIMIT = 128
HISTORY_TEXT_LIMIT = 16_000


def fake_extract(text: str) -> dict[str, Any]:
    """Interpret the documented deterministic fixture without touching approval state."""
    for variant in ((text.splitlines() or [""])[-1], " ".join(text.split())):
        outage = re.fullmatch(r"outage\s+(\S+)\s+(\S+)\s+(\S+)", variant.strip())
        if outage:
            device, start, end = outage.groups()
            return {
                "changes": [
                    {
                        "kind": "DEVICE_OUTAGE",
                        "strength": "HARD",
                        "device": {"original": device, "confidence": 1.0},
                        "start": start,
                        "end": end,
                    }
                ]
            }
        deadline = re.fullmatch(r"deadline\s+(\S+)\s+(\S+)", variant.strip())
        if deadline:
            task, end = deadline.groups()
            return {
                "changes": [
                    {
                        "kind": "DEADLINE",
                        "strength": "HARD",
                        "task": {"original": task, "confidence": 1.0},
                        "deadline": end,
                        "level": "HARD",
                        "weight": 1.0,
                    }
                ]
            }
    return {"changes": [{"kind": "DEVICE_OUTAGE", "strength": "HARD"}]}


def _extract(text: str, instance: Instance) -> DraftEnvelope:
    if os.environ.get("P7_LLM", "").lower() == "fake":
        raw = fake_extract(text)
    else:
        # P6's extractor prompt and adapter are reused with the application fact snapshot.
        # The archival base plan can be invalid after new L1 facts, so no WorldStore is built.
        prompt = (PROMPTS / "v001.md").read_text(encoding="utf-8")
        schema = json.loads((PROMPTS / "v001.schema.json").read_text(encoding="utf-8"))
        context = {
            "devices": [device.model_dump(mode="json") for device in instance.devices],
            "tasks": [{"id": task.id, "type": task.type} for task in instance.tasks],
            "blocked": [window.model_dump(mode="json") for window in instance.blocked],
            "aliases": {},
            "axis": instance.axis.model_dump(mode="json"),
            "now_slot": instance.now,
            "now_utc": instance.axis.to_dt(instance.now).isoformat(),
            "display_timezone": "Asia/Shanghai",
            "duration_unit": "minutes",
        }
        try:
            raw = llm.DeepSeek.from_environment().extract(
                [
                    {"role": "system", "content": prompt},
                    {
                        "role": "user",
                        "content": json.dumps(
                            {"request": text, "context": context}, ensure_ascii=False
                        ),
                    },
                ],
                schema,
            )
        except (RuntimeError, ValueError) as exc:
            raise ServiceError("LLM_UNAVAILABLE", "LLM extraction is unavailable", 502) from exc
    try:
        return DraftEnvelope.model_validate(raw)
    except ValueError as exc:
        raise ServiceError("LLM_OUTPUT_INVALID", "Expected structured P6 proposals", 502) from exc


def _event(proposal: Proposal, slot_minutes: int) -> dict[str, Any] | None:
    if isinstance(proposal, Outage):
        return {
            "type": "DEVICE_OUTAGE",
            "device_id": proposal.device.resolved_id,
            "start": proposal.start.isoformat(),
            "end": proposal.end.isoformat(),
        }
    if isinstance(proposal, Urgent):
        precedences = [
            {
                "pred": e.pred,
                "succ": e.succ,
                "lag_min_minutes": e.lag_min * slot_minutes,
                "lag_max_minutes": e.lag_max * slot_minutes if e.lag_max is not None else None,
            }
            for e in proposal.precedences
        ]
        tasks = [t.model_dump(mode="json", exclude={"preemptible"}) for t in proposal.tasks]
        if any(task.preemptible for task in proposal.tasks):
            raise ValueError("P7 public event does not expose preemption")
        return {"type": "URGENT_INSERT", "tasks": tasks, "precedences": precedences}
    return None


def _back_translation(proposal: Deadline | Outage | Urgent) -> str:
    if isinstance(proposal, Deadline):
        return f"将任务 {proposal.task.resolved_id} 的截止期改为 {proposal.deadline.isoformat()}"
    if isinstance(proposal, Outage):
        return (
            f"设备 {proposal.device.resolved_id} 停用 {proposal.start.isoformat()} "
            f"至 {proposal.end.isoformat()}"
        )
    return f"插入 {len(proposal.tasks)} 个紧急任务"


def turn(req: TurnRequest) -> dict[str, Any]:
    session = req.session_id or uuid4().hex
    history_key = (req.lab_id, session, req.revision)
    with HISTORY_LOCK:
        previous = HISTORY.get(history_key, "")
    text = "\n".join(filter(None, (previous, req.text)))[-HISTORY_TEXT_LIMIT:]
    context = req.context or execution_context(req.instance, req.base_plan)
    instance, _, context = apply_facts(req.instance, req.base_plan, req.events, context)
    envelope = _extract(text, instance)
    result: dict[str, Any] = {
        "session_id": session,
        "assistant_message": "请核对变更提案。",
        "clarifications": [],
        "pending_items": [],
    }
    for draft in envelope.changes:
        try:
            _, proposal = parse_draft(draft, instance)
            if isinstance(proposal, Overrun):
                raise ValueError("P7 暂不支持运行中任务超时事件")
            prepare_change(proposal, instance, req.base_plan, context)
            event = _event(proposal, instance.axis.slot_minutes)
            item = {
                "item_id": uuid4().hex,
                "ir": proposal.model_dump(mode="json"),
                "back_translation": _back_translation(proposal),
                "ambiguities": [],
                "action": "EVENT_INJECT" if event else "CONSTRAINT_CHANGE",
            }
            if event:
                item["event"] = event
            result["pending_items"].append(item)
        except ValueError:
            result["clarifications"].append("请补充唯一的设备或任务 ID、对齐的时间以及必要字段。")
    with HISTORY_LOCK:
        if result["clarifications"]:
            HISTORY[history_key] = text
            HISTORY.move_to_end(history_key)
            if len(HISTORY) > HISTORY_LIMIT:
                HISTORY.popitem(last=False)
            result["assistant_message"] = "部分信息需要补充。"
            result["pending_items"] = []
        else:
            HISTORY.pop(history_key, None)
    return result
