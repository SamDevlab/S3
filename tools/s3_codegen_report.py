"""Emit an experimental JSON attribution report for S3 x86-64 code generation."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bootstrap.s3.backends.x86_64 import NativeCodegenPolicy, X8664Backend, generate_native_assembly  # noqa: E402
from bootstrap.s3.backends.x86_64.emitter import X8664Emitter  # noqa: E402
from bootstrap.s3.backends.x86_64.instruction_budget import InstructionBudgetMode  # noqa: E402
from bootstrap.s3.codegen_report import build_codegen_report, compare_codegen_reports  # noqa: E402
from bootstrap.s3.codegen_optimization import analyze_redundant_noop_moves  # noqa: E402
from bootstrap.s3.lexer import SyntaxMode  # noqa: E402
from bootstrap.s3.optimizer import OptimizationLevel  # noqa: E402
from bootstrap.s3.pipeline import compile_source  # noqa: E402


def _make_report(
    source_path: Path,
    *,
    optimization: OptimizationLevel,
    mode: SyntaxMode,
    max_frames: int,
    max_instructions: int,
) -> dict[str, object]:
    source_bytes = source_path.read_bytes()
    source = source_bytes.decode("utf-8")
    compilation = compile_source(source, optimization, mode=mode)
    _ir, program = compilation.require_ordinary_artifacts()
    native_text = generate_native_assembly(
        program,
        max_frames=max_frames,
        max_instructions=max_instructions,
        native_policy=NativeCodegenPolicy.BASELINE,
    )
    mapped_text, native_origins = X8664Emitter(
        program,
        max_frames=max_frames,
        max_instructions=max_instructions,
        register_allocation=True,
        instruction_budget_mode=InstructionBudgetMode.PER_INSTRUCTION,
    ).emit_with_origins()
    if mapped_text != native_text:
        raise RuntimeError("origin collection changed generated native assembly")
    report = build_codegen_report(
        program,
        native_text,
        native_origins=native_origins,
        source_sha256=sha256(source_bytes).hexdigest(),
        optimization=optimization.value,
        max_frames=max_frames,
        max_instructions=max_instructions,
    )
    explanation = X8664Backend(
        max_frames=max_frames,
        max_instructions=max_instructions,
        register_allocation=True,
        native_policy=NativeCodegenPolicy.COMPACT_EA,
        instruction_budget_mode=InstructionBudgetMode.PER_INSTRUCTION,
    ).explain_native_policy(program)
    _unchanged_program, noop_moves = analyze_redundant_noop_moves(program)
    report["optimization_explain"] = {
        "emitted_policy": "baseline",
        "diagnostic_policy_requested": NativeCodegenPolicy.COMPACT_EA.value,
        "diagnostic_only": True,
        "compact_ea": explanation.to_dict(),
        "redundant_noop_moves": {
            "analysis_only": True,
            "assembly_rewritten": False,
            "input_instruction_count": noop_moves.input_instruction_count,
            "output_instruction_count": noop_moves.output_instruction_count,
            "candidate_noop_moves": noop_moves.candidate_noop_moves,
        },
    }
    try:
        report["input"]["git_head"] = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        report["input"]["git_worktree_dirty"] = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
    except (OSError, subprocess.CalledProcessError):
        report["input"]["git_head"] = "UNAVAILABLE"
        report["input"]["git_worktree_dirty"] = None
    report["input"]["tool_sha256"] = sha256(Path(__file__).read_bytes()).hexdigest()
    report["input"]["emitter_implementation_sha256"] = sha256(
        (ROOT / "bootstrap/s3/backends/x86_64/emitter.py").read_bytes()
    ).hexdigest()
    report["input"]["backend_implementation_sha256"] = sha256(
        (ROOT / "bootstrap/s3/backends/x86_64/backend.py").read_bytes()
    ).hexdigest()
    report["input"]["report_implementation_sha256"] = sha256(
        (ROOT / "bootstrap/s3/codegen_report.py").read_bytes()
    ).hexdigest()
    try:
        report["input"]["source_path"] = str(source_path.resolve().relative_to(ROOT))
    except ValueError:
        report["input"]["source_path"] = str(source_path.resolve())
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="S3 source file to compile and inspect")
    parser.add_argument("--baseline", type=Path, help="optional control S3 source for structural comparison")
    parser.add_argument("-O", choices=("0", "1"), default="1")
    parser.add_argument("--source-syntax", choices=("0.5", "0.6"), default="0.6")
    parser.add_argument("--max-frames", type=int, default=64)
    parser.add_argument("--max-instructions", type=int, default=1_000_000)
    parser.add_argument("-o", "--output", type=Path)
    args = parser.parse_args()
    if args.max_frames < 1 or args.max_instructions < 1:
        parser.error("resource limits must be positive")

    optimization = OptimizationLevel.parse(args.O)
    mode = SyntaxMode.V0_5 if args.source_syntax == "0.5" else SyntaxMode.V0_6
    report = _make_report(
        args.source,
        optimization=optimization,
        mode=mode,
        max_frames=args.max_frames,
        max_instructions=args.max_instructions,
    )
    if args.baseline is not None:
        control = _make_report(
            args.baseline,
            optimization=optimization,
            mode=mode,
            max_frames=args.max_frames,
            max_instructions=args.max_instructions,
        )
        report["comparison"] = compare_codegen_reports(control, report)
    rendered = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if args.output is None:
        sys.stdout.write(rendered)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
