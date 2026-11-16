"""Nested rollback for incremental event journals."""

from simulator.transaction import UndoJournal


def test_nested_commit_and_rollback_restore_writes() -> None:
    journal = UndoJournal()
    data = {"a": 1}
    values = {"x"}
    journal.begin()
    journal.item(data, "a")
    data["a"] = 2
    journal.begin()
    journal.item(data, "b")
    data["b"] = 3
    journal.member(values, "x")
    values.remove("x")
    journal.commit()
    journal.rollback()
    assert data == {"a": 1}
    assert values == {"x"}
    assert not journal.active


def test_inner_rollback_preserves_outer_changes() -> None:
    journal = UndoJournal()
    data = {"a": 1}
    journal.begin()
    journal.item(data, "a")
    data["a"] = 2
    journal.begin()
    journal.item(data, "a")
    data["a"] = 3
    journal.rollback()
    assert data == {"a": 2}
    journal.commit()
    assert data == {"a": 2}
