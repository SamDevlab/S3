from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True, slots=True)
class ReadinessStep:
    label: str
    args: tuple[str, ...]
    expected_returncode: int
    stdout_contains: tuple[str, ...] = ()
    output_contains: tuple[str, ...] = ()


READINESS_STEPS = (
    ReadinessStep(
        "manifest",
        ("tools/check_assembly_renderer_candidate_manifest.py",),
        0,
        stdout_contains=("assembly renderer candidate manifest: ok",),
    ),
    ReadinessStep(
        "symbols",
        ("tools/check_assembly_renderer_candidate_symbols.py",),
        0,
        stdout_contains=("assembly renderer candidate symbols: ok",),
    ),
    ReadinessStep(
        "fixtures",
        ("tools/check_assembly_renderer_candidate_fixtures.py",),
        0,
        stdout_contains=("assembly renderer candidate fixtures: ok",),
    ),
    ReadinessStep(
        "fixture expectations",
        ("tools/check_assembly_renderer_candidate_fixture_expectations.py",),
        0,
        stdout_contains=(
            "assembly renderer candidate fixture expectations: ok",
        ),
    ),
    ReadinessStep(
        "comparison plan",
        ("tools/check_assembly_renderer_candidate_comparison_plan.py",),
        0,
        stdout_contains=("assembly renderer candidate comparison plan: ok",),
    ),
    ReadinessStep(
        "actual outputs",
        ("tools/check_assembly_renderer_candidate_actual_outputs.py",),
        0,
        stdout_contains=("assembly renderer candidate actual outputs: ok",),
    ),
    ReadinessStep(
        "program check",
        ("tools/s3_program_check.py", "check"),
        0,
        stdout_contains=(
            "s3 program check: checked 9 program(s)",
            "s3 program check: hosted execution checked 6 program(s)",
        ),
    ),
    ReadinessStep(
        "candidate",
        ("tools/compare_assembly_renderer.py", "--candidate"),
        0,
        stdout_contains=(
            "status: stub",
            "directive id range: 0..5",
            "opcode id range: 0..7",
        ),
    ),
    ReadinessStep(
        "candidate symbols",
        ("tools/compare_assembly_renderer.py", "--candidate-symbols"),
        0,
        stdout_contains=(
            "S3 Assembly renderer candidate symbols",
            "0 .end renderer_directive_end_id",
            "7 TRET renderer_opcode_tret_id",
        ),
    ),
    ReadinessStep(
        "candidate fixtures",
        ("tools/compare_assembly_renderer.py", "--candidate-fixtures"),
        0,
        stdout_contains=(
            "S3 Assembly renderer candidate fixtures",
            "first examples/first.s3",
            "simple_call examples/simple_call.s3",
            "sign examples/sign.s3",
            "status: reference_only",
            "comparison: blocked",
        ),
    ),
    ReadinessStep(
        "candidate fixture expectations",
        ("tools/compare_assembly_renderer.py", "--candidate-fixture-expectations"),
        0,
        stdout_contains=(
            "S3 Assembly renderer candidate fixture expectations",
            "first tests/golden/inspect/first.assembly.txt",
            "simple_call tests/golden/inspect/simple_call.assembly.txt",
            "sign tests/golden/inspect/sign.assembly.txt",
            "status: reference_only",
            "comparison: blocked",
        ),
    ),
    ReadinessStep(
        "candidate comparison plan",
        ("tools/compare_assembly_renderer.py", "--candidate-comparison-plan"),
        0,
        stdout_contains=(
            "S3 Assembly renderer candidate comparison plan",
            "first expected=tests/golden/inspect/first.assembly.txt",
            "simple_call expected=tests/golden/inspect/simple_call.assembly.txt",
            "sign expected=tests/golden/inspect/sign.assembly.txt",
            "actual output status: not_implemented",
            "actual=available comparison=passed",
            "status: blocked",
            "comparison: blocked",
        ),
    ),
    ReadinessStep(
        "candidate actual outputs",
        ("tools/compare_assembly_renderer.py", "--candidate-actual-outputs"),
        0,
        stdout_contains=(
            "S3 Assembly renderer candidate actual outputs",
            "first planned=tests/golden/assembly_renderer_candidate_actual/first.assembly.txt",
            "exists=true",
            "status=available",
            "comparison=passed",
            "sha256=46ebd2aef715d7a7e9f7ada01ca844b8ae23494ff6a5333f78c75db2eaca2f67",
            "bytes=441",
            "lines=18",
            "simple_call planned=tests/golden/assembly_renderer_candidate_actual/simple_call.assembly.txt",
            "exists=true",
            "comparison=passed",
            "sha256=d6de00c8c50618bcc8f3a458267eb8590956a9451980084b1add2f59d3267c0f",
            "bytes=448",
            "lines=21",
            "sign planned=tests/golden/assembly_renderer_candidate_actual/sign.assembly.txt",
            "exists=true",
            "comparison=passed",
            "sha256=c077d2c49639b1a033505ec8c1ba1c60c78242e6e09c43f60a8aa5ed8b49e2d9",
            "bytes=946",
            "lines=36",
            "status: partial",
            "comparison: blocked",
        ),
    ),
    ReadinessStep(
        "candidate available comparisons",
        ("tools/compare_assembly_renderer.py", "--candidate-compare-available"),
        0,
        stdout_contains=(
            "S3 Assembly renderer candidate available comparisons",
            "first expected=tests/golden/inspect/first.assembly.txt",
            "actual=tests/golden/assembly_renderer_candidate_actual/first.assembly.txt",
            "status=passed",
            "simple_call expected=tests/golden/inspect/simple_call.assembly.txt",
            "actual=tests/golden/assembly_renderer_candidate_actual/simple_call.assembly.txt",
            "status=passed",
            "sign expected=tests/golden/inspect/sign.assembly.txt",
            "actual=tests/golden/assembly_renderer_candidate_actual/sign.assembly.txt",
            "status=passed",
            "available comparisons: 3",
            "passed comparisons: 3",
            "pending comparisons: 0",
            "blocked comparisons: 0",
            "status: partial",
            "comparison: partial",
        ),
    ),
    ReadinessStep(
        "candidate run",
        ("tools/compare_assembly_renderer.py", "--candidate-run"),
        0,
        stdout_contains=(
            "expected status: -1",
            "actual status: -1",
            "status: stub",
            "candidate renderer bootstrap: available",
            "s3 bootstrap spike: passed",
            "program: examples/self_hosting/assembly_renderer_bootstrap.s3",
            "expected return: 0",
            "actual return: 0",
            "s3 output model: passed",
            "program: examples/self_hosting/assembly_renderer_output_model.s3",
            "s3 text segment model: passed",
            "program: examples/self_hosting/assembly_renderer_text_segments.s3",
            "s3 line blueprint model: passed",
            "program: examples/self_hosting/assembly_renderer_line_blueprints.s3",
            "s3 line sequence model: passed",
            "program: examples/self_hosting/assembly_renderer_line_sequences.s3",
            "renderer implementation: not_implemented",
            "full text rendering: not_implemented",
        ),
    ),
    ReadinessStep(
        "comparison blocked",
        ("tools/compare_assembly_renderer.py", "--check"),
        1,
        stdout_contains=(
            "S3 Assembly renderer comparison check: blocked",
            "actual outputs: passed",
            "available comparisons: passed",
            "renderer implementation: not_implemented",
            "global check: blocked",
            (
                "reason: actual outputs pass, but the real S3 renderer is still "
                "not implemented"
            ),
        ),
    ),
)


def _run_step(step: ReadinessStep) -> bool:
    completed = subprocess.run(
        [sys.executable, *step.args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != step.expected_returncode:
        print(f"{step.label}: failed")
        print(f"  expected exit code: {step.expected_returncode}")
        print(f"  actual exit code: {completed.returncode}")
        return False

    ok = True
    for needle in step.stdout_contains:
        if needle not in completed.stdout:
            print(f"{step.label}: failed")
            print(f"  missing stdout: {needle}")
            ok = False
    combined_output = f"{completed.stdout}\n{completed.stderr}"
    for needle in step.output_contains:
        if needle not in combined_output:
            print(f"{step.label}: failed")
            print(f"  missing output: {needle}")
            ok = False
    return ok


def check() -> int:
    print("assembly renderer candidate readiness")
    for step in READINESS_STEPS:
        if not _run_step(step):
            return 1
        print(f"{step.label}: ok")

    print("assembly renderer candidate readiness: ok")
    return 0


def main() -> int:
    return check()


if __name__ == "__main__":
    raise SystemExit(main())
