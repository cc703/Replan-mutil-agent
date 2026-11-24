"""Canonical payload and domain-model hashes computed only in Python."""

import hashlib
import json

from scheduler_core.generation.canonical import instance_to_bytes
from scheduler_core.models import Instance


def digest(value: object) -> str:
    body = json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def instance_digest(instance: Instance) -> str:
    return hashlib.sha256(instance_to_bytes(instance)).hexdigest()
