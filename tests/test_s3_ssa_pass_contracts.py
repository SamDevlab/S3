from __future__ import annotations

import pytest

from bootstrap.s3.metrics import FixpointTelemetry
from bootstrap.s3.ssa_opt import SSA_PASS_CONTRACTS, _FIXPOINT_PASSES
from bootstrap.s3.ssa_optimizer import PassResult, SSAPassContract

pytestmark = [pytest.mark.s3_fast, pytest.mark.s3_contract]


def test_ssa_pass_contract_inventory_matches_active_fixpoint_passes() -> None:
    names = tuple(contract.name for contract in SSA_PASS_CONTRACTS)

    assert names == (
        "gvn",
        "copy_propagation",
        "dse",
        "global_dse",
        "dce",
        "adce",
        "licm",
        "sccp",
        "strength_reduction",
        "peephole",
    )
    assert _FIXPOINT_PASSES == set(names)
    assert "cse" not in names


def test_ssa_pass_contracts_are_internal_and_well_formed() -> None:
    telemetry_fields = set(FixpointTelemetry.__dataclass_fields__)

    for contract in SSA_PASS_CONTRACTS:
        assert contract.requires_ssa is True
        assert contract.preserves_ssa is True
        assert set(contract.telemetry_fields) <= telemetry_fields


def test_ssa_pass_contracts_capture_current_cfg_mutation_boundary() -> None:
    contracts = {contract.name: contract for contract in SSA_PASS_CONTRACTS}

    assert contracts["sccp"].mutates_cfg is True
    for name, contract in contracts.items():
        if name != "sccp":
            assert contract.mutates_cfg is False


def test_ssa_pass_contract_rejects_invalid_shape() -> None:
    with pytest.raises(ValueError, match="name must be non-empty"):
        SSAPassContract("", True, True, False)
    with pytest.raises(ValueError, match="must require SSA"):
        SSAPassContract("bad", False, True, False)
    with pytest.raises(ValueError, match="must preserve SSA"):
        SSAPassContract("bad", True, False, False)
    with pytest.raises(ValueError, match="duplicate required analyses"):
        SSAPassContract(
            "bad",
            True,
            True,
            False,
            required_analyses=("cfg", "cfg"),
        )


def test_pass_result_accepts_unmetered_structural_change() -> None:
    token = object()

    result = PassResult(function=token, changed=True)

    assert result.function is token
    assert result.changed is True
    assert result.telemetry == ()


def test_pass_result_rejects_invalid_telemetry() -> None:
    token = object()

    with pytest.raises(ValueError, match="non-negative"):
        PassResult(
            function=token,
            changed=True,
            telemetry=(("expressions_eliminated", -1),),
        )
    with pytest.raises(ValueError, match="duplicate telemetry fields"):
        PassResult(
            function=token,
            changed=True,
            telemetry=(
                ("expressions_eliminated", 1),
                ("expressions_eliminated", 1),
            ),
        )
