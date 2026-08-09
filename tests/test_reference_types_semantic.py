from __future__ import annotations

import pytest

from bootstrap.s3 import ast
from bootstrap.s3.diagnostics import DiagnosticCode, SemanticError
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.parser import parse
from bootstrap.s3.pipeline import compile_source
from bootstrap.s3.ir import IROpcode
from bootstrap.s3.semantic import analyze


def _parse(source: str) -> ast.Program:
    return parse(source, mode=SyntaxMode.V0_6)


def _analyze(source: str):
    return analyze(_parse(source))


def test_reference_types_and_prefix_expressions_parse() -> None:
    program = _parse(
        "fn main() -> tryte:\n"
        "    mut value: tryte = 1\n"
        "    shared: &tryte = &value\n"
        "    mutable: &mut tryte = &mut value\n"
        "    *mutable = *shared\n"
        "    return *mutable\n"
    )
    shared, mutable, assignment, result = program.functions[0].body.statements[1:]
    assert isinstance(shared, ast.VariableDeclaration)
    assert shared.type_name == ast.ReferenceType(
        ast.TypeName.TRYTE, False, shared.type_name.location
    )
    assert isinstance(mutable.type_name, ast.ReferenceType)
    assert mutable.type_name.mutable is True
    assert isinstance(assignment.target, ast.DereferenceTarget)
    assert isinstance(result.expression, ast.DereferenceExpression)


def test_shared_read_and_mutable_write_are_semantically_valid() -> None:
    model = _analyze(
        "fn main() -> tryte:\n"
        "    mut value: tryte = 1\n"
        "    shared: &tryte = &value\n"
        "    mutable: &mut tryte = &mut value\n"
        "    *mutable = *shared\n"
        "    return *shared\n"
    )
    assert model.contains_references is True


def test_reference_copy_preserves_origin() -> None:
    program = _parse(
        "fn main() -> tryte:\n"
        "    value: tryte = 1\n"
        "    first: &tryte = &value\n"
        "    second: &tryte = first\n"
        "    return *second\n"
    )
    model = analyze(program)
    second = program.functions[0].body.statements[2]
    assert isinstance(second, ast.VariableDeclaration)
    origin = model.reference_origins[id(second.initializer)]
    assert origin[1:] == (0, False)
    assert isinstance(origin[0], int)


def test_reference_parameters_are_type_checked() -> None:
    model = _analyze(
        "fn read(value: &tryte) -> tryte:\n"
        "    return *value\n"
        "fn main() -> tryte:\n"
        "    value: tryte = 1\n"
        "    return read(&value)\n"
    )
    assert model.contains_references is True


def test_mutable_reference_parameters_are_type_checked() -> None:
    model = _analyze(
        "fn write(value: &mut tryte) -> tryte:\n"
        "    *value = 2\n"
        "    return *value\n"
        "fn main() -> tryte:\n"
        "    mut value: tryte = 1\n"
        "    return write(&mut value)\n"
    )
    assert model.contains_references is True


def test_reference_mutability_is_part_of_assignment_type() -> None:
    with pytest.raises(SemanticError):
        _analyze(
            "fn main() -> tryte:\n"
            "    mut value: tryte = 1\n"
            "    shared: &tryte = &mut value\n"
            "    return 0\n"
        )
    with pytest.raises(SemanticError):
        _analyze(
            "fn main() -> tryte:\n"
            "    mut value: tryte = 1\n"
            "    mutable: &mut tryte = &value\n"
            "    return 0\n"
        )


def test_reference_origin_survives_inner_copy_and_rejects_escape() -> None:
    model = _analyze(
        "fn main() -> tryte:\n"
        "    value: tryte = 1\n"
        "    saved: &tryte = &value\n"
        "    while 0:\n"
        "        inner: &tryte = saved\n"
        "        return *inner\n"
        "    return *saved\n"
    )
    assert model.contains_references is True


def test_shadowed_symbols_have_distinct_reference_origins() -> None:
    program = _parse(
        "fn main() -> tryte:\n"
        "    value: tryte = 1\n"
        "    first: &tryte = &value\n"
        "    while 0:\n"
        "        value: tryte = 2\n"
        "        second: &tryte = &value\n"
        "        return *second\n"
        "    return *first\n"
    )
    model = analyze(program)
    first = program.functions[0].body.statements[1]
    loop = program.functions[0].body.statements[2]
    second = loop.body.statements[1]
    assert isinstance(first, ast.VariableDeclaration)
    assert isinstance(second, ast.VariableDeclaration)
    assert model.reference_origins[id(first.initializer)][0] != model.reference_origins[id(second.initializer)][0]


@pytest.mark.parametrize(
    ("source", "code"),
    [
        (
            "fn main() -> tryte:\n    value: tryte = 1\n    ref: &tryte = &value\n    *ref = 2\n    return 0\n",
            DiagnosticCode.SEMANTIC_REFERENCE_SHARED_WRITE,
        ),
        (
            "fn main() -> tryte:\n    mut value: tryte = 1\n    mut ref: &mut tryte = &mut value\n    return ref == ref\n",
            DiagnosticCode.SEMANTIC_REFERENCE_IDENTITY,
        ),
        (
            "fn main() -> tryte:\n    value: tryte = 1\n    ref: &&tryte = &&value\n    return 0\n",
            DiagnosticCode.SEMANTIC_REFERENCE_NESTED,
        ),
        (
            "fn main() -> tryte:\n    value: tryte = 1\n    ref: &mut tryte = &mut value\n    return &*ref\n",
            DiagnosticCode.SEMANTIC_REFERENCE_TARGET_NOT_ADDRESSABLE,
        ),
        (
            "fn main() -> tryte:\n    return &1\n",
            DiagnosticCode.SEMANTIC_REFERENCE_TARGET_NOT_ADDRESSABLE,
        ),
        (
            "fn main() -> tryte:\n    mut values: tryte[1] = [1]\n    ref: &tryte = &values[0]\n    return 0\n",
            DiagnosticCode.SEMANTIC_REFERENCE_TARGET_NOT_ADDRESSABLE,
        ),
    ],
)
def test_reference_restrictions_have_structured_diagnostics(source: str, code: DiagnosticCode) -> None:
    with pytest.raises(SemanticError) as captured:
        _analyze(source)
    assert captured.value.diagnostic_code is code


def test_mutable_address_of_immutable_local_is_rejected() -> None:
    with pytest.raises(SemanticError) as captured:
        _analyze(
            "fn main() -> tryte:\n"
            "    value: tryte = 1\n"
            "    ref: &mut tryte = &mut value\n"
            "    return 0\n"
        )
    assert captured.value.diagnostic_code is DiagnosticCode.SEMANTIC_REFERENCE_TARGET_NOT_ADDRESSABLE


def test_reference_cannot_escape_inner_lexical_scope() -> None:
    with pytest.raises(SemanticError) as captured:
        _analyze(
            "fn main() -> tryte:\n"
            "    outer: tryte = 0\n"
            "    mut saved: &tryte = &outer\n"
            "    while 0:\n"
            "        value: tryte = 1\n"
            "        saved = &value\n"
            "    return 0\n"
        )
    assert captured.value.diagnostic_code is DiagnosticCode.SEMANTIC_REFERENCE_ESCAPE


def test_reference_returns_and_aggregate_storage_are_rejected() -> None:
    with pytest.raises(SemanticError) as returned:
        _analyze("fn leak(value: tryte) -> &tryte:\n    return &value\nfn main() -> tryte:\n    return 0\n")
    assert returned.value.diagnostic_code is DiagnosticCode.SEMANTIC_REFERENCE_RETURN

    with pytest.raises(SemanticError) as aggregate:
        _analyze(
            "record Box:\n"
            "    value: &tryte\n"
            "fn main() -> tryte:\n"
            "    return 0\n"
        )
    assert aggregate.value.diagnostic_code is DiagnosticCode.SEMANTIC_REFERENCE_AGGREGATE


def test_valid_reference_program_reaches_reference_ir() -> None:
    compilation = compile_source(
        "fn main() -> tryte:\n"
        "    value: tryte = 1\n"
        "    ref: &tryte = &value\n"
        "    return *ref\n"
    )
    assert compilation.semantic_model.contains_references is True
    assert any(item.opcode is IROpcode.REFERENCE_LOAD for item in compilation.ir.functions[0].instructions)
