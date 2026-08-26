from __future__ import annotations

from tools.audit_stage1_semantic_def_use_requirements import inventory_source


def test_storage_reads_and_writes_require_explicit_ir_operations() -> None:
    source = """fn helper(value: i64) -> i64:
    mut x: i64 = value
    x = x + 1
    return x

fn main() -> tryte:
    return 7
"""
    result = inventory_source(source)
    counts = result["aggregate_counts"]
    required = set(result["required_instruction_semantics"])

    assert counts["scalar_local_stores"] >= 1
    assert counts["scalar_local_loads"] >= 1
    assert "LOAD_LOCAL" in required
    assert "STORE_LOCAL" in required
    assert result["critical_contract"]["mutable_local_is_storage_identity"] is True
    assert result["critical_contract"]["phi_required_for_local_storage"] is False


def test_fixed_array_index_reads_and_writes_are_not_scalar_local_aliases() -> None:
    source = """fn main() -> tryte:
    mut values: i64[2] = [1, 2]
    values[1] = values[0] + 3
    return to_tryte(values[1])
"""
    result = inventory_source(source)
    counts = result["aggregate_counts"]
    required = set(result["required_instruction_semantics"])

    assert counts["fixed_array_local_declarations"] == 1
    assert counts["fixed_array_loads"] >= 2
    assert counts["fixed_array_stores"] == 1
    assert "LOAD_INDEX" in required
    assert "STORE_INDEX" in required
    assert "FIXED_ARRAY_INIT_OR_ORDERED_ELEMENT_STORES" in required


def test_compound_array_assignment_is_load_compute_store() -> None:
    source = """fn main() -> tryte:
    mut values: i64[1] = [1]
    values[0] += 2
    return to_tryte(values[0])
"""
    result = inventory_source(source)
    counts = result["aggregate_counts"]

    assert counts["compound_assignments"] == 1
    assert counts["fixed_array_loads"] >= 2
    assert counts["fixed_array_stores"] == 1
    assert counts["arithmetic_operations"] >= 1
