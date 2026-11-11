"""Generate reproducible in-memory scheduling instances."""

from datetime import datetime, timezone

from scheduler_core.axis import TimeAxis
from scheduler_core.generation.dag import build_precedences
from scheduler_core.generation.params import GeneratorParams, SCALES, validate_inputs
from scheduler_core.generation.resources import make_devices, make_persons, make_setups
from scheduler_core.generation.rng import streams
from scheduler_core.generation.timing import assign_times
from scheduler_core.generation.workflow import make_tasks, task_groups
from scheduler_core.models import Instance


def generate_instance(
    scale: str,
    utilization: float,
    deadline_tightness: float,
    seed: int,
    *,
    params: GeneratorParams | None = None,
) -> Instance:
    """Build an in-memory instance, without modifying the inputs or doing IO.

    ``scale`` is S, M, or L; utilization is finite in [0.05, 1],
    deadline_tightness in [0, 1], and seed an integer in [0, 2**63-1].
    Booleans are not numbers here. Optional params must be valid for the scale.
    Times are integer five-minute slots from 2026-01-05 00:00 UTC
    (08:00 Asia/Shanghai). Returns a new Instance, not a schedule; it does
    not guarantee feasibility or optimality. TypeError denotes invalid input
    types; ValueError denotes invalid values, parameters or excessive horizon."""
    scale, utilization, deadline_tightness, seed, params = validate_inputs(
        scale, utilization, deadline_tightness, seed, params
    )
    n_tasks, n_devices, n_experiments = SCALES[scale]
    random = streams(seed)
    types = params.device_type_count[scale]
    devices = make_devices(n_devices, types, params, random["resources"])
    persons = make_persons(n_devices, params, random["skills"])
    setups = make_setups(devices, types, params, random["setups"])
    groups = task_groups(n_tasks, n_experiments, random["workflow"])
    edges = [
        edge
        for group in groups
        for edge in build_precedences(
            group,
            params.dag_depth_ratio,
            params.extra_edge_prob,
            params.lag_min_max,
            random["workflow"],
            random["lags"],
        )
    ]
    tasks = make_tasks(groups, types, devices, persons, params, random)
    timing = assign_times(
        tasks, groups, edges, devices, persons, utilization, deadline_tightness, params, random
    )
    return Instance(
        axis=TimeAxis(t0=datetime(2026, 1, 5, tzinfo=timezone.utc), horizon_slots=timing.horizon),
        devices=devices,
        tasks=timing.tasks,
        precedences=edges,
        persons=timing.persons,
        setups=setups,
        blocked=timing.blocked,
    )
