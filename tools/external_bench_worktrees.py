"""Prepare and clean isolated git worktrees for S3 external benchmark plans."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
EXTERNAL_ROOT = REPOSITORY_ROOT / "external-benchmarks"
sys.path.insert(0, str(EXTERNAL_ROOT))

from harness.core import ExternalBenchmarkError  # noqa: E402
from harness.worktrees import (  # noqa: E402
    cleanup_worktrees,
    prepare_worktrees,
    worktree_plan_document,
)


def _load_plan(path: Path) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ExternalBenchmarkError("run plan could not be read") from error
    except json.JSONDecodeError as error:
        raise ExternalBenchmarkError("run plan is not valid JSON") from error
    if not isinstance(document, dict):
        raise ExternalBenchmarkError("run plan must be a JSON object")
    return document


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Manage isolated worktrees for S3 external benchmark runs"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name in ("plan", "prepare"):
        command = subparsers.add_parser(name)
        command.add_argument("--plan-file", type=Path, required=True)
        command.add_argument("--repository-root", type=Path, default=REPOSITORY_ROOT)
        command.add_argument("--worktree-root", type=Path, required=True)
        if name == "prepare":
            command.add_argument(
                "--execute",
                action="store_true",
                help="actually create worktrees; otherwise emit the planned git operations",
            )

    cleanup = subparsers.add_parser("cleanup")
    cleanup.add_argument("--repository-root", type=Path, default=REPOSITORY_ROOT)
    cleanup.add_argument("--worktree-root", type=Path, required=True)
    cleanup.add_argument("--execute", action="store_true")
    cleanup.add_argument(
        "--discard-changes",
        action="store_true",
        help="allow removal of dirty experiment worktrees",
    )

    args = parser.parse_args(argv)
    try:
        if args.command in {"plan", "prepare"}:
            plan = _load_plan(args.plan_file)
            document = worktree_plan_document(
                plan,
                repository_root=args.repository_root,
                worktree_root=args.worktree_root,
            )
            if args.command == "prepare" and args.execute:
                specs = prepare_worktrees(
                    plan,
                    repository_root=args.repository_root,
                    worktree_root=args.worktree_root,
                )
                document = {
                    "schema_version": "1.0.0",
                    "operation": "prepared",
                    "worktrees": [spec.as_document() for spec in specs],
                }
            print(json.dumps(document, indent=2, sort_keys=True))
            return 0

        if not args.execute:
            raise ExternalBenchmarkError("cleanup requires explicit --execute")
        cleanup_worktrees(
            repository_root=args.repository_root,
            worktree_root=args.worktree_root,
            discard_changes=args.discard_changes,
        )
        print(json.dumps({"status": "CLEANED"}, sort_keys=True))
        return 0
    except ExternalBenchmarkError as error:
        raise SystemExit(str(error)) from error


if __name__ == "__main__":
    raise SystemExit(main())
