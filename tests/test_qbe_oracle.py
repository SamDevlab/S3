from __future__ import annotations

from dataclasses import replace
import os
import platform
from pathlib import Path
import shutil
import subprocess

import pytest

from bootstrap.s3.ir import (
    IRBasicBlock,
    IRFunction,
    IRInstruction,
    IRMemoryObject,
    IRModule,
    IRParameter,
    IRRegister,
    IROpcode,
    IRType,
)
from bootstrap.s3.emulator import execute_assembly
from bootstrap.s3.ir_emulator import execute_ir
from bootstrap.s3.optimizer import OptimizationLevel
from bootstrap.s3.pipeline import compile_source, compile_sources
from bootstrap.s3.backends.x86_64.backend import X8664Backend
from bootstrap.s3.verifier import IRVerificationError, verify_ir
from tools.qbe_oracle import QBETranslationError, translate_verified_ir


SCALAR_PROGRAMS = {
    "constant": """\
fn main() -> i64:
    return 42
""",
    "compare_branch": """\
fn classify(value: i64) -> i64:
    match value <=> 0:
        -1:
            return -1
        0:
            return 0
        1:
            return 1
fn main() -> i64:
    return classify(2)
""",
    "nested_call": """\
fn identity(value: i64) -> i64:
    return value
fn forward(value: i64) -> i64:
    return identity(value)
fn main() -> i64:
    return forward(7)
""",
    "f64_identity": """\
fn identity(value: f64) -> f64:
    return value
fn main() -> i64:
    return 0
""",
    "f64_compare": """\
fn classify(value: f64) -> i64:
    match value <=> 0.0:
        -1:
            return -1
        0:
            return 0
        1:
            return 1
fn main() -> i64:
    return classify(1.5)
""",
    "f64_arithmetic": """\
fn arithmetic(a: f64, b: f64) -> f64:
    return -(a * b) / b + a - a
fn main() -> trit:
    return arithmetic(12.5, 2.0) == -12.5
""",
    "f64_nan_relation": """\
fn nan_value(zero: f64) -> f64:
    return zero / zero
fn main() -> trit:
    return nan_value(0.0) != nan_value(0.0)
""",
    "f64_negative_infinity": """\
fn main() -> trit:
    return (1.0 / -0.0) < 0.0
""",
    "enum_match": """\
enum Sign:
    Negative
    Zero
    Positive
fn classify(value: Sign) -> tryte:
    match value:
        Sign.Negative:
            return -1
        Sign.Zero:
            return 0
        Sign.Positive:
            return 1
fn main() -> tryte:
    return classify(Sign.Positive)
""",
    "record_scalar_fields": """\
record Pair:
    left: tryte
    right: tryte
fn sum(pair: Pair) -> tryte:
    return pair.left + pair.right
fn main() -> tryte:
    return sum(Pair(left=7, right=5))
""",
    "fixed_array_loop_sum": """\
fn main() -> tryte:
    values: tryte[3] = [1, 2, 3]
    mut index: i64 = 0
    mut total: tryte = 0
    while index < 3:
        total = total + values[index]
        index = index + 1
    return total
""",
}

REAL_QBE_EXAMPLES = {
    "first_example": ("examples/first.s3", 6),
    "mutable_switch_example": ("examples/mutable_switch.s3", 10),
    "mutable_value_example": ("examples/mutable_value.s3", 15),
    "native_abi_example": ("examples/native_abi.s3", 7),
    "nested_calls_example": ("examples/nested_calls.s3", 12),
    "recursive_memory_example": ("examples/recursive_memory.s3", 6),
    "sign_example": ("examples/sign.s3", -1),
    "simple_call_example": ("examples/simple_call.s3", 15),
    "static_array_example": ("examples/static_array.s3", 13),
    "trit_array_example": ("examples/trit_array.s3", 1),
    "recursive_sum_example": ("examples/recursive_sum.s3", 10),
}
_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
QBE_PROGRAMS = dict(SCALAR_PROGRAMS)
QBE_PROGRAMS.update(
    {
        name: (_REPOSITORY_ROOT / path).read_text(encoding="utf-8")
        for name, (path, _) in REAL_QBE_EXAMPLES.items()
    }
)
MULTI_MODULE_PROGRAM = {
    "main.s3": """\
module main
from arithmetic import double
fn main() -> i64:
    return double(21)
""",
    "arithmetic.s3": """\
module arithmetic
export fn double(value: i64) -> i64:
    return value * 2
""",
}
MULTI_MODULE_NOMINAL_PROGRAM = {
    "main.s3": """\
module main
from model import Flag
from model import Sign
from consumer import score
fn main() -> tryte:
    flag: Flag = Flag(active=-1, amount=8, sign=Sign.Positive)
    return score(flag)
""",
    "model.s3": """\
module model
export enum Sign:
    Negative
    Positive
export record Flag:
    active: trit
    amount: tryte
    sign: Sign
export fn marker() -> tryte:
    return 0
""",
    "consumer.s3": """\
module consumer
from model import Flag
from model import Sign
export fn score(flag: Flag) -> tryte:
    match flag.sign:
        Sign.Negative:
            return 0
        Sign.Positive:
            return flag.amount
""",
}

I64_MIN = -(1 << 63)
I64_MAX = (1 << 63) - 1

_I64_CASE_PAIRS = {
    "add": (
        (I64_MIN, 0),
        (I64_MIN, 1),
        (I64_MIN + 1, -1),
        (I64_MAX, 0),
        (I64_MAX, -1),
        (-2, 3),
        (1 << 60, -(1 << 59)),
    ),
    "sub": (
        (I64_MIN, I64_MIN),
        (I64_MIN, -1),
        (I64_MAX, 1),
        (-1, I64_MIN),
        (I64_MAX, 0),
        (-7, 9),
        (1 << 60, -(1 << 60)),
    ),
    "mul": (
        (I64_MIN, 0),
        (I64_MIN, 1),
        (I64_MAX, 1),
        (-2, -3),
        (3_037_000_499, 3_037_000_499),
        (1 << 32, -(1 << 30)),
        (0, I64_MAX),
    ),
    "div": (
        (I64_MIN, 1),
        (I64_MIN, 2),
        (I64_MAX, -1),
        (-7, 3),
        (7, -3),
        (-7, -3),
        (I64_MAX, 3),
    ),
}

I64_ERROR_CASES = (
    ("add", I64_MAX, 1, "overflow"),
    ("add", I64_MIN, -1, "overflow"),
    ("sub", I64_MIN, 1, "overflow"),
    ("sub", I64_MAX, -1, "overflow"),
    ("mul", I64_MAX, 2, "overflow"),
    ("mul", I64_MIN, -1, "overflow"),
    ("neg", I64_MIN, None, "overflow"),
    ("div", 1, 0, "division_by_zero"),
    ("div", I64_MIN, -1, "overflow"),
)

_QBE_FAILURE_RUNTIME = r"""
#include <stdio.h>
#include <stdlib.h>

static _Noreturn void s3_qbe_fail(const char *category, int status) {
    fprintf(stderr, "QBE_SEMANTIC_ERROR=%s\n", category);
    fflush(stderr);
    _Exit(status);
}

void s3_qbe_fail_overflow(void) {
    s3_qbe_fail("overflow", 86);
}

void s3_qbe_fail_division_by_zero(void) {
    s3_qbe_fail("division_by_zero", 87);
}

void s3_qbe_fail_bounds(void) {
    s3_qbe_fail("bounds", 88);
}
"""

BALANCED_SCALAR_PROGRAM = """\
fn trit_add(a: trit, b: trit) -> trit:
    return a + b
fn trit_min(a: trit, b: trit) -> trit:
    return a & b
fn trit_max(a: trit, b: trit) -> trit:
    return a | b
fn tryte_add(a: tryte, b: tryte) -> tryte:
    return a + b
fn tryte_min(a: tryte, b: tryte) -> tryte:
    return a & b
fn tryte_max(a: tryte, b: tryte) -> tryte:
    return a | b
fn widen(value: tryte) -> i64:
    return to_i64(value)
fn floatize(value: tryte) -> f64:
    return to_f64(value)
fn classify(value: trit) -> i64:
    match value <=> 0:
        -1:
            return -1
        0:
            return 0
        1:
            return 1
fn check_0() -> trit:
    return trit_add(-1, 1) == 0
fn check_1() -> trit:
    return trit_add(-1, 0) == -1
fn check_2() -> trit:
    return trit_min(-1, 1) == -1
fn check_3() -> trit:
    return trit_max(-1, 1) == 1
fn check_4() -> trit:
    return tryte_add(364, 0) == 364
fn check_5() -> trit:
    return tryte_add(-364, 1) == -363
fn check_6() -> trit:
    return tryte_min(2, 1) == -1
fn check_7() -> trit:
    return tryte_max(2, 1) == 4
fn check_8() -> trit:
    return widen(-364) == -364
fn check_9() -> trit:
    return floatize(364) == 364.0
fn check_10() -> trit:
    return classify(-1) == -1
fn array_read(index: i64) -> tryte:
    values: tryte[3] = [1, 2, 3]
    return values[index]
fn check_11() -> trit:
    return array_read(1) == 2
fn main() -> trit:
    return check_0() | check_1() | check_2() | check_3() | check_4() | check_5() | check_6() | check_7() | check_8() | check_9() | check_10() | check_11()
"""

BALANCED_ERROR_CASES = (
    ("trit", "fn calc(a: trit, b: trit) -> trit:\n    return a + b\nfn main() -> trit:\n    return calc(1, 1)\n", "overflow"),
    ("tryte", "fn calc(a: tryte, b: tryte) -> tryte:\n    return a + b\nfn main() -> tryte:\n    return calc(364, 1)\n", "overflow"),
    ("narrow", "fn calc(a: i64) -> tryte:\n    return to_tryte(a)\nfn main() -> tryte:\n    return calc(365)\n", "overflow"),
    (
        "bounds",
        "fn index() -> i64:\n    return 5\n"
        "fn main() -> tryte:\n    values: tryte[3] = [1, 2, 3]\n"
        "    return values[index()]\n",
        "bounds",
    ),
)


def _i64_expected(operation: str, left: int, right: int) -> int:
    if operation == "add":
        return left + right
    if operation == "sub":
        return left - right
    if operation == "mul":
        return left * right
    assert operation == "div" and right != 0
    quotient = abs(left) // abs(right)
    return -quotient if (left < 0) != (right < 0) else quotient


def _i64_source_value(value: int) -> str:
    if value == I64_MIN:
        return "(-9223372036854775807 - 1)"
    return str(value)


def _checked_i64_valid_source() -> str:
    source = [
        "fn calc_add(a: i64, b: i64) -> i64:",
        "    return a + b",
        "fn calc_sub(a: i64, b: i64) -> i64:",
        "    return a - b",
        "fn calc_mul(a: i64, b: i64) -> i64:",
        "    return a * b",
        "fn calc_div(a: i64, b: i64) -> i64:",
        "    return a / b",
        "fn calc_neg(a: i64) -> i64:",
        "    return -a",
    ]
    checks = []
    for operation, pairs in _I64_CASE_PAIRS.items():
        for left, right in pairs:
            expected = _i64_expected(operation, left, right)
            index = len(checks)
            source.extend(
                [
                    f"fn check_{index}() -> trit:",
                    "    return calc_"
                    f"{operation}({_i64_source_value(left)}, {_i64_source_value(right)}) "
                    f"== {_i64_source_value(expected)}",
                ]
            )
            checks.append(f"check_{index}()")
    source.extend(
        [
            f"fn check_{len(checks)}() -> trit:",
            "    return calc_neg(-9223372036854775807) == 9223372036854775807",
        ]
    )
    checks.append(f"check_{len(checks)}()")
    source.extend(
        [
            "fn main() -> trit:",
            "    return " + " | ".join(checks),
        ]
    )
    return "\n".join(source) + "\n"


def _i64_error_source(operation: str, left: int, right: int | None) -> str:
    if operation == "neg":
        return (
            "fn calc(a: i64) -> i64:\n"
            "    return -a\n"
            f"fn main() -> i64:\n    return calc({_i64_source_value(left)})\n"
        )
    operator = {"add": "+", "sub": "-", "mul": "*", "div": "/"}[operation]
    assert right is not None
    return (
        f"fn calc(a: i64, b: i64) -> i64:\n    return a {operator} b\n"
        f"fn main() -> i64:\n"
        f"    return calc({_i64_source_value(left)}, {_i64_source_value(right)})\n"
    )


def _build_qbe_native(program, optimization, name, tmp_path, qbe, cc):
    stem = f"{name}-{optimization.value}"
    il_path = tmp_path / f"{stem}.ssa"
    assembly_path = tmp_path / f"{stem}.s"
    object_path = tmp_path / f"{stem}.o"
    executable_path = tmp_path / stem
    runtime_path = tmp_path / f"{stem}-runtime.c"
    il_path.write_text(translate_verified_ir(program), encoding="utf-8")
    qbe_result = subprocess.run(
        [qbe, "-o", str(assembly_path), str(il_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert qbe_result.returncode == 0, (
        f"QBE_IL_REJECTED: {name} {optimization.value}: {qbe_result.stderr}"
    )
    assert assembly_path.is_file() and assembly_path.stat().st_size > 0, (
        f"QBE_ASSEMBLY_FAILURE: {name} {optimization.value}: no assembly emitted"
    )
    qbe_assembly = subprocess.run(
        [cc, "-c", str(assembly_path), "-o", str(object_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert qbe_assembly.returncode == 0, (
        f"QBE_ASSEMBLY_FAILURE: {name} {optimization.value}: {qbe_assembly.stderr}"
    )
    runtime_path.write_text(_QBE_FAILURE_RUNTIME, encoding="utf-8")
    qbe_link = subprocess.run(
        [cc, "-no-pie", str(object_path), str(runtime_path), "-o", str(executable_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert qbe_link.returncode == 0, (
        f"QBE_LINK_FAILURE: {name} {optimization.value}: {qbe_link.stderr}"
    )
    return subprocess.run([str(executable_path)], check=False, capture_output=True)


def _build_s3_native(compilation, optimization, name, tmp_path, cc):
    assert compilation.assembly is not None
    stem = f"{name}-{optimization.value}-s3"
    assembly_path = tmp_path / f"{stem}.s"
    executable_path = tmp_path / stem
    assembly_path.write_text(
        X8664Backend().generate(compilation.assembly), encoding="utf-8"
    )
    link = subprocess.run(
        [cc, "-nostartfiles", "-no-pie", str(assembly_path), "-o", str(executable_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert link.returncode == 0, link.stderr
    return subprocess.run(
        [str(executable_path)], check=False, capture_output=True, text=True
    )


def _error_category(call) -> str:
    try:
        call()
    except Exception as error:
        text = str(error).lower()
        if "division by zero" in text:
            return "division_by_zero"
        if "out of bounds" in text or (" index " in text and "outside [" in text):
            return "bounds"
        if isinstance(error, IndexError):
            return "bounds"
        if (
            "overflow" in text
            or "outside [" in text
            or "outside the" in text
            or "outside tryte range" in text
        ):
            return "overflow"
        pytest.fail(f"unclassified semantic error: {error!r}")
    pytest.fail("expected a semantic error")


@pytest.mark.parametrize("optimization", [OptimizationLevel.O0, OptimizationLevel.O1])
@pytest.mark.parametrize("name", tuple(QBE_PROGRAMS))
def test_qbe_oracle_emits_deterministic_verified_program_il(name: str, optimization) -> None:
    program = compile_source(QBE_PROGRAMS[name], optimization=optimization).ir
    assert program is not None

    first = translate_verified_ir(program)
    second = translate_verified_ir(program)

    assert first == second
    assert "function " in first
    assert "QBE oracle; generated from verified S3 IR" in first
    assert "export function " in first
    assert "$main()" in first


@pytest.mark.parametrize("optimization", [OptimizationLevel.O0, OptimizationLevel.O1])
@pytest.mark.parametrize(
    "name,expected",
    tuple((name, expected) for name, (_, expected) in REAL_QBE_EXAMPLES.items()),
)
def test_qbe_real_s3_examples_match_explicit_results(name, expected, optimization) -> None:
    compilation = compile_source(QBE_PROGRAMS[name], optimization=optimization)
    assert compilation.ir is not None
    assert execute_ir(compilation.ir) == expected
    assert execute_assembly(compilation.assembly) == expected
    assert translate_verified_ir(compilation.ir)


@pytest.mark.parametrize("optimization", [OptimizationLevel.O0, OptimizationLevel.O1])
def test_qbe_composes_frontend_resolved_multi_module_program(optimization) -> None:
    compilation = compile_sources(MULTI_MODULE_PROGRAM, optimization=optimization)
    assert compilation.ir is not None
    assert execute_ir(compilation.ir) == 42
    assert execute_assembly(compilation.assembly) == 42

    text = translate_verified_ir(compilation.ir)
    assert "function l $__s3mod_arithmetic__double(l %r" in text
    assert "call $__s3mod_arithmetic__double(" in text


@pytest.mark.parametrize("optimization", [OptimizationLevel.O0, OptimizationLevel.O1])
def test_qbe_composes_cross_module_record_and_enum_values(optimization) -> None:
    compilation = compile_sources(
        MULTI_MODULE_NOMINAL_PROGRAM,
        optimization=optimization,
        entry_module="main",
    )
    assert compilation.ir is not None
    assert execute_ir(compilation.ir) == 8
    assert execute_assembly(compilation.assembly) == 8

    text = translate_verified_ir(compilation.ir)
    assert "function l $__s3mod_consumer__score(" in text
    assert "call $__s3mod_consumer__score(" in text


@pytest.mark.parametrize("optimization", [OptimizationLevel.O0, OptimizationLevel.O1])
def test_qbe_native_cross_module_record_enum_differential_when_linux_toolchain_exists(
    optimization, tmp_path
) -> None:
    required = os.environ.get("S3_QBE_NATIVE_REQUIRED") == "1"
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        if required:
            pytest.fail("QBE_BUILD_FAILURE: required native qualification is not Linux x86-64")
        pytest.skip("QBE native oracle requires Linux x86-64")
    qbe = shutil.which("qbe")
    cc = shutil.which("gcc") or shutil.which("cc")
    if qbe is None or cc is None:
        if required:
            pytest.fail("QBE_BUILD_FAILURE: required qbe executable or C compiler is unavailable")
        pytest.skip("QBE and a native C toolchain are required for the QBE execution gate")

    compilation = compile_sources(
        MULTI_MODULE_NOMINAL_PROGRAM,
        optimization=optimization,
        entry_module="main",
    )
    assert compilation.ir is not None and compilation.assembly is not None
    qbe_native = _build_qbe_native(
        compilation.ir, optimization, "multi-module-nominal", tmp_path, qbe, cc
    )
    s3_native = _build_s3_native(
        compilation, optimization, "multi-module-nominal", tmp_path, cc
    )
    assert execute_ir(compilation.ir) == 8
    assert execute_assembly(compilation.assembly) == 8
    assert qbe_native.returncode == 8, qbe_native.stderr.decode(errors="replace")
    assert s3_native.returncode == 0, s3_native.stdout + s3_native.stderr
    assert "program returned: 8" in s3_native.stdout


@pytest.mark.parametrize("optimization", [OptimizationLevel.O0, OptimizationLevel.O1])
def test_qbe_native_multi_module_differential_when_linux_toolchain_exists(
    optimization, tmp_path
) -> None:
    required = os.environ.get("S3_QBE_NATIVE_REQUIRED") == "1"
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        if required:
            pytest.fail("QBE_BUILD_FAILURE: required native qualification is not Linux x86-64")
        pytest.skip("QBE native oracle requires Linux x86-64")
    qbe = shutil.which("qbe")
    cc = shutil.which("gcc") or shutil.which("cc")
    if qbe is None or cc is None:
        if required:
            pytest.fail("QBE_BUILD_FAILURE: required qbe executable or C compiler is unavailable")
        pytest.skip("QBE and a native C toolchain are required for the QBE execution gate")

    compilation = compile_sources(MULTI_MODULE_PROGRAM, optimization=optimization)
    assert compilation.ir is not None and compilation.assembly is not None
    qbe_native = _build_qbe_native(
        compilation.ir, optimization, "multi-module", tmp_path, qbe, cc
    )
    s3_native = _build_s3_native(
        compilation, optimization, "multi-module", tmp_path, cc
    )
    assert execute_ir(compilation.ir) == 42
    assert execute_assembly(compilation.assembly) == 42
    assert qbe_native.returncode == 42, qbe_native.stderr.decode(errors="replace")
    assert s3_native.returncode == 0, s3_native.stdout + s3_native.stderr
    assert "program returned: 42" in s3_native.stdout


def test_qbe_oracle_preserves_compare_branch_and_scalar_call_shapes() -> None:
    program = compile_source(SCALAR_PROGRAMS["compare_branch"]).ir
    assert program is not None
    text = translate_verified_ir(program)

    assert "csltl" in text
    assert "csgtl" in text
    assert "phi @" in text
    assert "ceql" in text
    assert "jnz" in text
    assert "call $classify(l" in text


def test_qbe_oracle_emits_f64_comparisons_without_integer_coercion() -> None:
    program = compile_source(SCALAR_PROGRAMS["f64_compare"]).ir
    assert program is not None
    text = translate_verified_ir(program)
    assert "cltd" in text
    assert "cgtd" in text
    assert "csltl" not in text


def test_qbe_oracle_emits_checked_integer_and_balanced_scalar_lowering() -> None:
    source = """\
fn checked_add(a: i64, b: i64) -> i64:
    return a + b
fn checked_sub(a: i64, b: i64) -> i64:
    return a - b
fn checked_mul(a: i64, b: i64) -> i64:
    return a * b
fn checked_div(a: i64, b: i64) -> i64:
    return a / b
fn checked_neg(a: i64) -> i64:
    return -a
fn add_trit(a: trit, b: trit) -> trit:
    return a + b
fn add_tryte(a: tryte, b: tryte) -> tryte:
    return a + b
fn min_trit(a: trit, b: trit) -> trit:
    return a & b
fn max_trit(a: trit, b: trit) -> trit:
    return a | b
fn min_tryte(a: tryte, b: tryte) -> tryte:
    return a & b
fn max_tryte(a: tryte, b: tryte) -> tryte:
    return a | b
fn narrow(value: i64) -> tryte:
    return to_tryte(value)
fn widen(value: tryte) -> i64:
    return to_i64(value)
fn floatize(value: i64) -> f64:
    return to_f64(value)
fn main() -> i64:
    return 0
"""
    program = compile_source(source).ir
    assert program is not None
    text = translate_verified_ir(program)
    for operation in ("checked_add", "checked_sub", "checked_mul", "checked_div", "checked_neg"):
        assert f"${operation}" in text
    assert "s3_qbe_fail_overflow" in text
    assert "s3_qbe_fail_division_by_zero" in text
    assert "rem" in text
    assert "div" in text
    assert "sltof" in text
    assert "function l $min_tryte" in text
    assert text.count("phi @") >= 7


def test_qbe_oracle_tryte_minimum_preserves_balanced_digit_semantics() -> None:
    program = compile_source(
        "fn minimum(a: tryte, b: tryte) -> tryte:\n"
        "    return a & b\n"
        "fn main() -> trit:\n"
        "    return minimum(2, 1) == -1\n"
    ).ir
    assert program is not None
    text = translate_verified_ir(program)

    # The decimal ordering differs here: balanced digitwise min(2, 1) is -1.
    assert execute_ir(program) == -1
    assert "tryte_min_join" in text
    assert text.count("remainder_") >= 12


def test_qbe_oracle_lowers_checked_scalar_memory_and_fixed_arrays() -> None:
    program = compile_source(
        "fn read(index: i64) -> tryte:\n"
        "    values: tryte[3] = [1, 2, 3]\n"
        "    return values[index]\n"
        "fn main() -> tryte:\n"
        "    return read(1)\n"
    ).ir
    assert program is not None
    text = translate_verified_ir(program)
    assert "alloc8 24" in text
    assert "storel" in text
    assert "loadl" in text
    assert "s3_qbe_fail_bounds" in text
    assert "csgel" in text


def test_qbe_oracle_rejects_uninitialized_memory_loads() -> None:
    module = IRModule(
        (
            IRFunction(
                "main",
                (),
                IRType.TRYTE,
                (IRRegister(0, IRType.I64), IRRegister(1, IRType.TRYTE)),
                (
                    IRBasicBlock(
                        "entry",
                        (
                            IRInstruction(IROpcode.CONST, result=0, immediate=0),
                            IRInstruction(IROpcode.LOAD, result=1, operands=(0,), memory=0),
                            IRInstruction(IROpcode.RETURN, operands=(1,)),
                        ),
                    ),
                ),
                memory_objects=(IRMemoryObject(0, IRType.TRYTE, 1, True),),
            ),
        )
    )
    verify_ir(module)
    with pytest.raises(QBETranslationError, match="may load uninitialized memory"):
        translate_verified_ir(module)


def test_qbe_oracle_accepts_store_then_load_at_same_runtime_index() -> None:
    module = IRModule(
        (
            IRFunction(
                "main",
                (IRParameter("index", 0, IRType.I64),),
                IRType.TRYTE,
                (
                    IRRegister(0, IRType.I64),
                    IRRegister(1, IRType.TRYTE),
                    IRRegister(2, IRType.TRYTE),
                ),
                (
                    IRBasicBlock(
                        "entry",
                        (
                            IRInstruction(IROpcode.CONST, result=1, immediate=5),
                            IRInstruction(IROpcode.STORE, operands=(0, 1), memory=0),
                            IRInstruction(IROpcode.LOAD, result=2, operands=(0,), memory=0),
                            IRInstruction(IROpcode.RETURN, operands=(2,)),
                        ),
                    ),
                ),
                memory_objects=(IRMemoryObject(0, IRType.TRYTE, 2, True),),
            ),
        )
    )
    verify_ir(module)
    assert "loadl" in translate_verified_ir(module)


def test_qbe_oracle_rejects_memory_initialized_on_only_one_branch() -> None:
    module = IRModule(
        (
            IRFunction(
                "main",
                (IRParameter("condition", 0, IRType.TRIT),),
                IRType.TRYTE,
                (
                    IRRegister(0, IRType.TRIT),
                    IRRegister(1, IRType.I64),
                    IRRegister(2, IRType.TRYTE),
                    IRRegister(3, IRType.TRYTE),
                ),
                (
                    IRBasicBlock(
                        "entry",
                        (
                            IRInstruction(IROpcode.CONST, result=1, immediate=0),
                            IRInstruction(IROpcode.CONST, result=2, immediate=5),
                            IRInstruction(
                                IROpcode.BRANCH3,
                                operands=(0,),
                                targets=("store", "skip", "join"),
                            ),
                        ),
                    ),
                    IRBasicBlock(
                        "store",
                        (
                            IRInstruction(IROpcode.STORE, operands=(1, 2), memory=0),
                            IRInstruction(IROpcode.JUMP, targets=("join",)),
                        ),
                    ),
                    IRBasicBlock("skip", (IRInstruction(IROpcode.JUMP, targets=("join",)),)),
                    IRBasicBlock(
                        "join",
                        (
                            IRInstruction(IROpcode.LOAD, result=3, operands=(1,), memory=0),
                            IRInstruction(IROpcode.RETURN, operands=(3,)),
                        ),
                    ),
                ),
                memory_objects=(IRMemoryObject(0, IRType.TRYTE, 1, True),),
            ),
        )
    )
    verify_ir(module)
    with pytest.raises(QBETranslationError, match="may load uninitialized memory"):
        translate_verified_ir(module)


@pytest.mark.parametrize(
    "source,reason",
    [
        (
            """\
fn main() -> i64:
    mut values: i64_vector = i64_vector_new(1)
    return i64_vector_len(&values)
""",
            "unsupported register type vector",
        ),
        (
            """\
record Pair:
    value: i64
fn read(pair: &Pair) -> i64:
    return pair.value
fn main() -> i64:
    mut pair: Pair = Pair(value=1)
    return read(&pair)
""",
            "non-scalar ABI parameter",
        ),
        (
            """\
fn read(value: &i64) -> i64:
    return 0
fn main() -> i64:
    mut value: i64 = 1
    return read(&value)
""",
            "non-scalar ABI parameter",
        ),
    ],
)
def test_qbe_oracle_rejects_ir_outside_the_scalar_subset(
    source: str, reason: str
) -> None:
    program = compile_source(source).ir
    assert program is not None
    with pytest.raises(QBETranslationError, match=reason):
        translate_verified_ir(program)


def test_qbe_oracle_verifies_ir_before_translation() -> None:
    program = compile_source(SCALAR_PROGRAMS["constant"]).ir
    assert program is not None
    function = program.functions[0]
    block = function.blocks[0]
    constant = next(item for item in block.instructions if item.opcode is IROpcode.CONST)
    bad_constant = replace(constant, immediate=1 << 100)
    bad_instructions = tuple(
        bad_constant if item is constant else item for item in block.instructions
    )
    bad_function = replace(
        function,
        blocks=(replace(block, instructions=bad_instructions), *function.blocks[1:]),
    )
    bad_program = IRModule((bad_function, *program.functions[1:]), program.static_strings)

    with pytest.raises(IRVerificationError):
        translate_verified_ir(bad_program)


@pytest.mark.parametrize("optimization", [OptimizationLevel.O0, OptimizationLevel.O1])
@pytest.mark.parametrize("name", tuple(QBE_PROGRAMS))
def test_qbe_native_program_differential_when_linux_toolchain_exists(
    name, optimization, tmp_path
) -> None:
    required = os.environ.get("S3_QBE_NATIVE_REQUIRED") == "1"
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        if required:
            pytest.fail("QBE_BUILD_FAILURE: required native qualification is not Linux x86-64")
        pytest.skip("QBE native oracle requires Linux x86-64")
    qbe = shutil.which("qbe")
    cc = shutil.which("gcc") or shutil.which("cc")
    if qbe is None or cc is None:
        if required:
            pytest.fail("QBE_BUILD_FAILURE: required qbe executable or C compiler is unavailable")
        pytest.skip("QBE and a native C toolchain are required for the QBE execution gate")

    compilation = compile_source(
        QBE_PROGRAMS[name], optimization=optimization
    )
    program = compilation.ir
    assert program is not None
    native = _build_qbe_native(program, optimization, name, tmp_path, qbe, cc)
    s3_native = _build_s3_native(compilation, optimization, name, tmp_path, cc)

    result = execute_ir(program)
    assert isinstance(result, int)
    if name in REAL_QBE_EXAMPLES:
        assert result == REAL_QBE_EXAMPLES[name][1]
    assert execute_assembly(compilation.assembly) == result
    assert native.returncode == (result & 0xFF), (
        f"QBE_RUNTIME_MISMATCH: {name} {optimization.value}: "
        f"expected exit status {result & 0xFF}, got {native.returncode}; "
        f"stderr={native.stderr.decode(errors='replace')}"
    )
    assert s3_native.returncode == 0, s3_native.stdout + s3_native.stderr
    assert f"program returned: {result}" in s3_native.stdout


@pytest.mark.parametrize("optimization", [OptimizationLevel.O0, OptimizationLevel.O1])
def test_qbe_native_checked_i64_generated_corpus_when_linux_toolchain_exists(
    optimization, tmp_path
) -> None:
    required = os.environ.get("S3_QBE_NATIVE_REQUIRED") == "1"
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        if required:
            pytest.fail("QBE_BUILD_FAILURE: required native qualification is not Linux x86-64")
        pytest.skip("QBE native oracle requires Linux x86-64")
    qbe = shutil.which("qbe")
    cc = shutil.which("gcc") or shutil.which("cc")
    if qbe is None or cc is None:
        if required:
            pytest.fail("QBE_BUILD_FAILURE: required qbe executable or C compiler is unavailable")
        pytest.skip("QBE and a native C toolchain are required for the QBE execution gate")

    source = _checked_i64_valid_source()
    compilation = compile_source(source, optimization=optimization)
    program = compilation.ir
    assert program is not None
    native = _build_qbe_native(
        program, optimization, "checked-i64-generated", tmp_path, qbe, cc
    )
    s3_assembly_path = tmp_path / f"checked-i64-s3-{optimization.value}.s"
    s3_executable_path = tmp_path / f"checked-i64-s3-{optimization.value}"
    s3_assembly_path.write_text(
        X8664Backend().generate(compilation.assembly), encoding="utf-8"
    )
    s3_link = subprocess.run(
        [cc, "-nostartfiles", "-no-pie", str(s3_assembly_path), "-o", str(s3_executable_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert s3_link.returncode == 0, s3_link.stderr

    expected = execute_ir(program)
    assert expected == -1
    assert execute_assembly(compilation.assembly) == expected
    assert native.returncode == (expected & 0xFF), native.stderr.decode(errors="replace")
    s3_native = subprocess.run(
        [str(s3_executable_path)], check=False, capture_output=True, text=True
    )
    assert s3_native.returncode == 0, s3_native.stdout + s3_native.stderr
    assert f"program returned: {expected}" in s3_native.stdout


@pytest.mark.parametrize("optimization", [OptimizationLevel.O0, OptimizationLevel.O1])
def test_qbe_native_balanced_scalar_differential_when_linux_toolchain_exists(
    optimization, tmp_path
) -> None:
    required = os.environ.get("S3_QBE_NATIVE_REQUIRED") == "1"
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        if required:
            pytest.fail("QBE_BUILD_FAILURE: required native qualification is not Linux x86-64")
        pytest.skip("QBE native oracle requires Linux x86-64")
    qbe = shutil.which("qbe")
    cc = shutil.which("gcc") or shutil.which("cc")
    if qbe is None or cc is None:
        if required:
            pytest.fail("QBE_BUILD_FAILURE: required qbe executable or C compiler is unavailable")
        pytest.skip("QBE and a native C toolchain are required for the QBE execution gate")

    compilation = compile_source(BALANCED_SCALAR_PROGRAM, optimization=optimization)
    program = compilation.ir
    assert program is not None
    expected = execute_ir(program)
    assert expected == -1
    assert execute_assembly(compilation.assembly) == expected

    qbe_native = _build_qbe_native(
        program, optimization, "balanced-scalars", tmp_path, qbe, cc
    )
    assert qbe_native.returncode == (expected & 0xFF), qbe_native.stderr.decode(
        errors="replace"
    )

    s3_assembly_path = tmp_path / f"balanced-scalars-s3-{optimization.value}.s"
    s3_executable_path = tmp_path / f"balanced-scalars-s3-{optimization.value}"
    s3_assembly_path.write_text(
        X8664Backend().generate(compilation.assembly), encoding="utf-8"
    )
    s3_link = subprocess.run(
        [cc, "-nostartfiles", "-no-pie", str(s3_assembly_path), "-o", str(s3_executable_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert s3_link.returncode == 0, s3_link.stderr
    s3_native = subprocess.run(
        [str(s3_executable_path)], check=False, capture_output=True, text=True
    )
    assert s3_native.returncode == 0, s3_native.stdout + s3_native.stderr
    assert f"program returned: {expected}" in s3_native.stdout


@pytest.mark.parametrize("optimization", [OptimizationLevel.O0, OptimizationLevel.O1])
@pytest.mark.parametrize("operation,left,right,category", I64_ERROR_CASES)
def test_qbe_native_checked_i64_error_categories_match_s3(
    operation, left, right, category, optimization, tmp_path
) -> None:
    required = os.environ.get("S3_QBE_NATIVE_REQUIRED") == "1"
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        if required:
            pytest.fail("QBE_BUILD_FAILURE: required native qualification is not Linux x86-64")
        pytest.skip("QBE native oracle requires Linux x86-64")
    qbe = shutil.which("qbe")
    cc = shutil.which("gcc") or shutil.which("cc")
    if qbe is None or cc is None:
        if required:
            pytest.fail("QBE_BUILD_FAILURE: required qbe executable or C compiler is unavailable")
        pytest.skip("QBE and a native C toolchain are required for the QBE execution gate")

    compilation = compile_source(
        _i64_error_source(operation, left, right), optimization=optimization
    )
    program = compilation.ir
    assert program is not None
    qbe_native = _build_qbe_native(
        program,
        optimization,
        f"checked-i64-{operation}-{category}",
        tmp_path,
        qbe,
        cc,
    )
    assert _error_category(lambda: execute_ir(program)) == category
    assert _error_category(lambda: execute_assembly(compilation.assembly)) == category

    s3_assembly_path = tmp_path / f"checked-i64-error-{optimization.value}.s"
    s3_executable_path = tmp_path / f"checked-i64-error-{optimization.value}"
    s3_assembly_path.write_text(
        X8664Backend().generate(compilation.assembly), encoding="utf-8"
    )
    s3_link = subprocess.run(
        [cc, "-nostartfiles", "-no-pie", str(s3_assembly_path), "-o", str(s3_executable_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert s3_link.returncode == 0, s3_link.stderr
    s3_native = subprocess.run(
        [str(s3_executable_path)], check=False, capture_output=True, text=True
    )
    assert s3_native.returncode != 0
    if category == "overflow":
        assert "runtime error [overflow]" in s3_native.stderr
        assert qbe_native.returncode == 86
        assert b"QBE_SEMANTIC_ERROR=overflow" in qbe_native.stderr
    elif category == "division_by_zero":
        assert "runtime error [division by zero]" in s3_native.stderr
        assert qbe_native.returncode == 87
        assert b"QBE_SEMANTIC_ERROR=division_by_zero" in qbe_native.stderr
    else:
        assert "runtime error [bounds]" in s3_native.stderr
        assert qbe_native.returncode == 88
        assert b"QBE_SEMANTIC_ERROR=bounds" in qbe_native.stderr


@pytest.mark.parametrize("optimization", [OptimizationLevel.O0, OptimizationLevel.O1])
@pytest.mark.parametrize("name,source,category", BALANCED_ERROR_CASES)
def test_qbe_native_balanced_scalar_error_categories_match_s3(
    name, source, category, optimization, tmp_path
) -> None:
    required = os.environ.get("S3_QBE_NATIVE_REQUIRED") == "1"
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        if required:
            pytest.fail("QBE_BUILD_FAILURE: required native qualification is not Linux x86-64")
        pytest.skip("QBE native oracle requires Linux x86-64")
    qbe = shutil.which("qbe")
    cc = shutil.which("gcc") or shutil.which("cc")
    if qbe is None or cc is None:
        if required:
            pytest.fail("QBE_BUILD_FAILURE: required qbe executable or C compiler is unavailable")
        pytest.skip("QBE and a native C toolchain are required for the QBE execution gate")

    compilation = compile_source(source, optimization=optimization)
    program = compilation.ir
    assert program is not None
    qbe_native = _build_qbe_native(
        program, optimization, f"balanced-error-{name}", tmp_path, qbe, cc
    )
    assert _error_category(lambda: execute_ir(program)) == category
    assert _error_category(lambda: execute_assembly(compilation.assembly)) == category

    s3_assembly_path = tmp_path / f"balanced-error-{name}-s3-{optimization.value}.s"
    s3_executable_path = tmp_path / f"balanced-error-{name}-s3-{optimization.value}"
    s3_assembly_path.write_text(
        X8664Backend().generate(compilation.assembly), encoding="utf-8"
    )
    s3_link = subprocess.run(
        [cc, "-nostartfiles", "-no-pie", str(s3_assembly_path), "-o", str(s3_executable_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert s3_link.returncode == 0, s3_link.stderr
    s3_native = subprocess.run(
        [str(s3_executable_path)], check=False, capture_output=True, text=True
    )
    assert s3_native.returncode != 0
    if category == "overflow":
        assert "runtime error [overflow]" in s3_native.stderr
        assert qbe_native.returncode == 86
        assert b"QBE_SEMANTIC_ERROR=overflow" in qbe_native.stderr
    elif category == "division_by_zero":
        assert "runtime error [division by zero]" in s3_native.stderr
        assert qbe_native.returncode == 87
        assert b"QBE_SEMANTIC_ERROR=division_by_zero" in qbe_native.stderr
    else:
        assert "runtime error [bounds]" in s3_native.stderr
        assert qbe_native.returncode == 88
        assert b"QBE_SEMANTIC_ERROR=bounds" in qbe_native.stderr
