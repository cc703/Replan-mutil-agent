"""Deterministic collection of semantic validation violations."""

from typing import Literal, cast

from ..models import ValidationReport, Violation


class ViolationCollector:
    """Collect violations and produce the stable public report."""

    def __init__(self) -> None:
        self._violations: list[Violation] = []

    def add(
        self,
        code: str,
        reason: str,
        ids: list[str] | None = None,
        device: str | None = None,
        **values: object,
    ) -> None:
        detail = f"reason={reason};" + "".join(f" {k}={values[k]};" for k in sorted(values))
        self._violations.append(
            Violation(
                code=cast(
                    Literal["V1", "V2", "V3", "V4", "V5", "V6", "V7", "V8", "V9", "V10", "V11"],
                    code,
                ),
                task_ids=sorted(ids or []),
                device_id=device,
                detail=detail,
            )
        )

    def report(self) -> ValidationReport:
        self._violations.sort(
            key=lambda v: (
                int(v.code[1:]),
                v.task_ids,
                (v.device_id is not None, v.device_id or ""),
                v.detail,
            )
        )
        return ValidationReport(passed=not self._violations, violations=self._violations)
