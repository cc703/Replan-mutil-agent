"""Nested undo journal for simulator event transactions."""

from collections.abc import Callable, Iterable, MutableMapping, MutableSequence, MutableSet
from typing import Any, Self, SupportsIndex


class UndoJournal:
    """Record inverse writes; a committed child remains undoable by its parent."""

    def __init__(self) -> None:
        self._stack: list[list[Callable[[], object]]] = []

    @property
    def active(self) -> bool:
        return bool(self._stack)

    def begin(self) -> None:
        self._stack.append([])

    def record(self, undo: Callable[[], object]) -> None:
        if self._stack:
            self._stack[-1].append(undo)

    def commit(self) -> None:
        actions = self._stack.pop()
        if self._stack:
            self._stack[-1].extend(actions)

    def rollback(self) -> None:
        for undo in reversed(self._stack.pop()):
            undo()

    def attr(self, obj: Any, name: str) -> None:
        if self.active:
            old = getattr(obj, name)
            self.record(lambda: setattr(obj, name, old))

    def item(self, mapping: MutableMapping[Any, Any], key: Any) -> None:
        if self.active:
            present = key in mapping
            old = mapping.get(key)

            def undo() -> None:
                if present:
                    mapping[key] = old
                else:
                    mapping.pop(key, None)

            self.record(undo)

    def member(self, values: MutableSet[Any], value: Any) -> None:
        if self.active:
            present = value in values

            def undo() -> None:
                if present:
                    values.add(value)
                else:
                    values.discard(value)

            self.record(undo)

    def index(self, values: MutableSequence[Any], index: int) -> None:
        if self.active:
            old = values[index]
            self.record(lambda: values.__setitem__(index, old))


class JournalList(list[Any]):
    """List whose ordinary mutations join the current undo transaction."""

    def __init__(self, journal: UndoJournal) -> None:
        super().__init__()
        self._journal = journal

    def _save(self) -> None:
        if self._journal.active:
            old = self.copy()
            self._journal.record(lambda: list.__setitem__(self, slice(None), old))

    def append(self, value: Any) -> None:
        self._journal.record(lambda: list.pop(self))
        super().append(value)

    def extend(self, values: Iterable[Any]) -> None:
        added = list(values)
        start = len(self)
        self._journal.record(lambda: list.__delitem__(self, slice(start, None)))
        super().extend(added)

    def insert(self, index: SupportsIndex, value: Any) -> None:
        raw_index = index.__index__()
        position = max(0, min(len(self), raw_index if raw_index >= 0 else len(self) + raw_index))
        self._journal.record(lambda: list.__delitem__(self, position))
        super().insert(index, value)

    def pop(self, index: SupportsIndex = -1) -> Any:
        raw_index = index.__index__()
        position = raw_index if raw_index >= 0 else len(self) + raw_index
        value = self[index]
        self._journal.record(lambda: list.insert(self, position, value))
        return super().pop(index)

    def remove(self, value: Any) -> None:
        self.pop(self.index(value))

    def clear(self) -> None:
        self._save()
        super().clear()

    def __setitem__(self, index: Any, value: Any) -> None:
        self._save()
        super().__setitem__(index, value)

    def __delitem__(self, index: Any) -> None:
        self._save()
        super().__delitem__(index)

    def __iadd__(self, values: Iterable[Any]) -> Self:  # type: ignore[misc]
        self.extend(values)
        return self

    def __imul__(self, count: SupportsIndex) -> Self:
        self._save()
        return super().__imul__(count)

    def reverse(self) -> None:
        self._journal.record(lambda: list.reverse(self))
        super().reverse()

    def sort(self, *args: Any, **kwargs: Any) -> None:
        self._save()
        super().sort(*args, **kwargs)
