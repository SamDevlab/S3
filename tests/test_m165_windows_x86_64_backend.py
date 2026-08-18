from __future__ import annotations

from bootstrap.s3.assembly import AssemblyType
from bootstrap.s3.pipeline import compile_source
from bootstrap.s3.targets import (
    LINUX_X86_64_TARGET,
    WINDOWS_X86_64_TARGET,
    cross_platform_target_catalog,
)
from bootstrap.s3.windows_x86_64 import (
    WIN64_CALLEE_SAVED_REGISTERS,
    WIN64_CALLER_SAVED_REGISTERS,
    Win64CallLayout,
    Win64ResultLayout,
    WindowsX8664BackendPlan,
    probe_windows_toolchain,
)


def test_windows_target_identity_is_explicit_without_changing_linux_default() -> None:
    assert WINDOWS_X86_64_TARGET.name == "windows-x86_64"
    assert WINDOWS_X86_64_TARGET.architecture == LINUX_X86_64_TARGET.architecture
    assert WINDOWS_X86_64_TARGET.environment == "windows"
    assert cross_platform_target_catalog().names == (
        "linux-x86_64",
        "windows-x86_64",
    )


def test_win64_argument_registers_are_position_based_and_float_aware() -> None:
    layout = Win64CallLayout.for_arguments(
        (AssemblyType.I64, AssemblyType.F64, AssemblyType.REFERENCE, AssemblyType.TRYTE, AssemblyType.I64, AssemblyType.F64)
    )

    assert tuple(item.register for item in layout.arguments[:4]) == (
        "rcx",
        "xmm1",
        "r8",
        "r9",
    )
    assert layout.arguments[4].stack_offset == 32
    assert layout.arguments[5].stack_offset == 40
    assert layout.stack_reservation_bytes == 48
    assert layout.stack_reservation_bytes % 16 == 0


def test_win64_saved_register_contract_is_closed() -> None:
    assert "rbx" in WIN64_CALLEE_SAVED_REGISTERS
    assert "r12" in WIN64_CALLEE_SAVED_REGISTERS
    assert "rcx" in WIN64_CALLER_SAVED_REGISTERS
    assert set(WIN64_CALLEE_SAVED_REGISTERS).isdisjoint(WIN64_CALLER_SAVED_REGISTERS)


def test_result_slots_preserve_s3_logical_aggregate_contract() -> None:
    scalar = Win64ResultLayout.for_result_types((AssemblyType.F64,))
    aggregate = Win64ResultLayout.for_result_types((AssemblyType.I64, AssemblyType.TRYTE))

    assert scalar.scalar_register == "xmm0"
    assert scalar.transport == "scalar-register"
    assert aggregate.logical_slots == (0, 1)
    assert aggregate.scalar_register is None
    assert aggregate.transport == "s3-logical-result-slots"


def test_backend_plan_covers_compiled_functions_without_claiming_pe_codegen() -> None:
    compilation = compile_source(
        "fn add(left: i64, right: i64) -> i64:\n"
        "    return left + right\n"
        "fn main() -> i64:\n"
        "    return add(2, 3)\n"
    )
    plan = WindowsX8664BackendPlan.from_program(compilation.assembly)

    assert plan.target_name == "windows-x86_64"
    assert [item.name for item in plan.functions] == ["add", "main"]
    assert plan.functions[0].call_layout.arguments[0].register == "rcx"
    assert plan.codegen_status == "STRUCTURAL_ONLY_TOOLCHAIN_DEFERRED"


def test_windows_toolchain_probe_is_fail_closed() -> None:
    probe = probe_windows_toolchain()
    assert probe.available is False
    assert "compiler" in probe.missing
    assert "linker" in probe.missing
