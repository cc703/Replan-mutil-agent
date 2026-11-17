from typing import Any

from agent.evaluation import Item, prediction, score, score_cases
from agent.miniature import miniature


def test_wrong_prediction_reduces_exact_match() -> None:
    gold = [Item("deadline", "t", "10"), Item("outage", "d", "5")]
    assert score(gold, gold)["f1"] == 1
    assert score([gold[0], Item("outage", "wrong", "5")], gold)["f1"] == 0.5


def test_swapped_utterance_predictions_do_not_match_across_cases() -> None:
    first, second = Item("DEADLINE", "t", "10"), Item("DEADLINE", "t", "20")
    result = score_cases([([first], [second]), ([second], [first])])
    assert result["matched"] == 0 and result["f1"] == 0


def test_equal_instants_with_different_offsets_match() -> None:
    utc = Item("DEVICE_OUTAGE", "d", "2026-01-01T00:25:00+00:00|2026-01-01T00:35:00+00:00")
    local = Item("DEVICE_OUTAGE", "d", "2026-01-01T08:25:00+08:00|2026-01-01T08:35:00+08:00")
    assert score_cases([([utc], [local])])["f1"] == 1


def test_outage_end_and_second_urgent_task_are_scored() -> None:
    outage = {
        "kind": "DEVICE_OUTAGE",
        "strength": "HARD",
        "device": {"original": "d1", "resolved_id": "d1", "confidence": 1.0},
        "start": "2026-01-01T00:25:00Z",
        "end": "2026-01-01T00:35:00Z",
    }
    gold = prediction(outage, miniature())
    wrong = dict(outage, end="2026-01-01T00:40:00Z")
    assert score(prediction(wrong, miniature()), gold)["f1"] == 0
    task = {
        "id": "u1",
        "experiment_id": "e1",
        "type": "generic",
        "duration_minutes": 10,
        "release": "2026-01-01T00:00:00Z",
        "deadline": "2026-01-01T01:40:00Z",
        "compatible_devices": ["d1"],
    }
    urgent: dict[str, Any] = {
        "kind": "URGENT_TASK_INSERT",
        "strength": "HARD",
        "tasks": [task, dict(task, id="u2")],
    }
    gold = prediction(urgent, miniature())
    urgent["tasks"][1]["duration_minutes"] = 15
    assert score(prediction(urgent, miniature()), gold)["f1"] == 0.5


def test_multiple_and_relative_predictions_share_production_parser() -> None:
    ref = {"original": "t1", "resolved_id": "t1", "confidence": 1.0}
    deadline = {
        "kind": "DEADLINE",
        "strength": "HARD",
        "task": ref,
        "deadline": "今天 09:00",
        "level": "HARD",
        "weight": 1.0,
    }
    items = prediction({"changes": [deadline, dict(deadline, deadline="今天 09:05")]}, miniature())
    assert len(items) == 2 and items[0].value.startswith("2026-01-01T09:00:00+08:00")
