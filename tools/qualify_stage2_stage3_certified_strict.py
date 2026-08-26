"""Final authority wrapper for strict Stage2/Stage3 self-hosting certification.

The older fixed-point/strict-sandbox tools remain useful execution engines but
accept the historical Stage1 certification schema. This wrapper accepts only
``stage1-certification-gate.v2``, revalidates all content-hashed evidence,
verifies the exact Stage1 executable and canonical source, creates a v1
compatibility certificate in a temporary directory, runs the existing
strict+Landlock engine, and then independently rechecks every final gate.

Contract and source-manifest path arguments are location overrides only. The
Stage1 evidence policy, Stage2/Stage3 fixed-point policy, and compiler source
manifest must be byte-identical to their repository canonical authorities. The
consumer also re-opens the declared Git commit and compares the canonical source
blob byte-for-byte instead of trusting producer booleans.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from tools.qualify_stage2_stage3_fixed_point import (
    DEFAULT_HOST_IO,
    DEFAULT_MANIFEST,
    FixedPointError,
)
from tools.qualify_stage2_stage3_strict_sandbox import qualify_strict
from tools.selfhost_contract_authority import (
    ContractAuthorityError,
    require_authoritative_contract,
)
from tools.selfhost_source_authority import (
    SourceAuthorityError,
    require_authoritative_source_manifest,
    verify_git_commit_source_binding,
)
from tools.stage1_certification_evidence import (
    ROOT,
    Stage1CertificationEvidenceError,
    sha256_file,
    validate_stage1_evidence,
)


DEFAULT_STAGE1_CERT = (
    ROOT / "reports" / "selfhost" / "stage1" / "stage1-certification-gate.json"
)
DEFAULT_STAGE1_CONTRACT = (
    ROOT / "reports" / "selfhost" / "stage1"
    / "stage1-certification-gate-contract.json"
)
DEFAULT_FIXED_POINT_CONTRACT = (
    ROOT / "reports" / "selfhost" / "stage2"
    / "stage2-stage3-fixed-point-contract.json"
)
DEFAULT_REPORT = (
    ROOT / "reports" / "selfhost" / "stage2"
    / "stage2-stage3-certified-strict.json"
)
DEFAULT_WORKSPACE = Path(tempfile.gettempdir()) / "s3-stage2-stage3-certified-strict"


class CertifiedStrictError(RuntimeError):
    pass


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise CertifiedStrictError(f"{label} is missing: {path}") from error
    except json.JSONDecodeError as error:
        raise CertifiedStrictError(f"{label} is invalid JSON: {path}") from error
    if not isinstance(value, dict):
        raise CertifiedStrictError(f"{label} must be a JSON object")
    return value


def _validate_gate_contract_authority(
    gate: dict[str, Any],
    *,
    expected: dict[str, Any],
) -> None:
    embedded = gate.get("contract_authority")
    if not isinstance(embedded, dict):
        raise CertifiedStrictError("Stage1 gate lacks canonical contract authority binding")
    required = {
        "status": "PASS_CANONICAL_CONTRACT_AUTHORITY",
        "schema": "s3.selfhost.stage1-certification-gate-contract.v3",
        "sha256": expected.get("sha256"),
        "bytes": expected.get("bytes"),
        "exact_bytes_equal": True,
    }
    for field, value in required.items():
        if embedded.get(field) != value:
            raise CertifiedStrictError(
                f"Stage1 gate contract authority {field} must be {value!r}"
            )


def _validate_gate_source_manifest_authority(
    gate: dict[str, Any],
    *,
    expected: dict[str, Any],
) -> None:
    embedded = gate.get("source_manifest_authority")
    if not isinstance(embedded, dict):
        raise CertifiedStrictError("Stage1 gate lacks canonical source manifest authority binding")
    required = {
        "status": "PASS_CANONICAL_SOURCE_MANIFEST_AUTHORITY",
        "schema": "s3.compiler.sources.v1",
        "sha256": expected.get("sha256"),
        "bytes": expected.get("bytes"),
        "exact_bytes_equal": True,
    }
    for field, value in required.items():
        if embedded.get(field) != value:
            raise CertifiedStrictError(
                f"Stage1 gate source manifest authority {field} must be {value!r}"
            )
    expected_source = expected.get("source")
    embedded_source = embedded.get("source")
    if not isinstance(expected_source, dict) or not isinstance(embedded_source, dict):
        raise CertifiedStrictError("Stage1 gate source manifest authority lacks source binding")
    for field in ("path", "sha256", "bytes", "role", "ordering"):
        if embedded_source.get(field) != expected_source.get(field):
            raise CertifiedStrictError(
                f"Stage1 gate source manifest authority source.{field} mismatch"
            )


def validate_hashed_stage1_gate(
    gate: dict[str, Any],
    *,
    stage1: Path,
    canonical_source: bytes,
    canonical_source_path: Path,
    contract: dict[str, Any],
    contract_authority: dict[str, Any],
    source_manifest_authority: dict[str, Any],
) -> dict[str, Any]:
    if contract.get("schema") != "s3.selfhost.stage1-certification-gate-contract.v3":
        raise CertifiedStrictError("Stage1 certification contract schema mismatch")
    if gate.get("schema") != "s3.selfhost.stage1-certification-gate.v2":
        raise CertifiedStrictError("final Stage2/Stage3 wrapper requires Stage1 gate v2")
    _validate_gate_contract_authority(gate, expected=contract_authority)
    _validate_gate_source_manifest_authority(gate, expected=source_manifest_authority)

    canonical_sha = _sha_bytes(canonical_source)
    canonical = gate.get("canonical_source")
    if not isinstance(canonical, dict):
        raise CertifiedStrictError("Stage1 gate lacks canonical_source")
    if canonical.get("sha256") != canonical_sha:
        raise CertifiedStrictError("Stage1 gate canonical SHA differs from current manifest source")
    if canonical.get("bytes") != len(canonical_source):
        raise CertifiedStrictError("Stage1 gate canonical byte count differs from current manifest source")
    relative_canonical = canonical_source_path.resolve().relative_to(ROOT.resolve()).as_posix()
    if canonical.get("path") not in {
        str(canonical_source_path),
        str(canonical_source_path.resolve()),
        relative_canonical,
    }:
        raise CertifiedStrictError("Stage1 gate canonical path differs from manifest source")
    commit = canonical.get("commit")
    if not isinstance(commit, str):
        raise CertifiedStrictError("Stage1 gate lacks exact canonical commit binding")
    if canonical.get("working_tree_equals_commit_blob") is not True:
        raise CertifiedStrictError("Stage1 gate does not claim source equals committed blob")
    git_commit_binding = verify_git_commit_source_binding(
        commit=commit,
        source_path=canonical_source_path,
        source=canonical_source,
        root=ROOT,
    )

    stage1 = stage1.resolve()
    if not stage1.is_file() or not os.access(stage1, os.X_OK):
        raise CertifiedStrictError("Stage1 artifact is missing or not executable")
    stage1_sha = sha256_file(stage1)
    stage1_entry = gate.get("stage1_artifact")
    if not isinstance(stage1_entry, dict):
        raise CertifiedStrictError("Stage1 gate lacks stage1_artifact")
    if stage1_entry.get("sha256") != stage1_sha:
        raise CertifiedStrictError("Stage1 gate artifact SHA differs from executed Stage1")
    if stage1_entry.get("bytes") != stage1.stat().st_size:
        raise CertifiedStrictError("Stage1 gate artifact byte count differs from executed Stage1")

    qualification = gate.get("qualification")
    if not isinstance(qualification, dict):
        raise CertifiedStrictError("Stage1 gate lacks qualification")
    expected = {
        "stage1_certified_for_stage2": True,
        "self_emit": "PASS",
        "semantic_ir": "PASS_CODEGEN_COMPLETE_BOOTSTRAP_SUBSET",
        "verifier_v2": "PASS",
        "general_emitter": "PASS_BOOTSTRAP_REQUIRED_OPCODES",
        "full_self_hosting": False,
    }
    for key, value in expected.items():
        if qualification.get(key) != value:
            raise CertifiedStrictError(
                f"Stage1 gate qualification {key} must be {value!r}"
            )

    evidence = validate_stage1_evidence(
        gate,
        canonical_sha256=canonical_sha,
        stage1_sha256=stage1_sha,
        root=ROOT,
        contract=contract,
    )
    if evidence.get("status") != "PASS_STAGE1_HASHED_EVIDENCE_REVALIDATION":
        raise CertifiedStrictError("Stage1 hashed evidence did not revalidate")
    return {
        "canonical_sha256": canonical_sha,
        "canonical_bytes": len(canonical_source),
        "canonical_commit_binding": git_commit_binding,
        "stage1_sha256": stage1_sha,
        "stage1_bytes": stage1.stat().st_size,
        "contract_authority": contract_authority,
        "source_manifest_authority": source_manifest_authority,
        "evidence": evidence,
    }


def _compatibility_v1_gate(gate_v2: dict[str, Any]) -> dict[str, Any]:
    canonical = gate_v2["canonical_source"]
    qualification = gate_v2["qualification"]
    return {
        "schema": "s3.selfhost.stage1-certification-gate.v1",
        "canonical_source": {
            "sha256": canonical["sha256"],
            "bytes": canonical["bytes"],
        },
        "qualification": {
            "stage1_certified_for_stage2": qualification["stage1_certified_for_stage2"],
            "self_emit": qualification["self_emit"],
            "semantic_ir": qualification["semantic_ir"],
            "verifier_v2": qualification["verifier_v2"],
            "general_emitter": qualification["general_emitter"],
        },
        "compatibility_only": True,
        "authority": "NONE_EPHEMERAL_AFTER_V2_HASHED_EVIDENCE_REVALIDATION",
    }


def _final_qualification(strict: dict[str, Any], evidence_status: str) -> dict[str, Any]:
    if strict.get("schema") != "s3.selfhost.stage2-stage3-strict-sandbox.v4":
        raise CertifiedStrictError("underlying strict sandbox schema mismatch")
    qualification = strict.get("qualification")
    if not isinstance(qualification, dict):
        raise CertifiedStrictError("underlying strict sandbox lacks qualification")
    required = {
        "stage1_to_stage2": "PASS",
        "stage2_pythonless_compiler": "PASS_STRICT_PROCESS_AND_FILE_TRACE",
        "filesystem_inaccessible": "PASS_LANDLOCK",
        "stage2_conformance": "PASS",
        "stage2_to_stage3": "PASS",
        "stage2_stage3_exact_elf_fixed_point": True,
    }
    failures = {
        key: {"expected": expected, "actual": qualification.get(key)}
        for key, expected in required.items()
        if qualification.get(key) != expected
    }
    hashed_pass = evidence_status == "PASS_STAGE1_HASHED_EVIDENCE_REVALIDATION"
    engine_pass = qualification.get("full_self_hosting") is True and not failures
    full = hashed_pass and engine_pass
    return {
        **required,
        "stage1_hashed_evidence_revalidation": evidence_status,
        "underlying_strict_engine_full_self_hosting": qualification.get("full_self_hosting") is True,
        "failed_final_gates": failures,
        "full_self_hosting": full,
        "status": (
            "FULL_SELF_HOSTING_CERTIFIED_VIA_HASHED_STAGE1_GATE"
            if full
            else "BLOCKED_STRICT_SELF_HOSTING_CERTIFICATION"
        ),
        "next": (
            "FINAL_CERTIFICATION_COMPLETE"
            if full
            else "REPAIR_FAILED_HASHED_EVIDENCE_OR_STRICT_STAGE_GATE"
        ),
    }


def qualify_certified_strict(
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
    stage1_gate_path = stage1_certification.resolve()
    gate = _load_json(stage1_gate_path, "Stage1 certification gate v2")
    stage1_policy, stage1_contract_authority = require_authoritative_contract(
        stage1_contract,
        authoritative=DEFAULT_STAGE1_CONTRACT,
        expected_schema="s3.selfhost.stage1-certification-gate-contract.v3",
        label="Stage1 certification contract",
    )
    fixed_policy, fixed_contract_authority = require_authoritative_contract(
        fixed_point_contract,
        authoritative=DEFAULT_FIXED_POINT_CONTRACT,
        expected_schema="s3.selfhost.stage2-stage3-fixed-point-contract.v3",
        label="Stage2/Stage3 fixed-point contract",
    )
    canonical_path, canonical_source, manifest_document, source_manifest_authority = (
        require_authoritative_source_manifest(
            manifest,
            authoritative=DEFAULT_MANIFEST,
            root=ROOT,
        )
    )
    stage1_validation = validate_hashed_stage1_gate(
        gate,
        stage1=stage1,
        canonical_source=canonical_source,
        canonical_source_path=canonical_path,
        contract=stage1_policy,
        contract_authority=stage1_contract_authority,
        source_manifest_authority=source_manifest_authority,
    )

    with tempfile.TemporaryDirectory(prefix="s3-stage1-cert-v1-adapter-") as temporary:
        compat_path = Path(temporary) / "stage1-certification.compat-v1.json"
        compat = _compatibility_v1_gate(gate)
        compat_path.write_text(
            json.dumps(compat, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        compat_sha = sha256_file(compat_path)
        strict = qualify_strict(
            stage1=stage1,
            stage1_certification=compat_path,
            manifest=manifest,
            host_io=host_io,
            report=workspace.resolve().parent / (workspace.resolve().name + "-engine-v4.json"),
            workspace=workspace,
            stage4=stage4,
        )

    evidence_status = stage1_validation["evidence"]["status"]
    final = _final_qualification(strict, evidence_status)
    result = {
        "schema": "s3.selfhost.stage2-stage3-certified-strict.v1",
        "authority": "FINAL_SELF_HOSTING_AUTHORITY",
        "contract": {
            "schema": fixed_policy["schema"],
            "path": str(fixed_point_contract.resolve()),
            "sha256": fixed_contract_authority["sha256"],
            "authority": fixed_contract_authority,
        },
        "canonical_source": {
            "path": str(canonical_path),
            "sha256": stage1_validation["canonical_sha256"],
            "bytes": stage1_validation["canonical_bytes"],
            "manifest": manifest_document,
            "manifest_authority": source_manifest_authority,
            "git_commit_binding": stage1_validation["canonical_commit_binding"],
        },
        "stage1": {
            "path": str(stage1.resolve()),
            "sha256": stage1_validation["stage1_sha256"],
            "bytes": stage1_validation["stage1_bytes"],
        },
        "stage1_certification": {
            "path": str(stage1_gate_path),
            "sha256": sha256_file(stage1_gate_path),
            "schema": gate["schema"],
            "contract_authority": stage1_contract_authority,
            "source_manifest_authority": source_manifest_authority,
            "evidence_revalidation": stage1_validation["evidence"],
            "compatibility_adapter": {
                "schema": "s3.selfhost.stage1-certification-gate.v1",
                "sha256": compat_sha,
                "persisted": False,
                "authority": "NONE",
            },
        },
        "strict_execution_engine": strict,
        "qualification": final,
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
        result = qualify_certified_strict(
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
    except (
        CertifiedStrictError,
        ContractAuthorityError,
        SourceAuthorityError,
        FixedPointError,
        Stage1CertificationEvidenceError,
        OSError,
        ValueError,
    ) as error:
        parser.exit(2, f"certified strict Stage2/Stage3 qualification blocked: {error}\n")

    qualification = result["qualification"]
    print(f"REPORT={args.report.resolve()}")
    print(f"STAGE1_CONTRACT_AUTHORITY={result['stage1_certification']['contract_authority']['status']}")
    print(f"SOURCE_MANIFEST_AUTHORITY={result['canonical_source']['manifest_authority']['status']}")
    print(f"SOURCE_GIT_BINDING={result['canonical_source']['git_commit_binding']['status']}")
    print(f"FIXED_POINT_CONTRACT_AUTHORITY={result['contract']['authority']['status']}")
    print(f"STAGE1_HASHED_EVIDENCE={qualification['stage1_hashed_evidence_revalidation']}")
    print(f"STAGE1_TO_STAGE2={qualification['stage1_to_stage2']}")
    print(f"STAGE2_PYTHONLESS={qualification['stage2_pythonless_compiler']}")
    print(f"FILESYSTEM_INACCESSIBLE={qualification['filesystem_inaccessible']}")
    print(f"STAGE2_CONFORMANCE={qualification['stage2_conformance']}")
    print(f"STAGE2_TO_STAGE3={qualification['stage2_to_stage3']}")
    print(f"EXACT_ELF_FIXED_POINT={qualification['stage2_stage3_exact_elf_fixed_point']}")
    print("FULL_SELF_HOSTING=" + ("YES" if qualification["full_self_hosting"] else "NO"))
    print(f"STATUS={qualification['status']}")
    print(f"NEXT={qualification['next']}")
    return 0 if qualification["full_self_hosting"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
