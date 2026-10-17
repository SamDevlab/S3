"""CLI for Agent Memory V1 offline protocol smoke validation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
EXTERNAL_ROOT = REPOSITORY_ROOT / "external-benchmarks"
sys.path.insert(0, str(EXTERNAL_ROOT))

from harness.core import ExternalBenchmarkError  # noqa: E402
from harness.smoke import run_protocol_smoke  # noqa: E402


def _outside_repository(path: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(REPOSITORY_ROOT.resolve())
    except ValueError:
        return resolved
    raise ExternalBenchmarkError("smoke workspace must be outside the controller repository")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate all 28 Agent Memory V1 provider/scenario bundles offline"
    )
    parser.add_argument("--workspace-root", type=Path, required=True)
    parser.add_argument(
        "--with-oracles",
        action="store_true",
        help="also create subject worktrees and run the seven semantic scenario oracles",
    )
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args(argv)

    try:
        workspace_root = _outside_repository(args.workspace_root)
        result = run_protocol_smoke(
            repository_root=REPOSITORY_ROOT,
            workspace_root=workspace_root,
            with_oracles=args.with_oracles,
        )
        payload = json.dumps(result, indent=2, sort_keys=True, allow_nan=False)
        if args.output_json is not None:
            args.output_json.parent.mkdir(parents=True, exist_ok=True)
            args.output_json.write_text(payload + "\n", encoding="utf-8", newline="\n")
        print(payload)
        return 0 if result.get("status") == "PASS" else 1
    except ExternalBenchmarkError as error:
        raise SystemExit(str(error)) from error


if __name__ == "__main__":
    raise SystemExit(main())
