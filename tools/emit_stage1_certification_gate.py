"""Emit the only Stage1 -> Stage2 authorization gate after strict revalidation.

The output is never assembled from operator-provided PASS booleans. Evidence
paths are fixed by role, their current contents are hashed, and the complete gate
is passed through ``validate_stage1_evidence`` before it is written. The exact
canonical source must also be the exact blob stored at the current Git HEAD, so a
working-tree-only source edit cannot be certified accidentally.

Contract and source path arguments are location selections only, never policy or
compiler-source overrides. The contract must be byte-identical to canonical
policy and the source must resolve exactly to the single source declared by the
canonical compiler-sources manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any

from tools.selfhost_contract_authority import (
    ContractAuthorityError,
    require_authoritative_contract,
)
from tools.selfhost_source_authority import (
    SourceAuthorityError,
    require_authoritative_source_manifest,
)
from tools.stage1_certification_evidence import (
    ROOT,
    Stage1CertificationEvidenceError,
    sha256_file,
    validate_stage1_evidence,
)


DEFAULT_SOURCE = ROOT / "selfhost" / "compiler" / "s3c_stage1.s3"
DEFAULT_MANIFEST = ROOT / "selfhost" / "compiler" / "compiler-sources.json"
DEFAULT_CONTRACT = (
    ROOT / "reports" / "selfhost" / "stage1"
    / "stage1-certification-gate-contract.json"
)
DEFAULT_OUTPUT = (
    ROOT / "reports" / "selfhost" / "stage1" / "stage1-certification-gate.json"
)
DEFAULT_EVIDENCE_PATHS = {
    "native_source_coverage": "reports/selfhost/stage1/packed-token-lane-native-full-coverage.json",
    "representation_epoch": "reports/selfhost/stage1/stage1-representation-epoch.json",
    "reference_current_call_inventory": "reports/selfhost/stage1/reference-current-call-inventory.json",
    "native_call_reconciliation": "reports/selfhost/stage1/stage1-native-call-reconciliation.json",
    "reference_opcode_inventory": "reports/selfhost/stage1/reference-bootstrap-opcode-inventory.json",
    "hosted_fixture_opcode_coverage": "reports/selfhost/stage1/stage1-codegen-fixture-opcode-coverage.json",
    "native_codegen_fixtures": "reports/selfhost/stage1/stage1-codegen-complete-fixtures-native.json",
    "final_capacity": "reports/selfhost/stage1/stage1-final-capacity.json",
    "final_semantic_ir_verifier": "reports/selfhost/stage1/stage1-final-semantic-ir-verifier-call-bound.json",
    "final_self_emit": "reports/selfhost/stage1/stage1-final-self-emit.json",
}


class Stage1CertificationGateError(RuntimeError):
    pass


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise Stage1CertificationGateError(f"{label} is missing: {path}") from error
    except json.JSONDecodeError as error:
        raise Stage1CertificationGateError(f"{label} is invalid JSON: {path}") from error
    if not isinstance(value, dict):
        raise Stage1CertificationGateError(f"{label} must be a JSON object")
    return value


def _run_git(args: list[str]) -> bytes:
    completed = subprocess.run(
        ["git", *args],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        shell=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise Stage1CertificationGateError(
            f"git {' '.join(args)} failed with {completed.returncode}: {detail}"
        )
    return completed.stdout


def git_head_source_binding(source: Path) -> dict[str, Any]:
    source = source.resolve()
    root = ROOT.resolve()
    try:
        relative = source.relative_to(root)
    except ValueError as error:
        raise Stage1CertificationGateError("canonical source must be inside repository root") from error
    head = _run_git(["rev-parse", "HEAD"]).decode("ascii", errors="strict").strip()
    if len(head) != 40:
        raise Stage1CertificationGateError(f"unexpected Git HEAD: {head!r}")
    committed = _run_git(["show", f"{head}:{relative.as_posix()}"])
    working = source.read_bytes()
    if committed != working:
        raise Stage1CertificationGateError(
            "canonical source bytes differ from Git HEAD; commit/freeze the exact source before certification"
        )
    return {
        "path": relative.as_posix(),
        "sha256": _sha_bytes(working),
        "bytes": len(working),
        "commit": head,
        "working_tree_equals_commit_blob": True,
    }


def build_gate(
    *,
    canonical_source: dict[str, Any],
    stage1_path: Path,
    evidence_paths: dict[str, str],
    contract: dict[str, Any],
    root: Path = ROOT,
    contract_authority: dict[str, Any] | None = None,
    source_manifest_authority: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if contract.get("schema") != "s3.selfhost.stage1-certification-gate-contract.v3":
        raise Stage1CertificationGateError("Stage1 certification contract schema mismatch")
    roles = contract.get("required_evidence_roles")
    if not isinstance(roles, dict):
        raise Stage1CertificationGateError("certification contract lacks evidence role policy")
    expected_roles = set(roles)
    supplied_roles = set(evidence_paths)
    if supplied_roles != expected_roles:
        missing = sorted(expected_roles - supplied_roles)
        extra = sorted(supplied_roles - expected_roles)
        raise Stage1CertificationGateError(
            f"evidence role set mismatch: missing={missing} extra={extra}"
        )

    stage1 = stage1_path.resolve()
    if not stage1.is_file() or not os.access(stage1, os.X_OK):
        raise Stage1CertificationGateError("Stage1 artifact is missing or not executable")
    stage1_entry = {
        "path": str(stage1),
        "sha256": sha256_file(stage1),
        "bytes": stage1.stat().st_size,
    }

    root = root.resolve()
    evidence: dict[str, dict[str, str]] = {}
    for role in sorted(expected_roles):
        relative = evidence_paths[role]
        candidate = Path(relative)
        if candidate.is_absolute():
            raise Stage1CertificationGateError(
                f"evidence role {role} path must be repository-relative"
            )
        resolved = (root / candidate).resolve()
        try:
            resolved.relative_to(root)
        except ValueError as error:
            raise Stage1CertificationGateError(
                f"evidence role {role} escapes repository root"
            ) from error
        if not resolved.is_file():
            raise Stage1CertificationGateError(
                f"evidence role {role} is missing: {relative}"
            )
        evidence[role] = {
            "path": candidate.as_posix(),
            "sha256": sha256_file(resolved),
        }

    gate: dict[str, Any] = {
        "schema": contract["output_schema"],
        "canonical_source": canonical_source,
        "stage1_artifact": stage1_entry,
        "evidence": evidence,
        "qualification": {
            "stage1_certified_for_stage2": True,
            "self_emit": "PASS",
            "semantic_ir": "PASS_CODEGEN_COMPLETE_BOOTSTRAP_SUBSET",
            "verifier_v2": "PASS",
            "general_emitter": "PASS_BOOTSTRAP_REQUIRED_OPCODES",
            "full_self_hosting": False,
        },
    }
    if contract_authority is not None:
        if contract_authority.get("status") != "PASS_CANONICAL_CONTRACT_AUTHORITY":
            raise Stage1CertificationGateError("Stage1 contract authority did not pass")
        gate["contract_authority"] = contract_authority
    if source_manifest_authority is not None:
        if source_manifest_authority.get("status") != "PASS_CANONICAL_SOURCE_MANIFEST_AUTHORITY":
            raise Stage1CertificationGateError("canonical source manifest authority did not pass")
        manifest_source = source_manifest_authority.get("source")
        if not isinstance(manifest_source, dict):
            raise Stage1CertificationGateError("canonical source manifest binding lacks source")
        if manifest_source.get("sha256") != canonical_source.get("sha256"):
            raise Stage1CertificationGateError("canonical source SHA differs from manifest authority")
        if manifest_source.get("bytes") != canonical_source.get("bytes"):
            raise Stage1CertificationGateError("canonical source bytes differ from manifest authority")
        if manifest_source.get("path") != canonical_source.get("path"):
            raise Stage1CertificationGateError("canonical source path differs from manifest authority")
        gate["source_manifest_authority"] = source_manifest_authority

    revalidated = validate_stage1_evidence(
        gate,
        canonical_sha256=str(canonical_source["sha256"]),
        stage1_sha256=stage1_entry["sha256"],
        root=root,
        contract=contract,
    )
    gate["evidence_revalidation"] = revalidated
    return gate


def emit_gate(
    *,
    stage1: Path,
    source: Path,
    contract_path: Path,
    output_path: Path,
    evidence_paths: dict[str, str] | None = None,
) -> dict[str, Any]:
    contract, contract_authority = require_authoritative_contract(
        contract_path,
        authoritative=DEFAULT_CONTRACT,
        expected_schema="s3.selfhost.stage1-certification-gate-contract.v3",
        label="Stage1 certification contract",
    )
    canonical_path, _canonical_bytes, _manifest, source_manifest_authority = (
        require_authoritative_source_manifest(
            DEFAULT_MANIFEST,
            authoritative=DEFAULT_MANIFEST,
            root=ROOT,
        )
    )
    if source.resolve() != canonical_path.resolve():
        raise Stage1CertificationGateError(
            "--source must resolve to the exact canonical compiler source declared by compiler-sources.json"
        )
    canonical = git_head_source_binding(canonical_path)
    gate = build_gate(
        canonical_source=canonical,
        stage1_path=stage1,
        evidence_paths=DEFAULT_EVIDENCE_PATHS if evidence_paths is None else evidence_paths,
        contract=contract,
        root=ROOT,
        contract_authority=contract_authority,
        source_manifest_authority=source_manifest_authority,
    )

    output = output_path.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(gate, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    written = _load_json(output, "written Stage1 certification gate")
    validate_stage1_evidence(
        written,
        canonical_sha256=str(canonical["sha256"]),
        stage1_sha256=str(gate["stage1_artifact"]["sha256"]),
        root=ROOT,
        contract=contract,
    )
    return written


def _parse_evidence_overrides(values: list[str]) -> dict[str, str]:
    result = dict(DEFAULT_EVIDENCE_PATHS)
    for raw in values:
        if "=" not in raw:
            raise Stage1CertificationGateError(
                f"--evidence must be ROLE=repository/path.json, got {raw!r}"
            )
        role, path = raw.split("=", 1)
        if role not in result or not path:
            raise Stage1CertificationGateError(
                f"invalid evidence override {raw!r}"
            )
        result[role] = path
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage1", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--evidence",
        action="append",
        default=[],
        metavar="ROLE=PATH",
        help=(
            "override a default repository-relative evidence report path; "
            "--contract may relocate only an exact byte-identical canonical policy"
        ),
    )
    args = parser.parse_args(argv)
    try:
        gate = emit_gate(
            stage1=args.stage1,
            source=args.source,
            contract_path=args.contract,
            output_path=args.output,
            evidence_paths=_parse_evidence_overrides(args.evidence),
        )
    except (
        OSError,
        UnicodeError,
        ContractAuthorityError,
        SourceAuthorityError,
        Stage1CertificationEvidenceError,
        Stage1CertificationGateError,
    ) as error:
        parser.exit(2, f"Stage1 certification gate blocked: {error}\n")

    print(f"GATE={args.output.resolve()}")
    print(f"CANONICAL_SHA256={gate['canonical_source']['sha256']}")
    print(f"CANONICAL_COMMIT={gate['canonical_source']['commit']}")
    print(f"STAGE1_SHA256={gate['stage1_artifact']['sha256']}")
    print(f"CONTRACT_AUTHORITY={gate['contract_authority']['status']}")
    print(f"CONTRACT_SHA256={gate['contract_authority']['sha256']}")
    print(f"SOURCE_MANIFEST_AUTHORITY={gate['source_manifest_authority']['status']}")
    print(f"SOURCE_MANIFEST_SHA256={gate['source_manifest_authority']['sha256']}")
    print("EVIDENCE_REVALIDATION=PASS_STAGE1_HASHED_EVIDENCE_REVALIDATION")
    print("STAGE1_CERTIFIED_FOR_STAGE2=YES")
    print("STAGE2_CERTIFIED=NO")
    print("FULL_SELF_HOSTING=NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
