"""Static-link final authority for Stage2/Stage3 self-hosting certification.

This entrypoint composes the hashed-evidence certified wrapper with the shared
freestanding static linker. It temporarily replaces only the legacy fixed-point
module's link function; all compiler execution, strace, conformance, fixed-point,
ELF, and Landlock checks remain owned by the existing strict engine. The
replacement is restored even on failure.

The final authority re-opens the exact Stage2 and Stage3 artifacts recorded by
the fixed-point engine, audits both as freestanding static ELF, and binds the
audit SHA/byte counts back to the measured fixed-point entries. It also re-opens
the exact Stage1 final-self-emit evidence report selected by the Stage1 gate,
re-hashes that report to close the report-mutation/TOCTOU boundary, extracts its
certified Stage2 candidate, and requires the fixed-point Stage2 to be exactly the
same ELF by SHA256 and byte count. Since Stage2 == Stage3 is already an exact
fixed-point prerequisite, the final Stage3 is bound to the same Stage1 self-emit
candidate as well.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

import tools.qualify_stage2_stage3_fixed_point as fixed_point_module
from tools.audit_selfhost_freestanding_elf import audit_path
from tools.qualify_stage2_stage3_certified_strict import (
    DEFAULT_FIXED_POINT_CONTRACT,
    DEFAULT_HOST_IO,
    DEFAULT_MANIFEST,
    DEFAULT_STAGE1_CERT,
    DEFAULT_STAGE1_CONTRACT,
    CertifiedStrictError,
    qualify_certified_strict,
)
from tools.selfhost_static_link import STATIC_LINK_FLAGS, assemble_link_static


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = (
    ROOT / "reports" / "selfhost" / "stage2"
    / "stage2-stage3-certified-static.json"
)
DEFAULT_WORKSPACE = Path(tempfile.gettempdir()) / "s3-stage2-stage3-certified-static"


class CertifiedStaticError(RuntimeError):
    pass


def _require_mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CertifiedStaticError(f"{label} must be an object")
    return value


def _valid_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(char in "0123456789abcdefABCDEF" for char in value)
    )


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _audit_final_stage_artifacts(base: dict[str, Any]) -> dict[str, Any]:
    """Audit and content-bind the exact Stage2/Stage3 fixed-point artifacts."""

    strict = _require_mapping(base.get("strict_execution_engine"), "strict execution engine")
    fixed = _require_mapping(strict.get("base_fixed_point"), "fixed-point engine result")
    fixed_point = _require_mapping(fixed.get("fixed_point"), "fixed-point equality result")
    if fixed_point.get("stage2_stage3_bytes_equal") is not True:
        raise CertifiedStaticError("fixed-point engine did not prove Stage2/Stage3 byte equality")
    if fixed_point.get("stage2_stage3_sha256_equal") is not True:
        raise CertifiedStaticError("fixed-point engine did not prove Stage2/Stage3 SHA equality")

    audits: dict[str, Any] = {}
    for role in ("stage2", "stage3"):
        measured = _require_mapping(fixed.get(role), f"fixed-point {role}")
        raw_path = measured.get("path")
        expected_sha = measured.get("sha256")
        expected_bytes = measured.get("bytes")
        if not isinstance(raw_path, str) or not raw_path:
            raise CertifiedStaticError(f"fixed-point {role} lacks artifact path")
        if not _valid_sha256(expected_sha):
            raise CertifiedStaticError(f"fixed-point {role} lacks valid artifact SHA256")
        if not isinstance(expected_bytes, int) or expected_bytes <= 0:
            raise CertifiedStaticError(f"fixed-point {role} lacks valid artifact byte count")

        artifact_path = Path(raw_path).resolve()
        audit = audit_path(artifact_path)
        if audit.get("status") != "PASS_FREESTANDING_STATIC_ELF":
            raise CertifiedStaticError(f"{role} failed final freestanding static ELF audit")
        artifact = _require_mapping(audit.get("artifact"), f"{role} ELF audit artifact")
        actual_sha = artifact.get("sha256")
        actual_bytes = artifact.get("bytes")
        if actual_sha != expected_sha:
            raise CertifiedStaticError(
                f"{role} ELF audit SHA differs from fixed-point measurement: "
                f"expected={expected_sha} actual={actual_sha}"
            )
        if actual_bytes != expected_bytes:
            raise CertifiedStaticError(
                f"{role} ELF audit byte count differs from fixed-point measurement: "
                f"expected={expected_bytes} actual={actual_bytes}"
            )
        audits[role] = {
            "status": audit["status"],
            "path": str(artifact_path),
            "sha256": actual_sha,
            "bytes": actual_bytes,
            "fixed_point_sha256_bound": True,
            "fixed_point_bytes_bound": True,
            "audit": audit,
        }

    exact_same_sha = audits["stage2"]["sha256"] == audits["stage3"]["sha256"]
    exact_same_bytes = audits["stage2"]["bytes"] == audits["stage3"]["bytes"]
    if not exact_same_sha or not exact_same_bytes:
        raise CertifiedStaticError(
            "final Stage2/Stage3 artifact audits disagree despite fixed-point equality"
        )

    return {
        "status": "PASS_FINAL_STAGE2_STAGE3_FREESTANDING_STATIC_ELF_BINDING",
        "stage2": audits["stage2"],
        "stage3": audits["stage3"],
        "stage2_stage3_sha256_equal": exact_same_sha,
        "stage2_stage3_bytes_equal": exact_same_bytes,
    }


def _load_stage1_self_emit_stage2_binding(base: dict[str, Any]) -> dict[str, Any]:
    """Re-hash Stage1 final-self-emit evidence and extract its Stage2 identity."""

    certification = _require_mapping(
        base.get("stage1_certification"), "Stage1 certification result"
    )
    evidence = _require_mapping(
        certification.get("evidence_revalidation"),
        "Stage1 evidence revalidation",
    )
    if evidence.get("status") != "PASS_STAGE1_HASHED_EVIDENCE_REVALIDATION":
        raise CertifiedStaticError(
            "Stage1 evidence must be revalidated before Stage2 continuity binding"
        )
    validated_roles = _require_mapping(
        evidence.get("validated_roles"), "Stage1 validated evidence roles"
    )
    role = _require_mapping(
        validated_roles.get("final_self_emit"), "Stage1 final_self_emit evidence role"
    )
    raw_path = role.get("path")
    expected_report_sha = role.get("sha256")
    expected_schema = role.get("schema")
    if not isinstance(raw_path, str) or not raw_path:
        raise CertifiedStaticError("final_self_emit evidence role lacks report path")
    if not _valid_sha256(expected_report_sha):
        raise CertifiedStaticError("final_self_emit evidence role lacks valid report SHA256")
    if expected_schema != "s3.selfhost.stage1-final-self-emit.v1":
        raise CertifiedStaticError("final_self_emit evidence role schema mismatch")

    report_path = Path(raw_path).resolve()
    try:
        report_path.relative_to(ROOT.resolve())
    except ValueError as error:
        raise CertifiedStaticError(
            "final_self_emit evidence path escapes repository root"
        ) from error
    try:
        report_bytes = report_path.read_bytes()
    except OSError as error:
        raise CertifiedStaticError(
            f"final_self_emit evidence report is unavailable: {report_path}"
        ) from error
    actual_report_sha = _sha256_bytes(report_bytes)
    if actual_report_sha != expected_report_sha:
        raise CertifiedStaticError(
            "final_self_emit evidence report changed after Stage1 gate revalidation: "
            f"expected={expected_report_sha} actual={actual_report_sha}"
        )
    try:
        report_document = json.loads(report_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CertifiedStaticError(
            "final_self_emit evidence report is not valid UTF-8 JSON"
        ) from error
    if not isinstance(report_document, dict):
        raise CertifiedStaticError("final_self_emit evidence report must be an object")
    if report_document.get("schema") != expected_schema:
        raise CertifiedStaticError("final_self_emit report schema changed or is invalid")

    qualification = _require_mapping(
        report_document.get("qualification"), "final_self_emit qualification"
    )
    required_qualification = {
        "self_emit": "PASS",
        "stage1_certified_candidate": True,
        "stage2_artifact_created": True,
        "stage2_certified": False,
        "stage3_started": False,
        "full_self_hosting": False,
        "semantic_ir_native_call_boundary": "PASS",
    }
    for field, expected in required_qualification.items():
        if qualification.get(field) != expected:
            raise CertifiedStaticError(
                f"final_self_emit qualification {field} must be {expected!r}"
            )

    link_recipe = _require_mapping(
        report_document.get("link_recipe"), "final_self_emit link recipe"
    )
    if link_recipe.get("mode") != "STATIC_FREESTANDING_FINAL_AUTHORITY":
        raise CertifiedStaticError(
            "final_self_emit did not use the static freestanding final link recipe"
        )
    call_boundary = _require_mapping(
        report_document.get("semantic_ir_call_boundary"),
        "final_self_emit semantic IR call boundary",
    )
    if call_boundary.get("status") != "PASS":
        raise CertifiedStaticError("final_self_emit semantic IR call boundary did not PASS")
    if call_boundary.get("authority") != "STAGE1_FINAL_SEMANTIC_IR_NATIVE_CALL_BOUND":
        raise CertifiedStaticError("final_self_emit semantic IR authority mismatch")

    stage2 = _require_mapping(report_document.get("stage2"), "final_self_emit Stage2")
    stage2_sha = stage2.get("sha256")
    stage2_bytes = stage2.get("bytes")
    if not _valid_sha256(stage2_sha):
        raise CertifiedStaticError("final_self_emit Stage2 lacks valid SHA256")
    if not isinstance(stage2_bytes, int) or stage2_bytes <= 0:
        raise CertifiedStaticError("final_self_emit Stage2 lacks valid byte count")
    if stage2.get("elf_bytes_equal") is not True:
        raise CertifiedStaticError("final_self_emit Stage2 deterministic ELF bytes did not match")
    if stage2.get("elf_sha256_equal") is not True:
        raise CertifiedStaticError("final_self_emit Stage2 deterministic ELF SHA did not match")
    if stage2.get("certified") is not False:
        raise CertifiedStaticError("final_self_emit must not mark Stage2 certified by itself")

    second = _require_mapping(
        stage2.get("second_artifact"), "final_self_emit second Stage2 artifact"
    )
    if second.get("sha256") != stage2_sha or second.get("bytes") != stage2_bytes:
        raise CertifiedStaticError(
            "final_self_emit Stage2 deterministic artifacts do not share exact identity"
        )
    elf_audit = _require_mapping(
        stage2.get("freestanding_elf_audit"),
        "final_self_emit Stage2 freestanding ELF audit",
    )
    second_elf_audit = _require_mapping(
        stage2.get("second_freestanding_elf_audit"),
        "final_self_emit second Stage2 freestanding ELF audit",
    )
    if elf_audit.get("status") != "PASS_FREESTANDING_STATIC_ELF":
        raise CertifiedStaticError("final_self_emit Stage2 freestanding ELF audit did not PASS")
    if second_elf_audit.get("status") != "PASS_FREESTANDING_STATIC_ELF":
        raise CertifiedStaticError(
            "final_self_emit second Stage2 freestanding ELF audit did not PASS"
        )

    return {
        "status": "PASS_STAGE1_SELF_EMIT_STAGE2_CANDIDATE_EVIDENCE",
        "report": {
            "path": str(report_path),
            "sha256": actual_report_sha,
            "schema": expected_schema,
            "rehash_matches_stage1_gate": True,
        },
        "candidate": {
            "sha256": stage2_sha,
            "bytes": stage2_bytes,
            "deterministic_two_artifacts": True,
            "freestanding_static_elf": True,
            "stage2_certified_by_self_emit_alone": False,
        },
        "semantic_ir_call_boundary": {
            "status": call_boundary["status"],
            "authority": call_boundary["authority"],
        },
        "link_recipe": {
            "mode": link_recipe["mode"],
        },
    }


def _bind_fixed_point_to_stage1_self_emit(
    final_artifact_audits: dict[str, Any],
    self_emit_binding: dict[str, Any],
) -> dict[str, Any]:
    """Require fixed-point Stage2/Stage3 to continue from Stage1's Stage2 ELF."""

    candidate = _require_mapping(
        self_emit_binding.get("candidate"), "Stage1 self-emit Stage2 candidate"
    )
    candidate_sha = candidate.get("sha256")
    candidate_bytes = candidate.get("bytes")
    if not _valid_sha256(candidate_sha) or not isinstance(candidate_bytes, int):
        raise CertifiedStaticError("Stage1 self-emit Stage2 candidate identity is invalid")

    stage2 = _require_mapping(final_artifact_audits.get("stage2"), "final Stage2 audit")
    stage3 = _require_mapping(final_artifact_audits.get("stage3"), "final Stage3 audit")
    if stage2.get("sha256") != candidate_sha:
        raise CertifiedStaticError(
            "fixed-point Stage2 SHA differs from the Stage1 self-emit Stage2 candidate: "
            f"self_emit={candidate_sha} fixed_point={stage2.get('sha256')}"
        )
    if stage2.get("bytes") != candidate_bytes:
        raise CertifiedStaticError(
            "fixed-point Stage2 byte count differs from the Stage1 self-emit Stage2 candidate: "
            f"self_emit={candidate_bytes} fixed_point={stage2.get('bytes')}"
        )
    if stage3.get("sha256") != candidate_sha or stage3.get("bytes") != candidate_bytes:
        raise CertifiedStaticError(
            "fixed-point Stage3 does not preserve the exact Stage1 self-emit Stage2 identity"
        )

    return {
        "status": "PASS_STAGE1_SELF_EMIT_TO_STAGE2_STAGE3_CONTINUITY",
        "stage1_self_emit_stage2": {
            "sha256": candidate_sha,
            "bytes": candidate_bytes,
        },
        "fixed_point_stage2": {
            "sha256": stage2["sha256"],
            "bytes": stage2["bytes"],
            "matches_stage1_self_emit_candidate": True,
        },
        "fixed_point_stage3": {
            "sha256": stage3["sha256"],
            "bytes": stage3["bytes"],
            "matches_stage1_self_emit_candidate_via_exact_fixed_point": True,
        },
    }


def qualify_certified_static(
    *,
    stage1: Path,
    stage1_certification: Path,
    stage1_contract: Path,
    fixed_point_contract: Path,
    manifest: Path,
    host_io: Path,
    report: Path,
    workspace: Path,
    stage4: bool = False,
) -> dict[str, Any]:
    original_link = fixed_point_module._assemble_link
    engine_report = workspace.resolve().parent / (
        workspace.resolve().name + "-hashed-engine-v1.json"
    )
    fixed_point_module._assemble_link = assemble_link_static
    try:
        base = qualify_certified_strict(
            stage1=stage1,
            stage1_certification=stage1_certification,
            stage1_contract=stage1_contract,
            fixed_point_contract=fixed_point_contract,
            manifest=manifest,
            host_io=host_io,
            report=engine_report,
            workspace=workspace,
            stage4=stage4,
        )
    finally:
        fixed_point_module._assemble_link = original_link

    if base.get("schema") != "s3.selfhost.stage2-stage3-certified-strict.v1":
        raise CertifiedStaticError("hashed-evidence strict engine schema mismatch")
    base_qualification = base.get("qualification")
    if not isinstance(base_qualification, dict):
        raise CertifiedStaticError("hashed-evidence strict engine lacks qualification")

    final_artifact_audits = _audit_final_stage_artifacts(base)
    self_emit_stage2 = _load_stage1_self_emit_stage2_binding(base)
    stage2_continuity = _bind_fixed_point_to_stage1_self_emit(
        final_artifact_audits,
        self_emit_stage2,
    )
    artifacts_pass = (
        final_artifact_audits.get("status")
        == "PASS_FINAL_STAGE2_STAGE3_FREESTANDING_STATIC_ELF_BINDING"
    )
    continuity_pass = (
        stage2_continuity.get("status")
        == "PASS_STAGE1_SELF_EMIT_TO_STAGE2_STAGE3_CONTINUITY"
    )
    engine_full = base_qualification.get("full_self_hosting") is True
    full = engine_full and artifacts_pass and continuity_pass
    result: dict[str, Any] = {
        "schema": "s3.selfhost.stage2-stage3-certified-static.v1",
        "authority": "FINAL_SELF_HOSTING_AUTHORITY",
        "static_link_recipe": {
            "mode": "STATIC_FREESTANDING_FINAL_AUTHORITY",
            "flags": list(STATIC_LINK_FLAGS),
            "patched_module": "tools.qualify_stage2_stage3_fixed_point._assemble_link",
            "patch_scope": "THIS_QUALIFICATION_CALL_ONLY",
            "restored_after_run": True,
            "final_artifact_audit_required": True,
        },
        "hashed_evidence_strict_engine": base,
        "stage1_self_emit_stage2_evidence": self_emit_stage2,
        "final_artifact_audits": final_artifact_audits,
        "stage1_self_emit_stage2_continuity": stage2_continuity,
        "qualification": {
            "stage1_hashed_evidence_revalidation": base_qualification.get(
                "stage1_hashed_evidence_revalidation"
            ),
            "stage1_to_stage2": base_qualification.get("stage1_to_stage2"),
            "stage2_pythonless_compiler": base_qualification.get(
                "stage2_pythonless_compiler"
            ),
            "filesystem_inaccessible": base_qualification.get(
                "filesystem_inaccessible"
            ),
            "stage2_conformance": base_qualification.get("stage2_conformance"),
            "stage2_to_stage3": base_qualification.get("stage2_to_stage3"),
            "stage2_stage3_exact_elf_fixed_point": base_qualification.get(
                "stage2_stage3_exact_elf_fixed_point"
            ),
            "stage2_freestanding_static_elf": final_artifact_audits["stage2"]["status"],
            "stage3_freestanding_static_elf": final_artifact_audits["stage3"]["status"],
            "final_artifacts_bound_to_fixed_point": artifacts_pass,
            "stage1_self_emit_report_revalidated": self_emit_stage2["report"][
                "rehash_matches_stage1_gate"
            ],
            "stage2_matches_stage1_self_emit_candidate": continuity_pass,
            "stage3_matches_stage1_self_emit_candidate_via_fixed_point": continuity_pass,
            "static_freestanding_link_recipe": artifacts_pass,
            "underlying_strict_engine_full_self_hosting": engine_full,
            "full_self_hosting": full,
            "status": (
                "FULL_SELF_HOSTING_CERTIFIED_STATIC_HASHED_EVIDENCE"
                if full
                else "BLOCKED_STATIC_HASHED_SELF_HOSTING_CERTIFICATION"
            ),
            "next": (
                "FINAL_CERTIFICATION_COMPLETE"
                if full
                else "REPAIR_FAILED_STAGE1_EVIDENCE_SELF_EMIT_CONTINUITY_STRICT_SANDBOX_FIXED_POINT_OR_FINAL_ELF_BINDING"
            ),
        },
    }
    destination = report.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage1", type=Path, required=True)
    parser.add_argument("--stage1-certification", type=Path, default=DEFAULT_STAGE1_CERT)
    parser.add_argument("--stage1-contract", type=Path, default=DEFAULT_STAGE1_CONTRACT)
    parser.add_argument("--fixed-point-contract", type=Path, default=DEFAULT_FIXED_POINT_CONTRACT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--host-io", type=Path, default=DEFAULT_HOST_IO)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--stage4", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = qualify_certified_static(
            stage1=args.stage1,
            stage1_certification=args.stage1_certification,
            stage1_contract=args.stage1_contract,
            fixed_point_contract=args.fixed_point_contract,
            manifest=args.manifest,
            host_io=args.host_io,
            report=args.report,
            workspace=args.workspace,
            stage4=args.stage4,
        )
    except (CertifiedStrictError, CertifiedStaticError, OSError, RuntimeError, ValueError) as error:
        parser.exit(2, f"static certified Stage2/Stage3 qualification blocked: {error}\n")

    q = result["qualification"]
    print(f"REPORT={args.report.resolve()}")
    print("STATIC_FREESTANDING_LINK_RECIPE=YES")
    print(f"STAGE1_HASHED_EVIDENCE={q['stage1_hashed_evidence_revalidation']}")
    print(f"STAGE1_TO_STAGE2={q['stage1_to_stage2']}")
    print(f"STAGE2_PYTHONLESS={q['stage2_pythonless_compiler']}")
    print(f"FILESYSTEM_INACCESSIBLE={q['filesystem_inaccessible']}")
    print(f"STAGE2_CONFORMANCE={q['stage2_conformance']}")
    print(f"STAGE2_TO_STAGE3={q['stage2_to_stage3']}")
    print(f"EXACT_ELF_FIXED_POINT={q['stage2_stage3_exact_elf_fixed_point']}")
    print(f"STAGE2_FREESTANDING_ELF={q['stage2_freestanding_static_elf']}")
    print(f"STAGE3_FREESTANDING_ELF={q['stage3_freestanding_static_elf']}")
    print("FINAL_ARTIFACT_BINDING=" + ("PASS" if q["final_artifacts_bound_to_fixed_point"] else "FAIL"))
    print("SELF_EMIT_REPORT_REVALIDATED=" + ("PASS" if q["stage1_self_emit_report_revalidated"] else "FAIL"))
    print("STAGE2_MATCHES_STAGE1_SELF_EMIT=" + ("PASS" if q["stage2_matches_stage1_self_emit_candidate"] else "FAIL"))
    print("FULL_SELF_HOSTING=" + ("YES" if q["full_self_hosting"] else "NO"))
    print(f"STATUS={q['status']}")
    print(f"NEXT={q['next']}")
    return 0 if q["full_self_hosting"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
