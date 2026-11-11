import pytest
from scheduler_core.generate import generate_instance
from scheduler_core.generation.canonical import instance_from_bytes, instance_to_bytes


def test_roundtrip_and_reject_noncanonical() -> None:
    data = instance_to_bytes(generate_instance("S", 0.8, 0.5, 0))
    assert instance_to_bytes(instance_from_bytes(data)) == data
    for broken in (data[:-1], data + b"\n", b"\xef\xbb\xbf" + data, b'{"x":1,"x":2}\n', b"NaN\n"):
        with pytest.raises(ValueError):
            instance_from_bytes(broken)


def test_integrity_rejects_mutated_models() -> None:
    from datetime import timedelta
    from scheduler_core.generation.integrity import check_instance_integrity

    instance = generate_instance("S", 0.8, 0.5, 0)
    instance.devices[1].id = instance.devices[0].id
    with pytest.raises(ValueError):
        check_instance_integrity(instance)
    instance = generate_instance("S", 0.8, 0.5, 0)
    instance.axis.t0 += timedelta(microseconds=1)
    with pytest.raises(ValueError):
        check_instance_integrity(instance)
    instance = generate_instance("S", 0.8, 0.5, 0)
    instance.tasks[0].release = True
    with pytest.raises(ValueError):
        check_instance_integrity(instance)
    instance = generate_instance("S", 0.8, 0.5, 0)
    instance.tasks[0].compatible_devices = []
    with pytest.raises(ValueError):
        check_instance_integrity(instance)


def test_incomplete_lists_and_references() -> None:
    from scheduler_core.generation.integrity import check_instance_integrity

    instance = generate_instance("S", 0.8, 0.5, 0)
    instance.blocked = []
    instance.setups = []
    check_instance_integrity(instance)
    instance.tasks[0].compatible_devices = ["missing"]
    with pytest.raises(ValueError):
        check_instance_integrity(instance)


def test_noncanonical_json() -> None:
    import json

    instance = generate_instance("S", 0.8, 0.5, 0)
    value = json.loads(instance_to_bytes(instance))
    value["tasks"][0]["duration"] = float(value["tasks"][0]["duration"])
    with pytest.raises(ValueError):
        instance_from_bytes(
            (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
        )


@pytest.mark.parametrize(
    "data",
    [b"\xff\n", b"[]\n", b"{}x\n", b"NaN\n", b"Infinity\n", b"-Infinity\n", b'{"a":1,"a":2}\n'],
)
def test_invalid_json(data: bytes) -> None:
    with pytest.raises(ValueError):
        instance_from_bytes(data)


def test_noncanonical_collection_and_axis() -> None:
    import json

    base = json.loads(instance_to_bytes(generate_instance("S", 0.8, 0.5, 0)))
    variants = []
    import copy

    x = copy.deepcopy(base)
    x["devices"][0]["capabilities"] = ["x", "x"]
    variants.append(x)
    x = copy.deepcopy(base)
    x["persons"][0]["skills"] = ["z", "a"]
    variants.append(x)
    x = copy.deepcopy(base)
    x["axis"]["t0"] = "2026-01-05T08:00:00+08:00"
    variants.append(x)
    x = copy.deepcopy(base)
    x["axis"]["t0"] = "2026-01-05T00:00:00.000001+00:00"
    variants.append(x)
    x = copy.deepcopy(base)
    x["tasks"][0]["release"] = "0"
    variants.append(x)
    for value in variants:
        with pytest.raises(ValueError):
            instance_from_bytes(
                (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
            )
    data = instance_to_bytes(generate_instance("S", 0.8, 0.5, 0))
    with pytest.raises(ValueError):
        instance_from_bytes(data.replace(b'"axis":', b'"axis": ', 1))


@pytest.mark.parametrize(
    "case",
    [
        "duplicate_edge",
        "cycle",
        "missing_setup_device",
        "missing_window_device",
        "missing_person",
        "over_capacity",
        "cross_experiment",
        "status",
        "now",
        "kind",
        "disconnected",
        "time",
    ],
)
def test_integrity_profile_rejections(case: str) -> None:
    from scheduler_core.generation.integrity import check_generated_profile
    from scheduler_core.models import BlockedWindow, Precedence, SetupRule

    instance = generate_instance("S", 0.8, 0.5, 0)
    if case == "duplicate_edge":
        instance.precedences.append(instance.precedences[0])
    elif case == "cycle":
        edge = instance.precedences[0]
        instance.precedences.append(Precedence(pred=edge.succ, succ=edge.pred))
    elif case == "missing_setup_device":
        instance.setups.append(SetupRule(device_id="missing", task_type="x", slots=1))
    elif case == "missing_window_device":
        instance.blocked.append(BlockedWindow(device_id="missing", kind="CLOSED", start=0, end=1))
    elif case == "missing_person":
        instance.persons = []
        instance.tasks[0].requires_person = True
    elif case == "over_capacity":
        instance.tasks[0].demand = 99
    elif case == "cross_experiment":
        instance.precedences.append(
            Precedence(pred=instance.tasks[0].id, succ=instance.tasks[-1].id)
        )
    elif case == "status":
        instance.tasks[0].status = "RUNNING"
    elif case == "now":
        instance.now = 1
    elif case == "kind":
        instance.blocked.append(
            BlockedWindow(device_id=instance.devices[0].id, kind="FAULT", start=0, end=1)
        )
    elif case == "disconnected":
        instance.precedences = []
    elif case == "time":
        instance.tasks[0].deadline = instance.axis.horizon_slots + 1
    with pytest.raises(ValueError):
        check_generated_profile(instance, "S")


def test_json_spelling_and_noncanonical_sets() -> None:
    import copy
    import json

    instance = generate_instance("S", 0.8, 0.5, 0)
    instance.persons[0].skills = {"a", "b"}
    value = json.loads(instance_to_bytes(instance))
    noncanonical = [
        json.dumps(value, sort_keys=False, separators=(",", ":")),
        json.dumps(value, sort_keys=True),
        instance_to_bytes(instance).decode().replace('"a"', '"\\u0061"', 1).rstrip("\n"),
        instance_to_bytes(instance).decode().replace('"now":0', '"now":0.0', 1).rstrip("\n"),
    ]
    # Reversing root insertion order guarantees the first case is not canonical.
    noncanonical[0] = json.dumps(dict(reversed(list(value.items()))), separators=(",", ":"))
    for text in noncanonical:
        with pytest.raises(ValueError):
            instance_from_bytes((text + "\n").encode())
    duplicate = copy.deepcopy(value)
    duplicate["persons"][0]["skills"] = ["a", "a", "b"]
    with pytest.raises(ValueError):
        instance_from_bytes(
            (json.dumps(duplicate, sort_keys=True, separators=(",", ":")) + "\n").encode()
        )
