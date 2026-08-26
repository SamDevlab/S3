from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.audit_stage1_banked_storage_roundtrip import (
    BankLayout,
    BankLayoutError,
    BankLocation,
    SIGNED_I64_MAX,
    SIGNED_I64_MIN,
    audit,
    audit_layout,
)


pytestmark = pytest.mark.s3_fast


def _contract() -> dict[str, object]:
    root = Path(__file__).resolve().parents[1]
    return json.loads(
        (
            root
            / "reports"
            / "selfhost"
            / "stage1"
            / "banked-storage-roundtrip-contract.json"
        ).read_text(encoding="utf-8")
    )


@pytest.mark.parametrize(
    "capacities, probes",
    [
        ((365, 365), {0: (0, 0), 364: (0, 364), 365: (1, 0), 729: (1, 364)}),
        (
            (365, 365, 16),
            {
                0: (0, 0),
                364: (0, 364),
                365: (1, 0),
                729: (1, 364),
                730: (2, 0),
                745: (2, 15),
            },
        ),
        ((365,) * 11, {0: (0, 0), 3650: (10, 0), 4014: (10, 364)}),
    ],
)
def test_logical_indices_route_to_exact_bank_and_slot(
    capacities: tuple[int, ...],
    probes: dict[int, tuple[int, int]],
) -> None:
    layout = BankLayout(capacities)
    for logical, expected in probes.items():
        location = layout.locate(logical)
        assert location is not None
        assert (location.bank, location.slot) == expected
        assert layout.logical_index(location) == logical


def test_call_argument_tail_bank_has_exact_short_capacity() -> None:
    report = audit_layout("call_argument_pool", (365, 365, 16))
    assert report["total_capacity"] == 746
    assert report["boundary_indices"][-3:] == [730, 745]
    assert report["bijection"] is True
    assert report["all_valid_reads_roundtrip"] is True
    assert report["invalid_fail_closed_and_storage_unchanged"] is True


def test_full_width_payload_boundaries_roundtrip() -> None:
    report = audit_layout("wide", (2, 1))
    assert report["boundary_single_slot_mutation_and_roundtrip"] is True
    assert SIGNED_I64_MIN < 0
    assert SIGNED_I64_MAX > 0


def test_all_contract_layouts_pass_exhaustive_model() -> None:
    result = audit(_contract())
    assert result["status"] == "PASS_HOSTED_EXHAUSTIVE_BANK_ROUNDTRIP"
    assert result["native_evidence"] is False
    assert result["critical_result"]["all_layouts_bijective"] is True
    assert result["critical_result"]["all_boundaries_roundtrip"] is True
    assert result["critical_result"]["call_argument_tail_bank_16_proven"] is True
    assert result["critical_result"]["expanded_event_11_banks_proven"] is True


def test_invalid_locations_and_layouts_fail_closed() -> None:
    layout = BankLayout((2, 3))
    assert layout.locate(-1) is None
    assert layout.locate(5) is None
    assert layout.logical_index(BankLocation(-1, 0)) is None
    assert layout.logical_index(BankLocation(0, 2)) is None
    assert layout.logical_index(BankLocation(2, 0)) is None
    with pytest.raises(BankLayoutError):
        BankLayout(())
    with pytest.raises(BankLayoutError):
        BankLayout((365, 0))
