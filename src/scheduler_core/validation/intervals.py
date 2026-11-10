"""Pure half-open interval operations used by validation."""

from bisect import bisect_right
from collections import defaultdict
from collections.abc import Iterator
from heapq import heappop, heappush


def overlapping_pairs(intervals: list[tuple[int, int, str]]) -> list[tuple[str, str]]:
    """Return the same maximum-end-owner overlaps in stable scan order."""
    result: list[tuple[str, str]] = []
    max_end: int | None = None
    owner = ""
    for start, end, ident in sorted(intervals):
        if max_end is not None and start < max_end:
            result.append((owner, ident))
        if max_end is None or end > max_end:
            max_end, owner = end, ident
    return result


def merge_windows(windows: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Merge overlapping or touching windows."""
    merged: list[tuple[int, int]] = []
    for start, end in sorted(windows):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged


def overlapping_windows(
    merged: list[tuple[int, int]], ends: list[int], start: int, end: int
) -> Iterator[tuple[int, int]]:
    """Yield merged windows intersecting a half-open interval."""
    pos = bisect_right(ends, start)
    while pos < len(merged) and merged[pos][0] < end:
        yield merged[pos]
        pos += 1


def overloaded_segments(
    intervals: list[tuple[int, int, str, int]], capacity: int
) -> Iterator[tuple[int, int, list[str]]]:
    """Yield maximal overloaded segments and their participating identifiers."""
    events: dict[int, list[tuple[bool, str, int]]] = defaultdict(list)
    for start, end, ident, demand in intervals:
        events[start].append((True, ident, demand))
        events[end].append((False, ident, demand))
    active: set[str] = set()
    load = 0
    begin: int | None = None
    involved: set[str] = set()
    for point in sorted(events):
        entering_ids: set[str] = set()
        for entering, ident, demand in sorted(events[point]):
            if entering:
                entering_ids.add(ident)
                active.add(ident)
                load += demand
            else:
                active.discard(ident)
                load -= demand
        if load > capacity:
            if begin is None:
                begin = point
                involved.update(active)
            else:
                involved.update(entering_ids)
        elif begin is not None:
            yield begin, point, sorted(involved)
            begin, involved = None, set()


def cross_overlaps(
    windows: list[tuple[int, int]], intervals: list[tuple[int, int, str]]
) -> Iterator[str]:
    """Yield an identifier for every overlap between windows and intervals."""
    scan_events: list[tuple[int, int, int, str]] = []
    for number, (start, end) in enumerate(windows):
        scan_events.append((start, 1, end, str(number)))
    for start, end, ident in intervals:
        scan_events.append((start, 0, end, ident))
    active_intervals: dict[str, int] = {}
    active_windows: dict[str, int] = {}
    interval_heap: list[tuple[int, str]] = []
    window_heap: list[tuple[int, str]] = []
    for start, kind, end, ident in sorted(scan_events):
        while interval_heap and interval_heap[0][0] <= start:
            _, expired = heappop(interval_heap)
            active_intervals.pop(expired, None)
        while window_heap and window_heap[0][0] <= start:
            _, expired = heappop(window_heap)
            active_windows.pop(expired, None)
        if kind == 0:
            for _ in active_windows:
                yield ident
            active_intervals[ident] = end
            heappush(interval_heap, (end, ident))
        else:
            for active_ident in active_intervals:
                yield active_ident
            active_windows[ident] = end
            heappush(window_heap, (end, ident))
