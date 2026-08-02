from __future__ import annotations

import pytest

from bootstrap.s3.assembly import (
    ASSEMBLY_FORMAT_VERSION,
    AssemblyParseError,
    parse_assembly,
)
from bootstrap.s3.emulator import execute_assembly


def test_assembly_0_6_round_trips_multi_cell_results() -> None:
    source = """\
.s3asm 0.6.0

.function pair -> [tryte, trit]
    .register r0, tryte
    .register r1, trit
.label entry
    TCONST r0, 7
    TCONST r1, 1
    TRET [r0, r1]
.end
.function main -> tryte
    .register r0, tryte
    .register r1, trit
    .register r2, tryte
.label entry
    TCALL [r0, r1], pair
    TCONST r2, 0
    TRET r2
.end
"""

    program = parse_assembly(source)

    assert program.version == ASSEMBLY_FORMAT_VERSION
    assert program.functions[0].result_types[0].value == "tryte"
    assert program.functions[0].result_types[1].value == "trit"
    call = program.functions[1].blocks[0].instructions[0]
    assert call.result_registers == (0, 1)
    assert call.argument_registers == ()
    assert parse_assembly(program.render()) == program
    assert execute_assembly(program) == 0


def test_assembly_0_6_supports_full_result_discard() -> None:
    source = """\
.s3asm 0.6.0

.function pair -> [tryte, trit]
    .register r0, tryte
    .register r1, trit
.label entry
    TCONST r0, 7
    TCONST r1, 1
    TRET [r0, r1]
.end
.function main -> tryte
    .register r0, tryte
.label entry
    TCALL [], pair
    TCONST r0, 3
    TRET r0
.end
"""

    program = parse_assembly(source)
    call = program.functions[1].blocks[0].instructions[0]

    assert call.result_registers == ()
    assert call.argument_registers == ()
    assert "TCALL  [], pair" in program.render()
    assert execute_assembly(program) == 3


@pytest.mark.parametrize(
    ("body", "message"),
    (
        (".function main -> [tryte]\n", "0.5.0 functions cannot use"),
        (
            ".function main -> tryte\n"
            "    .register r0, tryte\n"
            ".label entry\n"
            "    TRET [r0]\n"
            ".end\n",
            "0.5.0 TRET cannot use",
        ),
        (
            ".function main -> tryte\n"
            "    .register r0, tryte\n"
            ".label entry\n"
            "    TCALL [r0], main\n"
            ".end\n",
            "0.5.0 TCALL cannot use",
        ),
    ),
)
def test_assembly_0_5_rejects_result_list_forms(
    body: str,
    message: str,
) -> None:
    with pytest.raises(AssemblyParseError, match=message):
        parse_assembly(".s3asm 0.5.0\n\n" + body)
