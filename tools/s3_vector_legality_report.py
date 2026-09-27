"""Emit a conservative diagnostic report for natural-loop vector legality."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bootstrap.s3.optimizer import OptimizationLevel  # noqa: E402
from bootstrap.s3.pipeline import compile_source  # noqa: E402
from bootstrap.s3.lexer import SyntaxMode  # noqa: E402
from bootstrap.s3.vector_legality import analyze_vector_legality  # noqa: E402
from tools.s3_source_identity import canonical_source_sha256  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("-O", choices=("0", "1"), default="1")
    parser.add_argument("--source-syntax", choices=("0.5", "0.6"), default="0.6")
    parser.add_argument("-o", "--output", type=Path)
    args = parser.parse_args()

    source_bytes = args.source.read_bytes()
    compilation = compile_source(
        source_bytes.decode("utf-8"),
        OptimizationLevel.parse(args.O),
        mode=SyntaxMode.V0_5 if args.source_syntax == "0.5" else SyntaxMode.V0_6,
    )
    ir, _assembly = compilation.require_ordinary_artifacts()
    functions = [analyze_vector_legality(function) for function in ir.functions]
    try:
        source_path = str(args.source.resolve().relative_to(ROOT))
    except ValueError:
        source_path = str(args.source.resolve())
    report = {
        "schema_version": "1.0.0",
        "report_kind": "S3_VECTOR_LEGALITY_RESEARCH",
        "provenance": {
            "source_sha256": canonical_source_sha256(source_bytes),
            "analysis_implementation_sha256": sha256(
                (ROOT / "bootstrap/s3/vector_legality.py").read_bytes()
            ).hexdigest(),
            "report_tool_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
            "git_head": subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
                capture_output=True, text=True,
            ).stdout.strip(),
            "git_worktree_dirty": bool(subprocess.run(
                ["git", "status", "--porcelain"], cwd=ROOT, check=True,
                capture_output=True, text=True,
            ).stdout.strip()),
            "optimization": args.O,
            "source_syntax": args.source_syntax,
            "source_path": source_path,
        },
        "summary": {
            "functions": len(functions),
            "loops_seen": sum(item["summary"]["loops_seen"] for item in functions),
            "vectorizable_loops": sum(item["summary"]["vectorizable_loops"] for item in functions),
            "not_vectorizable_loops": sum(item["summary"]["not_vectorizable_loops"] for item in functions),
            "unknown_loops": sum(item["summary"]["unknown_loops"] for item in functions),
            "transformation_authorized": False,
        },
        "functions": functions,
    }
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        sys.stdout.write(rendered)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
