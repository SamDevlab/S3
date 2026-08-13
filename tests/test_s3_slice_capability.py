from __future__ import annotations

import platform
from pathlib import Path

import pytest

from bootstrap.s3 import ast
from bootstrap.s3.backends.x86_64 import NativeToolchain, X8664Backend
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.parser import parse
from bootstrap.s3.pipeline import compile_source
from bootstrap.s3.semantic import analyze


def test_parser_accepts_shared_and_mutable_slice_parameter_types() -> None:
    program = parse(
        "fn sum(xs: &[f64]) -> f64:\n"
        "    return 0.0\n"
        "fn mutate(xs: &mut [i64]) -> trit:\n"
        "    return 0\n",
        mode=SyntaxMode.V0_6,
    )
    first, second = program.functions
    assert isinstance(first.parameters[0].type_name, ast.SliceType)
    assert first.parameters[0].type_name.element_type is ast.TypeName.F64
    assert first.parameters[0].type_name.mutable is False
    assert isinstance(second.parameters[0].type_name, ast.SliceType)
    assert second.parameters[0].type_name.element_type is ast.TypeName.I64
    assert second.parameters[0].type_name.mutable is True


def test_semantic_model_types_slice_length_and_index() -> None:
    program = parse(
        "fn sum(xs: &[f64]) -> f64:\n"
        "    return xs[0]\n"
        "fn main() -> trit:\n"
        "    values: f64[1] = [1.0]\n"
        "    return sum(&values) == 1.0\n",
        mode=SyntaxMode.V0_6,
    )
    model = analyze(program)
    indexed = program.functions[0].body.statements[0].expression
    assert model.declared_type_of(indexed) is ast.TypeName.F64


def test_hosted_ir_executes_shared_slice_and_mutable_slice() -> None:
    from bootstrap.s3.ir_emulator import execute_ir
    from bootstrap.s3.lowering import lower

    program = parse(
        "fn sum(xs: &[f64]) -> f64:\n"
        "    return xs[0] + xs[1]\n"
        "fn mutate(xs: &mut [i64]) -> trit:\n"
        "    xs[0] = 9\n"
        "    return xs[0] == 9\n"
        "fn main() -> trit:\n"
        "    values: i64[2] = [1, 2]\n"
        "    floats: f64[2] = [0.25, 0.75]\n"
        "    return (mutate(&mut values) == -1) & (sum(&floats) == 1.0)\n",
        mode=SyntaxMode.V0_6,
    )
    assert execute_ir(lower(program, analyze(program))) == -1


def test_o1_preserves_slice_reference_metadata_through_ssa_lowering() -> None:
    from bootstrap.s3.ir_emulator import execute_ir

    source = (
        "fn sum(xs: &[f64]) -> f64:\n"
        "    return xs[0] + xs[1]\n"
        "fn mutate(xs: &mut [i64]) -> trit:\n"
        "    xs[0] = 9\n"
        "    return xs[0] == 9\n"
        "fn main() -> trit:\n"
        "    mut values: i64[2] = [1, 2]\n"
        "    floats: f64[2] = [0.25, 0.75]\n"
        "    return (mutate(&mut values) == -1) & (sum(&floats) == 1.0)\n"
    )
    for optimization in ("O0", "O1"):
        compilation = compile_source(source, optimization, mode=SyntaxMode.V0_6)
        parameter = compilation.ir.functions[0].parameters[0]
        assert parameter.reference_is_slice is True
        assert parameter.slice_length_register is not None
        assert execute_ir(compilation.ir) == -1


def test_slice_length_metadata_survives_ir_round_trip() -> None:
    from bootstrap.s3.ir_serialization import deserialize_ir, serialize_ir
    from bootstrap.s3.lowering import lower

    program = parse(
        "fn sum(xs: &[f64]) -> f64:\n"
        "    return xs[0]\n"
        "fn main() -> trit:\n"
        "    return -1\n",
        mode=SyntaxMode.V0_6,
    )
    ir = lower(program, analyze(program))
    restored = deserialize_ir(serialize_ir(ir))
    parameter = restored.functions[0].parameters[0]
    assert parameter.reference_is_slice is True
    assert parameter.slice_length_register is not None


@pytest.mark.parametrize("register_allocation", [False, True])
def test_linux_native_slice_abi_and_bounds(
    register_allocation: bool,
    tmp_path: Path,
) -> None:
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        pytest.skip("slice native ABI requires Linux x86-64")
    source = (
        "fn sum(xs: &[f64]) -> f64:\n"
        "    return xs[0] + xs[1]\n"
        "fn forward(xs: &[f64]) -> f64:\n"
        "    return sum(xs)\n"
        "fn mutate(xs: &mut [i64]) -> trit:\n"
        "    xs[0] = 9\n"
        "    return xs[0] == 9\n"
        "fn check_small(ys: &[tryte], zs: &[trit]) -> trit:\n"
        "    return (ys[1] == 20) & (zs[0] == -1)\n"
        "fn main() -> trit:\n"
        "    values: i64[2] = [1, 2]\n"
        "    floats: f64[2] = [0.25, 0.75]\n"
        "    small: tryte[2] = [10, 20]\n"
        "    flags: trit[1] = [-1]\n"
        "    return (mutate(&mut values) == -1) & (forward(&floats) == 1.0) & (len(floats) == 2) & check_small(&small, &flags)\n"
    )
    compilation = compile_source(source, mode=SyntaxMode.V0_6)
    toolchain = NativeToolchain.detect()
    executable = toolchain.build(
        X8664Backend(register_allocation=register_allocation).generate(
            compilation.assembly
        ),
        tmp_path / f"slice-{register_allocation}",
    )
    completed = toolchain.run(executable)
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "program returned: -1"
