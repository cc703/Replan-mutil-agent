"""Shared CP-SAT expressions for optional deadline postponement."""

from ortools.sat.python import cp_model


def make_deltas(
    model: cp_model.CpModel, limits: dict[str, int]
) -> tuple[dict[str, cp_model.IntVar], dict[str, cp_model.IntVar]]:
    """Create exact positive-support indicators and nonnegative slot deltas."""
    deltas = {}
    active = {}
    for tid, limit in limits.items():
        delta = model.new_int_var(0, limit, f"relax:{tid}")
        bit = model.new_bool_var(f"relax_active:{tid}")
        model.add(delta >= 1).only_enforce_if(bit)
        model.add(delta == 0).only_enforce_if(bit.Not())
        deltas[tid], active[tid] = delta, bit
    return deltas, active


def set_objective(
    model: cp_model.CpModel,
    deltas: dict[str, cp_model.IntVar],
    active: dict[str, cp_model.IntVar],
    costs: dict[str, int],
    excluded: list[set[str]],
    limits: dict[str, int],
) -> None:
    """Minimize exact primary cost and then slots; exclude comparable supports."""
    for support in excluded:
        model.add(sum(1 - active[t] for t in support) >= 1)
        model.add(sum(active[t] for t in active.keys() - support) >= 1)
    model.add(sum(active.values()) >= 1)
    scale = sum(limits.values()) + 1
    model.minimize(sum((costs[t] * scale + 1) * delta for t, delta in deltas.items()))
