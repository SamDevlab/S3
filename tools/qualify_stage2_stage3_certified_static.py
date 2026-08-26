"""Static-link final authority for Stage2/Stage3 self-hosting certification.

This entrypoint composes the hashed-evidence certified wrapper with the shared
freestanding static linker.  It temporarily replaces only the legacy fixed-point
module's link function; all compiler execution, strace, conformance, fixed-point,
ELF, and Landlock checks remain owned by the existing strict engine.  The
replacement is restored even on failure.
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

import tools.qualify_stage2_stage3_fixed_point as fixed_point_module
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
    full = base_qualification.get("full_self_hosting") is True
    result: dict[str, Any] = {
        "schema": "s3.selfhost.stage2-stage3-certified-static.v1",
        "authority": "FINAL_SELF_HOSTING_AUTHORITY",
        "static_link_recipe": {
            "mode": "STATIC_FREESTANDING_FINAL_AUTHORITY",
            "flags": list(STATIC_LINK_FLAGS),
            "patched_module": "tools.qualify_stage2_stage3_fixed_point._assemble_link",
            "patch_scope": "THIS_QUALIFICATION_CALL_ONLY",
            "restored_after_run": True,
        },
        "hashed_evidence_strict_engine": base,
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
            "static_freestanding_link_recipe": True,
            "full_self_hosting": full,
            "status": (
                "FULL_SELF_HOSTING_CERTIFIED_STATIC_HASHED_EVIDENCE"
                if full
                else "BLOCKED_STATIC_HASHED_SELF_HOSTING_CERTIFICATION"
            ),
            "next": (
                "FINAL_CERTIFICATION_COMPLETE"
                if full
                else "REPAIR_FAILED_STAGE1_EVIDENCE_STRICT_SANDBOX_OR_FIXED_POINT_GATE"
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
    print("FULL_SELF_HOSTING=" + ("YES" if q["full_self_hosting"] else "NO"))
    print(f"STATUS={q['status']}")
    print(f"NEXT={q['next']}")
    return 0 if q["full_self_hosting"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
