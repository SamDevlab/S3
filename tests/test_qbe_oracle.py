from __future__ import annotations

from dataclasses import replace
from functools import lru_cache
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
ORDERING_WORKLOAD_SOURCE = (
    _REPOSITORY_ROOT / "examples/language_maturity/insertion_sort_search.s3"
).read_text(encoding="utf-8")
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
QBE_ORDERING_CASES = (
    ((29, -4, 8, 8, 17, 0), (-4, 8, 17, 30)),
    ((6, 5, 4, 3, 2, 1), (1, 4, 6, 7)),
)


def _qbe_ordering_program(values: tuple[int, ...], targets: tuple[int, ...]) -> dict[str, str]:
    lines = [
        "module main",
        "from s3.workloads.ordering import insertion_sort",
        "from s3.workloads.ordering import binary_search",
        "fn main() -> i64:",
        f"    mut values: i64_vector = i64_vector_new({len(values)})",
    ]
    lines.extend(
        f"    discard i64_vector_push(&mut values, {value})" for value in values
    )
    lines.extend(
        [
            "    mut failures: i64 = 0",
            "    discard insertion_sort(&mut values)",
        ]
    )
    for index, expected in enumerate(sorted(values)):
        lines.append(
            f"    failures = failures + mismatch_index(i64_vector_get(&values, {index}), {expected})"
        )
    for target in targets:
        expected_index = sorted(values).index(target) if target in values else -1
        lines.append(
            "    failures = failures + mismatch_index("
            f"binary_search(&values, {target}), {expected_index})"
        )
    lines.extend(
        [
            "    return failures",
            "fn mismatch_index(actual: i64, expected: i64) -> i64:",
            "    match actual == expected:",
            "        -1:",
            "            return 0",
            "        0:",
            "            return 1",
            "        1:",
            "            return 1",
        ]
    )
    return {
        "main.s3": "\n".join(lines) + "\n",
        "s3/workloads/ordering.s3": ORDERING_WORKLOAD_SOURCE,
    }


QBE_I64_VECTOR_PROGRAM = """\
fn mismatch_index(actual: i64, expected: i64) -> i64:
    match actual == expected:
        -1:
            return 0
        0:
            return 1
        1:
            return 1
fn main() -> i64:
    mut values: i64_vector = i64_vector_new(2)
    discard i64_vector_push(&mut values, 4)
    discard i64_vector_push(&mut values, -3)
    discard i64_vector_reserve(&mut values, 4)
    discard i64_vector_push(&mut values, 7)
    mut clone: i64_vector = i64_vector_clone(&values)
    discard i64_vector_set(&mut clone, 0, 10)
    mut slice: i64_vector = i64_vector_slice(&values, 1, 3)
    mut failures: i64 = 0
    failures = failures + mismatch_index(i64_vector_len(&values), 3)
    failures = failures + mismatch_index(i64_vector_capacity(&values), 4)
    failures = failures + mismatch_index(i64_vector_capacity(&clone), 4)
    failures = failures + mismatch_index(i64_vector_get(&values, 0), 4)
    failures = failures + mismatch_index(i64_vector_get(&clone, 0), 10)
    failures = failures + mismatch_index(i64_vector_len(&slice), 2)
    failures = failures + mismatch_index(i64_vector_capacity(&slice), 2)
    failures = failures + mismatch_index(i64_vector_get(&slice, 0), -3)
    failures = failures + mismatch_index(i64_vector_get(&slice, 1), 7)
    failures = failures + mismatch_index(i64_vector_pop(&mut values), 7)
    failures = failures + mismatch_index(i64_vector_len(&values), 2)
    return failures
"""

QBE_TRYTE_VECTOR_PROGRAM = """\
fn mismatch_tryte(actual: tryte, expected: tryte) -> i64:
    match actual == expected:
        -1:
            return 0
        0:
            return 1
        1:
            return 1
fn mismatch_i64(actual: i64, expected: i64) -> i64:
    match actual == expected:
        -1:
            return 0
        0:
            return 1
        1:
            return 1
fn main() -> i64:
    mut values: tryte_vector = tryte_vector_new(2)
    discard tryte_vector_push(&mut values, -364)
    discard tryte_vector_push(&mut values, 364)
    discard tryte_vector_reserve(&mut values, 4)
    discard tryte_vector_push(&mut values, 0)
    mut clone: tryte_vector = tryte_vector_clone(&values)
    discard tryte_vector_set(&mut clone, 1, -123)
    mut slice: tryte_vector = tryte_vector_slice(&clone, 0, 3)
    mut failures: i64 = 0
    failures = failures + mismatch_i64(tryte_vector_len(&values), 3)
    failures = failures + mismatch_i64(tryte_vector_capacity(&values), 4)
    failures = failures + mismatch_tryte(tryte_vector_get(&values, 0), -364)
    failures = failures + mismatch_tryte(tryte_vector_get(&values, 1), 364)
    failures = failures + mismatch_tryte(tryte_vector_get(&clone, 1), -123)
    failures = failures + mismatch_tryte(tryte_vector_get(&slice, 0), -364)
    failures = failures + mismatch_tryte(tryte_vector_get(&slice, 1), -123)
    failures = failures + mismatch_tryte(tryte_vector_get(&slice, 2), 0)
    discard tryte_vector_set(&mut clone, 2, -321)
    failures = failures + mismatch_tryte(tryte_vector_pop(&mut clone), -321)
    failures = failures + mismatch_i64(tryte_vector_len(&clone), 2)
    failures = failures + mismatch_tryte(tryte_vector_pop(&mut values), 0)
    failures = failures + mismatch_i64(tryte_vector_len(&values), 2)
    return failures
"""

QBE_F64_VECTOR_PROGRAM = """\
fn mismatch_f64(actual: f64, expected: f64) -> i64:
    match actual == expected:
        -1:
            return 0
        0:
            return 1
        1:
            return 1
fn mismatch_i64(actual: i64, expected: i64) -> i64:
    match actual == expected:
        -1:
            return 0
        0:
            return 1
        1:
            return 1
fn main() -> i64:
    mut values: f64_vector = f64_vector_new(2)
    discard f64_vector_push(&mut values, 1.5)
    discard f64_vector_push(&mut values, -2.25)
    discard f64_vector_reserve(&mut values, 4)
    discard f64_vector_push(&mut values, 0.5)
    mut clone: f64_vector = f64_vector_clone(&values)
    discard f64_vector_set(&mut clone, 0, 3.75)
    mut slice: f64_vector = f64_vector_slice(&clone, 0, 3)
    mut failures: i64 = 0
    failures = failures + mismatch_i64(f64_vector_len(&values), 3)
    failures = failures + mismatch_i64(f64_vector_capacity(&values), 4)
    failures = failures + mismatch_f64(f64_vector_get(&values, 0), 1.5)
    failures = failures + mismatch_f64(f64_vector_get(&values, 1), -2.25)
    failures = failures + mismatch_f64(f64_vector_get(&clone, 0), 3.75)
    failures = failures + mismatch_f64(f64_vector_get(&slice, 0), 3.75)
    failures = failures + mismatch_f64(f64_vector_get(&slice, 1), -2.25)
    failures = failures + mismatch_f64(f64_vector_get(&slice, 2), 0.5)
    discard f64_vector_set(&mut clone, 2, -4.5)
    failures = failures + mismatch_f64(f64_vector_pop(&mut clone), -4.5)
    failures = failures + mismatch_i64(f64_vector_len(&clone), 2)
    failures = failures + mismatch_f64(f64_vector_pop(&mut values), 0.5)
    return failures
"""

QBE_I64_VECTOR_PARAMETER_PROGRAM = """\
fn append_and_read(values: i64_vector) -> i64:
    discard i64_vector_reserve(&mut values, 3)
    discard i64_vector_push(&mut values, 9)
    return i64_vector_get(&values, 1) + i64_vector_capacity(&values) - 12
fn main() -> i64:
    mut values: i64_vector = i64_vector_new(1)
    discard i64_vector_push(&mut values, 3)
    return append_and_read(values)
"""

QBE_I64_VECTOR_ERROR_CASES = (
    (
        "capacity",
        """\
fn main() -> i64:
    mut values: i64_vector = i64_vector_new(1)
    discard i64_vector_push(&mut values, 1)
    discard i64_vector_push(&mut values, 2)
    return 0
""",
    ),
    (
        "bounds",
        """\
fn main() -> i64:
    mut values: i64_vector = i64_vector_new(1)
    discard i64_vector_push(&mut values, 1)
    return i64_vector_get(&values, -1)
""",
    ),
    (
        "allocation",
        """\
fn main() -> i64:
    mut values: i64_vector = i64_vector_new(8388609)
    return i64_vector_len(&values)
""",
    ),
)

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

_QBE_TEST_RUNTIME = r"""
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

_QBE_F64_VECTOR_ABI_SHIM = r"""
#include <stdint.h>
#include <string.h>

_Static_assert(sizeof(double) == sizeof(uint64_t), "QBE f64 ABI requires binary64");

extern int64_t __s3_builtin_f64_vector_get(void *reference, int64_t index);
extern int64_t __s3_builtin_f64_vector_pop(void *reference);
extern int64_t __s3_builtin_f64_vector_push(void *reference, uint64_t bits);
extern int64_t __s3_builtin_f64_vector_set(void *reference, int64_t index, uint64_t bits);

static uint64_t s3_qbe_f64_to_bits(double value) {
    uint64_t bits;
    memcpy(&bits, &value, sizeof(bits));
    return bits;
}

static double s3_qbe_f64_from_bits(uint64_t bits) {
    double value;
    memcpy(&value, &bits, sizeof(value));
    return value;
}

double __s3_qbe_f64_vector_get(void *reference, int64_t index) {
    return s3_qbe_f64_from_bits(
        (uint64_t)__s3_builtin_f64_vector_get(reference, index));
}

double __s3_qbe_f64_vector_pop(void *reference) {
    return s3_qbe_f64_from_bits((uint64_t)__s3_builtin_f64_vector_pop(reference));
}

int64_t __s3_qbe_f64_vector_push(void *reference, double value) {
    return __s3_builtin_f64_vector_push(reference, s3_qbe_f64_to_bits(value));
}

int64_t __s3_qbe_f64_vector_set(void *reference, int64_t index, double value) {
    return __s3_builtin_f64_vector_set(reference, index, s3_qbe_f64_to_bits(value));
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


@lru_cache(maxsize=2)
def _qbe_s3_runtime_assembly(optimization: OptimizationLevel) -> str:
    runtime_provider = compile_source(
        "fn main() -> i64:\n    return 0\n",
        optimization=optimization,
    )
    assert runtime_provider.assembly is not None
    return X8664Backend().generate(runtime_provider.assembly)


@pytest.mark.parametrize("optimization", [OptimizationLevel.O0, OptimizationLevel.O1])
def test_qbe_s3_runtime_provider_excludes_workload_functions(optimization) -> None:
    runtime_assembly = _qbe_s3_runtime_assembly(optimization)

    assert "__s3_builtin_i64_vector_new:" in runtime_assembly
    assert "__s3_builtin_tryte_vector_new:" in runtime_assembly
    assert "__s3_builtin_f64_vector_new:" in runtime_assembly
    assert "s3_main:" in runtime_assembly
    assert "__s3mod_" not in runtime_assembly


def _build_qbe_native(
    program,
    optimization,
    name,
    tmp_path,
    qbe,
    cc,
    *,
    s3_runtime_assembly: str | None = None,
    f64_vector_abi_shim: bool = False,
):
    stem = f"{name}-{optimization.value}"
    il_path = tmp_path / f"{stem}.ssa"
    assembly_path = tmp_path / f"{stem}.s"
    object_path = tmp_path / f"{stem}.o"
    executable_path = tmp_path / stem
    runtime_path = tmp_path / f"{stem}-runtime.c"
    runtime_assembly_path = tmp_path / f"{stem}-s3-runtime.s"
    runtime_object_path = tmp_path / f"{stem}-s3-runtime.o"
    exported_runtime_object_path = tmp_path / f"{stem}-s3-runtime-exported.o"
    f64_vector_shim_path = tmp_path / f"{stem}-f64-vector-shim.c"
    f64_vector_shim_object_path = tmp_path / f"{stem}-f64-vector-shim.o"
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
    runtime_path.write_text(_QBE_TEST_RUNTIME, encoding="utf-8")
    link_inputs = [str(object_path)]
    if s3_runtime_assembly is not None:
        runtime_assembly_path.write_text(s3_runtime_assembly, encoding="utf-8")
        runtime_compile = subprocess.run(
            [cc, "-c", str(runtime_assembly_path), "-o", str(runtime_object_path)],
            check=False,
            capture_output=True,
            text=True,
        )
        assert runtime_compile.returncode == 0, (
            f"S3_RUNTIME_ASSEMBLY_FAILURE: {name}: {runtime_compile.stderr}"
        )
        objcopy = shutil.which("objcopy")
        assert objcopy is not None, "QBE_BUILD_FAILURE: objcopy is required to expose S3 runtime symbols"
        expose_symbols = [
            "__s3_builtin_tryte_vector_new",
            "__s3_builtin_tryte_vector_len",
            "__s3_builtin_tryte_vector_capacity",
            "__s3_builtin_tryte_vector_reserve",
            "__s3_builtin_tryte_vector_push",
            "__s3_builtin_tryte_vector_pop",
            "__s3_builtin_tryte_vector_get",
            "__s3_builtin_tryte_vector_set",
            "__s3_builtin_tryte_vector_clone",
            "__s3_builtin_tryte_vector_slice",
            "__s3_builtin_f64_vector_new",
            "__s3_builtin_f64_vector_len",
            "__s3_builtin_f64_vector_capacity",
            "__s3_builtin_f64_vector_reserve",
            "__s3_builtin_f64_vector_push",
            "__s3_builtin_f64_vector_pop",
            "__s3_builtin_f64_vector_get",
            "__s3_builtin_f64_vector_set",
            "__s3_builtin_f64_vector_clone",
            "__s3_builtin_f64_vector_slice",
            "__s3_builtin_i64_vector_new",
            "__s3_builtin_i64_vector_len",
            "__s3_builtin_i64_vector_capacity",
            "__s3_builtin_i64_vector_reserve",
            "__s3_builtin_i64_vector_push",
            "__s3_builtin_i64_vector_pop",
            "__s3_builtin_i64_vector_get",
            "__s3_builtin_i64_vector_set",
            "__s3_builtin_i64_vector_clone",
            "__s3_builtin_i64_vector_slice",
        ]
        expose = subprocess.run(
            [
                objcopy,
                "--redefine-sym=_start=s3_qbe_test_unused_start",
                *[f"--globalize-symbol={symbol}" for symbol in expose_symbols],
                str(runtime_object_path),
                str(exported_runtime_object_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        assert expose.returncode == 0, (
            f"S3_RUNTIME_SYMBOL_EXPORT_FAILURE: {name}: {expose.stderr}"
        )
        link_inputs.append(str(exported_runtime_object_path))
    if f64_vector_abi_shim:
        assert s3_runtime_assembly is not None
        f64_vector_shim_path.write_text(
            _QBE_F64_VECTOR_ABI_SHIM, encoding="utf-8"
        )
        shim_compile = subprocess.run(
            [
                cc,
                "-c",
                str(f64_vector_shim_path),
                "-o",
                str(f64_vector_shim_object_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        assert shim_compile.returncode == 0, (
            f"QBE_F64_VECTOR_ABI_SHIM_FAILURE: {name}: {shim_compile.stderr}"
        )
        link_inputs.append(str(f64_vector_shim_object_path))
    qbe_link = subprocess.run(
        [cc, "-no-pie", *link_inputs, str(runtime_path), "-o", str(executable_path)],
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
        if "capacity" in text or "reserved capacity" in text:
            return "capacity"
        if "allocation" in text or "active limit" in text:
            return "allocation"
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


def _require_qbe_native_tools() -> tuple[str, str]:
    required = os.environ.get("S3_QBE_NATIVE_REQUIRED") == "1"
    if (
        platform.system() != "Linux"
        or platform.machine().lower() not in {"x86_64", "amd64"}
    ):
        if required:
            pytest.fail("QBE_BUILD_FAILURE: required native qualification is not Linux x86-64")
        pytest.skip("QBE native oracle requires Linux x86-64")
    qbe = shutil.which("qbe")
    cc = shutil.which("gcc") or shutil.which("cc")
    if qbe is None or cc is None:
        if required:
            pytest.fail("QBE_BUILD_FAILURE: required qbe executable or C compiler is unavailable")
        pytest.skip("QBE and a native C toolchain are required for the QBE execution gate")
    return qbe, cc


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


@pytest.mark.parametrize("target", ["arm64", "rv64"])
@pytest.mark.parametrize("optimization", [OptimizationLevel.O0, OptimizationLevel.O1])
def test_qbe_emits_portable_codegen_for_real_s3_examples(
    target, optimization, tmp_path
) -> None:
    required = os.environ.get("S3_QBE_NATIVE_REQUIRED") == "1"
    qbe = shutil.which("qbe")
    if qbe is None:
        if required:
            pytest.fail("QBE_BUILD_FAILURE: required qbe executable is unavailable")
        pytest.skip("QBE executable is required for cross-target code generation")

    for name in REAL_QBE_EXAMPLES:
        compilation = compile_source(
            QBE_PROGRAMS[name], optimization=optimization
        )
        assert compilation.ir is not None
        il_path = tmp_path / f"{name}-{optimization.value}.ssa"
        assembly_path = tmp_path / f"{name}-{optimization.value}-{target}.s"
        il_path.write_text(translate_verified_ir(compilation.ir), encoding="utf-8")
        result = subprocess.run(
            [qbe, "-t", target, "-o", str(assembly_path), str(il_path)],
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"QBE_TARGET_CODEGEN_FAILURE: {name} {optimization.value} {target}: "
            f"{result.stderr}"
        )
        assert assembly_path.is_file() and assembly_path.stat().st_size > 0


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


@pytest.mark.parametrize("optimization", [OptimizationLevel.O0, OptimizationLevel.O1])
@pytest.mark.parametrize("values,targets", QBE_ORDERING_CASES)
def test_qbe_composes_real_sorting_and_binary_search_workload(
    values, targets, optimization
) -> None:
    compilation = compile_sources(
        _qbe_ordering_program(values, targets),
        optimization=optimization,
        entry_module="main",
    )
    assert compilation.ir is not None and compilation.assembly is not None
    assert execute_ir(compilation.ir) == 0
    assert execute_assembly(compilation.assembly) == 0

    il = translate_verified_ir(compilation.ir)
    assert "call $__s3_builtin_i64_vector_new(" in il
    assert "call $__s3_builtin_i64_vector_push(" in il
    assert "call $__s3_builtin_i64_vector_get(" in il
    assert "call $__s3_builtin_i64_vector_set(" in il
    assert "call $__s3mod_s3_workloads_ordering__insertion_sort(" in il
    assert "call $__s3mod_s3_workloads_ordering__binary_search(" in il


@pytest.mark.parametrize("optimization", [OptimizationLevel.O0, OptimizationLevel.O1])
@pytest.mark.parametrize("values,targets", QBE_ORDERING_CASES)
def test_qbe_native_real_sorting_and_binary_search_differential_when_linux_toolchain_exists(
    values, targets, optimization, tmp_path
) -> None:
    qbe, cc = _require_qbe_native_tools()
    compilation = compile_sources(
        _qbe_ordering_program(values, targets),
        optimization=optimization,
        entry_module="main",
    )
    assert compilation.ir is not None and compilation.assembly is not None
    qbe_native = _build_qbe_native(
        compilation.ir,
        optimization,
        "ordering-workload",
        tmp_path,
        qbe,
        cc,
        s3_runtime_assembly=_qbe_s3_runtime_assembly(optimization),
    )
    s3_native = _build_s3_native(
        compilation, optimization, "ordering-workload", tmp_path, cc
    )

    assert execute_ir(compilation.ir) == 0
    assert execute_assembly(compilation.assembly) == 0
    assert qbe_native.returncode == 0, qbe_native.stderr.decode(errors="replace")
    assert s3_native.returncode == 0, s3_native.stdout + s3_native.stderr
    assert "program returned: 0" in s3_native.stdout


@pytest.mark.parametrize("target", ["arm64", "rv64"])
@pytest.mark.parametrize("optimization", [OptimizationLevel.O0, OptimizationLevel.O1])
def test_qbe_generates_portable_codegen_for_real_ordering_workload(
    target, optimization, tmp_path
) -> None:
    required = os.environ.get("S3_QBE_NATIVE_REQUIRED") == "1"
    qbe = shutil.which("qbe")
    if qbe is None:
        if required:
            pytest.fail("QBE_BUILD_FAILURE: required qbe executable is unavailable")
        pytest.skip("QBE executable is required for cross-target code generation")
    compilation = compile_sources(
        _qbe_ordering_program((5, -2, 7, 0), (-2, 0, 5, 7, 9)),
        optimization=optimization,
        entry_module="main",
    )
    assert compilation.ir is not None
    il_path = tmp_path / f"ordering-{optimization.value}.ssa"
    assembly_path = tmp_path / f"ordering-{optimization.value}-{target}.s"
    il_path.write_text(translate_verified_ir(compilation.ir), encoding="utf-8")
    result = subprocess.run(
        [qbe, "-t", target, "-o", str(assembly_path), str(il_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"{target} codegen rejected ordering workload: {result.stderr}"
    assert assembly_path.is_file() and assembly_path.stat().st_size > 0


@pytest.mark.parametrize("optimization", [OptimizationLevel.O0, OptimizationLevel.O1])
@pytest.mark.parametrize(
    "name,source",
    [
        ("i64-vector-operations", QBE_I64_VECTOR_PROGRAM),
        ("i64-vector-value-parameter", QBE_I64_VECTOR_PARAMETER_PROGRAM),
    ],
)
def test_qbe_i64_vector_operations_preserve_s3_semantics(
    name, source, optimization
) -> None:
    compilation = compile_source(source, optimization=optimization)
    assert compilation.ir is not None and compilation.assembly is not None
    assert execute_ir(compilation.ir) == 0
    assert execute_assembly(compilation.assembly) == 0

    il = translate_verified_ir(compilation.ir)
    for builtin in (
        "i64_vector_new",
        "i64_vector_len",
        "i64_vector_capacity",
        "i64_vector_reserve",
        "i64_vector_push",
        "i64_vector_pop",
        "i64_vector_get",
        "i64_vector_set",
        "i64_vector_clone",
        "i64_vector_slice",
    ):
        if name == "i64-vector-operations" or builtin in {
            "i64_vector_new",
            "i64_vector_push",
            "i64_vector_get",
        }:
            assert f"call $__s3_builtin_{builtin}(" in il
    if name == "i64-vector-value-parameter":
        function_index = next(
            index
            for index, function in enumerate(compilation.ir.functions)
            if function.name == "append_and_read"
        )
        slot = f"%s3_f{function_index}_vector_slot_0"
        assert f"storel %r0, {slot}" in il


@pytest.mark.parametrize("optimization", [OptimizationLevel.O0, OptimizationLevel.O1])
def test_qbe_tryte_vector_operations_preserve_s3_semantics(optimization) -> None:
    compilation = compile_source(QBE_TRYTE_VECTOR_PROGRAM, optimization=optimization)
    assert compilation.ir is not None and compilation.assembly is not None
    assert execute_ir(compilation.ir) == 0
    assert execute_assembly(compilation.assembly) == 0

    il = translate_verified_ir(compilation.ir)
    for operation in (
        "new",
        "len",
        "capacity",
        "reserve",
        "push",
        "pop",
        "get",
        "set",
        "clone",
        "slice",
    ):
        assert f"call $__s3_builtin_tryte_vector_{operation}(" in il
    assert "=l extsh %s3_f" in il


@pytest.mark.parametrize("optimization", [OptimizationLevel.O0, OptimizationLevel.O1])
def test_qbe_f64_vector_operations_preserve_s3_semantics(optimization) -> None:
    compilation = compile_source(QBE_F64_VECTOR_PROGRAM, optimization=optimization)
    assert compilation.ir is not None and compilation.assembly is not None
    assert execute_ir(compilation.ir) == 0
    assert execute_assembly(compilation.assembly) == 0

    il = translate_verified_ir(compilation.ir)
    for operation in (
        "new",
        "len",
        "capacity",
        "reserve",
        "push",
        "pop",
        "get",
        "set",
        "clone",
        "slice",
    ):
        adapter = operation in {"push", "pop", "get", "set"}
        stem = "__s3_qbe_f64_vector_" if adapter else "__s3_builtin_f64_vector_"
        assert f"call ${stem}{operation}(" in il
    assert "=d call $__s3_qbe_f64_vector_get(" in il
    assert "d %r" in il


@pytest.mark.parametrize("optimization", [OptimizationLevel.O0, OptimizationLevel.O1])
@pytest.mark.parametrize(
    "name,source",
    [
        ("i64-vector-operations", QBE_I64_VECTOR_PROGRAM),
        ("i64-vector-value-parameter", QBE_I64_VECTOR_PARAMETER_PROGRAM),
    ],
)
def test_qbe_native_i64_vector_semantics_match_s3_when_linux_toolchain_exists(
    name, source, optimization, tmp_path
) -> None:
    qbe, cc = _require_qbe_native_tools()
    compilation = compile_source(source, optimization=optimization)
    assert compilation.ir is not None and compilation.assembly is not None
    qbe_native = _build_qbe_native(
        compilation.ir,
        optimization,
        name,
        tmp_path,
        qbe,
        cc,
        s3_runtime_assembly=_qbe_s3_runtime_assembly(optimization),
    )
    s3_native = _build_s3_native(compilation, optimization, name, tmp_path, cc)

    assert execute_ir(compilation.ir) == 0
    assert execute_assembly(compilation.assembly) == 0
    assert qbe_native.returncode == 0, qbe_native.stderr.decode(errors="replace")
    assert s3_native.returncode == 0, s3_native.stdout + s3_native.stderr
    assert "program returned: 0" in s3_native.stdout


@pytest.mark.parametrize("optimization", [OptimizationLevel.O0, OptimizationLevel.O1])
def test_qbe_native_tryte_vector_semantics_match_s3_when_linux_toolchain_exists(
    optimization, tmp_path
) -> None:
    qbe, cc = _require_qbe_native_tools()
    compilation = compile_source(QBE_TRYTE_VECTOR_PROGRAM, optimization=optimization)
    assert compilation.ir is not None and compilation.assembly is not None
    qbe_native = _build_qbe_native(
        compilation.ir,
        optimization,
        "tryte-vector",
        tmp_path,
        qbe,
        cc,
        s3_runtime_assembly=_qbe_s3_runtime_assembly(optimization),
    )
    s3_native = _build_s3_native(
        compilation, optimization, "tryte-vector", tmp_path, cc
    )

    assert execute_ir(compilation.ir) == 0
    assert execute_assembly(compilation.assembly) == 0
    assert qbe_native.returncode == 0, qbe_native.stderr.decode(errors="replace")
    assert s3_native.returncode == 0, s3_native.stdout + s3_native.stderr
    assert "program returned: 0" in s3_native.stdout


@pytest.mark.parametrize("optimization", [OptimizationLevel.O0, OptimizationLevel.O1])
def test_qbe_native_f64_vector_semantics_match_s3_when_linux_toolchain_exists(
    optimization, tmp_path
) -> None:
    qbe, cc = _require_qbe_native_tools()
    compilation = compile_source(QBE_F64_VECTOR_PROGRAM, optimization=optimization)
    assert compilation.ir is not None and compilation.assembly is not None
    qbe_native = _build_qbe_native(
        compilation.ir,
        optimization,
        "f64-vector",
        tmp_path,
        qbe,
        cc,
        s3_runtime_assembly=_qbe_s3_runtime_assembly(optimization),
        f64_vector_abi_shim=True,
    )
    s3_native = _build_s3_native(
        compilation, optimization, "f64-vector", tmp_path, cc
    )

    assert execute_ir(compilation.ir) == 0
    assert execute_assembly(compilation.assembly) == 0
    assert qbe_native.returncode == 0, qbe_native.stderr.decode(errors="replace")
    assert s3_native.returncode == 0, s3_native.stdout + s3_native.stderr
    assert "program returned: 0" in s3_native.stdout


@pytest.mark.parametrize("optimization", [OptimizationLevel.O0, OptimizationLevel.O1])
@pytest.mark.parametrize("category,source", QBE_I64_VECTOR_ERROR_CASES)
def test_qbe_native_i64_vector_error_categories_match_s3(
    category, source, optimization, tmp_path
) -> None:
    qbe, cc = _require_qbe_native_tools()
    compilation = compile_source(source, optimization=optimization)
    assert compilation.ir is not None and compilation.assembly is not None
    qbe_native = _build_qbe_native(
        compilation.ir,
        optimization,
        f"i64-vector-{category}",
        tmp_path,
        qbe,
        cc,
        s3_runtime_assembly=_qbe_s3_runtime_assembly(optimization),
    )
    s3_native = _build_s3_native(
        compilation, optimization, f"i64-vector-{category}", tmp_path, cc
    )

    assert _error_category(lambda: execute_ir(compilation.ir)) == category
    assert _error_category(lambda: execute_assembly(compilation.assembly)) == category
    assert s3_native.returncode != 0
    assert qbe_native.returncode == s3_native.returncode
    native_error = {
        "capacity": "runtime error: dynamic buffer capacity",
        "bounds": "runtime error: bounds",
        "allocation": "runtime error: dynamic buffer allocation",
    }[category]
    assert native_error in s3_native.stderr
    assert qbe_native.stderr.decode(errors="replace") == s3_native.stderr


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
    mut values: bytes = bytes_new(1)
    return bytes_len(&values)
""",
            "unsupported register type bytes",
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
            "aggregate_field_load",
        ),
        (
            """\
fn read(value: &i64) -> i64:
    return 0
fn main() -> i64:
    mut value: i64 = 1
    return read(&value)
""",
            "vector reference shape",
        ),
    ],
)
def test_qbe_oracle_rejects_ir_outside_the_supported_subset(
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
