"""Integration and differential tests for the S3 register allocator."""

from __future__ import annotations

import os
from pathlib import Path
import textwrap
import pytest

from bootstrap.s3.assembly import parse_assembly
from bootstrap.s3.backends.x86_64 import (
    NativeBackendError,
    NativeToolchain,
    X8664Backend,
    generate_native_assembly,
)
from bootstrap.s3.backends.x86_64.allocation import analyze_allocation
from bootstrap.s3.backends.x86_64.registers import FULL_ALLOCATABLE_REGISTERS
from bootstrap.s3.emulator import Emulator, EmulatorError
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import compile_source


NATIVE_REQUIRED = os.environ.get("S3_NATIVE_REQUIRED") == "1"


@pytest.fixture(scope="session")
def native_toolchain() -> NativeToolchain:
    try:
        return NativeToolchain.detect()
    except NativeBackendError as error:
        if NATIVE_REQUIRED:
            pytest.fail(f"required native toolchain unavailable: {error}")
        pytest.skip(str(error))


def _run_native_allocated(program, toolchain, output, register_allocation=True):
    backend = X8664Backend(register_allocation=register_allocation)
    assembly = backend.generate(program)
    executable = toolchain.build(assembly, output)
    return toolchain.run(executable)


def test_default_path_is_identical() -> None:
    # FASE 24: DEFAULT_PATH_OUTPUT_IDENTICAL=YES
    source = """
    .function main -> tryte
        .register r0, tryte
        .register r1, tryte
        .register r2, tryte
    .label entry
        TCONST r0, 5
        TCONST r1, 10
        TADD r2, r0, r1
        TRET r2
    .end
    """
    program = parse_assembly(source)

    assembly_default = generate_native_assembly(program)
    assembly_opt_out = X8664Backend(register_allocation=False).generate(program)

    assert assembly_default == assembly_opt_out


def test_physical_residency_observed(native_toolchain, tmp_path) -> None:
    # FASE 25: PHYSICAL_RESIDENCY_OBSERVED=YES
    source = """
    .function main -> tryte
        .register r0, tryte
    .label entry
        TCONST r0, 42
        TRET r0
    .end
    """
    program = parse_assembly(source)

    backend = X8664Backend(register_allocation=True)
    assembly = backend.generate(program)
    function = program.functions[0]
    allocation = analyze_allocation(function)
    physical = allocation.physical_register(0)

    # Derive the observed physical register from the same AllocationPlan used
    # by the emitter, rather than coupling integration coverage to one color.
    assert physical is not None
    assert physical in FULL_ALLOCATABLE_REGISTERS
    assert f"mov {physical}, rax" in assembly

    # Run program to verify correctness
    executable = native_toolchain.build(assembly, tmp_path / "obs_exec")
    completed = native_toolchain.run(executable)
    assert completed.returncode == 0
    assert completed.stdout == "program returned: 42\n"


# 28. CASOS OBRIGATÓRIOS: Matrix of test programs in S3 Assembly (NO inline comments)
TEST_CASES = {
    "arithmetic": (
        """
        .function main -> tryte
            .register r0, tryte
            .register r1, tryte
            .register r2, tryte
        .label entry
            TCONST r0, 100
            TCONST r1, 25
            TADD r2, r0, r1
            TRET r2
        .end
        """,
        125
    ),
    "unary": (
        """
        .function main -> tryte
            .register r0, tryte
            .register r1, tryte
        .label entry
            TCONST r0, 5
            TINV r1, r0
            TRET r1
        .end
        """,
        -5
    ),
    "comparisons": (
        """
        .function main -> trit
            .register r0, tryte
            .register r1, tryte
            .register r2, trit
        .label entry
            TCONST r0, 10
            TCONST r1, 20
            TCMP r2, r0, r1
            TRET r2
        .end
        """,
        -1
    ),
    "branches": (
        """
        .function main -> tryte
            .register r0, trit
            .register r1, tryte
        .label entry
            TCONST r0, 0
            TBR3 r0, left, right, join
        .label left
            TCONST r1, 10
            TRET r1
        .label right
            TCONST r1, 20
            TRET r1
        .label join
            TCONST r1, 30
            TRET r1
        .end
        """,
        20
    ),
    "joins": (
        """
        .function main -> tryte
            .register r0, trit
            .register r1, tryte
            .register r2, tryte
        .label entry
            TCONST r0, -1
            TBR3 r0, left, right, join
        .label left
            TCONST r1, 10
            TJMP join
        .label right
            TCONST r1, 20
            TJMP join
        .label join
            TCONST r2, 5
            TADD r1, r1, r2
            TRET r1
        .end
        """,
        15
    ),
    "loops": (
        """
        .function main -> tryte
            .register r0, tryte
            .register r1, tryte
            .register r2, tryte
            .register r3, trit
            .register r4, tryte
            .register r5, tryte
        .label entry
            TCONST r0, 5
            TCONST r1, 0
            TCONST r2, -1
            TJMP header
        .label header
            TCONST r4, 0
            TCMP r3, r0, r4
            TBR3 r3, exit_negative, exit_neutral, body
        .label body
            TADD r1, r1, r0
            TADD r0, r0, r2
            TJMP header
        .label exit
            TRET r1
        .label exit_negative
            TJMP exit
        .label exit_neutral
            TJMP exit
        .end
        """,
        15
    ),
    "nested_loops": (
        """
        .function main -> tryte
            .register r0, tryte
            .register r1, tryte
            .register r2, tryte
            .register r3, tryte
            .register r4, trit
            .register r5, tryte
            .register r6, tryte
        .label entry
            TCONST r0, 3
            TCONST r1, 0
            TCONST r3, 1
            TCONST r6, -1
            TJMP outer_header
        .label outer_header
            TCONST r5, 0
            TCMP r4, r0, r5
            TBR3 r4, outer_exit_negative, outer_exit_neutral, outer_body
        .label outer_body
            TCONST r2, 2
            TJMP inner_header
        .label inner_header
            TCONST r5, 0
            TCMP r4, r2, r5
            TBR3 r4, inner_exit_negative, inner_exit_neutral, inner_body
        .label inner_body
            TADD r1, r1, r3
            TADD r2, r2, r6
            TJMP inner_header
        .label inner_exit
            TADD r0, r0, r6
            TJMP outer_header
        .label inner_exit_negative
            TJMP inner_exit
        .label inner_exit_neutral
            TJMP inner_exit
        .label outer_exit
            TRET r1
        .label outer_exit_negative
            TJMP outer_exit
        .label outer_exit_neutral
            TJMP outer_exit
        .end
        """,
        6
    ),
    "function_calls": (
        """
        .function add_helper -> tryte
            .param r0, tryte
            .param r1, tryte
            .register r2, tryte
        .label entry
            TADD r2, r0, r1
            TRET r2
        .end

        .function main -> tryte
            .register r0, tryte
            .register r1, tryte
            .register r2, tryte
        .label entry
            TCONST r0, 15
            TCONST r1, 30
            TCALL r2, add_helper, r0, r1
            TRET r2
        .end
        """,
        45
    ),
    "nested_calls": (
        """
        .function double_val -> tryte
            .param r0, tryte
            .register r1, tryte
        .label entry
            TADD r1, r0, r0
            TRET r1
        .end

        .function add_helper -> tryte
            .param r0, tryte
            .param r1, tryte
            .register r2, tryte
            .register r3, tryte
        .label entry
            TADD r2, r0, r1
            TCALL r3, double_val, r2
            TRET r3
        .end

        .function main -> tryte
            .register r0, tryte
            .register r1, tryte
            .register r2, tryte
        .label entry
            TCONST r0, 5
            TCONST r1, 10
            TCALL r2, add_helper, r0, r1
            TRET r2
        .end
        """,
        30
    ),
    "recursion": (
        """
        .function fact -> tryte
            .param r0, tryte
            .register r1, tryte
            .register r2, trit
            .register r3, tryte
            .register r4, tryte
            .register r5, tryte
            .register r6, tryte
        .label entry
            TCONST r1, 1
            TCONST r6, -1
            TCMP r2, r0, r1
            TBR3 r2, base_negative, base_neutral, recursive
        .label base_negative
            TJMP base
        .label base
            TRET r1
        .label base_neutral
            TJMP base
        .label recursive
            TADD r3, r0, r6
            TCALL r4, fact, r3
            TADD r5, r0, r0
            TADD r5, r5, r0
            TADD r1, r4, r0
            TRET r1
        .end

        .function main -> tryte
            .register r0, tryte
            .register r1, tryte
            .register r2, tryte
        .label entry
            TCONST r0, 3
            TCALL r1, fact, r0
            TRET r1
        .end
        """,
        6
    ),
    "six_plus_arguments": (
        """
        .function sum_eight -> tryte
            .param r0, tryte
            .param r1, tryte
            .param r2, tryte
            .param r3, tryte
            .param r4, tryte
            .param r5, tryte
            .param r6, tryte
            .param r7, tryte
            .register r8, tryte
        .label entry
            TADD r8, r0, r1
            TADD r8, r8, r2
            TADD r8, r8, r3
            TADD r8, r8, r4
            TADD r8, r8, r5
            TADD r8, r8, r6
            TADD r8, r8, r7
            TRET r8
        .end

        .function main -> tryte
            .register r0, tryte
            .register r1, tryte
            .register r2, tryte
            .register r3, tryte
            .register r4, tryte
            .register r5, tryte
            .register r6, tryte
            .register r7, tryte
            .register r8, tryte
        .label entry
            TCONST r0, 1
            TCONST r1, 1
            TCONST r2, 1
            TCONST r3, 1
            TCONST r4, 1
            TCONST r5, 1
            TCONST r6, 1
            TCONST r7, 1
            TCALL r8, sum_eight, r0, r1, r2, r3, r4, r5, r6, r7
            TRET r8
        .end
        """,
        8
    ),
    "memory_load_store": (
        """
        .function main -> tryte
            .memory m0, tryte, 5, mutable
            .register r0, tryte
            .register r1, tryte
            .register r2, tryte
        .label entry
            TCONST r0, 0
            TCONST r1, 123
            TSTORE m0, r0, r1
            TLOAD r2, m0, r0
            TRET r2
        .end
        """,
        123
    ),
    "immutable_memory_behavior": (
        """
        .function main -> tryte
            .memory m0, tryte, 3, immutable
            .register r0, tryte
            .register r1, tryte
            .register r2, tryte
        .label entry
            TCONST r0, 1
            TCONST r1, 42
            TSTORE m0, r0, r1
            TLOAD r2, m0, r0
            TRET r2
        .end
        """,
        42
    ),
    "high_register_pressure": (
        """
        .function main -> tryte
            .register r0, tryte
            .register r1, tryte
            .register r2, tryte
            .register r3, tryte
            .register r4, tryte
            .register r5, tryte
            .register r6, tryte
            .register r7, tryte
        .label entry
            TCONST r0, 1
            TCONST r1, 2
            TCONST r2, 3
            TCONST r3, 4
            TCONST r4, 5
            TCONST r5, 6
            TCONST r6, 7
            TADD r7, r0, r1
            TADD r7, r7, r2
            TADD r7, r7, r3
            TADD r7, r7, r4
            TADD r7, r7, r5
            TADD r7, r7, r6
            TRET r7
        .end
        """,
        28
    )
}


@pytest.mark.parametrize("name", list(TEST_CASES.keys()))
def test_equivalence_matrix(name, native_toolchain, tmp_path) -> None:
    source, expected = TEST_CASES[name]
    program = parse_assembly(source)

    # 1. Emulator check
    assert Emulator().execute(program) == expected

    # 2. Native Stack-Backed check (register_allocation=False)
    completed_stack = _run_native_allocated(
        program, native_toolchain, tmp_path / f"{name}_stack", register_allocation=False
    )
    assert completed_stack.returncode == 0
    assert completed_stack.stdout == f"program returned: {expected}\n"

    # 3. Native Register-Allocated check (register_allocation=True)
    completed_reg = _run_native_allocated(
        program, native_toolchain, tmp_path / f"{name}_reg", register_allocation=True
    )
    assert completed_reg.returncode == 0
    assert completed_reg.stdout == f"program returned: {expected}\n"


@pytest.mark.parametrize("name", list(TEST_CASES.keys()))
def test_equivalence_matrix_fixture_is_valid(name) -> None:
    source, expected = TEST_CASES[name]
    program = parse_assembly(source)
    assert Emulator().execute(program) == expected


# FASE 27: Matrix of O0 / O1 Optimization
def test_optimization_matrix_o0_o1(native_toolchain, tmp_path) -> None:
    high_level_source = textwrap.dedent("""
    fn main() -> tryte:
        mut a: tryte = 10
        mut b: tryte = 20
        return a + b
    """).strip()
    for opt in ("O0", "O1"):
        program = compile_source(high_level_source, opt, mode=SyntaxMode.V0_6).assembly

        # Emulator
        assert Emulator().execute(program) == 30

        # Stack-backed
        completed_stack = _run_native_allocated(
            program, native_toolchain, tmp_path / f"opt_matrix_{opt}_stack", register_allocation=False
        )
        assert completed_stack.returncode == 0
        assert completed_stack.stdout == "program returned: 30\n"

        # Register-allocated
        completed_reg = _run_native_allocated(
            program, native_toolchain, tmp_path / f"opt_matrix_{opt}_reg", register_allocation=True
        )
        assert completed_reg.returncode == 0
        assert completed_reg.stdout == "program returned: 30\n"


# Error scenarios: FASE 28 & FASE 29
def test_uninitialized_register_error(native_toolchain, tmp_path) -> None:
    source = """
    .function main -> tryte
        .register r0, tryte
        .register r1, tryte
    .label entry
        TCONST r0, 10
        TADD r1, r0, r1
        TRET r1
    .end
    """
    program = parse_assembly(source)

    # 1. Emulator check raises EmulatorError
    with pytest.raises(EmulatorError):
        Emulator().execute(program)

    # 2. Native Stack-backed check fails
    completed_stack = _run_native_allocated(
        program, native_toolchain, tmp_path / "uninit_stack", register_allocation=False
    )
    assert completed_stack.returncode != 0
    assert "uninitialized register" in completed_stack.stderr.lower()

    # 3. Native Register-allocated check fails identically
    completed_reg = _run_native_allocated(
        program, native_toolchain, tmp_path / "uninit_reg", register_allocation=True
    )
    assert completed_reg.returncode != 0
    assert "uninitialized register" in completed_reg.stderr.lower()


def test_overflow_error(native_toolchain, tmp_path) -> None:
    source = """
    .function main -> tryte
        .register r0, tryte
        .register r1, tryte
        .register r2, tryte
    .label entry
        TCONST r0, 300
        TCONST r1, 100
        TADD r2, r0, r1
        TRET r2
    .end
    """
    program = parse_assembly(source)

    # Emulator
    with pytest.raises(EmulatorError):
        Emulator().execute(program)

    # Native Stack
    completed_stack = _run_native_allocated(
        program, native_toolchain, tmp_path / "overflow_stack", register_allocation=False
    )
    assert completed_stack.returncode != 0
    assert "overflow" in completed_stack.stderr.lower()

    # Native Register
    completed_reg = _run_native_allocated(
        program, native_toolchain, tmp_path / "overflow_reg", register_allocation=True
    )
    assert completed_reg.returncode != 0
    assert "overflow" in completed_reg.stderr.lower()


def test_bounds_error(native_toolchain, tmp_path) -> None:
    source = """
    .function main -> tryte
        .memory m0, tryte, 3, mutable
        .register r0, tryte
        .register r1, tryte
    .label entry
        TCONST r0, 5
        TCONST r1, 10
        TSTORE m0, r0, r1
        TRET r1
    .end
    """
    program = parse_assembly(source)

    # Emulator
    with pytest.raises(EmulatorError):
        Emulator().execute(program)

    # Native Stack
    completed_stack = _run_native_allocated(
        program, native_toolchain, tmp_path / "bounds_stack", register_allocation=False
    )
    assert completed_stack.returncode != 0
    assert "index 5 outside [0, 3)" in completed_stack.stderr.lower()

    # Native Register
    completed_reg = _run_native_allocated(
        program, native_toolchain, tmp_path / "bounds_reg", register_allocation=True
    )
    assert completed_reg.returncode != 0
    assert "index 5 outside [0, 3)" in completed_reg.stderr.lower()


def test_stale_physical_value_bypass_initialization(native_toolchain, tmp_path) -> None:
    # FASE 29: STALE_PHYSICAL_VALUE_CANNOT_BYPASS_INITIALIZATION=YES
    source = """
    .function main -> tryte
        .register r0, tryte
        .register r1, tryte
        .register r2, tryte
    .label entry
        TCONST r0, 42
        TADD r2, r1, r0
        TRET r2
    .end
    """
    program = parse_assembly(source)

    # Emulator raises EmulatorError
    with pytest.raises(EmulatorError):
        Emulator().execute(program)

    # Native Register allocated must raise uninitialized error
    completed = _run_native_allocated(
        program, native_toolchain, tmp_path / "stale_reg", register_allocation=True
    )
    assert completed.returncode != 0
    assert "uninitialized register" in completed.stderr.lower()
