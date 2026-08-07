from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from s3_program_check import (
    get_hosted_display,
    get_program_inventory_display,
)

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
            get_program_inventory_display(),
            get_hosted_display(),
        ),
    ),
    ReadinessStep(
        "candidate",
        ("tools/compare_assembly_renderer.py", "--candidate"),
        0,
        stdout_contains=(
            "status: ready",
            "directive id range: 0..5",
            "opcode id range: 0..6",
        ),
    ),
    ReadinessStep(
        "candidate symbols",
        ("tools/compare_assembly_renderer.py", "--candidate-symbols"),
        0,
        stdout_contains=(
            "S3 Assembly renderer candidate symbols",
            "0 .end renderer_directive_end_id",
            "6 TRET renderer_opcode_tret_id",
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
            "actual output status: available",
            "actual=available comparison=passed",
            "status: passed",
            "comparison: passed",
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
            "sha256=31a70bf2e3b61ba920b0ca680702d287f7db9a4caa6ed2241cbfdba998a69316",
            "bytes=377",
            "lines=16",
            "simple_call planned=tests/golden/assembly_renderer_candidate_actual/simple_call.assembly.txt",
            "exists=true",
            "comparison=passed",
            "sha256=a5cd6a06c66b44f328ce3d0c1368b4acf35a980f5d2040b051f903126f02552b",
            "bytes=448",
            "lines=21",
            "sign planned=tests/golden/assembly_renderer_candidate_actual/sign.assembly.txt",
            "exists=true",
            "comparison=passed",
            "sha256=3a6d74bfafbd620372c23e5055376bd8d1269ec0cc3f60c7a412a3dde4e6e44b",
            "bytes=829",
            "lines=32",
            "status: passed",
            "comparison: passed",
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
            "status: passed",
            "comparison: passed",
        ),
    ),
    ReadinessStep(
        "candidate run",
        ("tools/compare_assembly_renderer.py", "--candidate-run"),
        0,
        stdout_contains=(
            "expected status: 1",
            "actual status: 1",
            "status: implemented",
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
            "s3 line content encoding model: passed",
            "program: examples/self_hosting/assembly_renderer_line_encodings.s3",
            "s3 event stream model: passed",
            "program: examples/self_hosting/assembly_renderer_event_stream.s3",
            "s3 event writer model: passed",
            "program: examples/self_hosting/assembly_renderer_event_writer.s3",
            "s3 output buffer model: passed",
            "program: examples/self_hosting/assembly_renderer_output_buffer.s3",
            "s3 renderer pipeline model: passed",
            "program: examples/self_hosting/assembly_renderer_pipeline.s3",
            "s3 text builder model: passed",
            "program: examples/self_hosting/assembly_renderer_text_builder.s3",
            "s3 text fragment model: passed",
            "program: examples/self_hosting/assembly_renderer_text_fragments.s3",
            "s3 fixed mutable tryte buffer: passed",
            "program: examples/self_hosting/fixed_tryte_buffer.s3",
            "renderer implementation: complete",
            "full text rendering: passed",
        ),
    ),
    ReadinessStep(
        "comparison passed",
        ("tools/compare_assembly_renderer.py", "--check"),
        0,
        stdout_contains=(
            "S3 Assembly renderer comparison check: ok",
            "actual outputs: passed",
            "available comparisons: passed",
            "renderer implementation: complete",
            "full text rendering: passed",
            "global check: passed",
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
