"""Promote the qualified compaction-first IR-v2 capacity candidate.

This tool is intentionally fail-closed.  It never treats static projections as
native evidence.  It validates the Linux x86-64 candidate report against the
current canonical source, deterministically rebuilds the candidate with the
same S3-source transform, and only rewrites the canonical source/manifest when
--in-place is explicitly requested.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from tools.patch_stage1_codegen_ir_v2_capacity import (
    BASELINE_SOURCE_SHA256,
    transform,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "selfhost" / "compiler" / "s3c_stage1.s3"
MANIFEST = ROOT / "selfhost" / "compiler" / "compiler-sources.json"
DEFAULT_REPORT = (
    ROOT
    / "reports"
    / "selfhost"
    / "stage1"
    / "codegen-ir-v2-capacity-native-candidate.json"
)


class PromotionError(RuntimeError):
    """Raised when native evidence is insufficient or inconsistent."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PromotionError(message)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PromotionError(f"cannot read valid JSON from {path}: {error}") from error
    if not isinstance(value, dict):
        raise PromotionError(f"expected JSON object in {path}")
    return value


def validate_native_report(
    report: dict[str, Any],
    *,
    canonical_bytes: bytes,
) -> tuple[bytes, dict[str, Any]]:
    """Validate report provenance and return the deterministic candidate bytes."""

    canonical_sha = _sha256(canonical_bytes)
    _require(
        canonical_sha == BASELINE_SOURCE_SHA256,
        "canonical source no longer matches the qualified pre-IR-v2 baseline",
    )

    _require(
        report.get("schema")
        == "s3.selfhost.codegen-ir-v2-capacity-native-candidate.v1",
        "unexpected native candidate report schema",
    )

    platform_info = report.get("platform") or {}
    _require(platform_info.get("system") == "Linux", "candidate was not qualified on Linux")
    _require(
        str(platform_info.get("machine", "")).lower() in {"x86_64", "amd64"},
        "candidate was not qualified on Linux x86-64",
    )
    _require(
        report.get("canonical_source_mutated") is False,
        "qualification report says the canonical source was mutated",
    )

    baseline = report.get("baseline") or {}
    _require(
        baseline.get("source_sha256") == canonical_sha,
        "report baseline SHA does not match current canonical source",
    )
    _require(
        baseline.get("source_bytes") == len(canonical_bytes),
        "report baseline byte count does not match current canonical source",
    )
    _require(baseline.get("native_events") == 1460, "unexpected native event baseline")
    _require(baseline.get("native_discard_events") == 699, "unexpected discard baseline")
    _require(baseline.get("event_capacity") == 1460, "unexpected event capacity")
    _require(baseline.get("parameter_capacity") == 64, "unexpected parameter capacity")
    _require(baseline.get("call_capacity") == 730, "unexpected call capacity")
    _require(baseline.get("call_argument_capacity") == 746, "unexpected call-argument capacity")

    contract_tests = report.get("contract_tests") or {}
    _require(contract_tests.get("status") == "PASS", "contract/capacity tests did not pass")

    qualification = report.get("qualification") or {}
    _require(qualification.get("contract_tests") == "PASS", "qualification did not record contract-test PASS")
    _require(qualification.get("candidate_build") == "PASS", "candidate build did not pass")
    _require(qualification.get("trivial_compile") == "PASS", "trivial compile did not pass")
    _require(
        qualification.get("self_source_expected_boundary") == "PASS",
        "candidate self-source did not reach the expected emitter boundary",
    )
    _require(qualification.get("audit_invariants") == "PASS", "native audit invariants did not pass")
    _require(qualification.get("event_headroom") == "PASS", "native event headroom did not pass")
    _require(
        qualification.get("capacity_candidate") == "PASS_NATIVE_CANDIDATE",
        "capacity candidate is not a native PASS candidate",
    )
    _require(
        qualification.get("canonical_commit_allowed") is True,
        "native report does not allow canonical promotion",
    )
    _require(qualification.get("stage2") == "NOT_STARTED", "Stage2 must not have started")
    _require(qualification.get("stage3") == "NOT_STARTED", "Stage3 must not have started")
    _require(qualification.get("full_self_hosting") is False, "full self-hosting must remain false")

    self_source = report.get("self_source") or {}
    _require(
        self_source.get("status") == "PASS_THROUGH_VERIFY_TO_EXPECTED_EMITTER_BOUNDARY",
        "unexpected self-source qualification status",
    )
    _require(self_source.get("returncode") == 2, "expected fail-closed emitter boundary exit 2")
    _require(self_source.get("stdout_bytes") == 0, "self-source qualification wrote unexpected stdout")
    _require(
        self_source.get("final_marker") == "S3_STAGE1_EMITTER_BLOCKED",
        "missing expected fail-closed emitter marker",
    )
    audit = self_source.get("audit")
    _require(isinstance(audit, dict), "native audit counters are missing")

    actual_events = audit.get("ir_instruction_count")
    actual_discards = audit.get("ast_discard_count")
    _require(isinstance(actual_events, int), "native instruction/event count is missing")
    _require(0 < actual_events < 1460, "native compaction did not create event headroom")
    _require(actual_discards == 699, "discard audit count changed during compaction")
    _require(audit.get("parameter_count") == 64, "parameter count changed during compaction")
    _require(audit.get("ast_call_count") == 656, "call count changed during compaction")
    _require(audit.get("ir_value_count") == 1213, "value count changed during compaction")
    _require(audit.get("ir_block_count") == 305, "block count changed during compaction")

    audit_invariants = report.get("audit_invariants") or {}
    expected_invariants = {
        "discard_count_preserved",
        "parameter_count_preserved",
        "call_count_preserved",
        "value_count_preserved",
        "block_count_preserved",
    }
    _require(expected_invariants <= set(audit_invariants), "native audit invariant fields are incomplete")
    _require(all(audit_invariants[name] is True for name in expected_invariants), "one or more native audit invariants failed")

    measurement = report.get("capacity_measurement") or {}
    _require(
        measurement.get("actual_ir_instruction_count") == actual_events,
        "capacity measurement disagrees with native audit",
    )
    _require(
        measurement.get("actual_ast_discard_count") == actual_discards,
        "discard measurement disagrees with native audit",
    )
    _require(
        measurement.get("actual_event_reduction_from_native_baseline")
        == 1460 - actual_events,
        "reported event reduction is inconsistent",
    )
    _require(
        measurement.get("actual_event_headroom") == 1460 - actual_events,
        "reported event headroom is inconsistent",
    )
    _require(
        measurement.get("projection_is_not_substituted_for_native_measurement") is True,
        "report does not preserve projection/native-evidence distinction",
    )

    candidate_bytes = transform(canonical_bytes.decode("utf-8")).encode("utf-8")
    candidate = report.get("candidate") or {}
    _require(
        candidate.get("transform") == "DROP_REDUNDANT_DISCARD_KEYWORD_EVENT",
        "unexpected candidate transform",
    )
    _require(
        candidate.get("source_sha256") == _sha256(candidate_bytes),
        "native report candidate SHA does not match deterministic transform",
    )
    _require(
        candidate.get("source_bytes") == len(candidate_bytes),
        "native report candidate byte count does not match deterministic transform",
    )

    return candidate_bytes, audit


def validate_manifest(manifest: dict[str, Any], canonical_bytes: bytes) -> None:
    _require(manifest.get("schema") == "s3.compiler.sources.v1", "unexpected source manifest schema")
    _require(manifest.get("source_count") == 1, "expected one canonical Stage1 source")
    _require(manifest.get("total_bytes") == len(canonical_bytes), "manifest total_bytes is stale")
    sources = manifest.get("sources")
    _require(isinstance(sources, list) and len(sources) == 1, "manifest sources must contain one entry")
    entry = sources[0]
    _require(entry.get("path") == "selfhost/compiler/s3c_stage1.s3", "unexpected canonical source path")
    _require(entry.get("sha256") == _sha256(canonical_bytes), "manifest source SHA is stale")
    _require(entry.get("role") == "canonical_stage1_compiler", "unexpected canonical source role")
    _require(entry.get("ordering") == 0, "unexpected canonical source ordering")


def promoted_manifest(manifest: dict[str, Any], candidate_bytes: bytes) -> dict[str, Any]:
    result = json.loads(json.dumps(manifest))
    result["total_bytes"] = len(candidate_bytes)
    result["sources"][0]["sha256"] = _sha256(candidate_bytes)
    return result


def _write_promoted_pair(
    *,
    candidate_bytes: bytes,
    new_manifest: dict[str, Any],
    original_source: bytes,
    original_manifest: bytes,
) -> None:
    """Replace source+manifest with rollback on any write/verification failure."""

    source_tmp = SOURCE.with_name(SOURCE.name + ".ir-v2-promote.tmp")
    manifest_tmp = MANIFEST.with_name(MANIFEST.name + ".ir-v2-promote.tmp")
    manifest_payload = (json.dumps(new_manifest, indent=2) + "\n").encode("utf-8")

    try:
        source_tmp.write_bytes(candidate_bytes)
        manifest_tmp.write_bytes(manifest_payload)
        _require(source_tmp.read_bytes() == candidate_bytes, "temporary promoted source verification failed")
        staged_manifest = json.loads(manifest_tmp.read_text(encoding="utf-8"))
        validate_manifest(staged_manifest, candidate_bytes)

        source_tmp.replace(SOURCE)
        manifest_tmp.replace(MANIFEST)

        _require(SOURCE.read_bytes() == candidate_bytes, "post-write canonical source verification failed")
        validate_manifest(_load_json(MANIFEST), candidate_bytes)
    except Exception as error:
        rollback_errors: list[str] = []
        try:
            SOURCE.write_bytes(original_source)
        except OSError as rollback_error:
            rollback_errors.append(f"source rollback failed: {rollback_error}")
        try:
            MANIFEST.write_bytes(original_manifest)
        except OSError as rollback_error:
            rollback_errors.append(f"manifest rollback failed: {rollback_error}")
        detail = f"promotion write failed and was rolled back: {error}"
        if rollback_errors:
            detail += "; " + "; ".join(rollback_errors)
        raise PromotionError(detail) from error
    finally:
        source_tmp.unlink(missing_ok=True)
        manifest_tmp.unlink(missing_ok=True)


def promote(*, report_path: Path, in_place: bool) -> dict[str, Any]:
    canonical_bytes = SOURCE.read_bytes()
    manifest_bytes = MANIFEST.read_bytes()
    manifest = _load_json(MANIFEST)
    validate_manifest(manifest, canonical_bytes)
    report = _load_json(report_path)
    candidate_bytes, audit = validate_native_report(report, canonical_bytes=canonical_bytes)
    new_manifest = promoted_manifest(manifest, candidate_bytes)

    result = {
        "status": "VALIDATED_NATIVE_CANDIDATE",
        "canonical_source_before_sha256": _sha256(canonical_bytes),
        "canonical_source_after_sha256": _sha256(candidate_bytes),
        "canonical_source_after_bytes": len(candidate_bytes),
        "native_ir_instruction_count": audit["ir_instruction_count"],
        "native_event_headroom": 1460 - audit["ir_instruction_count"],
        "write_requested": in_place,
        "canonical_source_mutated": False,
    }

    if in_place:
        _write_promoted_pair(
            candidate_bytes=candidate_bytes,
            new_manifest=new_manifest,
            original_source=canonical_bytes,
            original_manifest=manifest_bytes,
        )
        result["canonical_source_mutated"] = True
        result["status"] = "PROMOTED_NATIVE_QUALIFIED_CANDIDATE"

    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="after full native-report validation, transactionally rewrite canonical source and manifest",
    )
    args = parser.parse_args(argv)

    try:
        result = promote(report_path=args.report.resolve(), in_place=args.in_place)
    except PromotionError as error:
        parser.exit(2, f"promotion blocked: {error}\n")

    print(f"STATUS={result['status']}")
    print(f"SOURCE_BEFORE_SHA256={result['canonical_source_before_sha256']}")
    print(f"SOURCE_AFTER_SHA256={result['canonical_source_after_sha256']}")
    print(f"SOURCE_AFTER_BYTES={result['canonical_source_after_bytes']}")
    print(f"NATIVE_IR_INSTRUCTION_COUNT={result['native_ir_instruction_count']}")
    print(f"NATIVE_EVENT_HEADROOM={result['native_event_headroom']}")
    print(f"CANONICAL_SOURCE_MUTATED={result['canonical_source_mutated']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
