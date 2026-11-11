"""Canonical JSON encoding for generated instances."""

import json
from typing import Any

from scheduler_core.generation.integrity import check_instance_integrity
from scheduler_core.models import Instance


def _normalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _normalize(v) for k, v in value.items()}
    if isinstance(value, set):
        return sorted(value)
    if isinstance(value, list):
        return [_normalize(v) for v in value]
    return value


def instance_to_bytes(instance: Instance) -> bytes:
    """Encode a valid Instance as compact, sorted UTF-8 JSON with one newline.

    Caller must supply an integrity-valid Instance with UTC whole-second t0;
    this encoder does not itself run integrity checks. Sets are sorted and
    non-finite values raise ValueError. It neither mutates the instance nor
    performs IO; output represents slots in the instance axis units."""
    data = _normalize(instance.model_dump(mode="python"))
    data["axis"]["t0"] = instance.axis.t0.isoformat()
    return (
        json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def instance_from_bytes(data: bytes) -> Instance:
    """Decode canonical UTF-8 bytes into an integrity-checked Instance.

    Requires exactly canonical encoding from instance_to_bytes: sorted keys
    and sets, UTC whole-second t0, finite numbers and one trailing newline.
    Rejects duplicate keys, malformed JSON, invalid contracts, integrity
    failures and noncanonical bytes with ValueError. It does not perform IO;
    this checks structure, not scheduling feasibility or optimality."""

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    def invalid(value: str) -> None:
        raise ValueError(f"invalid JSON constant: {value}")

    try:
        raw = json.loads(data.decode("utf-8"), object_pairs_hook=pairs, parse_constant=invalid)
        if not isinstance(raw, dict):
            raise ValueError("instance must be an object")
        instance = Instance.model_validate(raw)
        check_instance_integrity(instance)
        if instance_to_bytes(instance) != data:
            raise ValueError("noncanonical instance")
        return instance
    except (UnicodeError, TypeError) as exc:
        raise ValueError("invalid instance bytes") from exc
