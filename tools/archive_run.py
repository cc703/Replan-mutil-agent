"""Archive a completed run or verify an existing archive."""

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


def main() -> int:
    """Parse arguments and run the requested maintenance operation."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True)
    parser.add_argument("--kind", choices=("experiment", "sim", "agent_eval"))
    parser.add_argument("--name")
    parser.add_argument("--root", type=Path, default=Path("artifacts"))
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--apply", action="store_true")
    action.add_argument("--verify", action="store_true")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
    from scheduler_core.io.artifacts import ArtifactStore
    from scheduler_core.io.errors import ArtifactError

    result: object
    applying = False
    try:
        maintenance = ArtifactStore.open_existing(args.root).maintenance()
        if args.verify:
            result = maintenance.verify_archive(args.run, args.kind, args.name)
        else:
            plan = maintenance.plan_archive(args.run, args.kind, args.name)
            applying = args.apply
            result = maintenance.archive(plan) if args.apply else plan
        payload = asdict(result)
        print(
            json.dumps(payload, default=str, sort_keys=True) if args.format == "json" else payload
        )
        return 4 if getattr(result, "status", "") == "PARTIAL_ARCHIVE" else 0
    except (ArtifactError, ValueError, OSError) as exc:
        print(
            json.dumps({"error": str(exc)}, sort_keys=True) if args.format == "json" else str(exc),
            file=sys.stderr,
        )
        return 4 if applying and str(exc) != "ARCHIVE_EXISTS" else 3


if __name__ == "__main__":
    raise SystemExit(main())
