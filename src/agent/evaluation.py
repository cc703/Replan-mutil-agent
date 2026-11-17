"""Exact-match scoring for synthetic offline extraction pipeline smoke cases."""

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from statistics import mean, pvariance
from typing import Any, cast

from scheduler_core.models import Instance

from .ir import Deadline, Outage, Overrun, Urgent, parse_draft, urgent_core


@dataclass(frozen=True)
class Item:
    kind: str
    entity: str
    value: str


def canonical(item: Item) -> Item:
    """Normalize independently supplied timestamps to UTC."""
    count = {"DEVICE_OUTAGE": 2, "DEADLINE": 1, "TASK_OVERRUN": 1}.get(item.kind, 0)
    if not count:
        return item
    fields = item.value.split("|")
    try:
        for index in range(count):
            value = datetime.fromisoformat(fields[index].replace("Z", "+00:00"))
            if value.utcoffset() is None:
                raise ValueError("timezone required")
            fields[index] = value.astimezone(timezone.utc).isoformat()
    except (ValueError, IndexError):
        return item
    return Item(item.kind, item.entity, "|".join(fields))


def score(predictions: list[Item], gold: list[Item]) -> dict[str, Any]:
    """Multiset exact matches, with explicit denominators and per-kind results."""
    predictions = [canonical(item) for item in predictions]
    gold = [canonical(item) for item in gold]
    predicted, expected = Counter(predictions), Counter(gold)
    matches = sum((predicted & expected).values())
    precision = matches / len(predictions) if predictions else 0.0
    recall = matches / len(gold) if gold else 0.0
    by_kind = {}
    for kind in sorted({item.kind for item in predictions + gold}):
        p = [item for item in predictions if item.kind == kind]
        g = [item for item in gold if item.kind == kind]
        hit = sum((Counter(p) & Counter(g)).values())
        kp = hit / len(p) if p else 0.0
        kr = hit / len(g) if g else 0.0
        by_kind[kind] = {
            "matched": hit,
            "predicted": len(p),
            "gold": len(g),
            "precision": kp,
            "recall": kr,
            "f1": 2 * kp * kr / (kp + kr) if kp + kr else 0.0,
        }
    return {
        "matched": matches,
        "predicted": len(predictions),
        "gold": len(gold),
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "by_kind": by_kind,
    }


def score_cases(cases: list[tuple[list[Item], list[Item]]]) -> dict[str, Any]:
    """Aggregate matches within each utterance; never match across utterances."""
    individual = [score(predicted, gold) for predicted, gold in cases]
    matched = sum(item["matched"] for item in individual)
    predicted_count = sum(item["predicted"] for item in individual)
    gold_count = sum(item["gold"] for item in individual)
    precision = matched / predicted_count if predicted_count else 0.0
    recall = matched / gold_count if gold_count else 0.0
    by_kind: dict[str, Any] = {}
    for kind in sorted({key for result in individual for key in result["by_kind"]}):
        groups = [result["by_kind"].get(kind, {}) for result in individual]
        hit = sum(item.get("matched", 0) for item in groups)
        p = sum(item.get("predicted", 0) for item in groups)
        g = sum(item.get("gold", 0) for item in groups)
        kp, kr = (hit / p if p else 0.0), (hit / g if g else 0.0)
        by_kind[kind] = {
            "matched": hit,
            "predicted": p,
            "gold": g,
            "precision": kp,
            "recall": kr,
            "f1": 2 * kp * kr / (kp + kr) if kp + kr else 0.0,
        }
    return {
        "matched": matched,
        "predicted": predicted_count,
        "gold": gold_count,
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "by_kind": by_kind,
    }


def prediction(response: dict[str, Any], instance: Instance) -> list[Item]:
    """Run recorded model output through the same untrusted IR and semantic checks."""
    changes = response.get("changes", [response])
    if (
        not isinstance(changes, list)
        or not changes
        or any(not isinstance(x, dict) for x in changes)
    ):
        return [Item("clarification", "", "")]
    output: list[Item] = []
    for change in changes:
        output.extend(_one_prediction(change, instance))
    return output


def _one_prediction(response: dict[str, Any], instance: Instance) -> list[Item]:
    try:
        _, proposal = parse_draft(response, instance)
    except ValueError as exc:
        kind = "unsupported" if "soft preference" in str(exc) else "clarification"
        return [Item(kind, "", "")]
    if isinstance(proposal, Outage):
        return [
            Item(
                proposal.kind,
                proposal.device.resolved_id or "",
                f"{proposal.start.isoformat()}|{proposal.end.isoformat()}",
            )
        ]
    if isinstance(proposal, Deadline):
        return [
            Item(
                proposal.kind,
                proposal.task.resolved_id or "",
                f"{proposal.deadline.isoformat()}|{proposal.level}|{proposal.weight}",
            )
        ]
    if isinstance(proposal, Overrun):
        return [Item(proposal.kind, proposal.task.resolved_id or "", proposal.end.isoformat())]
    assert isinstance(proposal, Urgent)
    items = []
    for task in proposal.tasks:
        fields = urgent_core(task, instance).model_dump(mode="json", exclude={"id"})
        fields["required_skills"] = sorted(fields["required_skills"])
        fields["compatible_devices"] = sorted(fields["compatible_devices"])
        items.append(Item(proposal.kind, task.id, json.dumps(fields, sort_keys=True)))
    for edge in proposal.precedences:
        items.append(
            Item(
                "URGENT_PRECEDENCE",
                f"{edge.pred}->{edge.succ}",
                json.dumps(edge.model_dump(mode="json"), sort_keys=True),
            )
        )
    return items


def evaluate(path: Path, instance: Instance) -> dict[str, Any]:
    """Score recorded predictions independently from gold three times."""
    rows = [json.loads(line) for line in path.read_text("utf-8").splitlines() if line.strip()]
    recordings = {row["utterance"]: row["recorded_response"] for row in rows}

    def recorded(utterance: str) -> dict[str, Any]:
        return cast(dict[str, Any], recordings[utterance])

    results = []
    for _ in range(3):
        pairs = [
            (
                prediction(recorded(row["utterance"]), instance),
                [Item(**item) for item in row["gold"]],
            )
            for row in rows
        ]
        result = score_cases(pairs)
        for category, name in (
            ("entity_ambiguity", "clarification_errors"),
            ("soft_hard", "soft_hard_errors"),
        ):
            cases = [row for row in rows if row["category"] == category]
            result[name] = {
                "errors": sum(
                    Counter(canonical(x) for x in prediction(recorded(row["utterance"]), instance))
                    != Counter(canonical(Item(**x)) for x in row["gold"])
                    for row in cases
                ),
                "total": len(cases),
            }
        result["categories"] = {}
        for category in sorted({row["category"] for row in rows}):
            cases = [row for row in rows if row["category"] == category]
            exact = sum(
                Counter(canonical(x) for x in prediction(recorded(row["utterance"]), instance))
                == Counter(canonical(Item(**x)) for x in row["gold"])
                for row in cases
            )
            result["categories"][category] = {"exact": exact, "total": len(cases)}
        results.append(result)
    values = [item["f1"] for item in results]
    return {
        "mode": "offline pipeline smoke, not DeepSeek accuracy",
        "repetitions": results,
        "f1_mean": mean(values),
        "f1_variance": pvariance(values),
    }
