"""Build and solve the initial CP-SAT model."""

from dataclasses import dataclass
from typing import Any
from ortools.sat.python import cp_model
from scheduler_core.models import Assignment, Instance
from .weights import LIMIT, scale_weights


@dataclass(frozen=True)
class RawResult:
    status: str
    assignments: dict[str, Assignment] | None
    makespan: int
    objective: float | None
    best_bound: float | None
    gap: float | None
    wall_seconds: float
    reasons: tuple[str, ...]


def _merge(windows: list[tuple[int, int]], horizon: int) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end in sorted(
        (max(0, s), min(horizon, e)) for s, e in windows if s < horizon and e > 0
    ):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged


def _add_objective(
    model: cp_model.CpModel,
    inst: Instance,
    ends: dict[str, cp_model.IntVar],
    selected: dict[tuple[str, str], cp_model.IntVar],
    h: int,
    load_bound: int,
    cm: int,
    ci: int,
) -> tuple[cp_model.IntVar, cp_model.IntVar]:
    cmax = model.new_int_var(0, h, "makespan")
    if ends:
        model.add_max_equality(cmax, list(ends.values()))
    else:
        model.add(cmax == 0)
    differences = []
    for typ in sorted({d.type for d in inst.devices}):
        loads = []
        for d in (d for d in inst.devices if d.type == typ):
            load = model.new_int_var(0, load_bound, f"load:{d.id}")
            model.add(
                load
                == sum(
                    t.duration * t.demand * selected[t.id, d.id]
                    for t in inst.tasks
                    if (t.id, d.id) in selected
                )
            )
            loads.append(load)
        maximum = model.new_int_var(0, load_bound, f"max:{typ}")
        minimum = model.new_int_var(0, load_bound, f"min:{typ}")
        model.add_max_equality(maximum, loads)
        model.add_min_equality(minimum, loads)
        diff = model.new_int_var(0, load_bound, f"diff:{typ}")
        model.add(diff == maximum - minimum)
        differences.append(diff)
    imbalance = model.new_int_var(0, load_bound, "imbalance")
    if differences:
        model.add_max_equality(imbalance, differences)
    else:
        model.add(imbalance == 0)
    model.minimize(cm * cmax + ci * imbalance)
    return cmax, imbalance


def _build_model(
    inst: Instance,
    h: int,
    load_bound: int,
    cm: int,
    ci: int,
) -> tuple[
    cp_model.CpModel,
    dict[str, cp_model.IntVar],
    dict[str, cp_model.IntVar],
    dict[tuple[str, str], cp_model.IntVar],
    dict[tuple[str, str], cp_model.IntVar],
    cp_model.IntVar,
    cp_model.IntVar,
]:
    model = cp_model.CpModel()
    starts = {t.id: model.new_int_var(0, h, f"start:{t.id}") for t in inst.tasks}
    ends = {t.id: model.new_int_var(0, h, f"end:{t.id}") for t in inst.tasks}
    devices = {d.id: d for d in inst.devices}
    setup = {(s.device_id, s.task_type): s.slots for s in inst.setups}
    di: dict[str, list[Any]] = {d.id: [] for d in inst.devices}
    demands: dict[str, list[int]] = {d.id: [] for d in inst.devices}
    pi: dict[str, list[Any]] = {p.id: [] for p in inst.persons}
    selected: dict[tuple[str, str], cp_model.IntVar] = {}
    people: dict[tuple[str, str], cp_model.IntVar] = {}
    for t in inst.tasks:
        start, end = starts[t.id], ends[t.id]
        model.add(end == start + t.duration)
        model.add(start >= max(t.release, inst.now))
        if t.deadline is not None:
            model.add(end <= t.deadline)
        choices = []
        for did in dict.fromkeys(t.compatible_devices):
            d = devices[did]
            if t.demand > d.capacity:
                continue
            s = setup.get((did, t.type), 0)
            b = model.new_bool_var(f"device:{t.id}:{did}")
            selected[t.id, did] = b
            choices.append(b)
            model.add(start >= s).only_enforce_if(b)
            interval = model.new_optional_interval_var(
                start - s, t.duration + s, end, b, f"device_interval:{t.id}:{did}"
            )
            di[did].append(interval)
            demands[did].append(t.demand)
        model.add_exactly_one(choices)
        if t.needs_person:
            choices = []
            for p in inst.persons:
                if not t.required_skills <= p.skills:
                    continue
                b = model.new_bool_var(f"person:{t.id}:{p.id}")
                people[t.id, p.id] = b
                choices.append(b)
                pi[p.id].append(
                    model.new_optional_interval_var(
                        start, t.duration, end, b, f"person_interval:{t.id}:{p.id}"
                    )
                )
            model.add_exactly_one(choices)
    for edge in inst.precedences:
        model.add(starts[edge.succ] >= ends[edge.pred] + edge.lag_min)
        if edge.lag_max is not None:
            model.add(starts[edge.succ] <= ends[edge.pred] + edge.lag_max)
    for d in inst.devices:
        windows = _merge([(w.start, w.end) for w in inst.blocked if w.device_id == d.id], h)
        for ws, we in windows:
            di[d.id].append(model.new_fixed_size_interval_var(ws, we - ws, f"blocked:{d.id}:{ws}"))
            demands[d.id].append(d.capacity)
        if d.capacity == 1:
            model.add_no_overlap(di[d.id])
        else:
            model.add_cumulative(di[d.id], demands[d.id], d.capacity)
    for p in inst.persons:
        for ws, we in _merge([(w.start, w.end) for w in p.blocked], h):
            pi[p.id].append(
                model.new_fixed_size_interval_var(ws, we - ws, f"person_block:{p.id}:{ws}")
            )
        model.add_no_overlap(pi[p.id])
    cmax, imbalance = _add_objective(model, inst, ends, selected, h, load_bound, cm, ci)
    return model, starts, ends, selected, people, cmax, imbalance


def run_model(
    inst: Instance,
    time_limit_s: float,
    num_workers: int,
    seed: int,
    objective_weights: dict[str, float] | None,
) -> RawResult:
    """Solve a prevalidated pending instance, returning raw status and assignments."""
    h = inst.axis.horizon_slots
    load_bound = sum(t.duration * t.demand for t in inst.tasks)
    resource_bound = sum(t.demand for t in inst.tasks) + sum(
        d.capacity * len(inst.blocked) for d in inst.devices
    )
    if h * 4 > LIMIT or load_bound > LIMIT or resource_bound > LIMIT:
        raise ValueError("instance exceeds safe integer bounds")
    cm, ci, scale = scale_weights(objective_weights, h, load_bound)
    model, starts, ends, selected, people, cmax, imbalance = _build_model(
        inst, h, load_bound, cm, ci
    )
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.num_search_workers = num_workers
    solver.parameters.random_seed = seed
    status = solver.solve(model)
    status_name = solver.status_name(status)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        reasons = (model.validate(),) if status == cp_model.MODEL_INVALID else ()
        return RawResult(status_name, None, 0, None, None, None, solver.wall_time, reasons)
    result = {}
    for t in inst.tasks:
        did = next(d for (tid, d), v in selected.items() if tid == t.id and solver.value(v))
        person = next(
            (p for (tid, p), v in people.items() if tid == t.id and solver.value(v)), None
        )
        result[t.id] = Assignment(
            task_id=t.id,
            device_id=did,
            person_id=person,
            start=solver.value(starts[t.id]),
            end=solver.value(ends[t.id]),
        )
    makespan = max((a.end for a in result.values()), default=0)
    loads_actual = {d.id: 0 for d in inst.devices}
    for t in inst.tasks:
        loads_actual[result[t.id].device_id] += t.duration * t.demand
    spreads = []
    for typ in {d.type for d in inst.devices}:
        group = [loads_actual[d.id] for d in inst.devices if d.type == typ]
        spreads.append(max(group) - min(group))
    actual = cm * makespan + ci * max(spreads, default=0)
    if actual != cm * solver.value(cmax) + ci * solver.value(imbalance):
        raise RuntimeError("objective mismatch")
    objective = actual / scale
    bound = solver.best_objective_bound / scale
    gap = max(0.0, objective - bound) / abs(objective) if objective else 0.0
    return RawResult(status_name, result, makespan, objective, bound, gap, solver.wall_time, ())
