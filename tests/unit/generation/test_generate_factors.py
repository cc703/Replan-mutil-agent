from scheduler_core.generate import generate_instance


def test_tightness_only_changes_deadlines() -> None:
    loose = generate_instance("M", 0.8, 0, 42)
    tight = generate_instance("M", 0.8, 1, 42)
    assert loose.axis == tight.axis
    for a, b in zip(loose.tasks, tight.tasks):
        assert a.deadline is not None and b.deadline is not None
        assert a.deadline >= b.deadline
        assert a.model_dump(exclude={"deadline"}) == b.model_dump(exclude={"deadline"})
    assert loose.devices == tight.devices
    assert loose.precedences == tight.precedences
    assert loose.blocked == tight.blocked
    assert loose.persons == tight.persons


def test_local_calendar_anchor() -> None:
    from scheduler_core.generation.timing import closed_windows
    from scheduler_core.models import Device

    windows = closed_windows(600, [Device(id="d", type="t")], {"d"})
    assert [(w.start, w.end) for w in windows] == [(144, 288), (432, 576)]


def test_skill_selection_uses_available_pairs() -> None:
    from scheduler_core.generation.params import GeneratorParams

    both = GeneratorParams(
        skill_task_prob=1.0, two_skill_prob=1.0, skill_count=2, min_skill_holders=2
    )
    instance = generate_instance("S", 0.8, 0.5, 8, params=both)
    assert all(len(t.required_skills) == 2 for t in instance.tasks)
    single = GeneratorParams(skill_task_prob=1.0, two_skill_prob=1.0, skill_count=1)
    instance = generate_instance("S", 0.8, 0.5, 8, params=single)
    assert all(len(t.required_skills) == 1 for t in instance.tasks)


def test_utilization_and_maintenance_isolation() -> None:
    from scheduler_core.generation.params import GeneratorParams

    low = generate_instance("M", 0.6, 0.5, 3)
    high = generate_instance("M", 0.95, 0.5, 3)
    assert low.axis.horizon_slots >= high.axis.horizon_slots
    assert low.devices == high.devices
    assert low.precedences == high.precedences
    assert low.setups == high.setups
    for a, b in zip(low.tasks, high.tasks):
        assert a.model_dump(exclude={"release", "deadline"}) == b.model_dump(
            exclude={"release", "deadline"}
        )
    none = generate_instance("M", 0.8, 0.5, 3, params=GeneratorParams(maint_fraction=0))
    all_ = generate_instance("M", 0.8, 0.5, 3, params=GeneratorParams(maint_fraction=1))
    assert none.tasks == all_.tasks
    assert none.devices == all_.devices
    assert none.persons == all_.persons
    assert [w for w in none.blocked if w.kind == "CLOSED"] == [
        w for w in all_.blocked if w.kind == "CLOSED"
    ]
    assert not [w for w in none.blocked if w.kind == "MAINT"]


def test_hard_deadline_and_depth_isolation() -> None:
    from scheduler_core.generation.params import GeneratorParams

    normal = generate_instance("L", 0.8, 0.5, 12)
    hard = generate_instance("L", 0.8, 0.5, 12, params=GeneratorParams(hard_deadline_fraction=1))
    assert all(t.deadline_level == "HARD" for t in hard.tasks)
    assert all(
        a.model_dump(exclude={"deadline_level"}) == b.model_dump(exclude={"deadline_level"})
        for a, b in zip(normal.tasks, hard.tasks)
    )
    shallow = generate_instance("L", 0.8, 0.5, 12, params=GeneratorParams(dag_depth_ratio=0.01))
    assert [t.duration for t in normal.tasks] == [t.duration for t in shallow.tasks]


def test_timing_inputs_are_unchanged_and_copies_are_independent(monkeypatch: object) -> None:
    import copy
    import importlib
    from typing import Any

    from pytest import MonkeyPatch

    from scheduler_core.generation.canonical import instance_to_bytes
    from scheduler_core.generation.params import GeneratorParams
    from scheduler_core.models import PersonBlockedWindow

    assert isinstance(monkeypatch, MonkeyPatch)
    module = importlib.import_module("scheduler_core.generate")
    original = module.assign_times
    calls: list[Any] = []

    def snapshot(args: tuple[Any, ...]) -> object:
        return copy.deepcopy(args[:8])

    def checked(*args: Any) -> Any:
        args[4][0].blocked.append(PersonBlockedWindow(start=0, end=1))
        before = snapshot(args)
        random = args[8]
        first_rng = copy.deepcopy(random)
        second_rng = copy.deepcopy(random)
        first = original(*args[:8], first_rng)
        second = original(*args[:8], second_rng)
        assert first == second
        assert {k: v.bit_generator.state for k, v in first_rng.items()} == {
            k: v.bit_generator.state for k, v in second_rng.items()
        }
        assert snapshot(args) == before
        tasks, groups, edges, devices, persons, _, _, params = args[:8]
        assert all(t.deadline is not None for t in first.tasks)
        assert any(t.release != old.release for t, old in zip(first.tasks, args[0]))
        assert all(t.deadline_level == "HARD" for t in first.tasks)
        assert any(p.blocked for p in first.persons)
        for old, new in zip(tasks, first.tasks):
            assert old is not new and old.id == new.id
            assert old.required_skills is not new.required_skills
            assert old.compatible_devices is not new.compatible_devices
        for old, new in zip(persons, first.persons):
            assert old is not new and old.id == new.id
            assert old.skills is not new.skills and old.blocked is not new.blocked
            assert all(a is not b for a, b in zip(old.blocked, new.blocked))
        result = original(*args)
        assert snapshot(args) == before
        assert result == first
        calls.append((groups, edges, devices, params))
        return result

    monkeypatch.setattr(module, "assign_times", checked)
    params = GeneratorParams(person_absence_prob=1.0, hard_deadline_fraction=1.0)
    before_params = params.model_dump()
    a = module.generate_instance("S", 0.8, 0.5, 0, params=params)
    b = module.generate_instance("S", 0.8, 0.5, 0, params=params)
    assert instance_to_bytes(a) == instance_to_bytes(b)
    assert params.model_dump() == before_params
    assert len(calls) == 2
