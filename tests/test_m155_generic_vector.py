from __future__ import annotations

import pytest

from bootstrap.s3.diagnostics import DiagnosticCode, SemanticError
from bootstrap.s3.pipeline import compile_source, run_source


def test_generic_i64_vector_maps_to_existing_ordered_vector_runtime() -> None:
    source = (
        "fn main() -> i64:\n"
        "    mut values: vector<i64> = vector_new<i64>(2)\n"
        "    discard vector_push<i64>(&mut values, 11)\n"
        "    discard vector_push<i64>(&mut values, 22)\n"
        "    discard vector_set<i64>(&mut values, 0, 7)\n"
        "    return vector_get<i64>(&values, 1)\n"
    )

    compilation = compile_source(source)
    assert compilation.semantic_model.contains_dynamic
    assert run_source(source, optimization="O0") == 22
    assert run_source(source, optimization="O1") == 22


def test_generic_f64_vector_preserves_element_specific_builtin_signature() -> None:
    source = (
        "fn main() -> i64:\n"
        "    mut values: vector<f64> = vector_new<f64>(1)\n"
        "    discard vector_push<f64>(&mut values, 1.5)\n"
        "    return vector_len<f64>(&values)\n"
    )

    compilation = compile_source(source)
    assert "f64_vector_len" in compilation.assembly_text
    assert run_source(source) == 1


def test_generic_vector_requires_explicit_element_type_and_closed_domain() -> None:
    missing = (
        "fn main() -> i64:\n"
        "    mut values: vector<i64> = vector_new(1)\n"
        "    return vector_len<i64>(&values)\n"
    )
    with pytest.raises(SemanticError, match="requires explicit type arguments"):
        compile_source(missing)

    invalid = (
        "fn main() -> i64:\n"
        "    mut values: vector<string> = vector_new<string>(1)\n"
        "    return vector_len<string>(&values)\n"
    )
    with pytest.raises(SemanticError) as error:
        compile_source(invalid)
    assert error.value.diagnostic_code is DiagnosticCode.SEMANTIC_INVALID_ARGUMENT_TYPE
