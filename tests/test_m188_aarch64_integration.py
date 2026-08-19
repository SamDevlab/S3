from __future__ import annotations

import struct

from bootstrap.s3.aarch64_toolchain import AAPCS64_V1, LinuxAArch64NativeAssemblyBackend, create_cross_platform_backend_registry
from bootstrap.s3.arm64_integration import Arm64ExecutionStatus, LinuxAArch64Integration, MacOSArm64Integration
from bootstrap.s3.backends.aarch64 import AARCH64_ELF_MACHINE
from bootstrap.s3.backends.macos_arm64 import ARM64_CPU_TYPE
from bootstrap.s3.pipeline import compile_source


def test_linux_aarch64_artifact_is_structurally_integrated_without_fake_execution() -> None:
    artifact = LinuxAArch64Integration().build_scalar_return(7)
    assert artifact.target.name == "linux-aarch64"
    assert artifact.assembly.instructions == ("mov x0, #7", "ret")
    assert struct.unpack_from("<H", artifact.container_header, 18)[0] == AARCH64_ELF_MACHINE
    assert artifact.structural_valid
    assert artifact.execution_status is Arm64ExecutionStatus.DEFERRED_BY_ENVIRONMENT


def test_macos_arm64_artifact_uses_macho_identity_and_explicit_deferment() -> None:
    artifact = MacOSArm64Integration().build_scalar_return(3)
    assert artifact.target.name == "macos-arm64"
    assert struct.unpack_from("<I", artifact.container_header, 0)[0] == 0xFEEDFACF
    assert struct.unpack_from("<i", artifact.container_header, 4)[0] == ARM64_CPU_TYPE
    assert artifact.execution_status is Arm64ExecutionStatus.DEFERRED_BY_ENVIRONMENT


def test_linux_aarch64_lowers_complete_s3_assembly_program_not_only_scalar_fixture() -> None:
    compilation = compile_source(
        "fn add(a: i64, b: i64) -> i64:\n"
        "    return a + b\n"
        "fn main() -> i64:\n"
        "    return add(2, 3)\n"
    )
    artifact = LinuxAArch64Integration().build_program(compilation.assembly)
    assert artifact.target.name == "linux-aarch64"
    assert artifact.structural_valid
    assert artifact.execution_status is Arm64ExecutionStatus.DEFERRED_BY_ENVIRONMENT
    assert ".globl add" in artifact.text
    assert ".globl main" in artifact.text
    assert "bl add" in artifact.text
    assert any(symbol.endswith("tadd") for symbol in artifact.runtime_symbols)
    assert 0 < artifact.instruction_count <= 100_000


def test_cross_platform_registry_selects_arm64_backends_without_changing_default_registry() -> None:
    registry = create_cross_platform_backend_registry()
    assert registry.native_assembly_targets == ("linux-aarch64", "linux-x86_64", "macos-arm64")
    compilation = compile_source("fn main() -> i64:\n    return 7\n")
    linux_text = registry.get_native_assembly("linux-aarch64").generate(compilation.assembly)
    macos_text = registry.get_native_assembly("macos-arm64").generate(compilation.assembly)
    assert ".globl main" in linux_text
    assert ".globl _main" in macos_text


def test_aapcs64_build_plan_records_abi_and_runtime_relocations() -> None:
    compilation = compile_source(
        "fn main() -> i64:\n"
        "    return 4 + 5\n"
    )
    backend = LinuxAArch64NativeAssemblyBackend()
    plan = backend.build_plan(compilation.assembly)
    assert plan.structurally_complete
    assert plan.abi is AAPCS64_V1
    assert plan.abi.stack_alignment == 16
    assert plan.abi.integer_arguments == ("x0", "x1", "x2", "x3", "x4", "x5", "x6", "x7")
    assert plan.abi.floating_arguments == ("v0", "v1", "v2", "v3", "v4", "v5", "v6", "v7")
    assert plan.abi.indirect_result == "x8"
    assert plan.abi.max_program_instructions == 100_000
    assert any(relocation.symbol.endswith("tadd") for relocation in plan.relocations)


def test_macos_and_linux_program_lowering_share_s3_program_semantics_but_platform_symbols_differ() -> None:
    compilation = compile_source(
        "fn child() -> i64:\n"
        "    return 4\n"
        "fn main() -> i64:\n"
        "    return child()\n"
    )
    linux = LinuxAArch64Integration().build_program(compilation.assembly)
    macos = MacOSArm64Integration().build_program(compilation.assembly)
    assert "bl child" in linux.text
    assert "bl _child" in macos.text
    assert linux.instruction_count == macos.instruction_count
    assert macos.execution_status is Arm64ExecutionStatus.DEFERRED_BY_ENVIRONMENT


def test_native_certificate_requires_exact_result() -> None:
    integration = LinuxAArch64Integration()
    artifact = integration.build_scalar_return(11)
    certified = integration.certify_native_result(artifact, exit_code=0, observed_value=11, expected_value=11)
    assert certified.execution_status is Arm64ExecutionStatus.NATIVE_CERTIFIED
