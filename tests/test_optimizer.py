from __future__ import annotations

from pathlib import Path

import pytest

from bootstrap.s3.diagnostics import SemanticError
from bootstrap.s3.emulator import Emulator, EmulatorError
from bootstrap.s3.cli import main as cli_main
from bootstrap.s3.ir import (
    IRBasicBlock,
    IRFunction,
    IRInstruction,
    IRModule,
    IROpcode,
    IRRegister,
    IRType,
)
from bootstrap.s3.optimizer import (
    OptimizationLevel,
    instruction_count,
    optimize_ir,
)
from bootstrap.s3.pipeline import compile_source, run_source
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.verifier import verify_ir


ROOT = Path(__file__).parents[1]


def test_o0_is_default_and_preserves_lowered_ir() -> None:
    source = "fn main() -> tryte { return 1 + 2; }"
    default = compile_source(source, mode=SyntaxMode.V0_5)
    explicit = compile_source(
        source,
        OptimizationLevel.O0,
        mode=SyntaxMode.V0_5,
    )
    assert default.ir == explicit.ir
    assert default.assembly == explicit.assembly


def test_o1_folds_constants_and_eliminates_dead_pure_results() -> None:
    source = """\
fn main() -> tryte {
    tryte unused = 10 + 20;
    tryte folded = (1 + 2) & 4;
    return folded | 5;
}
"""
    o0 = compile_source(source, "O0", mode=SyntaxMode.V0_5)
    o1 = compile_source(source, "O1", mode=SyntaxMode.V0_5)
    assert run_source(
        source,
        optimization="O0",
        mode=SyntaxMode.V0_5,
    ) == 12
    assert run_source(
        source,
        optimization="O1",
        mode=SyntaxMode.V0_5,
    ) == 12
    assert instruction_count(o1.ir) < instruction_count(o0.ir)
    opcodes = [
        instruction.opcode
        for instruction in o1.ir.functions[0].instructions
    ]
    assert opcodes == [IROpcode.CONST, IROpcode.RETURN]
    verify_ir(o1.ir)


def test_constant_overflow_is_rejected_before_optimization() -> None:
    source = "fn main() -> tryte { return 364 + 1; }"
    for level in ("O0", "O1"):
        with pytest.raises(
            SemanticError,
            match=r"1:33: semantic error: tryte overflow: 364 \+ 1 = 365",
        ):
            compile_source(source, level, mode=SyntaxMode.V0_5)


def test_o1_does_not_hide_runtime_overflow() -> None:
    source = """\
fn increment(value: tryte) -> tryte {
    return value + 1;
}
fn main() -> tryte {
    return increment(364);
}
"""
    o1 = compile_source(source, "O1", mode=SyntaxMode.V0_5)
    assert IROpcode.ADD in {
        instruction.opcode
        for function in o1.ir.functions
        for instruction in function.instructions
    }
    for level in ("O0", "O1"):
        with pytest.raises(EmulatorError, match="overflow"):
            run_source(
                source,
                optimization=level,
                mode=SyntaxMode.V0_5,
            )


def test_o1_removes_unreachable_blocks_and_threads_empty_jumps() -> None:
    module = IRModule(
        (
            IRFunction(
                "main",
                (),
                IRType.TRYTE,
                (
                    IRRegister(0, IRType.TRYTE),
                    IRRegister(1, IRType.TRYTE),
                ),
                (
                    IRBasicBlock(
                        "dead",
                        (
                            IRInstruction(
                                IROpcode.CONST,
                                result=1,
                                immediate=99,
                            ),
                            IRInstruction(IROpcode.RETURN, operands=(1,)),
                        ),
                    ),
                    IRBasicBlock(
                        "entry",
                        (
                            IRInstruction(
                                IROpcode.JUMP,
                                targets=("trampoline",),
                            ),
                        ),
                    ),
                    IRBasicBlock(
                        "trampoline",
                        (
                            IRInstruction(
                                IROpcode.JUMP,
                                targets=("result",),
                            ),
                        ),
                    ),
                    IRBasicBlock(
                        "result",
                        (
                            IRInstruction(
                                IROpcode.CONST,
                                result=0,
                                immediate=6,
                            ),
                            IRInstruction(IROpcode.RETURN, operands=(0,)),
                        ),
                    ),
                ),
            ),
        )
    )
    optimized = optimize_ir(module, "O1")
    function = optimized.functions[0]
    assert tuple(block.name for block in function.blocks) == ("entry", "result")
    assert function.blocks[0].instructions[0].targets == ("result",)
    assert tuple(register.index for register in function.registers) == (0,)
    verify_ir(optimized)


@pytest.mark.parametrize(
    "filename",
    tuple(path.name for path in sorted((ROOT / "examples").glob("*.s3"))),
)
def test_all_examples_match_between_o0_and_o1(filename: str) -> None:
    source = (ROOT / "examples" / filename).read_text(encoding="utf-8")
    o0 = compile_source(source, "O0", mode=SyntaxMode.V0_6)
    o1 = compile_source(source, "O1", mode=SyntaxMode.V0_6)
    verify_ir(o1.ir)
    assert Emulator().execute(o0.assembly) == Emulator().execute(o1.assembly)
    assert "TSUB" not in o1.assembly_text


def test_o1_native_assembly_is_deterministic() -> None:
    source = (ROOT / "examples" / "static_array.s3").read_text(
        encoding="utf-8"
    )
    first = compile_source(source, "O1", mode=SyntaxMode.V0_6).assembly
    second = compile_source(source, "O1", mode=SyntaxMode.V0_6).assembly
    assert first.render() == second.render()


def test_cli_accepts_o1_for_asm_run_and_native_asm(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "fold.s3"
    source.write_text(
        "fn main() -> tryte:\n    return (1 + 2) + 3\n",
        encoding="utf-8",
    )
    assert cli_main(["asm", str(source), "-O1"]) == 0
    assembly_output = capsys.readouterr()
    assert assembly_output.err == ""
    assert assembly_output.out.startswith(".s3asm 0.5.0\n")
    assert "TADD" not in assembly_output.out

    assert cli_main(["run", str(source), "-O1"]) == 0
    assert capsys.readouterr().out == "program returned: 6\n"

    native = tmp_path / "fold.s"
    assert cli_main(
        ["native-asm", str(source), "-O1", "-o", str(native)]
    ) == 0
    assert capsys.readouterr().err == ""
    native_text = native.read_text(encoding="utf-8")
    assert "s3_main:" in native_text
    assert "tryte result" not in native_text
