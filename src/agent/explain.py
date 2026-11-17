"""Evidence-backed claims with controlled rendering and deterministic fallback."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict


class Claim(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    key: str
    kind: Literal["number", "text"]
    value: int | float | str
    unit: str


class ClaimResponse(BaseModel):
    """Reject extra model text and malformed claim lists."""

    model_config = ConfigDict(extra="forbid", strict=True)
    claims: list[Claim]


@dataclass(frozen=True)
class Fact:
    kind: Literal["number", "text"]
    value: int | float | str
    unit: str


@dataclass(frozen=True)
class Explanation:
    text: str
    claims: tuple[Claim, ...]
    correct: int
    total: int
    fallback: bool


def explain(
    facts: dict[str, Fact], propose: Callable[[], list[Claim]], retries: int = 2
) -> Explanation:
    """Accept only exact evidence facts; output consists solely of controlled sentences."""
    if not facts:
        return Explanation("无可验证事实。", (), 0, 0, True)
    correct = total = 0
    for _ in range(retries + 1):
        try:
            claims = propose()
            if not claims:
                continue
            if any(not isinstance(claim, Claim) for claim in claims):
                raise ValueError("invalid claim response")
            good = [
                claim
                for claim in claims
                if claim.key in facts
                and (claim.kind, claim.value, claim.unit)
                == (facts[claim.key].kind, facts[claim.key].value, facts[claim.key].unit)
            ]
            correct += len(good)
            total += len(claims)
            if len(good) == len(claims):
                return Explanation(_render(claims), tuple(claims), correct, total, False)
        except (ValueError, TypeError, KeyError, RuntimeError):
            pass
    claims = [
        Claim(key=key, kind=fact.kind, value=fact.value, unit=fact.unit)
        for key, fact in sorted(facts.items())
    ]
    return Explanation(_render(claims), tuple(claims), correct, total, True)


def _render(claims: list[Claim]) -> str:
    return "；".join(f"{claim.key}：{claim.value}{claim.unit}" for claim in claims) + "。"
