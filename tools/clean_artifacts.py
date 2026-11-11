"""Inspect or clean expired temporary artifacts and failed runs."""

import argparse
import dataclasses
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, cast


def _json(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return {key: _json(item) for key, item in dataclasses.asdict(cast(Any, value)).items()}
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (tuple, list)):
        return [_json(item) for item in value]
    if isinstance(value, dict):
        return {key: _json(item) for key, item in value.items()}
    return value


def main() -> int:
    """Run maintenance and return documented CLI status codes."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", choices=("tmp", "failed-runs"), required=True)
    parser.add_argument("--older-than")
    parser.add_argument("--root", type=Path, default=Path("artifacts"))
    parser.add_argument("--index", type=Path, default=Path("docs/results/INDEX.md"))
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from scheduler_core.io.artifacts import ArtifactStore
    from scheduler_core.io.errors import ArtifactError

    try:
        maintenance = ArtifactStore.open_existing(args.root).maintenance()
        plan = maintenance.plan_cleanup(args.kind, args.older_than, args.index)
        result = maintenance.apply_cleanup(plan, args.index) if args.apply else None
    except ValueError as exc:
        parser.error(str(exc))
    except (ArtifactError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 3
    output = {"plan": _json(plan), "result": _json(result)}
    if args.format == "json":
        print(json.dumps(output, sort_keys=True, ensure_ascii=False))
    else:
        print(json.dumps(output, sort_keys=True, ensure_ascii=False, indent=2))
    return 4 if result is not None and result.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
