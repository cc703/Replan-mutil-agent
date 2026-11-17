from agent.explain import Claim, Fact, explain
from agent.evidence import candidate_facts
from agent.negotiation import negotiation_facts
from tests.unit.agent.test_store import make_world


def test_wrong_unit_falls_back_to_evidence() -> None:
    facts = {"延后": Fact("number", 10, "分钟")}
    result = explain(facts, lambda: [Claim(key="延后", kind="number", value=10, unit="槽")])
    assert result.fallback and result.text == "延后：10分钟。"
    assert (result.correct, result.total) == (0, 3)


def test_empty_facts_are_not_counted_as_correct() -> None:
    result = explain({}, lambda: [])
    assert result.total == 0 and result.fallback


def test_candidate_and_diagnosis_evidence_preserve_source_values() -> None:
    world = make_world()
    base = world.versions["p"].plan
    plan = base.model_copy(deep=True)
    plan.assignments["t"].start = 2
    plan.assignments["t"].end = 4
    plan.assignments["t"].device_id = "other"
    facts = candidate_facts(
        world.instance, base, plan, {"affected": ["t"], "reasons": {"t": "outage:d"}}, {"f1": 3.0}
    )
    assert facts["任务 t 新设备"].value == "other"
    assert facts["任务 t 结束变化"].value == 5
    assert facts["候选目标 f1"].value == 3.0
    diag = negotiation_facts(
        {
            "diagnosis": {
                "status": "CORE",
                "minimal": False,
                "solves": 2,
                "groups_total": 1,
                "groups": ["deadline:t"],
                "descriptions": ["deadline conflict"],
            },
            "proposals": [
                {
                    "cost": 2.0,
                    "optimal": False,
                    "description": "delay",
                    "deltas": {"t": 2},
                    "groups": ["deadline:t"],
                }
            ],
        }
    )
    assert diag["不可约性"].value == "未证明"
    assert diag["冲突组 0"].value == "deadline:t"
    assert diag["假设方案 0 任务 t 延后"].value == 2
