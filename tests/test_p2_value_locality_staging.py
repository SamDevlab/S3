from bootstrap.s3.assembly import AssemblyBlock, AssemblyInstruction, AssemblyOpcode, AssemblyType
from bootstrap.s3.codegen import _coalesce_local_moves


def _types(*items: tuple[int, AssemblyType]) -> tuple[tuple[int, AssemblyType], ...]:
    return items


def test_local_move_coalescing_removes_copy_chain_and_rewrites_uses() -> None:
    blocks = (
        AssemblyBlock(
            "entry",
            (
                AssemblyInstruction(AssemblyOpcode.TCONST, (0,), immediate=7),
                AssemblyInstruction(AssemblyOpcode.TMOV, (1, 0)),
                AssemblyInstruction(AssemblyOpcode.TMOV, (2, 1)),
                AssemblyInstruction(AssemblyOpcode.TADD, (3, 2, 0)),
                AssemblyInstruction(AssemblyOpcode.TRET, (3,)),
            ),
        ),
    )

    result = _coalesce_local_moves(
        blocks,
        _types(
            (0, AssemblyType.I64),
            (1, AssemblyType.I64),
            (2, AssemblyType.I64),
            (3, AssemblyType.I64),
        ),
    )

    assert [instruction.opcode for instruction in result[0].instructions] == [
        AssemblyOpcode.TCONST,
        AssemblyOpcode.TADD,
        AssemblyOpcode.TRET,
    ]
    assert result[0].instructions[1].registers == (3, 0, 0)


def test_local_move_coalescing_does_not_cross_basic_blocks() -> None:
    blocks = (
        AssemblyBlock(
            "entry",
            (
                AssemblyInstruction(AssemblyOpcode.TCONST, (0,), immediate=7),
                AssemblyInstruction(AssemblyOpcode.TMOV, (1, 0)),
            ),
        ),
        AssemblyBlock(
            "next",
            (
                AssemblyInstruction(AssemblyOpcode.TADD, (2, 1, 0)),
            ),
        ),
    )

    result = _coalesce_local_moves(
        blocks,
        _types(
            (0, AssemblyType.I64),
            (1, AssemblyType.I64),
            (2, AssemblyType.I64),
        ),
    )

    assert [instruction.opcode for instruction in result[0].instructions] == [
        AssemblyOpcode.TCONST,
        AssemblyOpcode.TMOV,
    ]
    assert result[1].instructions[0].registers == (2, 1, 0)


def test_local_move_coalescing_requires_matching_types() -> None:
    blocks = (
        AssemblyBlock(
            "entry",
            (
                AssemblyInstruction(AssemblyOpcode.TMOV, (1, 0)),
                AssemblyInstruction(AssemblyOpcode.TRET, (1,)),
            ),
        ),
    )

    result = _coalesce_local_moves(
        blocks,
        _types((0, AssemblyType.I64), (1, AssemblyType.F64)),
    )

    assert [instruction.opcode for instruction in result[0].instructions] == [
        AssemblyOpcode.TMOV,
        AssemblyOpcode.TRET,
    ]
