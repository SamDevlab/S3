"""Exhaustively audit bounded banked-storage logical/physical round trips.

Hosted/model evidence only. This utility does not mutate the Stage1 compiler and
does not replace native qualification of the exact transformed candidate.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = (
    ROOT / "reports" / "selfhost" / "stage1" /
    "banked-storage-roundtrip-contract.json"
)
DEFAULT_REPORT = (
    ROOT / "reports" / "selfhost" / "stage1" /
    "banked-storage-roundtrip-audit.json"
)

SIGNED_I64_MIN = -(2**63)
SIGNED_I64_MAX = 2**63 - 1


class BankLayoutError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class BankLocation:
    bank: int
    slot: int


@dataclass(frozen=True, slots=True)
class BankLayout:
    capacities: tuple[int, ...]

    def __post_init__(self) -> None:
        if not self.capacities:
            raise BankLayoutError("bank layout must contain at least one bank")
        if any(
            isinstance(capacity, bool)
            or not isinstance(capacity, int)
            or capacity <= 0
            for capacity in self.capacities
        ):
            raise BankLayoutError("bank capacities must be positive integers")

    @property
    def total_capacity(self) -> int:
        return sum(self.capacities)

    def locate(self, logical_index: int) -> BankLocation | None:
        if (
            isinstance(logical_index, bool)
            or not isinstance(logical_index, int)
            or logical_index < 0
            or logical_index >= self.total_capacity
        ):
            return None
        remaining = logical_index
        for bank, capacity in enumerate(self.capacities):
            if remaining < capacity:
                return BankLocation(bank, remaining)
            remaining -= capacity
        raise AssertionError("validated logical index was not routed")

    def logical_index(self, location: BankLocation) -> int | None:
        if (
            isinstance(location.bank, bool)
            or isinstance(location.slot, bool)
            or not isinstance(location.bank, int)
            or not isinstance(location.slot, int)
            or location.bank < 0
            or location.bank >= len(self.capacities)
            or location.slot < 0
            or location.slot >= self.capacities[location.bank]
        ):
            return None
        return sum(self.capacities[: location.bank]) + location.slot

    def boundary_indices(self) -> tuple[int, ...]:
        result = {0, self.total_capacity - 1}
        cursor = 0
        for capacity in self.capacities:
            result.add(cursor)
            result.add(cursor + capacity - 1)
            cursor += capacity
            if cursor < self.total_capacity:
                result.add(cursor)
        return tuple(sorted(result))


def _empty_storage(layout: BankLayout, sentinel: int) -> list[list[int]]:
    return [[sentinel] * capacity for capacity in layout.capacities]


def _write(
    layout: BankLayout,
    storage: list[list[int]],
    logical_index: int,
    value: int,
) -> bool:
    location = layout.locate(logical_index)
    if location is None:
        return False
    storage[location.bank][location.slot] = value
    return True


def _read(
    layout: BankLayout,
    storage: Sequence[Sequence[int]],
    logical_index: int,
) -> int | None:
    location = layout.locate(logical_index)
    if location is None:
        return None
    return storage[location.bank][location.slot]


def _flatten(storage: Sequence[Sequence[int]]) -> tuple[int, ...]:
    return tuple(value for bank in storage for value in bank)


def _payload_for(index: int) -> int:
    return index * 1_000_003 - 17


def audit_layout(name: str, capacities: Iterable[int]) -> dict[str, object]:
    layout = BankLayout(tuple(capacities))
    total = layout.total_capacity

    locations = [layout.locate(index) for index in range(total)]
    inverse_ok = all(
        location is not None and layout.logical_index(location) == index
        for index, location in enumerate(locations)
    )
    unique_locations = {
        (location.bank, location.slot)
        for location in locations
        if location is not None
    }
    bijective = inverse_ok and len(unique_locations) == total

    sentinel = SIGNED_I64_MIN + 1
    storage = _empty_storage(layout, sentinel)
    writes_ok = True
    for index in range(total):
        writes_ok = _write(layout, storage, index, _payload_for(index)) and writes_ok
    reads_ok = all(
        _read(layout, storage, index) == _payload_for(index)
        for index in range(total)
    )

    boundary_values = {
        layout.boundary_indices()[0]: SIGNED_I64_MIN,
        layout.boundary_indices()[-1]: SIGNED_I64_MAX,
    }
    for index in layout.boundary_indices():
        boundary_values.setdefault(index, -index - 1)
    boundary_storage = _empty_storage(layout, sentinel)
    boundary_roundtrip = True
    for index, value in boundary_values.items():
        before = _flatten(boundary_storage)
        wrote = _write(layout, boundary_storage, index, value)
        after = _flatten(boundary_storage)
        changed = [
            offset
            for offset, (left, right) in enumerate(zip(before, after))
            if left != right
        ]
        boundary_roundtrip = (
            boundary_roundtrip
            and wrote
            and _read(layout, boundary_storage, index) == value
            and len(changed) == 1
            and changed[0] == index
        )

    invalid_storage = _empty_storage(layout, sentinel)
    invalid_before = _flatten(invalid_storage)
    invalid_indices = (-2, -1, total, total + 1)
    invalid_writes = {
        index: _write(layout, invalid_storage, index, 123)
        for index in invalid_indices
    }
    invalid_reads = {
        index: _read(layout, invalid_storage, index)
        for index in invalid_indices
    }
    invalid_unchanged = _flatten(invalid_storage) == invalid_before
    invalid_closed = (
        invalid_unchanged
        and all(result is False for result in invalid_writes.values())
        and all(result is None for result in invalid_reads.values())
    )

    passed = bijective and writes_ok and reads_ok and boundary_roundtrip and invalid_closed
    return {
        "name": name,
        "capacities": list(layout.capacities),
        "bank_count": len(layout.capacities),
        "total_capacity": total,
        "boundary_indices": list(layout.boundary_indices()),
        "bijection": bijective,
        "all_valid_writes": writes_ok,
        "all_valid_reads_roundtrip": reads_ok,
        "boundary_single_slot_mutation_and_roundtrip": boundary_roundtrip,
        "invalid_fail_closed_and_storage_unchanged": invalid_closed,
        "invalid_write_results": invalid_writes,
        "invalid_read_results": invalid_reads,
        "pass": passed,
    }


DEFAULT_LAYOUTS = {
    "legacy_instruction_two_banks": (365, 365),
    "legacy_value_four_banks": (365, 365, 365, 365),
    "call_argument_pool": (365, 365, 16),
    "expanded_event_example": (365,) * 11,
}


def audit(contract: dict[str, object]) -> dict[str, object]:
    contract_examples = contract.get("required_layout_examples")
    contract_ok = (
        contract.get("schema") == "s3.selfhost.banked-storage-roundtrip-contract.v1"
        and isinstance(contract_examples, dict)
        and isinstance(contract.get("writer_reader_invariants"), list)
    )

    layouts: list[dict[str, object]] = []
    for name, capacities in DEFAULT_LAYOUTS.items():
        expected = None if not isinstance(contract_examples, dict) else contract_examples.get(name)
        declared_matches = expected == list(capacities)
        result = audit_layout(name, capacities)
        result["contract_layout_matches"] = declared_matches
        result["pass"] = bool(result["pass"] and declared_matches)
        layouts.append(result)

    passed = contract_ok and all(item["pass"] for item in layouts)
    return {
        "schema": "s3.selfhost.banked-storage-roundtrip-audit.v1",
        "status": "PASS_HOSTED_EXHAUSTIVE_BANK_ROUNDTRIP" if passed else "FAIL",
        "native_evidence": False,
        "canonical_source_mutated": False,
        "contract_valid": contract_ok,
        "layouts": layouts,
        "critical_result": {
            "all_layouts_bijective": all(item["bijection"] for item in layouts),
            "all_boundaries_roundtrip": all(
                item["boundary_single_slot_mutation_and_roundtrip"]
                for item in layouts
            ),
            "invalid_accesses_fail_closed": all(
                item["invalid_fail_closed_and_storage_unchanged"]
                for item in layouts
            ),
            "call_argument_tail_bank_16_proven": next(
                item["pass"]
                for item in layouts
                if item["name"] == "call_argument_pool"
            ),
            "expanded_event_11_banks_proven": next(
                item["pass"]
                for item in layouts
                if item["name"] == "expanded_event_example"
            ),
        },
        "qualification": {
            "native_evidence": False,
            "stage1_source_change": False,
            "stage2_allowed": False,
            "full_self_hosting": False,
            "next": (
                "RECONCILE_EXACT_TRANSFORMED_WRITER_READER_WITH_ROUNDTRIP_MODEL"
                if passed
                else "REPAIR_BANK_MAPPING_OR_BOUNDARY_PROOF"
            ),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)

    contract = json.loads(args.contract.resolve().read_text(encoding="utf-8"))
    if not isinstance(contract, dict):
        raise ValueError("banked-storage contract must be a JSON object")
    result = audit(contract)
    destination = args.report.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"REPORT={destination}")
    print(f"STATUS={result['status']}")
    for item in result["layouts"]:
        print(
            f"LAYOUT={item['name']} "
            f"BANKS={item['bank_count']} "
            f"CAPACITY={item['total_capacity']} "
            f"PASS={item['pass']}"
        )
    print("NATIVE_EVIDENCE=False")
    print(f"NEXT={result['qualification']['next']}")
    return 0 if result["status"].startswith("PASS_") else 2


if __name__ == "__main__":
    raise SystemExit(main())
