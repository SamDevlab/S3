from __future__ import annotations

import pytest

from bootstrap.s3.aarch64_object_link import AArch64ObjectLinkError, AArch64ObjectLinker
from bootstrap.s3.aarch64_toolchain import AArch64Relocation, LinuxAArch64NativeAssemblyBackend
from bootstrap.s3.pipeline import compile_source


def _plan():
    compilation = compile_source(
        "fn add(a: i64, b: i64) -> i64:\n"
        "    return a + b\n"
        "fn main() -> i64:\n"
        "    return add(2, 3)\n"
    )
    return LinuxAArch64NativeAssemblyBackend().build_plan(compilation.assembly)


def test_object_contains_exact_target_symbols_and_call_relocation() -> None:
    artifact = AArch64ObjectLinker().build_object(_plan())
    assert artifact.structural_valid
    assert artifact.bytes[:4] == b"\x7fELF"
    assert artifact.bytes[16:18] == (1).to_bytes(2, "little")
    assert artifact.bytes[18:20] == (183).to_bytes(2, "little")
    assert artifact.entry_symbol == "main"
    assert {symbol.name for symbol in artifact.symbols if symbol.defined} == {"add", "main"}
    assert any(relocation.symbol == "add" and relocation.kind == "call26" for relocation in artifact.relocations)


def test_link_requires_explicit_resolution_of_runtime_symbols() -> None:
    linker = AArch64ObjectLinker()
    artifact = linker.build_object(_plan())
    undefined = [symbol.name for symbol in artifact.symbols if not symbol.defined]
    if undefined:
        with pytest.raises(AArch64ObjectLinkError, match="unresolved"):
            linker.link(artifact)
    resolved = {name: 0x2000 + index * 0x100 for index, name in enumerate(undefined)}
    linked = linker.link(artifact, resolved_symbols=resolved)
    assert linked.structural_valid
    assert linked.bytes[16:18] == (2).to_bytes(2, "little")
    assert int.from_bytes(linked.bytes[24:32], "little") == linked.entrypoint
    with pytest.raises(AArch64ObjectLinkError, match="override"):
        linker.link(artifact, resolved_symbols={"main": 0x2000, **resolved})


def test_object_link_contract_rejects_unsupported_relocation() -> None:
    plan = _plan()
    broken = type(plan)(
        plan.target,
        plan.assembly_text,
        plan.container_header,
        plan.runtime_symbols,
        (AArch64Relocation("add", "absolute64", 0),),
        plan.abi,
        plan.defined_symbols,
        plan.entry_symbol,
    )
    with pytest.raises(AArch64ObjectLinkError, match="unsupported"):
        AArch64ObjectLinker().build_object(broken)


def test_object_link_contract_rejects_non_linux_target() -> None:
    plan = _plan()
    broken = type(plan)(
        "macos-arm64",
        plan.assembly_text,
        plan.container_header,
        plan.runtime_symbols,
        plan.relocations,
        plan.abi,
        plan.defined_symbols,
        plan.entry_symbol,
    )
    with pytest.raises(AArch64ObjectLinkError, match="linux-aarch64"):
        AArch64ObjectLinker().build_object(broken)


def test_object_encoder_emits_real_non_nop_text_and_rejects_unknown_instructions() -> None:
    plan = _plan()
    artifact = AArch64ObjectLinker().build_object(plan)
    text = artifact.bytes
    assert b"\xfd{\xbf\xa9" in text
    broken = type(plan)(
        plan.target,
        ".text\n.globl main\nmain:\n    totally_unknown x0\n    ret\n",
        plan.container_header,
        (),
        (),
        plan.abi,
        ("main",),
        "main",
    )
    with pytest.raises(AArch64ObjectLinkError, match="unsupported"):
        AArch64ObjectLinker().build_object(broken)
