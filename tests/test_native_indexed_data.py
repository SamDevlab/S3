from __future__ import annotations

from pathlib import Path

import pytest

from bootstrap.s3 import run_source
from bootstrap.s3.diagnostics import SemanticError
from bootstrap.s3.dynamic import BufferBoundsError
from bootstrap.s3.pipeline import compile_source


def _candidate_source(main: str) -> str:
    repository = Path(__file__).parents[1]
    parts = (
        "selfhost/substrate/generic_lexer_state.s3",
        "selfhost/substrate/native_semantic_execution.s3",
        "selfhost/substrate/native_typed_value_protocol.s3",
        "selfhost/substrate/native_indexed_value_protocol.s3",
    )
    source = "\n".join(
        (repository / path).read_text(encoding="utf-8") for path in parts
    )
    return source + "\n" + main


def test_native_indexed_contract_preserves_type_payload_and_metadata() -> None:
    source = _candidate_source(
        "fn main() -> i64:\n"
        "    return native_indexed_contract_case()\n"
    )
    assert run_source(source) == 1


def test_native_indexed_length_covers_empty_single_and_multiple_elements() -> None:
    source = _candidate_source(
        "fn main() -> i64:\n"
        "    return native_indexed_length_case()\n"
    )
    assert run_source(source) == 4


def test_native_indexed_local_read_checks_bounds_before_payload_access() -> None:
    source = _candidate_source(
        "fn main() -> i64:\n"
        "    return native_indexed_local_read_case()\n"
    )
    assert run_source(source) == 12


def test_native_indexed_payload_can_cross_a_vector_reference_parameter() -> None:
    source = _candidate_source(
        "fn main() -> i64:\n"
        "    return native_indexed_payload_parameter_case()\n"
    )
    assert run_source(source) == 42


def test_native_indexed_aggregate_reference_crosses_boundary_as_one_value() -> None:
    source = _candidate_source(
        "fn inspect(value: &NativeIndexedValue) -> i64:\n"
        "    return value.length\n"
        "fn main() -> i64:\n"
        "    mut values: NativeIndexedValue = native_indexed_i64_value(10, 20, 12, 0)\n"
        "    return inspect(&values) + values.length\n"
    )
    assert run_source(source) == 6


def test_native_indexed_aggregate_reference_preserves_payload_and_length() -> None:
    source = _candidate_source(
        "fn inspect(value: &NativeIndexedValue) -> i64:\n"
        "    return i64_vector_get(&value.i64_payload, value.length - 1)\n"
        "fn main() -> i64:\n"
        "    mut values: NativeIndexedValue = native_indexed_i64_value(10, 20, 12, 0)\n"
        "    return inspect(&values) + inspect(&values)\n"
    )
    assert run_source(source) == 24


def test_native_indexed_mutable_aggregate_reference_is_rejected() -> None:
    source = _candidate_source(
        "fn inspect(value: &mut NativeIndexedValue) -> i64:\n"
        "    return value.length\n"
        "fn main() -> i64:\n"
        "    return 0\n"
    )
    with pytest.raises(SemanticError, match="mutable aggregate references are not supported"):
        compile_source(source)


def test_native_indexed_i64_function_reads_borrowed_aggregate() -> None:
    source = _candidate_source(
        "fn main() -> i64:\n"
        "    mut values: NativeIndexedValue = native_indexed_i64_value(10, 20, 12, 0)\n"
        "    return native_indexed_i64_sum(&values)\n"
    )
    assert run_source(source) == 42


def test_native_indexed_f64_function_reads_borrowed_aggregate() -> None:
    source = _candidate_source(
        "fn main() -> f64:\n"
        "    mut values: NativeIndexedValue = native_indexed_f64_value(1.25, 2.5, 1.0, 0)\n"
        "    return native_indexed_f64_sum(&values)\n"
    )
    assert run_source(source) == 4.75


def test_native_indexed_bounds_follow_the_borrowed_payload() -> None:
    source = _candidate_source(
        "fn inspect(value: &NativeIndexedValue) -> i64:\n"
        "    return i64_vector_get(&value.i64_payload, value.length)\n"
        "fn main() -> i64:\n"
        "    mut values: NativeIndexedValue = native_indexed_i64_value(10, 20, 12, 0)\n"
        "    return inspect(&values)\n"
    )
    with pytest.raises(BufferBoundsError, match=r"outside \[0, length\)"):
        run_source(source)


def test_native_indexed_aggregate_boundary_has_one_reference_parameter() -> None:
    source = _candidate_source(
        "fn inspect(value: &NativeIndexedValue) -> i64:\n"
        "    return value.length\n"
        "fn main() -> i64:\n"
        "    mut values: NativeIndexedValue = native_indexed_i64_value(10, 20, 12, 0)\n"
        "    return inspect(&values)\n"
    )
    compilation = compile_source(source)
    inspect = next(function for function in compilation.ir.functions if function.name == "inspect")
    assert len(inspect.parameters) == 1
    assert inspect.parameters[0].reference_aggregate == "NativeIndexedValue"
    main = next(function for function in compilation.ir.functions if function.name == "main")
    call = next(instruction for instruction in main.instructions if instruction.callee == "inspect")
    assert len(call.operands) == 1


def test_native_indexed_ssd_uses_two_borrowed_aggregate_inputs() -> None:
    source = _candidate_source(
        "fn main() -> f64:\n"
        "    mut left: NativeIndexedValue = native_indexed_f64_value(1.0, 2.0, 3.0, 0)\n"
        "    mut right: NativeIndexedValue = native_indexed_f64_value(2.0, 4.0, 6.0, 0)\n"
        "    return native_indexed_ssd(&left, &right)\n"
    )
    assert run_source(source) == 14.0


def test_native_indexed_ssd_mismatched_lengths_return_explicit_invalid_result() -> None:
    source = _candidate_source(
        "fn main() -> f64:\n"
        "    mut left: NativeIndexedValue = native_indexed_f64_value(1.0, 2.0, 3.0, 0)\n"
        "    mut right: NativeIndexedValue = native_indexed_f64_single(2.0, 0)\n"
        "    return native_indexed_ssd(&left, &right)\n"
    )
    assert run_source(source) == -1.0


def test_native_indexed_protocol_is_explicit_and_has_no_host_fallback() -> None:
    repository = Path(__file__).parents[1]
    protocol = (
        repository / "selfhost/substrate/native_indexed_value_protocol.s3"
    ).read_text(encoding="utf-8")
    assert "record NativeIndexedValue:" in protocol
    assert "element_kind: i64" in protocol
    assert "length: i64" in protocol
    assert "mutability: i64" in protocol
    assert "ownership: i64" in protocol
    assert "lifetime: i64" in protocol
    assert "i64_payload: i64_vector" in protocol
    assert "f64_payload: f64_vector" in protocol
    assert "GenericLexer" not in protocol
    assert "GenericParser" not in protocol
