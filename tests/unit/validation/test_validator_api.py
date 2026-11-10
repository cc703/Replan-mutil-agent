"""Acceptance checks for independent schedule validation."""

import ast
from copy import deepcopy
from pathlib import Path

from scheduler_core.models import (
    Assignment,
    Instance,
    Plan,
    SetupRule,
)
from scheduler_core.validate import validate
import pytest


from .validation_helpers import execution_case, instance, reasons


def test_mini_fixture_golden_and_tamper() -> None:
    path = Path(__file__).resolve().parents[3] / "data/fixtures/mini.json"
    inst = Instance.model_validate_json(path.read_text(encoding="utf-8"))
    plan = Plan(
        id="gold",
        assignments={
            "A": Assignment(task_id="A", device_id="D1", start=0, end=4),
            "C": Assignment(task_id="C", device_id="D1", start=4, end=10),
            "D": Assignment(task_id="D", device_id="D2", start=0, end=6),
            "B": Assignment(task_id="B", device_id="D2", start=6, end=10),
        },
    )
    assert validate(inst, plan).passed
    plan.assignments["C"] = plan.assignments["C"].model_copy(update={"start": 3, "end": 9})
    assert reasons(validate(inst, plan), "V2", "DEVICE_OVERLAP") == [["A", "C"]]
    plan.assignments["B"] = plan.assignments["B"].model_copy(update={"start": 0, "end": 4})
    assert reasons(validate(inst, plan), "V3", "PRECEDENCE_MIN_LAG") == [["A", "B"]]


def test_deterministic_immutable_huge_and_import_boundary() -> None:
    inst = instance()
    inst.axis.horizon_slots = 10**9
    plan = Plan(
        id="p",
        assignments={
            "a": Assignment(task_id="a", device_id="d", start=0, end=4),
            "b": Assignment(task_id="b", device_id="d", start=2, end=6),
        },
    )
    before = deepcopy((inst.model_dump(), plan.model_dump()))
    report = validate(inst, plan)
    assert (inst.model_dump(), plan.model_dump()) == before
    inst.tasks.reverse()
    plan.assignments = dict(reversed(list(plan.assignments.items())))
    assert validate(inst, plan) == report
    root = Path(__file__).resolve().parents[3] / "src/scheduler_core"
    paths = [
        root / "validate.py",
        root / "validation_context.py",
        *sorted((root / "validation").glob("*.py")),
    ]
    graph: dict[str, set[str]] = {}
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = [
            a.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for a in node.names
        ]
        imports += [
            (node.module or "").split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        ]
        assert not {"ortools", "numpy", "random"}.intersection(imports)
        if path.parent.name == "validation":
            graph[path.stem] = {
                node.module.split(".")[0]
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module
            }
            assert not any(
                isinstance(node, ast.ImportFrom)
                and (
                    (node.level == 2 and node.module == "validate")
                    or (node.module or "").startswith("scheduler_core.validate")
                )
                for node in ast.walk(tree)
            )
            assert not any(
                alias.name.startswith("scheduler_core.validate")
                for node in ast.walk(tree)
                if isinstance(node, ast.Import)
                for alias in node.names
            )
    for start in graph:
        pending = list(graph[start])
        seen: set[str] = set()
        while pending:
            current = pending.pop()
            assert current != start
            if current not in seen:
                seen.add(current)
                pending.extend(graph.get(current, set()))


def test_wrong_context_and_base_type_rejected() -> None:
    inst = instance()
    plan = Plan(id="p", assignments={})
    with pytest.raises(TypeError):
        validate(inst, plan, base={})  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        validate(inst, plan, context={})  # type: ignore[arg-type]


def test_all_inputs_unchanged_and_setup_order_stable() -> None:
    inst, plan, base, ctx = execution_case("RUNNING", 10, remaining=0)
    inst.setups = [
        SetupRule(device_id="d", task_type="x", slots=1),
        SetupRule(device_id="d", task_type="x", slots=2),
    ]
    before = deepcopy(tuple(x.model_dump() for x in (inst, plan, base, ctx)))
    report = validate(inst, plan, base=base, context=ctx, free=set())
    assert tuple(x.model_dump() for x in (inst, plan, base, ctx)) == before
    inst.setups.reverse()
    assert validate(inst, plan, base=base, context=ctx, free=set()) == report
