from __future__ import annotations

from pathlib import Path

import pytest

from bootstrap.s3 import run_source
from bootstrap.s3.diagnostics import SemanticError
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


def test_native_indexed_aggregate_reference_boundary_fails_closed() -> None:
    source = _candidate_source(
        "fn inspect(value: &NativeIndexedValue) -> i64:\n"
        "    return value.length\n"
        "fn main() -> i64:\n"
        "    return 0\n"
    )
    with pytest.raises(SemanticError, match="reference target must be a scalar type"):
        compile_source(source)


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
