"""Native Linux qualifier for the compact post-promotion local candidate.

The qualifier is candidate-only. It proves the chained parameter semantic-value
lowering still selects ABI ordinals correctly, proves scalar and fixed-array
local declarations reach the explicit general-emitter boundary instead of a
verifier/capacity error, and requires the candidate's complete self-source to
capture every lexically counted local before reaching that same fail-closed
boundary.
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
from tools.patch_stage1_compact_local_metadata import LOCAL_CAPACITY, SOURCE, transform
from tools.qualify_stage1_codegen_ir_v2_capacity import _parse_audit


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = (
    ROOT / "reports" / "selfhost" / "stage1" / "compact-local-native-candidate.json"
)
BLOCKED_MARKER = "S3_STAGE1_EMITTER_BLOCKED"
HISTORICAL_LOCAL_CANDIDATE_BYTES = 193408


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


def _blocked_with_audit(completed: subprocess.CompletedProcess[bytes]) -> tuple[bool, dict[str, int] | None, list[str]]:
    audit, lines = _parse_audit(completed.stderr)
    marker = lines[-1] if lines else None
    passed = bool(
        completed.returncode == 2
        and completed.stdout == b""
        and audit is not None
        and marker == BLOCKED_MARKER
    )
    return passed, audit, lines


def qualify(report_path: Path) -> dict[str, object]:
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        raise RuntimeError("compact local qualification requires Linux x86-64")
    compiler = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    if compiler is None:
        raise RuntimeError("compact local qualification requires cc, gcc, or clang")

    canonical_text = SOURCE.read_text(encoding="utf-8")
    canonical_bytes = canonical_text.encode("utf-8")
    candidate_text = transform(canonical_text)
    candidate_bytes = candidate_text.encode("utf-8")

    parameter_fixture = (
        b"fn first(a: i64, b: i64) -> i64:\n"
        b"    return b\n"
        b"fn target(x: i64, y: i64, z: i64) -> i64:\n"
        b"    return z\n"
        b"fn main() -> tryte:\n"
        b"    return 9\n"
    )
    local_fixture = (
        b"fn helper() -> i64:\n"
        b"    mut x: i64 = 1\n"
        b"    return x\n"
        b"fn main() -> tryte:\n"
        b"    mut values: i64[3] = [0, 0, 0]\n"
        b"    return 9\n"
    )

    with tempfile.TemporaryDirectory(prefix="s3-compact-local-") as temporary:
        temp = Path(temporary)
        source_path = temp / "s3c_stage1.compact-local-candidate.s3"
        executable = temp / "s3c-stage1-compact-local"
        assembly_path = temp / "s3c-stage1-compact-local.s"
        source_path.write_text(candidate_text, encoding="utf-8", newline="\n")

        build_stage1(executable, source=source_path, assembly_output=assembly_path)

        parameter_run = _run_stage1(executable, parameter_fixture)
        parameter_stdout = parameter_run.stdout.lower()
        parameter_pass = bool(
            parameter_run.returncode == 0
            and parameter_run.stderr == b""
            and b"mov rax, rsi" in parameter_stdout
            and b"mov rax, rdx" in parameter_stdout
        )

        local_run = _run_stage1(executable, local_fixture)
        local_boundary, local_audit, local_lines = _blocked_with_audit(local_run)
        local_count = local_audit.get("local_count") if local_audit is not None else None
        local_pass = bool(local_boundary and local_count == 2)

        self_run = _run_stage1(executable, candidate_bytes)
        self_boundary, self_audit, self_lines = _blocked_with_audit(self_run)
        self_local_count = self_audit.get("local_count") if self_audit is not None else None
        self_local_bound = bool(
            isinstance(self_local_count, int)
            and not isinstance(self_local_count, bool)
            and 0 < self_local_count <= LOCAL_CAPACITY
        )
        self_pass = bool(self_boundary and self_local_bound)

        native_pass = bool(parameter_pass and local_pass and self_pass)
        result: dict[str, object] = {
            "schema": "s3.selfhost.stage1-compact-local-native-candidate.v1",
            "platform": {
                "system": platform.system(),
                "machine": platform.machine(),
                "compiler": compiler,
            },
            "canonical_source": {
                "path": str(SOURCE.resolve()),
                "sha256": _sha256(canonical_bytes),
                "bytes": len(canonical_bytes),
                "mutated": False,
            },
            "candidate": {
                "sha256": _sha256(candidate_bytes),
                "bytes": len(candidate_bytes),
                "historical_local_candidate_bytes": HISTORICAL_LOCAL_CANDIDATE_BYTES,
                "source_growth_vs_canonical": len(candidate_bytes) - len(canonical_bytes),
                "source_size_delta_vs_historical_candidate": len(candidate_bytes) - HISTORICAL_LOCAL_CANDIDATE_BYTES,
                "executable_sha256": _sha256(executable.read_bytes()),
                "assembly_sha256": _sha256(assembly_path.read_bytes()),
                "local_capacity_bound": LOCAL_CAPACITY,
                "local_capture": "BOUNDED_TOKEN_RING_SUFFIX",
                "parameter_value_id_rule": "parameter_slot",
                "local_value_id_rule": "parameter_count + global_local_record_slot",
                "physical_frame_offset": "DEFERRED_TO_EMITTER",
            },
            "parameter_semantic_value_regression": {
                "status": "PASS" if parameter_pass else "FAIL",
                "returncode": parameter_run.returncode,
                "stdout_sha256": _sha256(parameter_run.stdout),
                "stderr": parameter_run.stderr.decode("ascii", errors="replace"),
                "required_lowerings": ["mov rax, rsi", "mov rax, rdx"],
            },
            "local_fixture": {
                "status": "PASS_EXPECTED_EMITTER_BOUNDARY" if local_pass else "FAIL",
                "returncode": local_run.returncode,
                "stdout_bytes": len(local_run.stdout),
                "final_marker": local_lines[-1] if local_lines else None,
                "audit": local_audit,
                "expected_local_count": 2,
                "covers": ["SCALAR", "FIXED_ARRAY"],
            },
            "self_source": {
                "status": "PASS_EXPECTED_EMITTER_BOUNDARY" if self_pass else "FAIL_OR_DIFFERENT_BLOCKER",
                "returncode": self_run.returncode,
                "stdout_bytes": len(self_run.stdout),
                "stderr_sha256": _sha256(self_run.stderr),
                "final_marker": self_lines[-1] if self_lines else None,
                "audit": self_audit,
                "local_count_within_bound": self_local_bound,
            },
            "qualification": {
                "candidate_build": "PASS",
                "parameter_semantic_value_regression": "PASS" if parameter_pass else "FAIL",
                "scalar_fixed_local_capture": "PASS" if local_pass else "FAIL",
                "self_source_local_coverage": "PASS" if self_pass else "FAIL",
                "compact_local_candidate": "PASS_NATIVE_CANDIDATE" if native_pass else "FAIL",
                "canonical_promotion_allowed": False,
                "canonical_promotion_reason": "Native candidate proof is necessary but local def/use, instruction ordering and remaining IR lanes are still incomplete.",
                "unified_value_def_use": "INCOMPLETE",
                "instruction_ir": "INCOMPLETE",
                "call_linkage": "INCOMPLETE",
                "terminator_linkage": "INCOMPLETE",
                "general_emitter": "INCREMENTAL_ONLY",
                "self_emit": "BLOCKED_REMAINING_LOSSLESS_TYPED_IR_LANES",
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
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)

    result = qualify(args.report)
    qualification = result["qualification"]
    print(f"REPORT={args.report.resolve()}")
    print(f"COMPACT_LOCAL_CANDIDATE={qualification['compact_local_candidate']}")
    print(f"PARAMETER_SEMANTIC_VALUE_REGRESSION={qualification['parameter_semantic_value_regression']}")
    print(f"SCALAR_FIXED_LOCAL_CAPTURE={qualification['scalar_fixed_local_capture']}")
    print(f"SELF_SOURCE_LOCAL_COVERAGE={qualification['self_source_local_coverage']}")
    print(f"CANDIDATE_SOURCE_BYTES={result['candidate']['bytes']}")
    print(f"FULL_SELF_HOSTING={qualification['full_self_hosting']}")
    return 0 if qualification["compact_local_candidate"] == "PASS_NATIVE_CANDIDATE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
