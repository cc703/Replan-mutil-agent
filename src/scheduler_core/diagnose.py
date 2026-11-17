"""Conflict diagnostics using the scheduling model and proven deletion filtering."""

from dataclasses import dataclass
import math
import time
from typing import Literal

from ortools.sat.python import cp_model

from scheduler_core.diagnostics.core_search import reduce_core
from scheduler_core.diagnostics.groups import list_groups
from scheduler_core.diagnostics.inputs import prepare
from scheduler_core.models import ConflictCore, Instance, Plan, ReplanParams
from scheduler_core.replanning.model import solve_neighborhood
from scheduler_core.solving.run import _build_model
from scheduler_core.validation_context import ValidationContext


class DiagnosisUnknownError(RuntimeError):
    """The solver did not establish feasibility or infeasibility."""


class DiagnosisInconsistent(RuntimeError):
    """The diagnostic and ordinary models disagree on feasibility."""


@dataclass(frozen=True)
class DiagnoseResult:
    status: Literal["CORE", "FEASIBLE", "UNKNOWN", "BACKGROUND"]
    core: ConflictCore | None
    minimal: bool
    reasons: tuple[str, ...]
    solves: int
    wall_seconds: float
    groups_total: int


def diagnose_detailed(
    inst: Instance,
    plan0: Plan | None,
    free: set[str] | None,
    *,
    time_limit_s: float = 5.0,
    context: ValidationContext | None = None,
) -> DiagnoseResult:
    """Diagnose a post-event instance under a shared wall-clock budget."""
    started = time.perf_counter()
    if isinstance(time_limit_s, bool) or not isinstance(time_limit_s, (int, float)):
        raise TypeError("time_limit_s must be a number")
    if not math.isfinite(time_limit_s) or not 0 < time_limit_s <= 3600:
        raise ValueError("time_limit_s outside (0, 3600]")
    deadline = started + time_limit_s
    selected, frozen, ctx = prepare(inst, plan0, free, context)
    groups = list_groups(inst, plan0, selected, ctx, frozen)
    all_ids = {g.id for g in groups}
    solves = 0

    def solve(ids: set[str] | None, budget: float) -> str:
        if budget <= 0:
            return "UNKNOWN"
        if plan0 is None:
            h = inst.axis.horizon_slots
            load = sum(t.duration * t.demand for t in inst.tasks)
            model, *_ = _build_model(inst, h, load, 1, 0, enabled_groups=ids)
            remaining = deadline - time.perf_counter()
            if remaining <= 0:
                return "UNKNOWN"
            solver = cp_model.CpSolver()
            solver.parameters.max_time_in_seconds = min(budget, remaining)
            solver.parameters.num_search_workers = 1
            result = solver.status_name(solver.solve(model))
        else:
            result = solve_neighborhood(
                inst,
                plan0,
                selected,
                frozen,
                ctx,
                set(),
                ReplanParams(num_workers=1),
                min(budget, deadline - time.perf_counter()),
                enabled_groups=ids,
            ).status
        if result == "MODEL_INVALID":
            raise RuntimeError("invalid diagnostic model")
        return result

    def finish(
        status: Literal["CORE", "FEASIBLE", "UNKNOWN", "BACKGROUND"],
        core: ConflictCore | None = None,
        minimal: bool = False,
        reasons: tuple[str, ...] = (),
    ) -> DiagnoseResult:
        return DiagnoseResult(
            status, core, minimal, reasons, solves, time.perf_counter() - started, len(groups)
        )

    normal = solve(None, deadline - time.perf_counter())
    solves += 1
    if normal == "UNKNOWN" or time.perf_counter() >= deadline:
        return finish("UNKNOWN")
    grouped = solve(all_ids, deadline - time.perf_counter())
    solves += 1
    if grouped == "UNKNOWN" or time.perf_counter() >= deadline:
        return finish("UNKNOWN")
    feasible = {"FEASIBLE", "OPTIMAL"}
    if (normal in feasible) != (grouped in feasible):
        raise DiagnosisInconsistent("ordinary and diagnostic model disagree")
    if grouped in feasible:
        return finish("FEASIBLE")
    background = solve(set(), deadline - time.perf_counter())
    solves += 1
    if background == "INFEASIBLE":
        details = []
        devices = {device.id: device for device in inst.devices}
        for task in inst.tasks:
            if max(task.release, inst.now) + task.duration > inst.axis.horizon_slots:
                details.append(f"Task {task.id} cannot fit within horizon")
            if not any(
                d in devices and devices[d].capacity >= task.demand for d in task.compatible_devices
            ):
                details.append(f"Task {task.id} has no eligible device")
        reasons = tuple(details) or ("Background constraints are infeasible",)
        return finish(
            "BACKGROUND", ConflictCore(group_ids=[], descriptions=list(reasons)), True, reasons
        )
    if background == "UNKNOWN":
        return finish(
            "CORE",
            ConflictCore(group_ids=sorted(all_ids), descriptions=[g.description for g in groups]),
            False,
        )
    # The initial model supports deadline assumption literals. Other groups remain
    # fixed, so add them back to the returned sufficient set and prove it again.
    initial = all_ids
    if plan0 is None and time.perf_counter() < deadline and solves < 199:
        literals: dict[str, cp_model.IntVar] = {}
        h = inst.axis.horizon_slots
        load = sum(t.duration * t.demand for t in inst.tasks)
        model, *_ = _build_model(inst, h, load, 1, 0, assumption_literals=literals)
        remaining = deadline - time.perf_counter()
        if remaining > 0:
            solver = cp_model.CpSolver()
            solver.parameters.num_search_workers = 1
            solver.parameters.max_time_in_seconds = remaining
            status = solver.solve(model)
            solves += 1
            if status == cp_model.MODEL_INVALID:
                raise RuntimeError("invalid assumption model")
            if status == cp_model.INFEASIBLE:
                indices = set(solver.sufficient_assumptions_for_infeasibility())
                candidate = (all_ids - literals.keys()) | {
                    gid for gid, lit in literals.items() if lit.index in indices
                }
                remaining = deadline - time.perf_counter()
                if remaining > 0:
                    proof = solve(candidate, remaining)
                    solves += 1
                    if proof == "INFEASIBLE":
                        initial = candidate
    elif plan0 is not None and time.perf_counter() < deadline and solves < 199:
        raw = solve_neighborhood(
            inst,
            plan0,
            selected,
            frozen,
            ctx,
            set(),
            ReplanParams(num_workers=1),
            deadline - time.perf_counter(),
            use_assumptions=True,
        )
        solves += 1
        if raw.status == "MODEL_INVALID":
            raise RuntimeError("invalid assumption model")
        if raw.status == "INFEASIBLE" and raw.assumption_core is not None:
            assumed = {g.id for g in groups if g.id.startswith("deadline:")}
            candidate = (all_ids - assumed) | raw.assumption_core
            remaining = deadline - time.perf_counter()
            if remaining > 0:
                proof = solve(candidate, remaining)
                solves += 1
                if proof == "INFEASIBLE":
                    initial = candidate
    reduced = reduce_core(initial, solve, deadline, solves=solves)
    solves = reduced.solves
    core = ConflictCore(
        group_ids=sorted(reduced.groups),
        descriptions=[g.description for g in groups if g.id in reduced.groups],
    )
    return finish("CORE", core, reduced.minimal)


def diagnose(
    inst: Instance,
    plan0: Plan | None,
    free: set[str] | None,
    *,
    time_limit_s: float = 5.0,
    context: ValidationContext | None = None,
) -> ConflictCore | None:
    """Return a proven core, None for feasible, or raise if not established."""
    result = diagnose_detailed(inst, plan0, free, time_limit_s=time_limit_s, context=context)
    if result.status == "UNKNOWN":
        raise DiagnosisUnknownError("diagnosis did not complete")
    return result.core
