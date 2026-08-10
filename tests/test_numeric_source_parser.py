from __future__ import annotations

import pytest

from bootstrap.s3 import ast
from bootstrap.s3.lexer import SyntaxMode, TokenKind, tokenize
from bootstrap.s3.parser import parse
from bootstrap.s3.semantic import analyze
from bootstrap.s3.ir_emulator import execute_ir
from bootstrap.s3.lowering import lower
from bootstrap.s3.codegen import generate_assembly
from bootstrap.s3.emulator import Emulator
from bootstrap.s3.backends.x86_64 import generate_native_assembly
from bootstrap.s3.backends.x86_64 import NativeBackendError
from bootstrap.s3.assembly import parse_assembly
from bootstrap.s3.ir_serialization import deserialize_ir, serialize_ir


def test_lexer_distinguishes_numeric_keywords_and_float_literals() -> None:
    tokens = tokenize("i64 f64 12 0.5", mode=SyntaxMode.V0_6)
    assert [token.kind for token in tokens[:4]] == [
        TokenKind.I64,
        TokenKind.F64,
        TokenKind.INTEGER,
        TokenKind.FLOAT,
    ]


def test_parser_accepts_i64_and_f64_types_and_literals() -> None:
    program = parse(
        "fn main() -> f64:\n"
        "    value: f64 = 0.5\n"
        "    return value\n",
        mode=SyntaxMode.V0_6,
    )
    function = program.functions[0]
    assert function.return_type is ast.TypeName.F64
    declaration = function.body.statements[0]
    assert isinstance(declaration, ast.VariableDeclaration)
    assert declaration.type_name is ast.TypeName.F64
    assert isinstance(declaration.initializer, ast.FloatLiteral)
    assert declaration.initializer.value == 0.5


def test_semantic_model_records_f64_literal_type() -> None:
    program = parse(
        "fn main() -> f64:\n"
        "    value: f64 = 0.5\n"
        "    return value\n",
        mode=SyntaxMode.V0_6,
    )
    model = analyze(program)
    initializer = program.functions[0].body.statements[0].initializer
    assert model.declared_type_of(initializer) is ast.TypeName.F64


def test_numeric_addition_lowers_and_executes_end_to_end() -> None:
    program = parse(
        "fn main() -> f64:\n"
        "    return 0.5 + 0.25\n",
        mode=SyntaxMode.V0_6,
    )
    assert execute_ir(lower(program, analyze(program))) == 0.75


def test_numeric_compare_lowers_and_executes_end_to_end() -> None:
    program = parse(
        "fn main() -> trit:\n"
        "    return 1.0 <=> 2.0\n",
        mode=SyntaxMode.V0_6,
    )
    assert execute_ir(lower(program, analyze(program))) == -1


def test_numeric_addition_executes_through_typed_assembly() -> None:
    program = parse(
        "fn main() -> f64:\n"
        "    return 0.5 + 0.25\n",
        mode=SyntaxMode.V0_6,
    )
    module = lower(program, analyze(program))
    assert Emulator().execute(generate_assembly(module)) == 0.75


def test_numeric_f64_native_lowering_uses_sse2() -> None:
    program = parse(
        "fn add(left: f64, right: f64) -> f64:\n"
        "    return left + right\n"
        "fn main() -> trit:\n"
        "    return add(0.5, 0.25) <=> 1.0\n",
        mode=SyntaxMode.V0_6,
    )
    native = generate_native_assembly(generate_assembly(lower(program, analyze(program))))
    assert "addsd xmm0, xmm1" in native
    assert "ucomisd xmm0, xmm1" in native
    assert "movq xmm0, rax" in native
    assert "movq xmm1, rax" in native
    assert "movq rax, xmm0" in native


def test_numeric_i64_native_lowering_checks_machine_overflow() -> None:
    program = parse(
        "fn add(left: i64, right: i64) -> i64:\n"
        "    return left + right\n"
        "fn main() -> i64:\n"
        "    return add(4000000000, 1)\n",
        mode=SyntaxMode.V0_6,
    )
    native = generate_native_assembly(generate_assembly(lower(program, analyze(program))))
    assert "add rax, r10" in native
    assert "jo .L__s3_failure_site_" in native


def test_numeric_ir_and_assembly_round_trip_f64_constants() -> None:
    program = parse(
        "fn main() -> f64:\n"
        "    return 0.5\n",
        mode=SyntaxMode.V0_6,
    )
    module = lower(program, analyze(program))
    restored_ir = deserialize_ir(serialize_ir(module))
    assembly = generate_assembly(restored_ir)
    restored_assembly = parse_assembly(assembly.render())
    assert Emulator().execute(restored_assembly) == 0.5


def test_i64_index_executes_through_ir_assembly_and_native_lowering() -> None:
    program = parse(
        "fn main() -> tryte:\n"
        "    values: tryte[3] = [4, 5, 6]\n"
        "    index: i64 = 1\n"
        "    return values[index]\n",
        mode=SyntaxMode.V0_6,
    )
    module = lower(program, analyze(program))
    assert execute_ir(module) == 5
    assembly = generate_assembly(module)
    assert Emulator().execute(assembly) == 5
    native = generate_native_assembly(assembly)
    assert "cmp rax, 3" in native


def test_native_backend_rejects_unprintable_f64_entry_result() -> None:
    program = parse(
        "fn main() -> f64:\n"
        "    return 0.5\n",
        mode=SyntaxMode.V0_6,
    )
    assembly = generate_assembly(lower(program, analyze(program)))
    with pytest.raises(NativeBackendError, match="cannot return f64"):
        generate_native_assembly(assembly)
