"""Fail closed when a Stage1 tool profile is incompatible with current source IR epoch."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.audit_stage1_representation_epoch import (
    DEFAULT_CONTRACT as DEFAULT_EPOCH_CONTRACT,
    RepresentationEpochError,
    classify_source,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "selfhost" / "compiler" / "s3c_stage1.s3"
DEFAULT_COMPATIBILITY = (
    ROOT / "reports" / "selfhost" / "stage1" / "representation-tool-compatibility.json"
)


class RepresentationCompatibilityError(RuntimeError):
    pass


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise RepresentationCompatibilityError(f"{label} is missing: {path}") from error
    except json.JSONDecodeError as error:
        raise RepresentationCompatibilityError(f"{label} is invalid JSON: {path}") from error
    if not isinstance(value, dict):
        raise RepresentationCompatibilityError(f"{label} must be a JSON object")
    return value


def evaluate_profile(
    epoch_report: dict[str, Any],
    *,
    profile_name: str,
    compatibility: dict[str, Any],
) -> dict[str, Any]:
    if compatibility.get("schema") != "s3.selfhost.stage1-representation-tool-compatibility.v1":
        raise RepresentationCompatibilityError("representation compatibility schema mismatch")
    if epoch_report.get("schema") != "s3.selfhost.stage1-representation-epoch.v1":
        raise RepresentationCompatibilityError("representation epoch schema mismatch")
    if epoch_report.get("status") != "PASS_REPRESENTATION_EPOCH_CLASSIFIED":
        raise RepresentationCompatibilityError("representation epoch is inconsistent")

    profiles = compatibility.get("profiles")
    if not isinstance(profiles, dict):
        raise RepresentationCompatibilityError("compatibility contract lacks profiles")
    profile = profiles.get(profile_name)
    if not isinstance(profile, dict):
        raise RepresentationCompatibilityError(f"unknown representation compatibility profile: {profile_name}")

    representation = epoch_report.get("representation")
    if not isinstance(representation, dict):
        raise RepresentationCompatibilityError("representation epoch report lacks representation data")
    epoch = representation.get("epoch")
    if isinstance(epoch, bool) or not isinstance(epoch, int) or epoch < 0:
        raise RepresentationCompatibilityError("invalid representation epoch value")

    reasons: list[str] = []
    allowed_epochs = profile.get("allowed_epochs")
    if allowed_epochs is not None:
        if not isinstance(allowed_epochs, list) or not all(isinstance(item, int) and not isinstance(item, bool) for item in allowed_epochs):
            raise RepresentationCompatibilityError(f"profile {profile_name} has invalid allowed_epochs")
        if epoch not in allowed_epochs:
            reasons.append(
                "EPOCH_NOT_ALLOWED:" + str(epoch) + " not in " + ",".join(str(item) for item in allowed_epochs)
            )

    minimum_epoch = profile.get("minimum_epoch")
    if minimum_epoch is not None:
        if isinstance(minimum_epoch, bool) or not isinstance(minimum_epoch, int) or minimum_epoch < 0:
            raise RepresentationCompatibilityError(f"profile {profile_name} has invalid minimum_epoch")
        if epoch < minimum_epoch:
            reasons.append(f"EPOCH_TOO_OLD:{epoch}<{minimum_epoch}")

    if profile.get("forbid_packed_parameter") is True and representation.get("packed_parameter_record_present") is True:
        reasons.append("PACKED_PARAMETER_FORBIDDEN")
    if profile.get("forbid_packed_local") is True and representation.get("packed_local_record_present") is True:
        reasons.append("PACKED_LOCAL_FORBIDDEN")

    passed = not reasons
    return {
        "schema": "s3.selfhost.stage1-representation-tool-compatibility-check.v1",
        "status": "PASS_REPRESENTATION_COMPATIBILITY" if passed else "BLOCKED_REPRESENTATION_COMPATIBILITY",
        "native_evidence": False,
        "profile": profile_name,
        "source": dict(epoch_report.get("source", {})),
        "representation": {
            "epoch": epoch,
            "name": representation.get("name"),
            "packed_parameter_record_present": representation.get("packed_parameter_record_present"),
            "packed_local_record_present": representation.get("packed_local_record_present"),
            "explicit_parameter_metadata_complete": representation.get("explicit_parameter_metadata_complete"),
            "explicit_local_metadata_complete": representation.get("explicit_local_metadata_complete"),
        },
        "compatible": passed,
        "reasons": reasons,
        "profile_reason": profile.get("reason"),
        "qualification": {
            "tool_may_continue_to_its_own_source_sha_and_native_gates": passed,
            "this_check_is_native_evidence": False,
            "stage2_allowed": False,
            "full_self_hosting": False,
            "next": (
                "RUN_TOOL_SPECIFIC_SOURCE_SHA_AND_QUALIFICATION_GATES"
                if passed
                else "DO_NOT_REAPPLY_HISTORICAL_TRANSFORM;_MIGRATE_OR_USE_CURRENT_REPRESENTATION_AUDITOR"
            ),
        },
    }


def check_source(
    source_bytes: bytes,
    *,
    profile_name: str,
    epoch_contract: dict[str, Any],
    compatibility: dict[str, Any],
) -> dict[str, Any]:
    try:
        source_text = source_bytes.decode("utf-8")
        epoch_report = classify_source(
            source_text,
            source_bytes=source_bytes,
            contract=epoch_contract,
        )
    except (UnicodeDecodeError, RepresentationEpochError) as error:
        raise RepresentationCompatibilityError(str(error)) from error
    return evaluate_profile(
        epoch_report,
        profile_name=profile_name,
        compatibility=compatibility,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--epoch-contract", type=Path, default=DEFAULT_EPOCH_CONTRACT)
    parser.add_argument("--compatibility", type=Path, default=DEFAULT_COMPATIBILITY)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)

    try:
        result = check_source(
            args.source.resolve().read_bytes(),
            profile_name=args.profile,
            epoch_contract=_load_json(args.epoch_contract.resolve(), "representation epoch contract"),
            compatibility=_load_json(args.compatibility.resolve(), "representation compatibility contract"),
        )
    except (OSError, RepresentationCompatibilityError) as error:
        parser.exit(2, f"Stage1 representation compatibility blocked: {error}\n")

    if args.report is not None:
        destination = args.report.resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        print(f"REPORT={destination}")
    print(f"STATUS={result['status']}")
    print(f"PROFILE={result['profile']}")
    print(f"EPOCH={result['representation']['epoch']}")
    print(f"COMPATIBLE={result['compatible']}")
    print("REASONS=" + ",".join(result["reasons"]))
    print(f"NEXT={result['qualification']['next']}")
    return 0 if result["compatible"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
