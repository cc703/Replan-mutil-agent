"""Independent verification, canonical evidence and validated plan views."""

from dataclasses import asdict
from typing import Any
from zoneinfo import ZoneInfo

from scheduler_core.models import Instance, Plan, ValidationReport
from scheduler_core.plan_diff import diff_plans
from scheduler_core.validate import validate

from .errors import ServiceError
from .hashing import digest, instance_digest
from .schemas import Evidence, ValidateRequest
from .schemas_events import apply_facts, execution_context

SHANGHAI = ZoneInfo("Asia/Shanghai")


def report_body(report: ValidationReport) -> dict[str, Any]:
    return {
        "passed": report.passed,
        "violations": [
            {**v.model_dump(), "reason": v.detail.split(";", 1)[0][7:]} for v in report.violations
        ],
    }


def verify(evidence: Evidence) -> ValidationReport:
    if evidence.base_plan is None:
        if evidence.plan.parent_id is not None or evidence.free is not None:
            raise ServiceError("PLAN_INTEGRITY_ERROR", "Missing parent for evidence", 422)
    elif evidence.free is None or evidence.context is None or evidence.context.snapshot is None:
        raise ServiceError("PLAN_INTEGRITY_ERROR", "Incomplete replan evidence", 422)
    return validate(
        evidence.instance,
        evidence.plan,
        base=evidence.base_plan,
        free=evidence.free,
        context=evidence.context,
    )


def require_verified(evidence: Evidence, code: str = "VALIDATION_FAILED") -> dict[str, Any]:
    report = report_body(verify(evidence))
    if not report["passed"]:
        raise ServiceError(
            code, "Plan failed independent validation", 422, violations=report["violations"]
        )
    return report


def validate_current(req: ValidateRequest) -> dict[str, Any]:
    report = verify(req)
    hash_ok = req.expected_plan_sha256 is None or req.expected_plan_sha256 == digest(
        req.plan.model_dump(mode="json")
    )
    if report.passed and hash_ok and req.additional_events:
        parent = req.base_plan or req.current_base_plan
        if parent is None or (req.base_plan is None and parent != req.plan):
            raise ServiceError("PLAN_INTEGRITY_ERROR", "Missing current initial plan", 422)
        context = req.context or execution_context(req.instance, parent)
        try:
            post, _, current = apply_facts(req.instance, parent, req.additional_events, context)
        except ServiceError as exc:
            raise ServiceError(
                "PLAN_INTEGRITY_ERROR",
                "Current facts cannot be reconstructed",
                422,
                failure=exc.code,
                **exc.details,
            ) from exc
        report = validate(post, req.plan, base=req.base_plan, free=req.free, context=current)
    response = report_body(report)
    response["passed"] = report.passed and hash_ok
    response["plan_sha256_ok"] = hash_ok
    return response


def changes(instance: Instance, base: Plan, plan: Plan) -> list[dict[str, Any]]:
    rows = []
    for item in diff_plans(instance, base, plan):
        row = asdict(item)
        row["before"] = _with_times(instance, item.before.model_dump()) if item.before else None
        row["after"] = _with_times(instance, item.after.model_dump()) if item.after else None
        rows.append(row)
    return rows


def _with_times(instance: Instance, values: dict[str, Any]) -> dict[str, Any]:
    return {
        **values,
        "start_iso": instance.axis.to_dt(values["start"]).astimezone(SHANGHAI).isoformat(),
        "end_iso": instance.axis.to_dt(values["end"]).astimezone(SHANGHAI).isoformat(),
    }


def plan_view(evidence: Evidence, *, checked: bool = False) -> dict[str, Any]:
    if not checked:
        require_verified(evidence)
    instance, plan, base = evidence.instance, evidence.plan, evidence.base_plan
    index = {task.id: task for task in instance.tasks}
    assignments = []
    for task_id, assignment in sorted(plan.assignments.items()):
        task = index[task_id]
        assignments.append(
            {
                **_with_times(instance, assignment.model_dump()),
                "task_type": task.type,
                "deadline": task.deadline,
                "late": task.deadline is not None and assignment.end > task.deadline,
                "changed": base is not None and base.assignments.get(task_id) != assignment,
            }
        )
    return {
        "devices": [
            {"id": device.id, "type": device.type, "capacity": device.capacity}
            for device in instance.devices
        ],
        "assignments": assignments,
        "blocked": [_with_times(instance, window.model_dump()) for window in instance.blocked],
    }


def plan_body(evidence: Evidence) -> dict[str, Any]:
    validation = require_verified(evidence)
    return {
        "evidence": evidence.model_dump(mode="json"),
        "instance_post_sha256": instance_digest(evidence.instance),
        "plan_sha256": digest(evidence.plan.model_dump(mode="json")),
        "view": plan_view(evidence, checked=True),
        "validation": validation,
    }
