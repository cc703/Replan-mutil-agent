"""Build controlled facts from independent solver and diagnostic evidence."""

from typing import Any
from scheduler_core.models import Instance, Plan
from scheduler_core.plan_diff import diff_plans
from .explain import Fact


def candidate_facts(
    instance: Instance, base: Plan, plan: Plan, impact: dict[str, Any], metrics: dict[str, float]
) -> dict[str, Fact]:
    changes = diff_plans(instance, base, plan)
    facts = {
        f"任务 {item.task_id} 开始变化": Fact(
            "number", item.start_delta * instance.axis.slot_minutes, "分钟"
        )
        for item in changes
        if item.start_delta is not None
    }
    facts.update(
        {
            "计划总工期": Fact(
                "number", plan.metrics.makespan * instance.axis.slot_minutes, "分钟"
            ),
            "移动任务数": Fact("number", plan.metrics.moved, "个"),
            "更换设备数": Fact("number", plan.metrics.switched, "个"),
            "影响任务数": Fact("number", len(impact.get("affected", [])), "个"),
        }
    )
    for change in changes:
        for label, assignment in (("原", change.before), ("新", change.after)):
            prefix = f"任务 {change.task_id} {label}"
            if assignment is None:
                facts[f"{prefix}安排"] = Fact("text", "无", "")
            else:
                facts[f"{prefix}设备"] = Fact("text", assignment.device_id, "")
                facts[f"{prefix}人员"] = Fact("text", assignment.person_id or "无", "")
                facts[f"{prefix}开始"] = Fact("number", assignment.start, "槽")
                facts[f"{prefix}结束"] = Fact("number", assignment.end, "槽")
        if change.before and change.after:
            delta = (change.after.end - change.before.end) * instance.axis.slot_minutes
            facts[f"任务 {change.task_id} 结束变化"] = Fact("number", delta, "分钟")
            task = next((t for t in instance.tasks if t.id == change.task_id), None)
            if task is not None and task.deadline is not None:
                before_late = max(0, change.before.end - task.deadline)
                after_late = max(0, change.after.end - task.deadline)
                facts[f"任务 {change.task_id} 逾期变化"] = Fact(
                    "number", (after_late - before_late) * instance.axis.slot_minutes, "分钟"
                )
        for label in ("added", "removed", "moved", "device_changed", "person_changed"):
            facts[f"任务 {change.task_id} {label}"] = Fact(
                "text", str(getattr(change, label)).lower(), ""
            )
    units = {
        "tardiness": "加权槽",
        "makespan": "槽",
        "moved": "个",
        "switched": "个",
        "shift_total": "槽",
        "urgent_delay": "槽",
        "solve_seconds": "秒",
        "gap": "比例",
    }
    for name, value in plan.metrics.model_dump().items():
        facts[f"指标 {name}"] = (
            Fact("text", "未知", "") if value is None else Fact("number", value, units[name])
        )
    for name, value in metrics.items():
        facts[f"候选目标 {name}"] = Fact(
            "number", value, {"f1": "加权槽", "f2": "综合分", "f3": "槽"}[name]
        )
    for group in ("frozen", "affected", "unaffected"):
        for task_id in impact.get(group, []):
            facts[f"任务 {task_id} 影响分组"] = Fact("text", group, "")
    for task_id, reason in impact.get("reasons", {}).items():
        facts[f"任务 {task_id} 影响原因"] = Fact("text", reason, "")
    return facts
