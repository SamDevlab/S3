"""Qualify the compaction-first Stage1 IR-v2 capacity candidate on Linux x86-64.

This is transactional with respect to the canonical source: it transforms the
qualified baseline in memory, writes the candidate only to a temporary/build
directory, builds a real Stage1 through the existing Stage0 boundary, executes
that Stage1 on both a trivial program and the candidate self-source, and writes
an evidence JSON report. It never rewrites s3c_stage1.s3 or its manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path

from tools.build_stage1_compiler import build_stage1
from tools.patch_stage1_codegen_ir_v2_capacity import (
    BASELINE_SOURCE_SHA256,
    transform,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "selfhost" / "compiler" / "s3c_stage1.s3"
DEFAULT_REPORT = (
    ROOT
    / "reports"
    / "selfhost"
    / "stage1"
    / "codegen-ir-v2-capacity-native-candidate.json"
)

AUDIT_FIELDS = (
    "function_count",
    "foreign_count",
    "parameter_count",
    "local_count",
    "ast_assignment_count",
    "ast_call_count",
    "ast_return_count",
    "ast_match_count",
    "ast_while_count",
    "ast_break_count",
    "ast_binop_count",
    "ast_comparison_count",
    "ast_cast_count",
    "ast_discard_count",
    "local_function_count",
    "ir_foreign_function_count",
    "ir_parameter_count",
    "ir_local_count",
    "ir_block_count",
    "ir_instruction_count",
    "ir_value_count",
    "ir_internal_call_count",
    "ir_foreign_call_count",
    "ir_branch_count",
    "ir_loop_count",
    "ir_return_count",
)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _run_stage1(executable: Path, source: bytes) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [str(executable)],
        input=source,
        capture_output=True,
        check=False,
        shell=False,
    )


def _parse_audit(stderr: bytes) -> tuple[dict[str, int] | None, list[str]]:
    lines = stderr.splitlines()
    text_lines = [line.decode("ascii", errors="replace") for line in lines]
    for line in lines:
        if not line.startswith(b"S3_STAGE1_AUDIT "):
            continue
        raw = line.split()[1:]
        if len(raw) != len(AUDIT_FIELDS):
            return None, text_lines
        try:
            values = [int(value) for value in raw]
        except ValueError:
            return None, text_lines
        return dict(zip(AUDIT_FIELDS, values, strict=True)), text_lines
    return None, text_lines


def _expected_trivial_assembly(value: int) -> bytes:
    return (
        ".intel_syntax noprefix\n"
        ".section .text\n"
        ".globl _start\n"
        ".type _start, @function\n"
        "_start:\n"
        "    mov eax, 60\n"
        f"    mov edi, {value}\n"
        "    syscall\n"
        "    ud2\n"
        ".size _start, .-_start\n"
        ".section .note.GNU-Stack,\"\",@progbits\n"
    ).encode("ascii")


def _run_contract_tests() -> dict[str, object]:
    completed = subprocess.run(
        [
            shutil.which("python3") or "python3",
            "-m",
            "pytest",
            "-q",
            "tests/test_stage1_codegen_ir_contract.py",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
        shell=False,
    )
    return {
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "status": "PASS" if completed.returncode == 0 else "FAIL",
    }


def qualify(*, report_path: Path, run_contract_tests: bool) -> dict[str, object]:
    if platform.system() != "Linux" or platform.machine().lower() not in {
        "x86_64",
        "amd64",
    }:
        raise RuntimeError("native capacity qualification requires Linux x86-64")

    compiler = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    if compiler is None:
        raise RuntimeError("native capacity qualification requires cc, gcc, or clang")

    baseline_bytes = SOURCE.read_bytes()
    baseline_sha = _sha256_bytes(baseline_bytes)
    if baseline_sha != BASELINE_SOURCE_SHA256:
        raise RuntimeError(
            "canonical source is not the qualified pre-IR-v2 baseline: "
            f"expected {BASELINE_SOURCE_SHA256}, got {baseline_sha}"
        )

    contract_tests = (
        _run_contract_tests()
        if run_contract_tests
        else {"status": "SKIPPED_BY_OPERATOR"}
    )
    if run_contract_tests and contract_tests["status"] != "PASS":
        raise RuntimeError("IR-v2 contract tests failed before candidate build")

    baseline_text = baseline_bytes.decode("utf-8")
    candidate_text = transform(baseline_text)
    candidate_bytes = candidate_text.encode("utf-8")

    with tempfile.TemporaryDirectory(prefix="s3-ir-v2-capacity-") as temporary:
        temp = Path(temporary)
        candidate_source = temp / "s3c_stage1.ir-v2-capacity.s3"
        executable = temp / "s3c-stage1-ir-v2-capacity"
        assembly = temp / "s3c-stage1-ir-v2-capacity.s"
        candidate_source.write_bytes(candidate_bytes)

        build_stage1(
            executable,
            source=candidate_source,
            assembly_output=assembly,
        )

        executable_bytes = executable.read_bytes()
        assembly_bytes = assembly.read_bytes()

        trivial_source = b"fn main() -> tryte:\n    return 7\n"
        trivial = _run_stage1(executable, trivial_source)
        trivial_pass = (
            trivial.returncode == 0
            and trivial.stderr == b""
            and trivial.stdout == _expected_trivial_assembly(7)
        )

        self_run = _run_stage1(executable, candidate_bytes)
        audit, stderr_lines = _parse_audit(self_run.stderr)
        marker = stderr_lines[-1] if stderr_lines else None
        self_boundary_pass = (
            self_run.returncode == 2
            and self_run.stdout == b""
            and audit is not None
            and marker == "S3_STAGE1_EMITTER_BLOCKED"
        )

        baseline_events = 1460
        baseline_discards = 699
        actual_events = audit.get("ir_instruction_count") if audit else None
        actual_discards = audit.get("ast_discard_count") if audit else None
        actual_event_reduction = (
            baseline_events - actual_events if actual_events is not None else None
        )

        result = {
            "schema": "s3.selfhost.codegen-ir-v2-capacity-native-candidate.v1",
            "platform": {
                "system": platform.system(),
                "machine": platform.machine(),
                "compiler": compiler,
            },
            "canonical_source_mutated": False,
            "baseline": {
                "source_sha256": baseline_sha,
                "source_bytes": len(baseline_bytes),
                "native_events": baseline_events,
                "native_discard_events": baseline_discards,
                "event_capacity": 1460,
                "parameter_capacity": 64,
                "call_capacity": 730,
                "call_argument_capacity": 746,
            },
            "candidate": {
                "transform": "DROP_REDUNDANT_DISCARD_KEYWORD_EVENT",
                "source_sha256": _sha256_bytes(candidate_bytes),
                "source_bytes": len(candidate_bytes),
                "stage1_executable_sha256": _sha256_bytes(executable_bytes),
                "stage1_executable_bytes": len(executable_bytes),
                "stage1_assembly_sha256": _sha256_bytes(assembly_bytes),
                "stage1_assembly_bytes": len(assembly_bytes),
            },
            "contract_tests": contract_tests,
            "trivial_compile": {
                "status": "PASS" if trivial_pass else "FAIL",
                "returncode": trivial.returncode,
                "stdout_sha256": _sha256_bytes(trivial.stdout),
                "stderr": trivial.stderr.decode("ascii", errors="replace"),
            },
            "self_source": {
                "status": "PASS_THROUGH_VERIFY_TO_EXPECTED_EMITTER_BOUNDARY"
                if self_boundary_pass
                else "FAIL_OR_DIFFERENT_BLOCKER",
                "returncode": self_run.returncode,
                "stdout_bytes": len(self_run.stdout),
                "stderr_lines": stderr_lines,
                "audit": audit,
                "final_marker": marker,
            },
            "capacity_measurement": {
                "actual_ir_instruction_count": actual_events,
                "actual_ast_discard_count": actual_discards,
                "actual_event_reduction_from_native_baseline": actual_event_reduction,
                "actual_event_headroom": (
                    1460 - actual_events if actual_events is not None else None
                ),
                "projection_was_761_events": True,
                "projection_is_not_substituted_for_native_measurement": True,
            },
            "qualification": {
                "candidate_build": "PASS",
                "trivial_compile": "PASS" if trivial_pass else "FAIL",
                "self_source_expected_boundary": (
                    "PASS" if self_boundary_pass else "FAIL"
                ),
                "capacity_candidate": (
                    "PASS_NATIVE_CANDIDATE"
                    if trivial_pass and self_boundary_pass and actual_events is not None
                    and actual_events < 1460
                    else "FAIL"
                ),
                "canonical_commit_allowed": bool(
                    trivial_pass
                    and self_boundary_pass
                    and actual_events is not None
                    and actual_events < 1460
                ),
                "self_emit": "NOT_ATTEMPTED_GENERAL_EMITTER_STILL_BLOCKED",
                "stage2": "NOT_STARTED",
                "stage3": "NOT_STARTED",
                "full_self_hosting": False,
            },
        }

    report_path = report_path.resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--skip-contract-tests", action="store_true")
    args = parser.parse_args(argv)

    result = qualify(
        report_path=args.report,
        run_contract_tests=not args.skip_contract_tests,
    )
    qualification = result["qualification"]
    print(f"REPORT={args.report.resolve()}")
    print(f"CAPACITY_CANDIDATE={qualification['capacity_candidate']}")
    print(f"CANONICAL_COMMIT_ALLOWED={qualification['canonical_commit_allowed']}")
    audit = result["self_source"]["audit"]
    if audit is not None:
        print(f"ACTUAL_IR_INSTRUCTION_COUNT={audit['ir_instruction_count']}")
        print(f"ACTUAL_AST_DISCARD_COUNT={audit['ast_discard_count']}")
        print(f"ACTUAL_PARAMETER_COUNT={audit['parameter_count']}")
        print(f"ACTUAL_CALL_COUNT={audit['ast_call_count']}")
    return 0 if qualification["canonical_commit_allowed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
