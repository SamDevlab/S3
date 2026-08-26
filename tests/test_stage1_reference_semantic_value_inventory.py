from __future__ import annotations

import json
from pathlib import Path

import pytest

from bootstrap.s3.pipeline import compile_source
from tools.audit_stage1_reference_semantic_value_inventory import (
    _reference_ir_inventory,
    _semantic_constant_inventory,
)


pytestmark = pytest.mark.s3_fast


def test_reference_ir_inventory_tracks_results_uses_calls_and_storage() -> None:
    compilation = compile_source(
        "fn add(a: i64, b: i64) -> i64:\n"
        "    return a + b\n\n"
        "fn main() -> tryte:\n"
        "    mut values: i64[2] = [2, 5]\n"
        "    values[0] = add(values[0], values[1])\n"
        "    return to_tryte(values[0])\n",
        optimization="O0",
    )
    report = _reference_ir_inventory(compilation, inline_min=-730, inline_max=730)
    assert report["instruction_count"] > 0
    assert report["result_register_count"] > 0
    assert report["non_constant_result_register_count"] > 0
    assert report["operand_use_count"] > 0
    assert report["call_count"] >= 2  # add + to_tryte
    assert report["call_argument_operand_uses"] >= 3
    assert report["load_count"] > 0
    assert report["store_count"] > 0
    assert report["terminator_count"] >= 2
    assert report["opcode_histogram"]["load"] > 0
    assert report["opcode_histogram"]["store"] > 0


def test_wide_typed_i64_constant_consumes_header_plus_extension_slot() -> None:
    compilation = compile_source(
        "fn wide() -> i64:\n"
        "    return 1000000000000\n\n"
        "fn main() -> tryte:\n"
        "    return 0\n",
        optimization="O0",
    )
    report = _reference_ir_inventory(compilation, inline_min=-730, inline_max=730)
    wide = report["wide_typed_integer_constants"]
    assert {"type": "i64", "value": 1000000000000} in wide
    assert report["wide_unique_typed_integer_constants"] >= 1
    # Every unique numeric constant consumes a header; every wide numeric
    # constant consumes one additional raw-i64 extension slot.
    assert report["interned_numeric_constant_physical_slots"] == (
        report["unique_typed_numeric_constants"]
        + report["wide_unique_typed_integer_constants"]
    )


def test_semantic_oracle_uses_contextual_literal_type() -> None:
    compilation = compile_source(
        "fn value() -> i64:\n"
        "    mut x: i64 = 1000\n"
        "    return x\n\n"
        "fn main() -> tryte:\n"
        "    return 0\n",
        optimization="O0",
    )
    report = _semantic_constant_inventory(compilation)
    assert {"type": "i64", "value": 1000} in report["unique_typed_numeric_constants"]


def test_contract_keeps_reference_ir_non_authoritative_for_stage2() -> None:
    root = Path(__file__).resolve().parents[1]
    contract = json.loads(
        (
            root
            / "reports"
            / "selfhost"
            / "stage1"
            / "reference-semantic-value-inventory-contract.json"
        ).read_text(encoding="utf-8")
    )
    interpretation = contract["interpretation"]
    assert interpretation["reference_ir_is_architecture_authority"] is False
    assert interpretation["reference_ir_is_sizing_and_semantic_oracle"] is True
    assert interpretation["native_evidence"] is False
    assert interpretation["stage2_allowed_from_this_report"] is False
    assert interpretation["full_self_hosting_allowed_from_this_report"] is False
    assert contract["planned_stage1_value_storage"]["total_physical_slots"] == 1460
