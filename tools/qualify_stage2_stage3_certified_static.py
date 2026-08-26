"""Static-link final authority for Stage2/Stage3 self-hosting certification.

This entrypoint composes the hashed-evidence certified wrapper with the shared
freestanding static linker. It temporarily replaces only the legacy fixed-point
module's link function; all compiler execution, strace, conformance, fixed-point,
ELF, and Landlock checks remain owned by the existing strict engine. The
replacement is restored even on failure.

The final authority additionally re-opens the exact Stage2 and Stage3 artifacts
recorded by the fixed-point engine, audits both as freestanding static ELF, and
binds the audit SHA/byte counts back to the measured fixed-point entries. A
successful underlying engine therefore cannot be upgraded to FULL_SELF_HOSTING
if either final artifact is stale, replaced, dynamic, malformed, or otherwise
not the exact freestanding ELF measured by the fixed-point run.
"""

from __future__ import annotations

import argparse
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
        if not isinstance(expected_sha, str) or len(expected_sha) != 64:
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
    artifacts_pass = (
        final_artifact_audits.get("status")
        == "PASS_FINAL_STAGE2_STAGE3_FREESTANDING_STATIC_ELF_BINDING"
    )
    engine_full = base_qualification.get("full_self_hosting") is True
    full = engine_full and artifacts_pass
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
        "final_artifact_audits": final_artifact_audits,
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
                else "REPAIR_FAILED_STAGE1_EVIDENCE_STRICT_SANDBOX_FIXED_POINT_OR_FINAL_ELF_BINDING"
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
    print("FULL_SELF_HOSTING=" + ("YES" if q["full_self_hosting"] else "NO"))
    print(f"STATUS={q['status']}")
    print(f"NEXT={q['next']}")
    return 0 if q["full_self_hosting"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
