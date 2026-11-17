"""Approval tokens bind all fields and cannot be replayed."""

from dataclasses import replace

import pytest

from agent.permits import Binding, PermitStore, payload_digest


def test_exact_binding_and_single_use() -> None:
    store = PermitStore()
    approved = Binding("L1", "event", "s1", 4, payload_digest({"id": "d"}))
    token = store.issue(approved)
    for other in (
        replace(approved, level="L2"),
        replace(approved, session="s2"),
        replace(approved, revision=5),
        replace(approved, digest=payload_digest({"id": "e"})),
    ):
        with pytest.raises(PermissionError):
            store.apply(token, other, lambda: None)
    assert store.apply(token, approved, lambda: 42) == 42
    with pytest.raises(PermissionError):
        store.apply(token, approved, lambda: None)


def test_failed_action_consumes_approval() -> None:
    store = PermitStore()
    binding = Binding("L2", "commit", "s", 1, payload_digest({"plan": 1}))
    token = store.issue(binding)

    def fail() -> None:
        raise ValueError("stale version")

    with pytest.raises(ValueError):
        store.apply(token, binding, fail)
    with pytest.raises(PermissionError):
        store.apply(token, binding, lambda: None)
