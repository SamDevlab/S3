from __future__ import annotations

import pytest

from bootstrap.s3.assembly import parse_assembly
from bootstrap.s3.assembly_verifier import AssemblyVerifier, AssemblyVerifierError
from bootstrap.s3.backends.x86_64 import generate_native_assembly
from bootstrap.s3.emulator import Emulator, EmulatorError


VALID = """\
.function main -> tryte
    .register r0, tryte
.label entry
    TCONST r0, 1
    TRET r0
.end
"""


INVALID = """\
.function main -> tryte
    .register r0, trit
.label entry
    TCONST r0, 1
    TRET r0
.end
"""


def test_verifier_accepts_valid_and_rejects_invalid_assembly() -> None:
    verifier = AssemblyVerifier()
    verifier.validate(parse_assembly(VALID), entry="main")
    with pytest.raises(AssemblyVerifierError, match="TRET types"):
        verifier.validate(parse_assembly(INVALID), entry="main")


def test_emulator_public_validate_delegates_to_shared_verifier() -> None:
    program = parse_assembly(INVALID)
    with pytest.raises(EmulatorError, match="TRET types"):
        Emulator().validate(program, entry="main")


def test_native_backend_uses_verifier_without_executing_program() -> None:
    assert "Emulator" not in generate_native_assembly.__module__
    with pytest.raises(AssemblyVerifierError, match="TRET types"):
        generate_native_assembly(parse_assembly(INVALID))


def test_verifier_does_not_execute_valid_program() -> None:
    program = parse_assembly(VALID)
    AssemblyVerifier().validate(program, entry="main")
    assert Emulator().execute(program) == 1
