from __future__ import annotations

import hashlib
from types import SimpleNamespace

from bootstrap.s3.assembly import (
    AssemblyBlock,
    AssemblyFunction,
    AssemblyInstruction,
    AssemblyOpcode,
    AssemblyProgram,
    AssemblyType,
)
from bootstrap.s3.assembly_fingerprint import assembly_program_sha256
from bootstrap.s3.compiler_provider import CompilerKind
from tools import characterize_s3c_ng_provider as characterization


def test_compile_hash_uses_structural_assembly_fingerprint(monkeypatch) -> None:
    assembly = AssemblyProgram(
        functions=(
            AssemblyFunction(
                name="main",
                return_type=AssemblyType.F64,
                parameters=(),
                register_types=(
                    (0, AssemblyType.F64),
                    (1, AssemblyType.F64),
                    (2, AssemblyType.F64),
                ),
                blocks=(
                    AssemblyBlock(
                        label="entry",
                        instructions=(
                            AssemblyInstruction(
                                opcode=AssemblyOpcode.TNDIFF,
                                registers=(2, 0, 1),
                            ),
                            AssemblyInstruction(
                                opcode=AssemblyOpcode.TRET,
                                registers=(2,),
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )
    ir = object()
    output = SimpleNamespace(require_ordinary_artifacts=lambda: (ir, assembly))
    monkeypatch.setattr(
        characterization,
        "compile_source_set_with_provider",
        lambda *_args, **_kwargs: output,
    )
    monkeypatch.setattr(characterization, "serialize_ir", lambda _ir: "canonical-ir")

    _, ir_hash, assembly_hash = characterization._compile_and_hash(
        {"main.s3": "unused"},
        provider=CompilerKind.PYTHON,
        executable=None,
        entry_module="main",
    )

    assert ir_hash == hashlib.sha256(b"canonical-ir").hexdigest()
    assert assembly_hash == assembly_program_sha256(assembly)
