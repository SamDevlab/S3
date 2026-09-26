"""Contracts for the P4 default global value-residency policy."""

from __future__ import annotations

import textwrap

import pytest

from bootstrap.s3.assembly import parse_assembly
from bootstrap.s3.backends.x86_64 import (
    NativeBackendError,
    NativeToolchain,
    X8664Backend,
    generate_native_assembly,
)
from bootstrap.s3.pipeline import compile_source


def _simple_program():
    return parse_assembly(
        """
        .function main -> tryte
            .register r0, tryte
            .register r1, tryte
        .label entry
            TCONST r0, 10
            TMOV r1, r0
            TRET r1
        .end
        """
    )


def test_native_default_uses_global_residency_and_explicit_stack_opt_out() -> None:
    program = _simple_program()
    default = generate_native_assembly(program)
    allocated = X8664Backend(register_allocation=True).generate(program)
    stack = X8664Backend(register_allocation=False).generate(program)

    assert default == allocated
    assert default != stack
    default_frame_value_stores = [
        line
        for line in default.splitlines()
        if "mov qword ptr [rbp" in line and "r15" not in line
    ]
    assert default_frame_value_stores == []
    assert "mov qword ptr [rbp" in stack


def test_address_taken_target_remains_memory_identity_under_global_residency() -> None:
    source = """
    fn main() -> tryte:
        mut value: tryte = 10
        r: &mut tryte = &mut value
        return *r
    """
    native = generate_native_assembly(
        compile_source(textwrap.dedent(source), "O0").assembly
    )

    assert "mov word ptr [rbp" in native


def test_call_aware_global_residency_keeps_liveness_contract() -> None:
    program = parse_assembly(
        """
        .function helper -> tryte
            .param r0, tryte
        .label entry
            TRET r0
        .end
        .function main -> tryte
            .register r0, tryte
            .register r1, tryte
        .label entry
            TCONST r0, 10
            TCALL r1, helper, r0
            TADD r0, r0, r1
            TRET r0
        .end
        """
    )
    default = X8664Backend().generate(program)
    stack = X8664Backend(register_allocation=False).generate(program)

    assert default != stack
    assert "call s3_helper" in default
    assert "call s3_helper" in stack


def test_dead_incoming_parameter_does_not_clobber_live_resident_parameter(
    tmp_path,
) -> None:
    program = parse_assembly(
        """
        .function helper -> tryte
            .param r0, tryte
            .param r1, tryte
        .label entry
            TRET r0
        .end
        .function main -> tryte
            .register r0, tryte
            .register r1, tryte
            .register r2, tryte
        .label entry
            TCONST r0, 10
            TCONST r1, 2
            TCALL r2, helper, r0, r1
            TRET r2
        .end
        """
    )
    try:
        toolchain = NativeToolchain.detect()
    except NativeBackendError as error:
        pytest.skip(str(error))

    executable = toolchain.build(
        generate_native_assembly(program),
        tmp_path / "dead-incoming-parameter",
    )
    completed = toolchain.run(executable)

    assert completed.returncode == 0
    assert completed.stderr == ""
    assert completed.stdout == "program returned: 10\n"
