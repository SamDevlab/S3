from __future__ import annotations

import math
import os
import platform
from pathlib import Path

import pytest

from bootstrap.s3.backends.x86_64 import NativeBackendError, NativeToolchain, generate_native_assembly
from bootstrap.s3.emulator import Emulator
from bootstrap.s3.ir import IROpcode
from bootstrap.s3.ir_emulator import execute_ir
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import compile_source


def compile_program(source: str, optimization: str = "O0"):
    return compile_source(source, optimization, mode=SyntaxMode.V0_6)


def test_i64_arithmetic_is_source_visible_end_to_end() -> None:
    source = (
        "fn arithmetic(a: i64, b: i64) -> i64:\n"
        "    return -(a * b) / b + a - a\n"
        "fn main() -> trit:\n"
        "    return arithmetic(123456, 3) == -123456\n"
    )
    for optimization in ("O0", "O1"):
        compilation = compile_program(source, optimization)
        assert execute_ir(compilation.ir) == -1
        assert Emulator().execute(compilation.assembly) == -1
        opcodes = {instruction.opcode for fn in compilation.ir.functions for instruction in fn.instructions}
        assert IROpcode.NUMERIC_DIFFERENCE in opcodes
        assert IROpcode.MULTIPLY in opcodes
        assert IROpcode.DIVIDE in opcodes
        assert IROpcode.COMPARE in opcodes


@pytest.mark.s3_native
@pytest.mark.skipif(
    platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"},
    reason="requires Linux x86-64 native toolchain",
)
def test_i64_subtraction_handles_int64_min_without_false_intermediate_overflow(tmp_path: Path) -> None:
    source = (
        "fn minimum(seed: i64) -> i64:\n"
        "    return seed * 2\n"
        "fn subtract(a: i64, b: i64) -> i64:\n"
        "    return a - b\n"
        "fn main() -> trit:\n"
        "    return (subtract(minimum(-4611686018427387904), minimum(-4611686018427387904)) == 0) & (subtract(-1, minimum(-4611686018427387904)) == 9223372036854775807)\n"
    )
    toolchain = NativeToolchain.detect()
    for optimization in ("O0", "O1"):
        compilation = compile_program(source, optimization)
        assert execute_ir(compilation.ir) == -1
        assert Emulator().execute(compilation.assembly) == -1
        assert any(
            instruction.opcode is IROpcode.NUMERIC_DIFFERENCE
            for function in compilation.ir.functions
            for instruction in function.instructions
        )
        native_source = generate_native_assembly(compilation.assembly)
        assert "sub rax, r10" in native_source
        executable = toolchain.build(native_source, tmp_path / f"subtract-{optimization.lower()}")
        completed = toolchain.run(executable)
        assert completed.returncode == 0
        assert completed.stderr == ""
        assert completed.stdout.strip() == "program returned: -1"

def test_f64_arithmetic_and_ieee_special_values_are_preserved() -> None:
    source = (
        "fn arithmetic(a: f64, b: f64) -> f64:\n"
        "    return -(a * b) / b + a - a\n"
        "fn divzero(a: f64, b: f64) -> f64:\n"
        "    return a / b\n"
        "fn main() -> trit:\n"
        "    return arithmetic(12.5, 2.0) == -12.5\n"
    )
    compilation = compile_program(source)
    assert execute_ir(compilation.ir) == -1
    assert Emulator().execute(compilation.assembly) == -1

    special = compile_program(
        "fn divzero(a: f64, b: f64) -> f64:\n"
        "    return a / b\n"
        "fn main() -> trit:\n"
        "    return divzero(1.0, 0.0) > 0.0\n"
    )
    assert execute_ir(special.ir) == -1
    assert Emulator().execute(special.assembly) == -1


def test_f64_nan_relations_follow_ieee_rules() -> None:
    source = (
        "fn nan_value(zero: f64) -> f64:\n"
        "    return zero / zero\n"
        "fn main() -> trit:\n"
        "    return nan_value(0.0) != nan_value(0.0)\n"
    )
    compilation = compile_program(source)
    assert execute_ir(compilation.ir) == -1
    assert Emulator().execute(compilation.assembly) == -1
    assert any(
        instruction.opcode is IROpcode.RELATE
        for function in compilation.ir.functions
        for instruction in function.instructions
    )

    false_relation = compile_program(
        "fn nan_value(zero: f64) -> f64:\n"
        "    return zero / zero\n"
        "fn main() -> trit:\n"
        "    return nan_value(0.0) < 1.0\n"
    )
    assert execute_ir(false_relation.ir) == 0
    assert Emulator().execute(false_relation.assembly) == 0


def test_explicit_numeric_conversions_are_source_visible() -> None:
    source = (
        "fn widen(x: tryte) -> i64:\n"
        "    return to_i64(x)\n"
        "fn floatize(x: i64) -> f64:\n"
        "    return to_f64(x)\n"
        "fn narrow(x: i64) -> tryte:\n"
        "    return to_tryte(x)\n"
        "fn main() -> trit:\n"
        "    return (floatize(widen(12)) == 12.0) & (narrow(widen(12)) == 12)\n"
    )
    for optimization in ("O0", "O1"):
        compilation = compile_program(source, optimization)
        assert execute_ir(compilation.ir) == -1
        assert Emulator().execute(compilation.assembly) == -1
        assert any(
            instruction.opcode is IROpcode.CONVERT
            for function in compilation.ir.functions
            for instruction in function.instructions
        )


def test_checked_i64_to_tryte_rejects_runtime_out_of_range() -> None:
    source = (
        "fn narrow(x: i64) -> tryte:\n"
        "    return to_tryte(x)\n"
        "fn main() -> tryte:\n"
        "    return narrow(1000)\n"
    )
    compilation = compile_program(source)
    with pytest.raises(Exception, match="tryte|364"):
        execute_ir(compilation.ir)
    with pytest.raises(Exception, match="tryte|364"):
        Emulator().execute(compilation.assembly)


@pytest.mark.s3_native
@pytest.mark.skipif(
    platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"},
    reason="requires Linux x86-64 native toolchain",
)
def test_large_i64_loop_reaches_one_million(tmp_path: Path) -> None:
    source = (
        "fn main() -> trit:\n"
        "    mut counter: i64 = 0\n"
        "    while counter < 1000000:\n"
        "        counter = counter + 1\n"
        "    return counter == 1000000\n"
    )
    compilation = compile_program(source, "O0")
    assert execute_ir(compilation.ir) == -1
    # Running ten-million-plus bytecode instructions in the Python Assembly
    # emulator is characterization, not the capability gate.  The same typed
    # Assembly is instead lowered and executed through the real Linux backend.
    toolchain = NativeToolchain.detect()
    native_source = generate_native_assembly(
        compilation.assembly,
        max_instructions=20_000_000,
    )
    executable = toolchain.build(native_source, tmp_path / "million-loop")
    completed = toolchain.run(executable)
    assert completed.returncode == 0
    assert completed.stderr == ""
    assert completed.stdout.strip() == "program returned: -1"


def test_scientific_scalar_probe_matches_expected_formula() -> None:
    source = (
        "fn score(logp: f64, mw: f64, aromatic: f64, tpsa: f64) -> f64:\n"
        "    return -3.0 + logp * -0.35 + (mw / 100.0) * -0.2 + aromatic * -0.4 + (tpsa / 50.0) * 0.15\n"
        "fn main() -> trit:\n"
        "    return (score(2.0, 300.0, 2.0, 50.0) > -4.551) & (score(2.0, 300.0, 2.0, 50.0) < -4.549)\n"
    )
    compilation = compile_program(source)
    assert execute_ir(compilation.ir) == -1
    assert Emulator().execute(compilation.assembly) == -1


pytestmark_native = [pytest.mark.s3_native, pytest.mark.s3_differential]


def test_numeric_closure_executes_natively(tmp_path: Path) -> None:
    try:
        toolchain = NativeToolchain.detect()
    except NativeBackendError as error:
        if os.environ.get("S3_NATIVE_REQUIRED") == "1":
            pytest.fail(f"required native toolchain unavailable: {error}")
        pytest.skip(str(error))
    source = (
        "fn calc_i(a: i64, b: i64) -> i64:\n"
        "    return -(a * b) / b\n"
        "fn calc_f(a: f64, b: f64) -> f64:\n"
        "    return -(a * b) / b\n"
        "fn main() -> trit:\n"
        "    return (calc_i(123456, 3) == -123456) & (calc_f(12.5, 2.0) == -12.5)\n"
    )
    for optimization in ("O0", "O1"):
        compilation = compile_program(source, optimization)
        native_source = generate_native_assembly(compilation.assembly, max_instructions=2_000_000)
        executable = toolchain.build(native_source, tmp_path / optimization.lower())
        completed = toolchain.run(executable)
        assert completed.returncode == 0
        assert completed.stderr == ""
        assert completed.stdout == "program returned: -1\n"
