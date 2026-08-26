from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.audit_stage1_relation_dispatch import (
    _generated_dispatch_source,
    relation_probe,
)
from tools.stage1_relation_dispatch import (
    DispatchCase,
    DispatchContractError,
    audit_contiguous_banks,
    emit_balanced_boolean_dispatch,
    route_boolean_dispatch,
)


pytestmark = pytest.mark.s3_fast


def test_repository_relation_runtime_distinguishes_boolean_from_three_way_compare() -> None:
    probe = relation_probe()
    assert probe["status"] == "PASS"
    results = probe["results"]
    assert results["less_true"]["actual"] == -1
    assert results["less_false"]["actual"] == 0
    assert results["greater_true"]["actual"] == -1
    assert results["greater_false"]["actual"] == 0
    assert results["compare_less"]["actual"] == -1
    assert results["compare_equal"]["actual"] == 0
    assert results["compare_greater"]["actual"] == 1


@pytest.mark.parametrize("bank_count", [1, 2, 3, 4, 5, 11, 16, 32, 64])
def test_safe_dispatch_routes_every_contiguous_bank_one_to_one(bank_count: int) -> None:
    report = audit_contiguous_banks(bank_count)
    assert report["pass"] is True
    assert report["all_valid_exact"] is True
    assert report["one_to_one"] is True
    assert report["invalid_fail_closed"] is True


def test_bank_11_routes_are_exact_and_out_of_range_is_closed() -> None:
    keys = tuple(range(11))
    assert [route_boolean_dispatch(index, keys) for index in keys] == list(keys)
    assert route_boolean_dispatch(-1, keys) is None
    assert route_boolean_dispatch(11, keys) is None
    assert route_boolean_dispatch(12, keys) is None


def test_boolean_relation_positive_arm_is_fail_closed_in_generated_tree() -> None:
    cases = tuple(
        DispatchCase(index, (f"return {index}",))
        for index in range(11)
    )
    source = emit_balanced_boolean_dispatch(
        "bank",
        cases,
        fail_closed_body=("return -99",),
    )
    lines = source.splitlines()
    less_matches = [index for index, line in enumerate(lines) if "match bank < " in line]
    assert less_matches
    for match_index in less_matches:
        block_indent = len(lines[match_index]) - len(lines[match_index].lstrip())
        positive_arm_seen = False
        fail_closed_seen = False
        for line in lines[match_index + 1 :]:
            indent = len(line) - len(line.lstrip())
            if indent <= block_indent:
                break
            if line.strip() == "1:" and indent == block_indent + 4:
                positive_arm_seen = True
                continue
            if positive_arm_seen and line.strip() == "return -99":
                fail_closed_seen = True
                break
        assert positive_arm_seen is True
        assert fail_closed_seen is True


def test_generated_bank_11_program_exercises_all_valid_and_invalid_selectors() -> None:
    source = _generated_dispatch_source(11)
    assert "route(0) == 0" in source
    assert "route(10) == 10" in source
    assert "route(-1) == -99" in source
    assert "route(11) == -99" in source
    assert "route(12) == -99" in source


def test_unsafe_three_way_interpretation_of_boolean_less_collapses_greater() -> None:
    def boolean_less(lhs: int, rhs: int) -> int:
        return -1 if lhs < rhs else 0

    pivot = 5
    assert boolean_less(4, pivot) == -1
    assert boolean_less(5, pivot) == 0
    assert boolean_less(6, pivot) == 0
    assert boolean_less(6, pivot) != 1


def test_dispatch_rejects_duplicate_or_unsorted_keys() -> None:
    with pytest.raises(DispatchContractError, match="unique"):
        emit_balanced_boolean_dispatch(
            "bank",
            (
                DispatchCase(0, ("return 0",)),
                DispatchCase(0, ("return 1",)),
            ),
        )
    with pytest.raises(DispatchContractError, match="strictly increasing"):
        emit_balanced_boolean_dispatch(
            "bank",
            (
                DispatchCase(1, ("return 1",)),
                DispatchCase(0, ("return 0",)),
            ),
        )


def test_contract_requires_boolean_positive_one_to_be_fail_closed() -> None:
    root = Path(__file__).resolve().parents[1]
    contract = json.loads(
        (
            root
            / "reports"
            / "selfhost"
            / "stage1"
            / "capacity-dispatch-proof-contract.json"
        ).read_text(encoding="utf-8")
    )
    boolean = contract["relation_semantics"]["boolean_relations"]
    compare = contract["relation_semantics"]["three_way_compare"]
    assert boolean["true_value"] == -1
    assert boolean["false_value"] == 0
    assert "UNREACHABLE" in boolean["positive_one_meaning"]
    assert compare["less_value"] == -1
    assert compare["equal_value"] == 0
    assert compare["greater_value"] == 1
