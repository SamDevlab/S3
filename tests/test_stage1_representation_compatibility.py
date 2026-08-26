from __future__ import annotations

import pytest

from tools.audit_stage1_representation_epoch import classify_source
from tools.check_stage1_representation_compatibility import (
    RepresentationCompatibilityError,
    evaluate_profile,
)


pytestmark = pytest.mark.s3_fast


def _epoch_contract() -> dict[str, object]:
    return {
        "schema": "s3.selfhost.stage1-representation-epoch-contract.v1",
        "output_schema": "s3.selfhost.stage1-representation-epoch.v1",
        "explicit_parameter_arrays_required": [
            "ir_parameter_owner",
            "ir_parameter_name",
            "ir_parameter_ordinal",
            "ir_parameter_type",
        ],
        "packed_parameter_marker": "ir_parameter_records",
        "packed_local_marker": "ir_local_records",
        "explicit_local_array_minimum": 8,
        "local_array_prefix": "ir_local_",
        "local_array_exclusions": ["ir_local_records"],
    }


def _compatibility() -> dict[str, object]:
    return {
        "schema": "s3.selfhost.stage1-representation-tool-compatibility.v1",
        "profiles": {
            "legacy_packed_parameter_candidate_builder": {
                "allowed_epochs": [0],
                "reason": "legacy parameter builder",
            },
            "legacy_packed_local_candidate_builder_from_canonical": {
                "allowed_epochs": [0],
                "reason": "legacy local builder",
            },
            "legacy_ir_v2_full_chain": {
                "allowed_epochs": [0],
                "reason": "legacy chain",
            },
            "explicit_parameter_metadata_consumer": {
                "minimum_epoch": 2,
                "forbid_packed_parameter": True,
                "reason": "explicit parameter consumer",
            },
            "explicit_parameter_local_metadata_consumer": {
                "minimum_epoch": 3,
                "forbid_packed_parameter": True,
                "forbid_packed_local": True,
                "reason": "explicit local consumer",
            },
        },
    }


def _arrays(names: list[str]) -> str:
    return "\n".join(f"    mut {name}: i64[8] = [0, 0, 0, 0, 0, 0, 0, 0]" for name in names)


def _report(epoch: int) -> dict[str, object]:
    parameter = ["ir_parameter_owner", "ir_parameter_name", "ir_parameter_ordinal", "ir_parameter_type"]
    local = [
        "ir_local_owner",
        "ir_local_name",
        "ir_local_type",
        "ir_local_mutability",
        "ir_local_storage_kind",
        "ir_local_ordinal",
        "ir_local_extent",
        "ir_local_value_id",
    ]
    names: list[str]
    if epoch == 0:
        names = []
    elif epoch == 1:
        names = ["ir_parameter_records"]
    elif epoch == 2:
        names = parameter
    elif epoch == 3:
        names = parameter + local
    else:
        raise AssertionError(epoch)
    source = "fn main() -> tryte:\n" + (_arrays(names) + "\n" if names else "") + "    return 0\n"
    return classify_source(source, contract=_epoch_contract())


@pytest.mark.parametrize(
    "profile",
    [
        "legacy_packed_parameter_candidate_builder",
        "legacy_packed_local_candidate_builder_from_canonical",
        "legacy_ir_v2_full_chain",
    ],
)
def test_historical_profiles_accept_only_epoch_zero(profile: str) -> None:
    assert evaluate_profile(_report(0), profile_name=profile, compatibility=_compatibility())["compatible"] is True
    for epoch in (1, 2, 3):
        result = evaluate_profile(_report(epoch), profile_name=profile, compatibility=_compatibility())
        assert result["compatible"] is False
        assert any(reason.startswith("EPOCH_NOT_ALLOWED") for reason in result["reasons"])


def test_explicit_parameter_consumer_requires_epoch_two_or_newer() -> None:
    for epoch in (0, 1):
        assert evaluate_profile(
            _report(epoch),
            profile_name="explicit_parameter_metadata_consumer",
            compatibility=_compatibility(),
        )["compatible"] is False
    for epoch in (2, 3):
        assert evaluate_profile(
            _report(epoch),
            profile_name="explicit_parameter_metadata_consumer",
            compatibility=_compatibility(),
        )["compatible"] is True


def test_explicit_local_consumer_requires_epoch_three() -> None:
    for epoch in (0, 1, 2):
        assert evaluate_profile(
            _report(epoch),
            profile_name="explicit_parameter_local_metadata_consumer",
            compatibility=_compatibility(),
        )["compatible"] is False
    assert evaluate_profile(
        _report(3),
        profile_name="explicit_parameter_local_metadata_consumer",
        compatibility=_compatibility(),
    )["compatible"] is True


def test_unknown_profile_fails_closed() -> None:
    with pytest.raises(RepresentationCompatibilityError, match="unknown"):
        evaluate_profile(_report(0), profile_name="does_not_exist", compatibility=_compatibility())


def test_inconsistent_epoch_fails_before_profile_evaluation() -> None:
    source = "fn main() -> tryte:\n" + _arrays([
        "ir_parameter_records",
        "ir_parameter_owner",
        "ir_parameter_name",
        "ir_parameter_ordinal",
        "ir_parameter_type",
    ]) + "\n    return 0\n"
    inconsistent = classify_source(source, contract=_epoch_contract())
    assert inconsistent["status"] == "BLOCKED_REPRESENTATION_EPOCH_INCONSISTENT"
    with pytest.raises(RepresentationCompatibilityError, match="inconsistent"):
        evaluate_profile(
            inconsistent,
            profile_name="legacy_ir_v2_full_chain",
            compatibility=_compatibility(),
        )
