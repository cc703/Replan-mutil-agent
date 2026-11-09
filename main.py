"""A dependency-free, deterministic multi-agent replanning demo."""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Task:
    name: str
    agent: str
    status: str = "pending"
    result: Optional[str] = None


def run_demo() -> None:
    tasks: List[Task] = [
        Task("Collect requirements", "analyst"),
        Task("Draft an implementation plan", "planner"),
        Task("Validate the plan", "reviewer"),
    ]
    failed_once = False

    print("Multi-agent replan demo")
    while True:
        task = next((item for item in tasks if item.status == "pending"), None)
        if task is None:
            break

        print("[{}] {}: {}".format(task.agent, task.name, "running"))
        if task.name == "Validate the plan" and not failed_once:
            failed_once = True
            task.status = "blocked"
            task.result = "The proposed API is unavailable."
            print("  Blocked: {}".format(task.result))
            print("[coordinator] Replanning around the blocker...")
            tasks.insert(
                tasks.index(task),
                Task("Choose a local fallback", "planner"),
            )
            task.status = "pending"
            continue

        task.status = "done"
        task.result = "completed"
        print("  Done")

    print("\nFinal task status:")
    for task in tasks:
        print("- {}: {} ({})".format(task.name, task.status, task.agent))
    print("\nThe coordinator recovered from a blocked task and finished the plan.")


if __name__ == "__main__":
    run_demo()
