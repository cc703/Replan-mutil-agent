"""Acceptance checks for independent schedule validation."""

from itertools import combinations_with_replacement, product

from scheduler_core.validate import validate


from .validation_helpers import capacity_case, overlap_case, reasons


def test_exhaustive_overlap_oracle() -> None:
    spans = [(s, e) for s in range(5) for e in range(s + 1, 6)]
    count = 0
    observed: set[str] = set()
    cases = list(combinations_with_replacement(spans, 3)) + [
        ((0, 2), (1, 3), (3, 5), (4, 5)),
        ((0, 5), (0, 3), (1, 2), (4, 5)),
        ((0, 1), (1, 2), (2, 3), (3, 4)),
    ]
    for intervals in cases:
        n = len(intervals)
        if any(a == b for i, a in enumerate(intervals) for b in intervals[i + 1 :]):
            observed.add("identical")
        if any(
            a[0] == b[0] and a != b for i, a in enumerate(intervals) for b in intervals[i + 1 :]
        ):
            observed.add("same_start")
        if any(
            a[1] == b[1] and a != b for i, a in enumerate(intervals) for b in intervals[i + 1 :]
        ):
            observed.add("same_end")
        if any(a[0] < b[0] and b[1] < a[1] for a in intervals for b in intervals):
            observed.add("nested")
        if any(a[1] == b[0] for a in intervals for b in intervals):
            observed.add("touching")
        if intervals == ((0, 2), (1, 3), (3, 5), (4, 5)):
            observed.add("two_components")
        if intervals == ((0, 1), (1, 2), (2, 3), (3, 4)):
            observed.add("touching_chain")
        for mask in (0, 3, (1 << n) - 1):
            inst, plan = overlap_case(intervals, mask)
            report = validate(inst, plan)
            for code, reason, indices in (
                ("V2", "DEVICE_OVERLAP", range(n)),
                ("V7", "PERSON_OVERLAP", [i for i in range(n) if mask & (1 << i)]),
            ):
                pairs = [
                    (str(i), str(j))
                    for i in indices
                    for j in indices
                    if i < j
                    and intervals[i][0] < intervals[j][1]
                    and intervals[j][0] < intervals[i][1]
                ]
                expected = {x for pair in pairs for x in pair}
                violations = [
                    v
                    for v in report.violations
                    if v.code == code and f"reason={reason};" in v.detail
                ]
                assert {x for v in violations for x in v.task_ids} == expected
                assert len(violations) <= max(0, len(indices) - 1)
                for left, right in pairs:
                    component = {left, right}
                    while True:
                        expanded = component | {
                            x for pair in pairs if component.intersection(pair) for x in pair
                        }
                        if expanded == component:
                            break
                        component = expanded
                    assert any(component.intersection(v.task_ids) for v in violations)
            count += 1
    assert count == 2049
    assert observed == {
        "identical",
        "same_start",
        "same_end",
        "nested",
        "touching",
        "two_components",
        "touching_chain",
    }


def test_exhaustive_capacity_oracle() -> None:
    spans = [(0, 1), (0, 3), (1, 2), (1, 4), (3, 4)]
    count = 0
    combinations_seen: set[tuple[int, int]] = set()
    for intervals in combinations_with_replacement(spans, 3):
        for demands in product((1, 2, 3), repeat=3):
            for cap in (1, 2, 3, 4):
                combinations_seen.update((cap, demand) for demand in demands)
                inst, plan = capacity_case(intervals, demands, cap)
                report = validate(inst, plan)
                if cap == 1:
                    pairs = [
                        (str(i), str(j))
                        for i in range(3)
                        for j in range(i + 1, 3)
                        if demands[i] <= cap
                        and demands[j] <= cap
                        and intervals[i][0] < intervals[j][1]
                        and intervals[j][0] < intervals[i][1]
                    ]
                    overlaps = [
                        v
                        for v in report.violations
                        if v.code == "V2" and "reason=DEVICE_OVERLAP;" in v.detail
                    ]
                    assert {tid for v in overlaps for tid in v.task_ids} == {
                        tid for pair in pairs for tid in pair
                    }
                    assert {
                        v.task_ids[0]
                        for v in report.violations
                        if v.code == "V9" and "reason=DEMAND_EXCEEDS_CAPACITY;" in v.detail
                    } == {str(i) for i, d in enumerate(demands) if d > cap}
                    assert not reasons(report, "V9", "CAPACITY_EXCEEDED")
                    count += 1
                    continue
                segments: list[tuple[int, int, set[str]]] = []
                points = sorted({x for pair in intervals for x in pair})
                for start, end in zip(points, points[1:]):
                    active = {
                        str(i)
                        for i, (s, e) in enumerate(intervals)
                        if s <= start and end <= e and demands[i] <= cap
                    }
                    if sum(demands[int(i)] for i in active) > cap:
                        if segments and segments[-1][1] == start:
                            prev = segments.pop()
                            segments.append((prev[0], end, prev[2] | active))
                        else:
                            segments.append((start, end, active))
                violations = [
                    v
                    for v in report.violations
                    if v.code == "V9" and "reason=CAPACITY_EXCEEDED;" in v.detail
                ]
                assert len(violations) == len(segments)
                for start, end, active in segments:
                    assert any(
                        set(v.task_ids) == active
                        and f"start={start};" in v.detail
                        and f"end={end};" in v.detail
                        for v in violations
                    )
                assert {
                    v.task_ids[0]
                    for v in report.violations
                    if v.code == "V9" and "reason=DEMAND_EXCEEDS_CAPACITY;" in v.detail
                } == {str(i) for i, d in enumerate(demands) if d > cap}
                count += 1
    assert count == 3780
    assert combinations_seen == set(product((1, 2, 3, 4), (1, 2, 3)))
