"""Qualify the Stage1 IR-v2 local-metadata candidate on Linux x86-64.

This phase is fully transactional. It consumes a complete PASS native parameter
report, recomputes the exact local static preflight, validates current call and
call-argument pressure against the already-closed native 736-argument oracle,
builds the exact local candidate through Stage0 in a temporary directory, and
requires the real Stage1 candidate to reach the existing fail-closed general
emitter boundary with exact native counts.

It never rewrites/promotes the canonical compiler and never starts Stage2/3.
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
from typing import Any

from tools.audit_stage1_codegen_ir_v2_call_arguments import (
    CLOSURE as CALL_ARGUMENT_CLOSURE,
    _load_closure,
    audit as audit_call_arguments,
)
from tools.build_stage1_compiler import build_stage1
from tools.patch_stage1_codegen_ir_v2_locals import (
    LocalCandidateError,
    SOURCE,
    transform_locals,
    validate_parameter_prerequisite,
)
from tools.preflight_stage1_codegen_ir_v2_locals import (
    DEFAULT_REPORT as DEFAULT_LOCAL_PREFLIGHT_REPORT,
    build_preflight,
)
from tools.qualify_stage1_codegen_ir_v2_capacity import (
    _expected_trivial_assembly,
    _parse_audit,
)
from tools.qualify_stage1_codegen_ir_v2_parameters import (
    DEFAULT_REPORT as DEFAULT_PARAMETER_REPORT,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = (
    ROOT / "reports" / "selfhost" / "stage1" /
    "codegen-ir-v2-locals-native-candidate.json"
)

EVENT_CAPACITY = 1460
VALUE_CAPACITY = 1460
BLOCK_CAPACITY = 365
CALL_CAPACITY = 730
CALL_ARGUMENT_CAPACITY = 746
PARAMETER_CAPACITY = 64

_REQUIRED_PARAMETER_QUALIFICATION = {
    "static_preflight": "PASS",
    "prerequisite_capacity_report": "PASS_VALIDATED",
    "candidate_build": "PASS",
    "trivial_compile": "PASS",
    "parameter_verifier_to_emitter_boundary": "PASS",
    "capacity_guards": "PASS",
    "parameter_ir_v2_candidate": "PASS_NATIVE_CANDIDATE",
}


class LocalNativeQualificationError(RuntimeError):
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise LocalNativeQualificationError(f"cannot read JSON report: {error}") from error
    if not isinstance(value, dict):
        raise LocalNativeQualificationError("report must be a JSON object")
    return value


def validate_parameter_report_strict(
    report: dict[str, Any],
    *,
    canonical_source: str,
) -> tuple[str, dict[str, int], dict[str, Any]]:
    """Validate all parameter subgates, provenance, and expected boundary."""

    try:
        parameter_source, normalized = validate_parameter_prerequisite(
            report,
            canonical_source=canonical_source,
        )
    except LocalCandidateError as error:
        raise LocalNativeQualificationError(str(error)) from error

    platform_info = report.get("platform")
    if not isinstance(platform_info, dict):
        raise LocalNativeQualificationError("parameter report platform evidence is missing")
    if platform_info.get("system") != "Linux" or str(platform_info.get("machine", "")).lower() not in {
        "x86_64",
        "amd64",
    }:
        raise LocalNativeQualificationError("parameter report is not Linux x86-64 evidence")

    qualification = report.get("qualification")
    if not isinstance(qualification, dict):
        raise LocalNativeQualificationError("parameter qualification is missing")
    for key, expected in _REQUIRED_PARAMETER_QUALIFICATION.items():
        if qualification.get(key) != expected:
            raise LocalNativeQualificationError(
                f"parameter subgate {key} must be {expected!r}; got {qualification.get(key)!r}"
            )
    if qualification.get("canonical_commit_allowed") is not False:
        raise LocalNativeQualificationError(
            "parameter candidate report must remain non-promoting at this phase"
        )

    self_source = report.get("self_source")
    if not isinstance(self_source, dict):
        raise LocalNativeQualificationError("parameter self-source evidence is missing")
    if self_source.get("status") != "PASS_PARAMETER_VERIFIER_TO_EXPECTED_EMITTER_BOUNDARY":
        raise LocalNativeQualificationError("parameter self-source did not pass its verifier boundary")
    if self_source.get("returncode") != 2:
        raise LocalNativeQualificationError("parameter self-source expected return code 2")
    if self_source.get("stdout_bytes") != 0:
        raise LocalNativeQualificationError("parameter self-source expected zero stdout bytes")
    if self_source.get("final_marker") != "S3_STAGE1_EMITTER_BLOCKED":
        raise LocalNativeQualificationError("parameter self-source final marker is not emitter blocked")

    audit = self_source.get("audit")
    if not isinstance(audit, dict):
        raise LocalNativeQualificationError("parameter native audit is missing")
    for key, value in audit.items():
        if isinstance(value, bool):
            raise LocalNativeQualificationError(f"parameter audit field {key} cannot be boolean")

    return parameter_source, normalized, audit


def _run_stage1(executable: Path, source: bytes) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [str(executable)],
        input=source,
        capture_output=True,
        check=False,
        shell=False,
    )


def _native_count_guards(
    audit: dict[str, int] | None,
    *,
    parameter_audit: dict[str, Any],
    preflight: dict[str, Any],
) -> dict[str, bool]:
    if audit is None:
        return {
            "audit_present": False,
            "local_count_exact": False,
            "ir_local_count_exact": False,
            "events_exact_projection": False,
            "values_exact_projection": False,
            "blocks_exact_projection": False,
            "calls_exact_projection": False,
            "parameter_count_exact": False,
            "ir_parameter_count_exact": False,
            "function_identity_preserved": False,
            "foreign_function_count_preserved": False,
            "local_function_count_preserved": False,
            "event_capacity": False,
            "value_capacity": False,
            "block_capacity": False,
            "call_capacity": False,
        }

    local_candidate = preflight.get("local_candidate")
    projection_section = preflight.get("native_headroom_projection")
    if not isinstance(local_candidate, dict) or not isinstance(projection_section, dict):
        raise LocalNativeQualificationError("local preflight is missing candidate/projection sections")
    projections = projection_section.get("projected_candidate_counts")
    if not isinstance(projections, dict):
        raise LocalNativeQualificationError("local preflight projected counts are missing")
    required = local_candidate.get("required_records_including_candidate_self_source")
    selected = local_candidate.get("selected_capacity")
    if not isinstance(required, int) or isinstance(required, bool):
        raise LocalNativeQualificationError("local preflight required record count is invalid")
    if not isinstance(selected, int) or isinstance(selected, bool):
        raise LocalNativeQualificationError("local preflight selected capacity is invalid")

    preserved_pairs = (
        ("function_count", "function_count"),
        ("foreign_count", "foreign_count"),
        ("local_function_count", "local_function_count"),
    )
    identity_preserved = all(
        isinstance(parameter_audit.get(before), int)
        and audit.get(after) == parameter_audit.get(before)
        for before, after in preserved_pairs
    )

    return {
        "audit_present": True,
        "local_count_exact": audit.get("local_count") == required == selected,
        "ir_local_count_exact": audit.get("ir_local_count") == required,
        "events_exact_projection": audit.get("ir_instruction_count") == projections.get("events"),
        "values_exact_projection": audit.get("ir_value_count") == projections.get("values"),
        "blocks_exact_projection": audit.get("ir_block_count") == projections.get("blocks"),
        "calls_exact_projection": audit.get("ast_call_count") == projections.get("calls"),
        "parameter_count_exact": audit.get("parameter_count") == PARAMETER_CAPACITY,
        "ir_parameter_count_exact": audit.get("ir_parameter_count") == PARAMETER_CAPACITY,
        "function_identity_preserved": identity_preserved,
        "foreign_function_count_preserved": audit.get("foreign_count") == parameter_audit.get("foreign_count"),
        "local_function_count_preserved": audit.get("local_function_count") == parameter_audit.get("local_function_count"),
        "event_capacity": isinstance(audit.get("ir_instruction_count"), int) and 0 < audit["ir_instruction_count"] < EVENT_CAPACITY,
        "value_capacity": isinstance(audit.get("ir_value_count"), int) and 0 < audit["ir_value_count"] < VALUE_CAPACITY,
        "block_capacity": isinstance(audit.get("ir_block_count"), int) and 0 < audit["ir_block_count"] < BLOCK_CAPACITY,
        "call_capacity": isinstance(audit.get("ast_call_count"), int) and 0 < audit["ast_call_count"] <= CALL_CAPACITY,
    }


def qualify(
    *,
    parameter_report_path: Path,
    report_path: Path,
    static_preflight_report_path: Path = DEFAULT_LOCAL_PREFLIGHT_REPORT,
) -> dict[str, object]:
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        raise LocalNativeQualificationError("local IR-v2 qualification requires Linux x86-64")
    compiler = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    if compiler is None:
        raise LocalNativeQualificationError("local IR-v2 qualification requires cc, gcc, or clang")

    canonical_bytes = SOURCE.read_bytes()
    canonical_source = canonical_bytes.decode("utf-8")
    parameter_report_bytes = parameter_report_path.resolve().read_bytes()
    parameter_report = _load_json(parameter_report_path.resolve())
    parameter_source, _, parameter_audit = validate_parameter_report_strict(
        parameter_report,
        canonical_source=canonical_source,
    )

    preflight = build_preflight(parameter_report, canonical_source=canonical_source)
    preflight_path = static_preflight_report_path.resolve()
    preflight_path.parent.mkdir(parents=True, exist_ok=True)
    preflight_path.write_text(
        json.dumps(preflight, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    if preflight.get("local_native_qualification_allowed") is not True:
        raise LocalNativeQualificationError(
            f"local static preflight does not authorize native qualification: {preflight.get('status')}"
        )
    if preflight.get("next") != "NATIVE_LOCAL_METADATA_CANDIDATE":
        raise LocalNativeQualificationError("local static preflight routed to a different next gate")

    local_metadata = preflight.get("local_candidate")
    if not isinstance(local_metadata, dict):
        raise LocalNativeQualificationError("local preflight candidate metadata is missing")
    selected = local_metadata.get("selected_capacity")
    if not isinstance(selected, int) or isinstance(selected, bool):
        raise LocalNativeQualificationError("local preflight selected capacity is unavailable")
    local_source = transform_locals(parameter_source, local_capacity=selected)
    local_bytes = local_source.encode("utf-8")
    if local_metadata.get("source_sha256") != _sha256(local_bytes):
        raise LocalNativeQualificationError("rebuilt local candidate SHA differs from preflight")
    if local_metadata.get("source_bytes") != len(local_bytes):
        raise LocalNativeQualificationError("rebuilt local candidate byte count differs from preflight")

    call_closure = _load_closure(CALL_ARGUMENT_CLOSURE)
    call_argument_audit = audit_call_arguments(
        canonical_source=canonical_source,
        closure=call_closure,
        local_candidate=local_source,
    )
    if call_argument_audit.get("status") != "PASS_STATIC_CALL_ARGUMENT_MODEL":
        raise LocalNativeQualificationError(
            f"call-argument preflight blocked local native qualification: {call_argument_audit.get('status')}"
        )
    local_call_model = call_argument_audit.get("local_candidate")
    if not isinstance(local_call_model, dict) or local_call_model.get(
        "safe_under_current_call_and_argument_capacities"
    ) is not True:
        raise LocalNativeQualificationError("local candidate call-argument capacity is not statically safe")

    with tempfile.TemporaryDirectory(prefix="s3-ir-v2-locals-") as temporary:
        temp = Path(temporary)
        source_path = temp / "s3c_stage1.ir-v2-locals.s3"
        executable = temp / "s3c-stage1-ir-v2-locals"
        assembly = temp / "s3c-stage1-ir-v2-locals.s"
        source_path.write_bytes(local_bytes)

        build_stage1(executable, source=source_path, assembly_output=assembly)

        executable_bytes = executable.read_bytes()
        assembly_bytes = assembly.read_bytes()
        trivial = _run_stage1(executable, b"fn main() -> tryte:\n    return 7\n")
        trivial_pass = (
            trivial.returncode == 0
            and trivial.stderr == b""
            and trivial.stdout == _expected_trivial_assembly(7)
        )

        self_run = _run_stage1(executable, local_bytes)
        audit, stderr_lines = _parse_audit(self_run.stderr)
        marker = stderr_lines[-1] if stderr_lines else None
        self_boundary_pass = bool(
            self_run.returncode == 2
            and self_run.stdout == b""
            and audit is not None
            and marker == "S3_STAGE1_EMITTER_BLOCKED"
        )
        count_guards = _native_count_guards(
            audit,
            parameter_audit=parameter_audit,
            preflight=preflight,
        )
        count_guards_pass = all(count_guards.values())
        native_pass = bool(trivial_pass and self_boundary_pass and count_guards_pass)

        result: dict[str, object] = {
            "schema": "s3.selfhost.codegen-ir-v2-locals-native-candidate.v1",
            "platform": {
                "system": platform.system(),
                "machine": platform.machine(),
                "compiler": compiler,
            },
            "canonical_source_mutated": False,
            "canonical": {
                "source_sha256": _sha256(canonical_bytes),
                "source_bytes": len(canonical_bytes),
            },
            "parameter_prerequisite": {
                "report_path": str(parameter_report_path.resolve()),
                "report_sha256": _sha256(parameter_report_bytes),
                "status": "PASS_STRICTLY_VALIDATED",
                "source_sha256": _sha256(parameter_source.encode("utf-8")),
                "native_audit": parameter_audit,
            },
            "local_static_preflight": preflight,
            "call_argument_preflight": call_argument_audit,
            "candidate": {
                "transform_chain": [
                    "DROP_REDUNDANT_DISCARD_KEYWORD_EVENT",
                    "ADD_PACKED_PARAMETER_IR_V2",
                    "ADD_SHAPE_PRESERVING_PACKED_LOCAL_IR_V2",
                ],
                "selected_local_capacity": selected,
                "source_sha256": _sha256(local_bytes),
                "source_bytes": len(local_bytes),
                "stage1_executable_sha256": _sha256(executable_bytes),
                "stage1_executable_bytes": len(executable_bytes),
                "stage1_assembly_sha256": _sha256(assembly_bytes),
                "stage1_assembly_bytes": len(assembly_bytes),
            },
            "trivial_compile": {
                "status": "PASS" if trivial_pass else "FAIL",
                "returncode": trivial.returncode,
                "stdout_sha256": _sha256(trivial.stdout),
                "stderr": trivial.stderr.decode("ascii", errors="replace"),
            },
            "self_source": {
                "status": (
                    "PASS_LOCAL_VERIFIER_TO_EXPECTED_EMITTER_BOUNDARY"
                    if self_boundary_pass and count_guards_pass
                    else "FAIL_OR_DIFFERENT_BLOCKER"
                ),
                "returncode": self_run.returncode,
                "stdout_bytes": len(self_run.stdout),
                "stderr_lines": stderr_lines,
                "audit": audit,
                "final_marker": marker,
            },
            "native_count_guards": count_guards,
            "qualification": {
                "parameter_prerequisite": "PASS_STRICTLY_VALIDATED",
                "local_static_preflight": "PASS",
                "call_argument_preflight": "PASS",
                "candidate_build": "PASS",
                "trivial_compile": "PASS" if trivial_pass else "FAIL",
                "local_verifier_to_emitter_boundary": (
                    "PASS" if self_boundary_pass and count_guards_pass else "FAIL"
                ),
                "native_count_guards": "PASS" if count_guards_pass else "FAIL",
                "local_ir_v2_candidate": (
                    "PASS_NATIVE_CANDIDATE" if native_pass else "FAIL"
                ),
                "canonical_commit_allowed": False,
                "canonical_commit_reason": (
                    "Candidate-only checkpoint; review native local evidence before any canonical promotion."
                ),
                "unified_value_def_use": "NOT_STARTED",
                "general_emitter": "BLOCKED_IR_V2_INCOMPLETE",
                "self_emit": "NOT_STARTED",
                "stage2": "NOT_STARTED",
                "stage3": "NOT_STARTED",
                "full_self_hosting": False,
                "next": (
                    "UNIFIED_VALUE_NAMESPACE_CANDIDATE_PREFLIGHT"
                    if native_pass
                    else "REPAIR_LOCAL_METADATA_NATIVE_CANDIDATE"
                ),
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
    parser.add_argument("--parameter-report", type=Path, default=DEFAULT_PARAMETER_REPORT)
    parser.add_argument("--static-preflight-report", type=Path, default=DEFAULT_LOCAL_PREFLIGHT_REPORT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)

    result = qualify(
        parameter_report_path=args.parameter_report,
        static_preflight_report_path=args.static_preflight_report,
        report_path=args.report,
    )
    qualification = result["qualification"]
    print(f"REPORT={args.report.resolve()}")
    print(f"PARAMETER_PREREQUISITE={qualification['parameter_prerequisite']}")
    print(f"LOCAL_STATIC_PREFLIGHT={qualification['local_static_preflight']}")
    print(f"CALL_ARGUMENT_PREFLIGHT={qualification['call_argument_preflight']}")
    print(f"LOCAL_IR_V2_CANDIDATE={qualification['local_ir_v2_candidate']}")
    print(f"CANONICAL_COMMIT_ALLOWED={qualification['canonical_commit_allowed']}")
    audit = result["self_source"]["audit"]
    if audit is not None:
        print(f"LOCAL_COUNT={audit['local_count']}")
        print(f"IR_LOCAL_COUNT={audit['ir_local_count']}")
        print(f"IR_INSTRUCTION_COUNT={audit['ir_instruction_count']}")
        print(f"IR_VALUE_COUNT={audit['ir_value_count']}")
        print(f"IR_BLOCK_COUNT={audit['ir_block_count']}")
        print(f"CALL_COUNT={audit['ast_call_count']}")
    local_call_model = result["call_argument_preflight"]["local_candidate"]["model"]
    print(f"STATIC_LOCAL_CALL_ARGUMENTS={local_call_model['total_call_arguments']}")
    print(f"STATIC_LOCAL_CALL_ARGUMENT_HEADROOM={local_call_model['call_argument_headroom']}")
    print(f"NEXT={qualification['next']}")
    print("CANONICAL_SOURCE_MUTATED=False")
    print("STAGE2=NOT_STARTED")
    print("STAGE3=NOT_STARTED")
    return 0 if qualification["local_ir_v2_candidate"] == "PASS_NATIVE_CANDIDATE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
