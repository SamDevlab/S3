"""Qualify the packed-parameter phase of Stage1 codegen IR v2 on Linux x86-64.

Prerequisite: a valid native compaction-capacity report. This qualifier never
mutates the canonical compiler. It rebuilds the exact compaction candidate from
the canonical baseline, applies the packed-parameter transform in memory, runs
static bounded preflight, builds a real Stage1 via Stage0, and requires the
candidate self-source to pass the new verifier and reach the existing expected
fail-closed general-emitter boundary.
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
from tools.patch_stage1_codegen_ir_v2_parameters import transform_parameters
from tools.preflight_stage1_codegen_ir_v2_parameters import build_preflight
from tools.promote_stage1_codegen_ir_v2_capacity import (
    DEFAULT_REPORT as DEFAULT_CAPACITY_REPORT,
    SOURCE,
    _load_json,
    validate_native_report,
)
from tools.qualify_stage1_codegen_ir_v2_capacity import (
    _expected_trivial_assembly,
    _parse_audit,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = (
    ROOT
    / "reports"
    / "selfhost"
    / "stage1"
    / "codegen-ir-v2-parameters-native-candidate.json"
)

EVENT_CAPACITY = 1460
VALUE_CAPACITY = 1460
BLOCK_CAPACITY = 365
PARAMETER_CAPACITY = 64
CALL_CAPACITY = 730


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _run_stage1(executable: Path, source: bytes) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [str(executable)],
        input=source,
        capture_output=True,
        check=False,
        shell=False,
    )


def qualify(*, capacity_report_path: Path, report_path: Path) -> dict[str, object]:
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        raise RuntimeError("parameter IR-v2 qualification requires Linux x86-64")
    compiler = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    if compiler is None:
        raise RuntimeError("parameter IR-v2 qualification requires cc, gcc, or clang")

    canonical_bytes = SOURCE.read_bytes()
    capacity_report = _load_json(capacity_report_path.resolve())
    compacted_bytes, compacted_audit = validate_native_report(
        capacity_report,
        canonical_bytes=canonical_bytes,
    )

    preflight = build_preflight(canonical_bytes.decode("utf-8"))
    if preflight.get("preflight_pass") is not True:
        raise RuntimeError("parameter IR-v2 static bounded preflight failed")

    parameter_text = transform_parameters(compacted_bytes.decode("utf-8"))
    parameter_bytes = parameter_text.encode("utf-8")

    with tempfile.TemporaryDirectory(prefix="s3-ir-v2-parameters-") as temporary:
        temp = Path(temporary)
        source_path = temp / "s3c_stage1.ir-v2-parameters.s3"
        executable = temp / "s3c-stage1-ir-v2-parameters"
        assembly = temp / "s3c-stage1-ir-v2-parameters.s"
        source_path.write_bytes(parameter_bytes)

        build_stage1(executable, source=source_path, assembly_output=assembly)

        trivial = _run_stage1(executable, b"fn main() -> tryte:\n    return 7\n")
        trivial_pass = (
            trivial.returncode == 0
            and trivial.stderr == b""
            and trivial.stdout == _expected_trivial_assembly(7)
        )

        self_run = _run_stage1(executable, parameter_bytes)
        audit, stderr_lines = _parse_audit(self_run.stderr)
        marker = stderr_lines[-1] if stderr_lines else None
        self_boundary_pass = bool(
            self_run.returncode == 2
            and self_run.stdout == b""
            and audit is not None
            and marker == "S3_STAGE1_EMITTER_BLOCKED"
        )

        capacity_guards = {
            "event_count_below_capacity": bool(
                audit is not None
                and isinstance(audit.get("ir_instruction_count"), int)
                and 0 < audit["ir_instruction_count"] < EVENT_CAPACITY
            ),
            "value_count_below_capacity": bool(
                audit is not None
                and isinstance(audit.get("ir_value_count"), int)
                and 0 < audit["ir_value_count"] < VALUE_CAPACITY
            ),
            "block_count_below_capacity": bool(
                audit is not None
                and isinstance(audit.get("ir_block_count"), int)
                and 0 < audit["ir_block_count"] < BLOCK_CAPACITY
            ),
            "parameter_count_exact": bool(
                audit is not None and audit.get("parameter_count") == PARAMETER_CAPACITY
            ),
            "call_count_below_capacity": bool(
                audit is not None
                and isinstance(audit.get("ast_call_count"), int)
                and 0 < audit["ast_call_count"] < CALL_CAPACITY
            ),
        }
        capacity_guards_pass = all(capacity_guards.values())
        native_pass = bool(trivial_pass and self_boundary_pass and capacity_guards_pass)

        result = {
            "schema": "s3.selfhost.codegen-ir-v2-parameters-native-candidate.v1",
            "platform": {
                "system": platform.system(),
                "machine": platform.machine(),
                "compiler": compiler,
            },
            "canonical_source_mutated": False,
            "prerequisite_capacity_report": {
                "path": str(capacity_report_path.resolve()),
                "status": "PASS_VALIDATED",
                "compacted_source_sha256": _sha256(compacted_bytes),
                "native_audit": compacted_audit,
            },
            "static_preflight": preflight,
            "candidate": {
                "transform_chain": [
                    "DROP_REDUNDANT_DISCARD_KEYWORD_EVENT",
                    "ADD_PACKED_PARAMETER_IR_V2",
                ],
                "source_sha256": _sha256(parameter_bytes),
                "source_bytes": len(parameter_bytes),
                "stage1_executable_sha256": _sha256(executable.read_bytes()),
                "stage1_executable_bytes": executable.stat().st_size,
                "stage1_assembly_sha256": _sha256(assembly.read_bytes()),
                "stage1_assembly_bytes": assembly.stat().st_size,
                "parameter_storage": "one packed i64[64] lane",
                "parameter_value_id_reservation": "0..parameter_count-1",
            },
            "trivial_compile": {
                "status": "PASS" if trivial_pass else "FAIL",
                "returncode": trivial.returncode,
                "stdout_sha256": _sha256(trivial.stdout),
                "stderr": trivial.stderr.decode("ascii", errors="replace"),
            },
            "self_source": {
                "status": (
                    "PASS_PARAMETER_VERIFIER_TO_EXPECTED_EMITTER_BOUNDARY"
                    if self_boundary_pass
                    else "FAIL_OR_DIFFERENT_BLOCKER"
                ),
                "returncode": self_run.returncode,
                "stdout_bytes": len(self_run.stdout),
                "stderr_lines": stderr_lines,
                "audit": audit,
                "final_marker": marker,
            },
            "capacity_guards": capacity_guards,
            "qualification": {
                "static_preflight": "PASS",
                "prerequisite_capacity_report": "PASS_VALIDATED",
                "candidate_build": "PASS",
                "trivial_compile": "PASS" if trivial_pass else "FAIL",
                "parameter_verifier_to_emitter_boundary": (
                    "PASS" if self_boundary_pass else "FAIL"
                ),
                "capacity_guards": "PASS" if capacity_guards_pass else "FAIL",
                "parameter_ir_v2_candidate": (
                    "PASS_NATIVE_CANDIDATE" if native_pass else "FAIL"
                ),
                "canonical_commit_allowed": False,
                "canonical_commit_reason": (
                    "This phase is candidate-only until the compaction checkpoint is reviewed/promoted and the parameter report is separately reviewed."
                ),
                "local_ir_v2": "NOT_STARTED",
                "unified_value_def_use": "NOT_STARTED",
                "general_emitter": "BLOCKED_IR_V2_INCOMPLETE",
                "self_emit": "NOT_STARTED",
                "stage2": "NOT_STARTED",
                "stage3": "NOT_STARTED",
                "full_self_hosting": False,
            },
        }

    destination = report_path.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capacity-report", type=Path, default=DEFAULT_CAPACITY_REPORT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)

    result = qualify(
        capacity_report_path=args.capacity_report,
        report_path=args.report,
    )
    qualification = result["qualification"]
    print(f"REPORT={args.report.resolve()}")
    print(f"PARAMETER_IR_V2_CANDIDATE={qualification['parameter_ir_v2_candidate']}")
    print(f"CANONICAL_COMMIT_ALLOWED={qualification['canonical_commit_allowed']}")
    print(f"GENERAL_EMITTER={qualification['general_emitter']}")
    audit = result["self_source"]["audit"]
    if audit is not None:
        print(f"IR_INSTRUCTION_COUNT={audit['ir_instruction_count']}")
        print(f"IR_VALUE_COUNT={audit['ir_value_count']}")
        print(f"IR_BLOCK_COUNT={audit['ir_block_count']}")
        print(f"PARAMETER_COUNT={audit['parameter_count']}")
        print(f"LOCAL_COUNT={audit['local_count']}")
        print(f"CALL_COUNT={audit['ast_call_count']}")
    return 0 if qualification["parameter_ir_v2_candidate"] == "PASS_NATIVE_CANDIDATE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
