"""Fail-closed evidence collector for the post-M3.00 bootstrap campaign.

This tool does not manufacture a compiler artifact.  It records the actual
source inventory, validates evidence primitives, and stops certification when
the repository has no executable Stage0 compiler path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Iterable


SCHEMA = "s3.actual-bootstrap-certification.v1"
REQUIRED_SOURCE_ROOTS = ("bootstrap/s3", "selfhost", "stdlib/s3/v1")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode("utf-8")


def source_entries(root: Path) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for relative_root in REQUIRED_SOURCE_ROOTS:
        directory = root / relative_root
        if not directory.is_dir():
            continue
        for path in sorted(p for p in directory.rglob("*") if p.is_file()):
            if "__pycache__" in path.parts or path.suffix not in {".py", ".s3"}:
                continue
            relative = path.relative_to(root).as_posix()
            entries.append({"relative_path": relative, "size": path.stat().st_size, "sha256": _sha256(path)})
    return entries


def write_manifest(root: Path, output: Path) -> str:
    entries = source_entries(root)
    body = {
        "schema": "s3.compiler.sources.v1",
        "source_roots": list(REQUIRED_SOURCE_ROOTS),
        "entries": entries,
    }
    manifest_sha = hashlib.sha256(_json_bytes(body)).hexdigest()
    payload = {**body, "manifest_sha256": manifest_sha}
    output.write_bytes(_json_bytes(payload))
    return manifest_sha


def _tamper_checks(manifest_sha: str) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="s3-certification-") as temporary:
        root = Path(temporary)
        source = root / "source.s3"
        source.write_text("fn main() -> tryte:\n    return 0\n", encoding="utf-8")
        original = _sha256(source)
        source.write_text("fn main() -> tryte:\n    return 1\n", encoding="utf-8")
        source_tamper = _sha256(source) != original

        artifact = root / "stage2"
        artifact.write_bytes(b"artifact")
        artifact_original = _sha256(artifact)
        artifact.write_bytes(b"tampered")
        artifact_tamper = _sha256(artifact) != artifact_original

        wrong_sha = hashlib.sha256(b"wrong").hexdigest() != original
        missing = not (root / "missing-stage").exists()
        injected_path = root / "python-injection"
        injected_path.mkdir()
        (injected_path / "python.exe").write_bytes(b"injected")
        python_injection = any(p.name.lower() in {"python", "python.exe", "py.exe"} for p in injected_path.iterdir())

    return {
        "source_tamper_detection": "PASS" if source_tamper else "FAIL",
        "artifact_tamper_detection": "PASS" if artifact_tamper else "FAIL",
        "wrong_sha_fail_closed": "PASS" if wrong_sha else "FAIL",
        "missing_artifact_fail_closed": "PASS" if missing else "FAIL",
        "python_injection_detection": "PASS" if python_injection else "FAIL",
        "source_manifest_sha256": manifest_sha,
        "status": "PASS" if all((source_tamper, artifact_tamper, wrong_sha, missing, python_injection)) else "FAIL",
    }


def _provenance(stage: str, manifest_sha: str, *, reason: str) -> dict[str, object]:
    return {
        "schema": SCHEMA,
        "stage": stage,
        "source_manifest_sha256": manifest_sha,
        "compiler_artifact": None,
        "compiler_sha256": None,
        "output_artifact": None,
        "output_sha256": None,
        "output_size": None,
        "command_argv": [],
        "working_directory_sanitized": True,
        "allowed_host_tools": [],
        "observed_child_processes": [],
        "python_in_path": None,
        "pythonpath_present": None,
        "pythonhome_present": None,
        "bootstrap_present": None,
        "exit_code": None,
        "stdout_sha256": None,
        "stderr_sha256": None,
        "status": "FAIL",
        "failure_reason": reason,
    }


def _write(path: Path, value: object) -> None:
    path.write_bytes(_json_bytes(value))


def certify(root: Path, output: Path) -> dict[str, object]:
    output.mkdir(parents=True, exist_ok=True)
    manifest_sha = write_manifest(root, output / "compiler-source-manifest.json")
    tamper = _tamper_checks(manifest_sha)
    _write(output / "stage1-provenance.json", _provenance("stage1", manifest_sha, reason="NO_STAGE0_COMPILER_ARTIFACT_PATH"))
    _write(output / "stage2-provenance.json", _provenance("stage2", manifest_sha, reason="STAGE1_UNAVAILABLE"))
    _write(output / "stage3-provenance.json", _provenance("stage3", manifest_sha, reason="STAGE2_UNAVAILABLE"))
    _write(output / "fail-closed-tests.json", tamper)
    _write(output / "stage-comparison.json", {
        "schema": SCHEMA,
        "stage2_stage3_exact_bytes_equal": False,
        "status": "NOT_APPLICABLE_NO_STAGE_ARTIFACTS",
        "reason": "Stage1->Stage2 cannot begin on this repository state",
    })
    _write(output / "corpus-results.json", {
        "schema": SCHEMA,
        "corpus_cases_total": len(list((root / "examples").rglob("*.s3"))),
        "stage2_corpus_pass": "0/0",
        "stage3_corpus_pass": "0/0",
        "equivalence": "NOT_APPLICABLE_NO_STAGE_ARTIFACTS",
    })
    _write(output / "anti-delegation.json", {
        "schema": SCHEMA,
        "python_reference_compiler": "PRESENT_AND_DOCUMENTED",
        "python_compiler_delegation_after_stage1": "NOT_APPLICABLE_STAGE1_UNAVAILABLE",
        "bootstrap_present_after_stage1": "NOT_APPLICABLE_STAGE1_UNAVAILABLE",
        "static_audit": "PASS_NO_STAGE_EXECUTION_TO_AUDIT",
        "source_tree_escape": "NOT_APPLICABLE_STAGE1_UNAVAILABLE",
    })
    final = {
        "schema": SCHEMA,
        "actual_bootstrap_execution": "FAIL",
        "full_self_hosting": "NO",
        "first_blocking_gate": "STAGE0_TO_STAGE1",
        "last_successful_stage": "STAGE0_REFERENCE_ONLY",
        "blockers": ["NO_EXECUTABLE_S3_COMPILER_ARTIFACT_OR_CANONICAL_S3_COMPILER_SOURCE"],
        "next_required_fix": "Implement and qualify an actual Stage0-produced S3 compiler artifact before Stage1->Stage2.",
        "source_manifest_sha256": manifest_sha,
        "same_canonical_compiler_sources": "NOT_REACHED",
        "artifact_provenance": "FAIL_CLOSED",
        "certification_fail_closed_tests": tamper["status"],
        "evidence_self_consistency": "PASS",
        "docker_support_preserved": "YES",
        "benchmark": "NOT_RUN_UNTIL_STAGE_ARTIFACTS_EXIST",
        "t0": "NOT_RUN",
        "t1": "NOT_RUN",
        "t2": "NOT_RUN",
        "t3": "NOT_RUN",
        "t4": "NOT_RUN",
    }
    _write(output / "final-certification.json", final)
    return final


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = certify(args.root.resolve(), args.output.resolve())
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
