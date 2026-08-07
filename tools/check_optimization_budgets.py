"""Check versioned structural O1 budgets for selected S3 programs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPOSITORY_ROOT))

from bootstrap.s3.metrics import (  # noqa: E402
    OptimizationBudget,
    evaluate_optimization_budget,
)
from bootstrap.s3.pipeline import compile_source  # noqa: E402

DEFAULT_MANIFEST = REPOSITORY_ROOT / "benchmarks" / "optimization-budgets.json"
MANIFEST_FORMAT = "s3-optimization-budgets"
MANIFEST_VERSION = "1.0.0"


def evaluate_manifest(path: Path) -> dict[str, Any]:
    document = _load_manifest(path)
    results = []
    for entry in document["programs"]:
        source_path = _source_path(entry["source"])
        source = source_path.read_text(encoding="utf-8")
        before = compile_source(source, "O0").ir
        after = compile_source(source, "O1").ir
        raw_budget = entry["budget"]
        budget = OptimizationBudget(
            maximum_blocks=raw_budget["maximum_blocks"],
            maximum_instructions=raw_budget["maximum_instructions"],
            maximum_branches=raw_budget["maximum_branches"],
            require_non_growth=raw_budget.get("require_non_growth", True),
        )
        evaluation = evaluate_optimization_budget(before, after, budget)
        results.append(
            {
                "id": entry["id"],
                "source": entry["source"],
                "status": "PASS" if evaluation.passed else "FAIL",
                "before": _metrics_dict(evaluation.metrics.before),
                "after": _metrics_dict(evaluation.metrics.after),
                "budget": {
                    "maximum_blocks": budget.maximum_blocks,
                    "maximum_instructions": budget.maximum_instructions,
                    "maximum_branches": budget.maximum_branches,
                    "require_non_growth": budget.require_non_growth,
                },
                "violations": list(evaluation.violations),
            }
        )
    return {
        "format": MANIFEST_FORMAT,
        "version": MANIFEST_VERSION,
        "status": "PASS" if all(item["status"] == "PASS" for item in results) else "FAIL",
        "programs": results,
    }


def _load_manifest(path: Path) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid optimization budget manifest: {path}: {error}") from error
    if not isinstance(document, dict):
        raise ValueError("optimization budget manifest must be an object")
    if document.get("format") != MANIFEST_FORMAT:
        raise ValueError(f"unsupported optimization budget format: {document.get('format')!r}")
    if document.get("version") != MANIFEST_VERSION:
        raise ValueError(f"unsupported optimization budget version: {document.get('version')!r}")
    programs = document.get("programs")
    if not isinstance(programs, list) or not programs:
        raise ValueError("optimization budget manifest must contain programs")
    identifiers = [entry.get("id") for entry in programs if isinstance(entry, dict)]
    if len(identifiers) != len(programs) or any(not identifier for identifier in identifiers):
        raise ValueError("every optimization budget program must have a non-empty id")
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("optimization budget program ids must be unique")
    return document


def _source_path(value: object) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError("optimization budget source must be a non-empty string")
    relative = Path(value)
    if relative.is_absolute():
        raise ValueError(f"optimization budget source must be relative: {value}")
    resolved = (REPOSITORY_ROOT / relative).resolve()
    try:
        resolved.relative_to(REPOSITORY_ROOT.resolve())
    except ValueError as error:
        raise ValueError(f"optimization budget source escapes the repository: {value}") from error
    if not resolved.is_file():
        raise ValueError(f"optimization budget source does not exist: {value}")
    return resolved


def _metrics_dict(metrics) -> dict[str, int]:
    return {
        "block_count": metrics.block_count,
        "instruction_count": metrics.instruction_count,
        "branch_count": metrics.branch_count,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args(argv)
    try:
        report = evaluate_manifest(args.manifest)
    except (KeyError, TypeError, ValueError) as error:
        print(f"optimization budget error: {error}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True) + "\n", end="")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
