from __future__ import annotations

import struct

from bootstrap.s3.macos_arm64_integration import build_macos_arm64_program, build_macos_arm64_scalar_return
from bootstrap.s3.pipeline import compile_source


def test_macos_arm64_release_artifact_is_macho_and_execution_deferment_is_explicit() -> None:
    artifact = build_macos_arm64_scalar_return(19)
    assert artifact.format == "mach-o-64-arm64"
    assert artifact.artifact.target.name == "macos-arm64"
    assert struct.unpack_from("<I", artifact.artifact.container_header, 0)[0] == 0xFEEDFACF
    assert artifact.execution_deferred


def test_macos_arm64_uses_shared_aarch64_return_contract() -> None:
    artifact = build_macos_arm64_scalar_return(-2)
    assert artifact.artifact.assembly.instructions == ("mov x0, #-2", "ret")


def test_macos_arm64_program_path_lowers_compiler_assembly_and_keeps_deferment_honest() -> None:
    compilation = compile_source(
        "fn twice(a: i64) -> i64:\n"
        "    return a * 2\n"
        "fn main() -> i64:\n"
        "    return twice(6)\n"
    )
    artifact = build_macos_arm64_program(compilation.assembly)
    assert artifact.format == "mach-o-64-arm64"
    assert artifact.execution_deferred
    assert ".globl _twice" in artifact.text
    assert ".globl _main" in artifact.text
    assert "bl _twice" in artifact.text
    assert any(symbol.endswith("tmul") for symbol in artifact.artifact.runtime_symbols)
