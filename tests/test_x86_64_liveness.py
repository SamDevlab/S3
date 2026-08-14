"""Tests for CFG-aware register liveness analysis on S3 Assembly."""

from __future__ import annotations

import pytest

from bootstrap.s3.assembly import (
    AssemblyInstruction,
    AssemblyOpcode,
    AssemblyType,
    parse_assembly,
)
from bootstrap.s3.backends.x86_64.liveness import (
    InstructionSite,
    analyze_liveness,
    instruction_use_def,
)

pytestmark = [pytest.mark.s3_fast, pytest.mark.s3_contract]


def _get_first_func_liveness(source: str):
    program = parse_assembly(source)
    func = program.functions[0]
    return func, analyze_liveness(func)


def test_straight_line() -> None:
    # 1. straight-line: definição -> uso -> morte
    source = """
    .function main -> tryte
        .register r0, tryte
        .register r1, tryte
    .label entry
        TCONST r0, 42
        TMOV r1, r0
        TRET r1
    .end
    """
    _, liveness = _get_first_func_liveness(source)
    entry = liveness.blocks["entry"]

    # TCONST r0, 42
    assert entry.instructions[0].uses == frozenset()
    assert entry.instructions[0].defs == frozenset({0})
    assert entry.instructions[0].live_before == frozenset()
    assert entry.instructions[0].live_after == frozenset({0})

    # TMOV r1, r0
    assert entry.instructions[1].uses == frozenset({0})
    assert entry.instructions[1].defs == frozenset({1})
    assert entry.instructions[1].live_before == frozenset({0})
    assert entry.instructions[1].live_after == frozenset({1})

    # TRET r1
    assert entry.instructions[2].uses == frozenset({1})
    assert entry.instructions[2].defs == frozenset()
    assert entry.instructions[2].live_before == frozenset({1})
    assert entry.instructions[2].live_after == frozenset()


def test_overwrite() -> None:
    # 2. overwrite: definição posterior mata valor anterior
    source = """
    .function main -> tryte
        .register r0, tryte
    .label entry
        TCONST r0, 10
        TCONST r0, 20
        TRET r0
    .end
    """
    _, liveness = _get_first_func_liveness(source)
    entry = liveness.blocks["entry"]

    # First TCONST r0, 10 -> r0 is defined but immediately overwritten
    assert entry.instructions[0].live_before == frozenset()
    assert entry.instructions[0].live_after == frozenset()  # r0 is dead here because next instruction overwrites it

    # Second TCONST r0, 20 -> r0 defined and then returned
    assert entry.instructions[1].live_before == frozenset()
    assert entry.instructions[1].live_after == frozenset({0})


def test_parameter_live_in() -> None:
    # 3. parameter live-in
    source = """
    .function add_one -> tryte
        .param r0, tryte
        .register r1, tryte
    .label entry
        TCONST r1, 1
        TADD r0, r0, r1
        TRET r0
    .end
    """
    _, liveness = _get_first_func_liveness(source)
    entry = liveness.blocks["entry"]

    # Parameter r0 should be live-in of the entry block
    assert 0 in entry.live_in
    assert entry.instructions[0].live_before == frozenset({0})
    assert entry.instructions[0].live_after == frozenset({0, 1})

    # TADD r0, r0, r1
    assert entry.instructions[1].live_before == frozenset({0, 1})
    assert entry.instructions[1].live_after == frozenset({0})


def test_unary_op() -> None:
    # 4. unary op (TINV)
    source = """
    .function invert -> tryte
        .param r0, tryte
        .register r1, tryte
    .label entry
        TINV r1, r0
        TRET r1
    .end
    """
    _, liveness = _get_first_func_liveness(source)
    entry = liveness.blocks["entry"]

    assert entry.instructions[0].uses == frozenset({0})
    assert entry.instructions[0].defs == frozenset({1})


def test_binary_op() -> None:
    # 5. binary op (TMIN, TMAX, TCMP)
    source = """
    .function main -> tryte
        .register r0, tryte
        .register r1, tryte
        .register r2, tryte
    .label entry
        TCONST r0, 1
        TCONST r1, 2
        TMIN r2, r0, r1
        TMAX r2, r0, r1
        TCMP r2, r0, r1
        TRET r2
    .end
    """
    _, liveness = _get_first_func_liveness(source)
    entry = liveness.blocks["entry"]

    # TMIN r2, r0, r1
    assert entry.instructions[2].uses == frozenset({0, 1})
    assert entry.instructions[2].defs == frozenset({2})

    # TMAX r2, r0, r1
    assert entry.instructions[3].uses == frozenset({0, 1})
    assert entry.instructions[3].defs == frozenset({2})

    # TCMP r2, r0, r1
    assert entry.instructions[4].uses == frozenset({0, 1})
    assert entry.instructions[4].defs == frozenset({2})


def test_branch_diamond() -> None:
    # 6. branch diamond
    # 7. valor usado em ambos successors (r0)
    # 8. valor usado em apenas um successor (r1 / r2)
    # 9. join
    # 18. blocos na ordem original
    source = """
    .function main -> tryte
        .register r0, tryte
        .register r1, tryte
        .register r2, tryte
        .register r3, tryte
    .label entry
        TCONST r0, 0
        TCONST r1, 10
        TCONST r2, 20
        TBR3 r0, left, middle, right
    .label left
        TADD r3, r0, r1
        TJMP join
    .label middle
        TADD r3, r0, r2
        TJMP join
    .label right
        TMOV r3, r0
        TJMP join
    .label join
        TRET r3
    .end
    """
    func, liveness = _get_first_func_liveness(source)

    # Blocks should keep original order
    assert [b.label for b in func.blocks] == ["entry", "left", "middle", "right", "join"]
    assert list(liveness.blocks.keys()) == ["entry", "left", "middle", "right", "join"]

    # check block successors
    # TBR3 r0, left, middle, right
    entry_term = liveness.blocks["entry"].instructions[-1].instruction
    assert entry_term.opcode is AssemblyOpcode.TBR3

    # check liveness propagation
    # In join block: r3 is live-in
    assert liveness.blocks["join"].live_in == frozenset({3})

    # In left block: r3 is defined, r0 and r1 are used, and it jumps to join (where r3 is needed).
    # So live_in of left is {0, 1}
    assert liveness.blocks["left"].live_in == frozenset({0, 1})
    assert liveness.blocks["left"].live_out == frozenset({3})

    # In middle block: live_in is {0, 2}
    assert liveness.blocks["middle"].live_in == frozenset({0, 2})
    assert liveness.blocks["middle"].live_out == frozenset({3})

    # In right block: live_in is {0} (since r1 and r2 are not used there)
    assert liveness.blocks["right"].live_in == frozenset({0})
    assert liveness.blocks["right"].live_out == frozenset({3})

    # In entry block: live_out must be union of successors live_in:
    # live_out[entry] = live_in[left] | live_in[middle] | live_in[right]
    #                 = {0, 1} | {0, 2} | {0} = {0, 1, 2}
    assert liveness.blocks["entry"].live_out == frozenset({0, 1, 2})


def test_loop_backedge() -> None:
    # 10. loop/backedge exigindo mais de uma iteração de dataflow
    source = """
    .function loop_test -> tryte
        .register r0, tryte
        .register r1, tryte
    .label entry
        TCONST r0, 10
        TCONST r1, 0
        TJMP header
    .label header
        TBR3 r0, body, exit, exit
    .label body
        TCONST r1, 1
        TMIN r0, r0, r1
        TJMP header
    .label exit
        TRET r1
    .end
    """
    _, liveness = _get_first_func_liveness(source)

    # In exit block: r1 is live-in
    assert liveness.blocks["exit"].live_in == frozenset({1})

    # In body block: r0 and r1 must be live-in because it modifies them and branches back to header
    # Let's check header: live_in should contain {0, 1}
    assert liveness.blocks["header"].live_in == frozenset({0, 1})
    assert liveness.blocks["body"].live_in == frozenset({0})


def test_tcall_liveness() -> None:
    # 12. TCALL arguments são uses
    # 13. TCALL result registers são defs
    # 14. valor realmente live across call
    # 15. argumento que morre na call NÃO é live-across-call
    source = """
    .function main -> tryte
        .register r0, tryte
        .register r1, tryte
        .register r2, tryte
    .label entry
        TCONST r0, 5
        TCONST r1, 10
        TCALL r2, helper, r0
        TADD r2, r2, r1
        TRET r2
    .end
    """
    _, liveness = _get_first_func_liveness(source)
    entry = liveness.blocks["entry"]
    tcall_inst = entry.instructions[2].instruction

    # TCALL (r2), helper, r0
    assert entry.instructions[2].uses == frozenset({0})
    assert entry.instructions[2].defs == frozenset({2})

    # r1 is defined before the call and used after the call, so it survives the call (live across call)
    assert 1 in entry.instructions[2].live_before
    assert 1 in entry.instructions[2].live_after
    assert liveness.live_across_call(InstructionSite("entry", 2)) == frozenset({1})

    # r0 is used by the call but not live after the call, so it does not survive the call
    assert 0 not in entry.instructions[2].live_after
    assert 0 not in liveness.live_across_call(InstructionSite("entry", 2))

    # r2 is defined by the call, so it is in live_after but NOT in live_before of the call.
    # Therefore it is not live across call.
    assert 2 in entry.instructions[2].live_after
    assert 2 not in entry.instructions[2].live_before
    assert 2 not in liveness.live_across_call(InstructionSite("entry", 2))


def test_tload_tstore() -> None:
    # 17. TLOAD/TSTORE
    source = """
    .function memory_test -> tryte
        .memory m0, tryte, 5, mutable
        .register r0, tryte
        .register r1, tryte
        .register r2, tryte
    .label entry
        TCONST r0, 0
        TCONST r1, 15
        TSTORE m0, r0, r1
        TLOAD r2, m0, r0
        TRET r2
    .end
    """
    _, liveness = _get_first_func_liveness(source)
    entry = liveness.blocks["entry"]

    # TSTORE m0, r0, r1 -> uses r0, r1
    assert entry.instructions[2].uses == frozenset({0, 1})
    assert entry.instructions[2].defs == frozenset()

    # TLOAD r2, m0, r0 -> uses r0, defs r2
    assert entry.instructions[3].uses == frozenset({0})
    assert entry.instructions[3].defs == frozenset({2})


def test_deterministic_behavior() -> None:
    # 19. resultado determinístico
    source = """
    .function main -> tryte
        .register r0, tryte
        .register r1, tryte
    .label entry
        TCONST r0, 1
        TCONST r1, 2
        TRET r0
    .end
    """
    _, liveness1 = _get_first_func_liveness(source)
    _, liveness2 = _get_first_func_liveness(source)

    assert liveness1.blocks["entry"].live_in == liveness2.blocks["entry"].live_in
    assert liveness1.blocks["entry"].live_out == liveness2.blocks["entry"].live_out


def test_opcode_use_def_exhaustive() -> None:
    # 16. múltiplos resultados de call, se ISA atual suportar (TCALL result_width > 1)
    # 20. cobertura explícita de TODOS os AssemblyOpcode atuais
    # 21. Opcode use/def exhaustiveness check
    
    # We construct individual mock instructions for all opcodes to test use/def coverage
    for opcode in AssemblyOpcode:
        # Construct parameters for a valid mock instruction
        result_width = 1
        registers = (0, 1, 2)
        
        if opcode is AssemblyOpcode.TCALL:
            inst = AssemblyInstruction(
                opcode=opcode,
                registers=(0, 1, 2),
                callee="helper",
                result_width=2,  # test multiple result cells
            )
            uses, defs = instruction_use_def(inst)
            assert uses == frozenset({2})
            assert defs == frozenset({0, 1})
            continue

        inst = AssemblyInstruction(
            opcode=opcode,
            registers=registers,
            immediate=42,
            static_string="s0",
            labels=("left", "middle", "right"),
            memory=0,
        )

        uses, defs = instruction_use_def(inst)
        # Verify that it succeeded without raising any exception
        assert isinstance(uses, frozenset)
        assert isinstance(defs, frozenset)


def test_adversarial_diamond_and_loop() -> None:
    # 22. testes de CFG adversariais: diamond e loop
    diamond_source = """
    .function diamond_cfg -> tryte
        .param r0, tryte
        .register r1, tryte
        .register r2, tryte
        .register r3, tryte
    .label entry
        TBR3 r0, left, right, join
    .label left
        TCONST r1, 10
        TJMP join
    .label right
        TCONST r2, 20
        TJMP join
    .label join
        TADD r3, r1, r2
        TRET r3
    .end
    """
    _, liveness = _get_first_func_liveness(diamond_source)

    # Check join: r1, r2 are live-in
    assert liveness.blocks["join"].live_in == frozenset({1, 2})

    # Check left: r2 must be in live_in because left doesn't define it, but join needs it
    assert 2 in liveness.blocks["left"].live_in
    assert 1 not in liveness.blocks["left"].live_in  # left defines r1

    # Check right: r1 must be in live_in because right doesn't define it, but join needs it
    assert 1 in liveness.blocks["right"].live_in
    assert 2 not in liveness.blocks["right"].live_in  # right defines r2

    # Check entry: live_out must contain both r1 and r2 (from left and right live_ins)
    assert liveness.blocks["entry"].live_out == frozenset({1, 2})
    assert 0 in liveness.blocks["entry"].live_in

    # Loop CFG adversarial case
    loop_source = """
    .function loop_cfg -> tryte
        .param r0, tryte
        .register r1, tryte
    .label entry
        TMOV r1, r0
        TJMP header
    .label header
        TBR3 r1, body, exit, exit
    .label body
        TCONST r1, 5
        TJMP header
    .label exit
        TRET r1
    .end
    """
    _, loop_liveness = _get_first_func_liveness(loop_source)
    assert loop_liveness.blocks["header"].live_in == frozenset({1})
    assert loop_liveness.blocks["body"].live_in == frozenset()  # body overwrites r1
