from __future__ import annotations

import ctypes
import platform
import subprocess
from pathlib import Path

import pytest

from bootstrap.s3.backends.x86_64 import InstructionBudgetMode, generate_ffi_assembly
from bootstrap.s3.pipeline import compile_source
from bootstrap.s3.ffi import build_shared_library
from bootstrap.s3.pipeline import compile_source


def test_foreign_and_exported_functions_are_source_visible_and_stable() -> None:
    source = """\
foreign fn host_add(a: i64, b: i64) -> i64
export fn add(a: i64, b: i64) -> i64:
    return a + b
fn main() -> i64:
    return host_add(1, 2)
"""
    result = compile_source(source)
    assert [(function.name, function.external, function.exported) for function in result.ir.functions] == [
        ("add", False, True),
        ("main", False, False),
        ("host_add", True, False),
    ]
    assembly = generate_ffi_assembly(result.assembly)
    assert ".globl add" in assembly
    assert "call host_add" in assembly
    assert "call add" not in assembly


def test_exported_borrowed_slice_uses_pointer_plus_i64_length_abi() -> None:
    source = """\
export fn sum(xs: &[i64]) -> i64:
    return xs[0] + xs[1]
fn main() -> i64:
    return 0
"""
    result = compile_source(source)
    assembly = generate_ffi_assembly(result.assembly)
    assert ".globl sum" in assembly
    assert "sum:" in assembly
    exported = next(function for function in result.assembly.functions if function.name == "sum")
    assert exported.exported is True
    assert [parameter.type.value for parameter in exported.parameters] == ["reference", "i64"]


def test_o1_ssa_round_trip_preserves_exported_function_metadata() -> None:
    source = """\
fn absolute(value: f64) -> f64:
    match value < 0.0:
        -1:
            return 0.0 - value
        0:
            return value
        1:
            return value
export fn magnitude(value: f64) -> f64:
    return absolute(value)
fn main() -> i64:
    return 0
"""

    result = compile_source(source, optimization="O1")
    ir_function = next(function for function in result.ir.functions if function.name == "magnitude")
    assembly_function = next(function for function in result.assembly.functions if function.name == "magnitude")

    assert ir_function.exported is True
    assert assembly_function.exported is True
    assert ".globl magnitude" in generate_ffi_assembly(result.assembly)


def test_ffi_assembly_accepts_explicit_budget_modes_and_keeps_per_default() -> None:
    source = """\
export fn count(limit: i64) -> i64:
    mut value: i64 = 0
    while value < limit:
        value = value + 1
    return value
fn main() -> i64:
    return 0
"""
    program = compile_source(source, optimization="O1").assembly

    per = generate_ffi_assembly(program)
    per_explicit = generate_ffi_assembly(program, instruction_budget_mode=InstructionBudgetMode.PER_INSTRUCTION)
    exact = generate_ffi_assembly(program, instruction_budget_mode=InstructionBudgetMode.EXACT_SEGMENT)
    hybrid = generate_ffi_assembly(program, instruction_budget_mode=InstructionBudgetMode.LOOP_HYBRID)

    assert per == per_explicit
    assert exact != per
    assert hybrid != per


@pytest.mark.skipif(platform.system() != "Linux", reason="requires Linux shared linker")
def test_real_shared_library_c_abi_and_zero_copy_slice(tmp_path: Path) -> None:
    source = """\
export fn add(a: i64, b: i64) -> i64:
    return a + b
export fn multiply(a: f64, b: f64) -> f64:
    return a * b
export fn sum(xs: &[i64]) -> i64:
    return xs[0] + xs[1]
export fn bump(xs: &mut [i64]) -> i64:
    xs[0] = xs[0] + 1
    return xs[0]
fn main() -> i64:
    return 0
"""
    library = build_shared_library(source, tmp_path / "libffi.so")
    symbols = subprocess.run(
        ["nm", "-D", "--defined-only", str(library)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert all(f" {name}" in symbols for name in ("add", "multiply", "sum", "bump"))
    lib = ctypes.CDLL(str(library))
    lib.add.argtypes = [ctypes.c_int64, ctypes.c_int64]
    lib.add.restype = ctypes.c_int64
    assert lib.add(2, 5) == 7
    lib.multiply.argtypes = [ctypes.c_double, ctypes.c_double]
    lib.multiply.restype = ctypes.c_double
    assert lib.multiply(1.5, 4.0) == pytest.approx(6.0)
    values = (ctypes.c_int64 * 2)(4, 9)
    lib.sum.argtypes = [ctypes.POINTER(ctypes.c_int64), ctypes.c_int64]
    lib.sum.restype = ctypes.c_int64
    assert lib.sum(values, 2) == 13
    lib.bump.argtypes = [ctypes.POINTER(ctypes.c_int64), ctypes.c_int64]
    lib.bump.restype = ctypes.c_int64
    assert lib.bump(values, 2) == 5
    assert values[0] == 5


@pytest.mark.skipif(platform.system() != "Linux", reason="requires Linux C toolchain")
def test_real_s3_to_c_calls_integer_and_float_foreign_symbols(tmp_path: Path) -> None:
    helper = tmp_path / "helper.c"
    helper.write_text(
        "long host_add(long a, long b) { return a + b; }\n"
        "double host_scale(double a, double b) { return a * b; }\n",
        encoding="ascii",
    )
    helper_object = tmp_path / "helper.o"
    subprocess.run(
        ["cc", "-fPIC", "-c", str(helper), "-o", str(helper_object)],
        check=True,
    )
    source = """\
foreign fn host_add(a: i64, b: i64) -> i64
foreign fn host_scale(a: f64, b: f64) -> f64
export fn call_host_add() -> i64:
    return host_add(7, 8)
export fn call_host_scale() -> f64:
    return host_scale(1.25, 4.0)
fn main() -> i64:
    return 0
"""
    library = build_shared_library(
        source,
        tmp_path / "libforeign.so",
        extra_objects=(helper_object,),
    )
    lib = ctypes.CDLL(str(library))
    lib.call_host_add.restype = ctypes.c_int64
    assert lib.call_host_add() == 15
    lib.call_host_scale.restype = ctypes.c_double
    assert lib.call_host_scale() == pytest.approx(5.0)


@pytest.mark.skipif(platform.system() != "Linux", reason="requires Linux shared linker")
def test_scientific_batch_score_matches_python_reference(tmp_path: Path) -> None:
    source = """\
export fn score(logp: &[f64], mw: &[f64], tpsa: &[f64], aromatic_rings: &[i64]) -> f64:
    return -3.0 + logp[0] * -0.35 + (mw[0] / 100.0) * -0.2 + to_f64(aromatic_rings[0]) * -0.4 + (tpsa[0] / 50.0) * 0.15
fn main() -> i64:
    return 0
"""
    library = build_shared_library(source, tmp_path / "libscore.so")
    lib = ctypes.CDLL(str(library))
    lib.score.argtypes = [
        ctypes.POINTER(ctypes.c_double), ctypes.c_int64,
        ctypes.POINTER(ctypes.c_double), ctypes.c_int64,
        ctypes.POINTER(ctypes.c_double), ctypes.c_int64,
        ctypes.POINTER(ctypes.c_int64), ctypes.c_int64,
    ]
    lib.score.restype = ctypes.c_double
    logp = (ctypes.c_double * 1)(2.1)
    mw = (ctypes.c_double * 1)(310.0)
    tpsa = (ctypes.c_double * 1)(75.0)
    rings = (ctypes.c_int64 * 1)(3)
    actual = lib.score(logp, 1, mw, 1, tpsa, 1, rings, 1)
    expected = -3.0 + 2.1 * -0.35 + (310.0 / 100.0) * -0.2 + 3 * -0.4 + (75.0 / 50.0) * 0.15
    assert actual == pytest.approx(expected)
