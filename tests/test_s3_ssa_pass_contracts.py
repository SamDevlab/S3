from __future__ import annotations

import pytest

from bootstrap.s3.metrics import FixpointTelemetry
from bootstrap.s3.ssa_opt import SSA_PASS_CONTRACTS, _FIXPOINT_PASSES
from bootstrap.s3.ssa_optimizer import SSAPassContract


def test_ssa_pass_contract_inventory_matches_active_fixpoint_passes() -> None:
    names = tuple(contract.name for contract in SSA_PASS_CONTRACTS)

    assert names == (
        "gvn",
        "copy_propagation",
        "dse",
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
