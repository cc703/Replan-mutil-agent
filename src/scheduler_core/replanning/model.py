"""CP-SAT model for a single P4 neighborhood."""

from dataclasses import dataclass
import time

from ortools.sat.python import cp_model

from scheduler_core.diagnostics.relax_model import make_deltas, set_objective
from scheduler_core.models import Assignment, Instance, Plan, ReplanParams, Task
from scheduler_core.solving.search import _merge
from scheduler_core.validation_context import ValidationContext
from .objective import objective_coefficients


@dataclass(frozen=True)
class ModelResult:
    status: str
    assignments: dict[str, Assignment] | None
    objective: float | None
    bound: float | None
    deltas: dict[str, int] | None = None
    assumption_core: set[str] | None = None


def solve_neighborhood(
    inst: Instance,
    base: Plan,
    free: set[str],
    frozen: set[str],
    context: ValidationContext,
    urgent: set[str],
    params: ReplanParams,
    time_limit: float,
    *,
    tardiness_only: bool = False,
    enabled_groups: set[str] | None = None,
    relax_limits: dict[str, int] | None = None,
    relax_costs: dict[str, int] | None = None,
    excluded_supports: list[set[str]] | None = None,
    use_assumptions: bool = False,
) -> ModelResult:
    """Solve one neighborhood; caller independently validates any returned assignment."""
    started = time.perf_counter()

    def enabled(group: str) -> bool:
        return enabled_groups is None or group in enabled_groups

    h = inst.axis.horizon_slots
    tasks = [t for t in inst.tasks if t.status in ("PENDING", "SCHEDULED", "RUNNING", "DONE")]
    task_map = {t.id: t for t in tasks}
    devices = {d.id: d for d in inst.devices}
    model = cp_model.CpModel()
    deltas, active = make_deltas(model, relax_limits or {})
    assumptions: dict[str, cp_model.IntVar] = {}
    starts = {t.id: model.new_int_var(0, h, f"start:{t.id}") for t in tasks}
    ends = {t.id: model.new_int_var(0, h, f"end:{t.id}") for t in tasks}
    selected: dict[tuple[str, str], cp_model.IntVar] = {}
    people: dict[tuple[str, str], cp_model.IntVar] = {}
    intervals: dict[str, list[cp_model.IntervalVar]] = {d.id: [] for d in inst.devices}
    demands: dict[str, list[int]] = {d.id: [] for d in inst.devices}
    person_intervals: dict[str, list[cp_model.IntervalVar]] = {p.id: [] for p in inst.persons}
    records = {r.task_id: r for r in context.snapshot.records} if context.snapshot else {}
    setups = {(s.device_id, s.task_type): s.slots for s in inst.setups}
    for task in tasks:
        tid = task.id
        start, end = starts[tid], ends[tid]
        old = base.assignments.get(tid)
        record = records.get(tid)
        is_execution = task.status in ("RUNNING", "DONE")
        is_fixed = (tid in frozen and enabled(f"frozen:{tid}")) or (
            tid not in frozen and tid not in free and enabled(f"pinned:{tid}")
        )
        duration = task.duration
        if is_execution:
            if old is None or record is None:
                raise ValueError(f"missing execution evidence for {tid}")
            actual_end = (
                record.actual_end
                if task.status == "DONE"
                else max(record.planned_end or 0, inst.now + (record.remaining_estimate or 0))
            )
            if actual_end is None:
                raise ValueError("missing actual end")
            duration = actual_end - record.start
            if is_fixed:
                model.add(start == record.start)
                model.add(end == actual_end)
            else:
                model.add(end == start + duration)
        else:
            model.add(end == start + duration)
            model.add(start >= task.release)
            if tid not in frozen:
                model.add(start >= inst.now)
        if is_fixed:
            if old is None:
                raise ValueError(f"missing fixed assignment for {tid}")
            model.add(start == old.start)
            if task.status not in ("RUNNING", "DONE"):
                model.add(end == old.end)
        model.add(start >= task.release)
        if task.deadline is not None and enabled(f"deadline:{tid}"):
            auth = [a for a in context.deadline_authorizations if a.task_id == tid]
            deadline = task.deadline
            if (
                len(auth) == 1
                and task.deadline_level == "NEGOTIABLE"
                and auth[0].acted_at <= inst.now
                and (auth[0].valid_until is None or auth[0].valid_until >= inst.now)
            ):
                deadline = auth[0].relaxed_deadline
            constraint = model.add(end <= deadline + deltas.get(tid, 0))
            if use_assumptions:
                literal = model.new_bool_var(f"assume:deadline:{tid}")
                assumptions[f"deadline:{tid}"] = literal
                constraint.only_enforce_if(literal)
                model.add_assumption(literal)
        choices = []
        for did in dict.fromkeys(task.compatible_devices):
            d = devices.get(did)
            if d is None or task.demand > d.capacity:
                continue
            b = model.new_bool_var(f"device:{tid}:{did}")
            selected[tid, did] = b
            choices.append(b)
            setup = 0 if task.status in ("RUNNING", "DONE") else setups.get((did, task.type), 0)
            model.add(start >= setup).only_enforce_if(b)
            interval = model.new_optional_interval_var(
                start - setup, duration + setup, end, b, f"di:{tid}:{did}"
            )
            intervals[did].append(interval)
            demands[did].append(task.demand)
            if is_fixed and old is not None:
                model.add(b == int(did == old.device_id))
        model.add_exactly_one(choices)
        person_choices = []
        for person in inst.persons:
            if not task.required_skills <= person.skills:
                continue
            b = model.new_bool_var(f"person:{tid}:{person.id}")
            people[tid, person.id] = b
            person_choices.append(b)
            person_intervals[person.id].append(
                model.new_optional_interval_var(start, duration, end, b, f"pi:{tid}:{person.id}")
            )
            if is_fixed and old is not None:
                model.add(b == int(person.id == old.person_id))
        if task.needs_person:
            model.add_exactly_one(person_choices)
        else:
            model.add_at_most_one(person_choices)
            if not is_fixed:
                for b in person_choices:
                    model.add(b == 0)
    for edge in inst.precedences:
        if (
            edge.pred in task_map
            and edge.succ in task_map
            and enabled(f"precedence:{edge.pred}>{edge.succ}")
        ):
            model.add(starts[edge.succ] >= ends[edge.pred] + edge.lag_min)
            if edge.lag_max is not None:
                model.add(starts[edge.succ] <= ends[edge.pred] + edge.lag_max)
    _add_calendars(model, inst, context, intervals, demands, person_intervals, enabled_groups)
    scale = _add_objective(
        model, tasks, base, starts, ends, selected, people, urgent, params, h, tardiness_only
    )
    if relax_limits is not None:
        assert relax_costs is not None
        set_objective(model, deltas, active, relax_costs, excluded_supports or [], relax_limits)
    remaining = time_limit - (time.perf_counter() - started)
    if remaining <= 0:
        return ModelResult("UNKNOWN", None, None, None)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = remaining
    solver.parameters.num_search_workers = params.num_workers
    solver.parameters.random_seed = params.seed
    status = solver.solve(model)
    name = solver.status_name(status)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        core = None
        if status == cp_model.INFEASIBLE and use_assumptions:
            indices = set(solver.sufficient_assumptions_for_infeasibility())
            core = {gid for gid, lit in assumptions.items() if lit.index in indices}
        return ModelResult(name, None, None, None, assumption_core=core)
    assignments = {}
    for task in tasks:
        tid = task.id
        did = next(d for (t, d), b in selected.items() if t == tid and solver.value(b))
        pid: str | None = next(
            (p for (t, p), b in people.items() if t == tid and solver.value(b)), None
        )
        assignments[tid] = Assignment(
            task_id=tid,
            device_id=did,
            person_id=pid,
            start=solver.value(starts[tid]),
            end=solver.value(ends[tid]),
        )
    return ModelResult(
        name,
        assignments,
        solver.objective_value / scale,
        solver.best_objective_bound / scale,
        {tid: solver.value(delta) for tid, delta in deltas.items()}
        if relax_limits is not None
        else None,
    )


def _add_calendars(
    model: cp_model.CpModel,
    inst: Instance,
    context: ValidationContext,
    intervals: dict[str, list[cp_model.IntervalVar]],
    demands: dict[str, list[int]],
    person_intervals: dict[str, list[cp_model.IntervalVar]],
    enabled_groups: set[str] | None = None,
) -> None:
    h = inst.axis.horizon_slots

    def enabled(group: str) -> bool:
        return enabled_groups is None or group in enabled_groups

    bound = {(b.device_id, b.start, b.end) for b in context.running_block_bindings}
    for device in inst.devices:
        windows = [
            (w.start, w.end)
            for w in inst.blocked
            if w.device_id == device.id
            and enabled(f"window:{w.device_id}:{w.start}:{w.end}:{w.kind}")
            and (w.kind != "RUNNING" or (w.device_id, w.start, w.end) not in bound)
        ]
        for s, e in _merge(windows, h):
            intervals[device.id].append(
                model.new_fixed_size_interval_var(s, e - s, f"block:{device.id}:{s}")
            )
            demands[device.id].append(device.capacity)
        if enabled(f"capacity:{device.id}"):
            model.add_cumulative(intervals[device.id], demands[device.id], device.capacity)
    for person in inst.persons:
        for s, e in _merge(
            [
                (w.start, w.end)
                for w in person.blocked
                if enabled(f"person_window:{person.id}:{w.start}:{w.end}")
            ],
            h,
        ):
            person_intervals[person.id].append(
                model.new_fixed_size_interval_var(s, e - s, f"pb:{person.id}:{s}")
            )
        if enabled(f"person:{person.id}"):
            model.add_no_overlap(person_intervals[person.id])


def _add_objective(
    model: cp_model.CpModel,
    tasks: list[Task],
    base: Plan,
    starts: dict[str, cp_model.IntVar],
    ends: dict[str, cp_model.IntVar],
    selected: dict[tuple[str, str], cp_model.IntVar],
    people: dict[tuple[str, str], cp_model.IntVar],
    urgent: set[str],
    params: ReplanParams,
    h: int,
    tardiness_only: bool,
) -> int:
    coeff, scale = objective_coefficients(
        params.alpha,
        0 if tardiness_only else params.beta_moved,
        0 if tardiness_only else params.beta_switched,
        0 if tardiness_only else params.beta_shift,
        0 if tardiness_only else params.gamma,
        h,
        [t.weight for t in tasks],
        len(urgent & {t.id for t in tasks}),
    )
    terms: list[cp_model.LinearExpr | int] = []
    for i, task in enumerate(tasks):
        tid = task.id
        if task.deadline is not None:
            tard = model.new_int_var(0, h, f"tard:{tid}")
            model.add_max_equality(tard, [0, ends[tid] - task.deadline])
            terms.append(coeff[i] * tard)
        old = base.assignments.get(tid)
        if old is not None:
            moved = model.new_bool_var(f"moved:{tid}")
            model.add(starts[tid] != old.start).only_enforce_if(moved)
            model.add(starts[tid] == old.start).only_enforce_if(moved.Not())
            shift = model.new_int_var(0, h, f"shift:{tid}")
            model.add_abs_equality(shift, starts[tid] - old.start)
            switched = 1 - selected[tid, old.device_id] if (tid, old.device_id) in selected else 1
            terms.extend(
                [
                    coeff[len(tasks)] * moved,
                    coeff[len(tasks) + 1] * switched,
                    coeff[len(tasks) + 2] * shift,
                ]
            )
            model.add_hint(starts[tid], old.start)
            for (task_id, did), b in selected.items():
                if task_id == tid:
                    model.add_hint(b, int(did == old.device_id))
            for (task_id, hint_pid), b in people.items():
                if task_id == tid:
                    model.add_hint(b, int(hint_pid == old.person_id))
        if tid in urgent:
            terms.append(coeff[len(tasks) + 3] * ends[tid])
    model.minimize(sum(terms))
    return scale
