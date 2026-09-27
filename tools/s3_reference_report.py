"""Emit conservative reference-origin, liveness, effect, and escape facts."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bootstrap.s3.lexer import SyntaxMode  # noqa: E402
from bootstrap.s3.optimizer import OptimizationLevel  # noqa: E402
from bootstrap.s3.pipeline import compile_source  # noqa: E402
from bootstrap.s3.reference_analysis import analyze_module_references  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="S3 source file to analyze")
    parser.add_argument("-O", choices=("0", "1"), default="1")
    parser.add_argument("--source-syntax", choices=("0.5", "0.6"), default="0.6")
    parser.add_argument("-o", "--output", type=Path)
    args = parser.parse_args()

    source_bytes = args.source.read_bytes()
    source = source_bytes.decode("utf-8")
    optimization = OptimizationLevel.parse(args.O)
    mode = SyntaxMode.V0_5 if args.source_syntax == "0.5" else SyntaxMode.V0_6
    compilation = compile_source(source, optimization, mode=mode)
    if compilation.ir is None:
        parser.error("reference report requires an ordinary IR artifact")
    reports = analyze_module_references(compilation.ir)

    statuses = Counter(
        fact.escape.value for report in reports for fact in report.references
    )
    origins = Counter(
        "UNKNOWN" if fact.origin_unknown else "KNOWN"
        for report in reports for fact in report.references
    )
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        head = "UNAVAILABLE"
    try:
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
    except (OSError, subprocess.CalledProcessError):
        dirty = None
    try:
        source_path = str(args.source.resolve().relative_to(ROOT))
    except ValueError:
        source_path = str(args.source.resolve())

    payload = {
        "schema_version": "1.0.0",
        "report_kind": "S3_REFERENCE_DATAFLOW_RESEARCH",
        "provenance": {
            "git_head": head,
            "git_worktree_dirty": dirty,
            "source_path": source_path,
            "source_sha256": sha256(source_bytes).hexdigest(),
            "analysis_implementation_sha256": sha256(
                (ROOT / "bootstrap/s3/reference_analysis.py").read_bytes()
            ).hexdigest(),
            "report_tool_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
            "optimization": optimization.value,
            "source_syntax": args.source_syntax,
        },
        "summary": {
            "function_count": len(reports),
            "complete_function_count": sum(report.complete for report in reports),
            "incomplete_function_count": sum(not report.complete for report in reports),
            "reference_values": sum(len(report.references) for report in reports),
            "origin_status_counts": dict(sorted(origins.items())),
            "escape_status_counts": dict(sorted(statuses.items())),
            "transformation_authorized": False,
        },
        "interpretation": {
            "complete_means": "NO_UNSUPPORTED_REFERENCE_CONSTRUCT_OR_UNKNOWN_EFFECT_WAS_ENCOUNTERED",
            "not_a_proof_of": [
                "optimizer_safety",
                "interprocedural_no_escape",
                "runtime_address_identity",
                "absence_of_language_level_aliasing_outside_modeled_regions",
            ],
        },
        "functions": [report.to_dict() for report in reports],
    }
    rendered = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if args.output is None:
        sys.stdout.write(rendered)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
