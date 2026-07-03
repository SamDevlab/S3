from __future__ import annotations

import pytest

from bootstrap.s3.assembly import AssemblyParseError, parse_assembly
from bootstrap.s3.emulator import EmulatorError, execute_assembly


def test_invalid_register_is_detected() -> None:
    source = """\
.function main -> tryte
    .register r0, tryte
    TCONST r1, 1
    TRET r0
.end
"""
    with pytest.raises(EmulatorError, match="invalid register r1"):
        execute_assembly(source)


def test_uninitialized_register_is_detected() -> None:
    source = """\
.function main -> tryte
    .register r0, tryte
    TRET r0
.end
"""
    with pytest.raises(EmulatorError, match="uninitialized register r0"):
        execute_assembly(source)


def test_emulator_detects_overflow() -> None:
    source = """\
.function main -> tryte
    .register r0, tryte
    .register r1, tryte
    .register r2, tryte
    TCONST r0, 364
    TCONST r1, 1
    TADD r2, r0, r1
    TRET r2
.end
"""
    with pytest.raises(EmulatorError, match="tryte overflow"):
        execute_assembly(source)


def test_assembly_parser_rejects_unknown_opcode() -> None:
    source = """\
.function main -> tryte
    .register r0, tryte
    TSUB r0, r0, r0
.end
"""
    with pytest.raises(AssemblyParseError, match="unknown opcode 'TSUB'"):
        parse_assembly(source)


def test_comparison_requires_trit_destination() -> None:
    source = """\
.function main -> tryte
    .register r0, tryte
    .register r1, tryte
    .register r2, tryte
    TCONST r1, 1
    TCONST r2, 2
    TCMP r0, r1, r2
    TRET r0
.end
"""
    with pytest.raises(EmulatorError, match="destination must be a trit"):
        execute_assembly(source)

