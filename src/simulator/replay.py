"""Replay canonical logs without resampling recorded durations."""

from pydantic import TypeAdapter
from scheduler_core.models import Event, Instance, Plan

from .engine import Scheduler, SimResult, Simulator
from .log import (
    DurationSampled,
    EndRun,
    Header,
    Injected,
    ReplayMismatch,
    ReplanCalled,
    ReplanResultRecord,
    parse_log,
)
from .scenarios import Scenario


def replay(data: bytes, *, scheduler: Scheduler | None = None) -> SimResult:
    """Reconstruct a run; use recorded callback plans when scheduler is omitted."""
    try:
        entries = parse_log(data)
    except (ValueError, UnicodeError) as exc:
        for index, line in enumerate(data.splitlines(keepends=True)):
            try:
                parse_log(line)
            except (ValueError, UnicodeError) as line_error:
                raise ReplayMismatch(index, line, str(line_error)) from line_error
        raise ReplayMismatch(0, data, str(exc)) from exc
    if not entries or not isinstance(entries[0], Header) or not isinstance(entries[-1], EndRun):
        raise ValueError("replay requires header and end marker")
    header = entries[0]
    callback_results: list[Plan | None] = []
    awaiting = False
    for entry in entries:
        if isinstance(entry, ReplanCalled):
            awaiting = True
        elif awaiting and isinstance(entry, ReplanResultRecord):
            callback_results.append(
                Plan.model_validate_json(entry.plan_json) if entry.plan_json else None
            )
            awaiting = False
    position = 0

    def recorded(*_: object) -> Plan | None:
        nonlocal position
        if position >= len(callback_results):
            raise ReplayMismatch(len(entries), "recorded callback", "unexpected callback")
        result = callback_results[position]
        position += 1
        return result

    callback: Scheduler = scheduler if scheduler is not None else recorded
    engine = Simulator(
        Instance.model_validate_json(header.instance_json),
        Plan.model_validate_json(header.plan_json),
        Scenario.model_validate_json(header.scene_json),
        callback,
        header.seed,
        replay_external=entries,
    )
    engine.replay_samples = {
        (item.task_id, item.attempt): item.actual
        for item in entries
        if isinstance(item, DurationSampled)
    }
    engine.replay_exact = scheduler is None
    for item in entries:
        if isinstance(item, Injected):
            engine.run(item.time)
            event: Event = TypeAdapter(Event).validate_json(item.event_json)
            engine.inject(event, item.at)
    result = engine.run(entries[-1].t_end)
    if scheduler is None:
        actual = parse_log(result.log)
        for index in range(max(len(entries), len(actual))):
            expected = entries[index] if index < len(entries) else None
            observed = actual[index] if index < len(actual) else None
            if expected != observed:
                raise ReplayMismatch(index, expected, observed)
    return result
