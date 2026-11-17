"""Offline demonstration and synthetic pipeline evaluation."""

import argparse
from datetime import datetime
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from langgraph.types import Command
from scheduler_core.io.artifacts import ArtifactStore
from scheduler_core.validation_context import ExecutionSnapshot, ValidationContext

from .evaluation import evaluate
from .graph import build_graph
from .llm import DeepSeek, online_explainer, online_extractor, online_router
from .miniature import miniature
from .solver import initial
from .store import WorldStore
from .trace import Trace


def demo(*, interactive: bool = False, online: bool = False) -> None:
    instance = miniature()
    _, evidence = initial(instance)
    if evidence is None:
        raise RuntimeError("initial plan unavailable")
    store = WorldStore("demo", instance, evidence)
    context = ValidationContext(
        snapshot=ExecutionSnapshot(plan_id=evidence.plan.id, as_of=0, base_as_of=0)
    )
    response: dict[str, object] = {
        "kind": "DEVICE_OUTAGE",
        "strength": "HARD",
        "device": {"original": "d1", "resolved_id": "d1", "confidence": 1.0},
        "start": "2026-01-01T00:25:00Z",
        "end": "2026-01-01T00:35:00Z",
    }
    trace = Trace(
        "online" if online else "offline", Path("src/agent/prompts/extract/v001.md").read_bytes()
    )
    if online:
        client = DeepSeek.from_environment(trace)
        extractor = online_extractor(client, store)
        explainer = online_explainer(client)
        router = online_router(client)
    elif interactive:

        def extractor(_: str) -> dict[str, object]:
            raw = json.loads(input("输入离线录制的模型响应 JSON: "))
            if not isinstance(raw, dict):
                raise ValueError("expected object")
            return raw

        explainer = None
        router = None
    else:

        def extractor(_: str) -> dict[str, object]:
            return response

        explainer = None
        router = None
    graph = build_graph(store, extractor, context, trace, explainer, router)
    config = {"configurable": {"thread_id": "demo"}}
    text = input("请输入请求: ") if interactive else "设备 d1 在 00:25 至 00:35 停机"
    state = graph.invoke({"text": text}, config)
    while state.get("__interrupt__"):
        prompt = state["__interrupt__"][0].value
        if prompt["kind"] == "form":
            print(prompt["error"])
            try:
                edited = json.loads(input("输入变更 JSON（空行退出）: ") or "null")
            except ValueError:
                edited = {}
            state = graph.invoke(Command(resume=edited), config)
            continue
        if prompt["kind"] == "ROLLBACK_TARGET":
            print(json.dumps(prompt, ensure_ascii=False))
            state = graph.invoke(Command(resume=input("目标版本（空行退出）: ") or None), config)
            continue
        shown = dict(prompt)
        if prompt["kind"] == "L1":
            shown.pop("binding", None)
            shown["proposal"] = dict(shown["proposal"])

            def show_times(item: dict[str, object]) -> None:
                for key in ("start", "end", "deadline", "release"):
                    value = item.get(key)
                    if isinstance(value, str):
                        item[key] = (
                            datetime.fromisoformat(value.replace("Z", "+00:00"))
                            .astimezone(ZoneInfo("Asia/Shanghai"))
                            .isoformat()
                        )

            show_times(shown["proposal"])
            if "tasks" in shown["proposal"]:
                shown["proposal"]["tasks"] = [dict(item) for item in shown["proposal"]["tasks"]]
                for task in shown["proposal"]["tasks"]:
                    show_times(task)
        print(json.dumps(shown, ensure_ascii=False, indent=2))
        if input("确认？[y/N] ").strip().lower() != "y":
            state = graph.invoke(Command(resume=False), config)
            break
        if prompt["kind"] == "L1":
            token = store.authorize("L1", "change", prompt["binding"])
            state = graph.invoke(Command(resume=token), config)
        elif prompt["kind"] == "L2":
            choice = input("选择候选编号（从 0 开始）: ").strip()
            if not choice.isdigit() or int(choice) >= len(prompt["plans"]):
                state = graph.invoke(Command(resume=False), config)
                break
            plan = prompt["plans"][int(choice)]
            token = store.authorize("L2", "commit", plan)
            state = graph.invoke(
                Command(resume={"token": token, "candidate_id": plan["id"]}), config
            )
        elif prompt["kind"] == "NEGOTIATION":
            choice = input("选择假设方案编号（从 0 开始，空行退出）: ").strip()
            state = graph.invoke(Command(resume=int(choice) if choice.isdigit() else None), config)
        elif prompt["kind"] == "L2_ROLLBACK":
            token = store.authorize("L2", "rollback", prompt["binding"])
            state = graph.invoke(Command(resume=token), config)
        else:
            state = graph.invoke(Command(resume=False), config)
    stale = store.versions[store.active].instance != store.instance
    print(f"结果: {state.get('outcome', '未完成')}；正式版本: {store.active}；需重算: {stale}")
    trace.finish({})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["demo", "eval", "chat"])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--offline", action="store_true")
    mode.add_argument("--online", action="store_true")
    args = parser.parse_args()
    if args.command == "chat":
        demo(interactive=True, online=args.online)
    elif args.command == "demo" and args.offline:
        demo()
    elif args.command == "eval" and args.offline:
        path = Path("data/eval_sets/extraction_smoke/v001.jsonl")
        result = evaluate(path, miniature())
        run = ArtifactStore().new_run(
            "agent_eval",
            "extraction-smoke",
            "offline",
            command="python -m agent eval --offline",
            metadata={"mode": "offline", "fixture": "v001"},
        )
        run.write_json("score.json", result)
        run.finish("completed", outputs=["score.json"])
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        parser.error("demo and eval are offline only")


if __name__ == "__main__":
    main()
