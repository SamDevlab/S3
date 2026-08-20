from __future__ import annotations

import pytest

from bootstrap.s3.aarch64_toolchain import LinuxAArch64NativeAssemblyBackend
from bootstrap.s3.assembly import (
    AssemblyBlock,
    AssemblyFunction,
    AssemblyInstruction,
    AssemblyOpcode,
    AssemblyParameter,
    AssemblyProgram,
    AssemblyType,
    parse_assembly,
)
from bootstrap.s3.assembly_verifier import AssemblyVerifierError
from bootstrap.s3.backends.x86_64.emitter import X8664Emitter
from bootstrap.s3.backends.x86_64.register_init_safety import (
    proven_initialized_register_reads,
)
from bootstrap.s3.codegen_optimization import analyze_redundant_noop_moves
from bootstrap.s3.emulator import Emulator


def _native(program: AssemblyProgram) -> str:
    return X8664Emitter(
        program,
        max_frames=64,
        max_instructions=100_000,
        register_allocation=False,
    ).emit()


def _main_block(native: str) -> str:
    return native.split(".L_s3_f4_main_b5_entry:", 1)[1].split(
        ".size s3_main", 1
    )[0]


def _run(program: AssemblyProgram, *, max_instructions: int = 100_000):
    return Emulator(max_instructions=max_instructions).execute(program, entry="main")


def _initialized_self_move() -> AssemblyProgram:
    return parse_assembly(
        ".function main -> i64\n"
        "    .register r0, i64\n"
        ".label entry\n"
        "    TCONST r0, 7\n"
        "    TMOV r0, r0\n"
        "    TRET r0\n"
        ".end\n"
    )


def _uninitialized_self_move() -> AssemblyProgram:
    return parse_assembly(
        ".function main -> i64\n"
        "    .register r0, i64\n"
        ".label entry\n"
        "    TMOV r0, r0\n"
        "    TCONST r0, 7\n"
        "    TRET r0\n"
        ".end\n"
    )


def test_initialized_self_move_preserves_assembly_and_result() -> None:
    program = _initialized_self_move()
    candidate, report = analyze_redundant_noop_moves(program)

    assert candidate is program
    assert report.input_instruction_count == 3
    assert report.output_instruction_count == 3
    assert report.candidate_noop_moves == 1
    assert _run(program) == _run(candidate) == 7


def test_uninitialized_self_move_preserves_failure() -> None:
    program = _uninitialized_self_move()
    candidate, report = analyze_redundant_noop_moves(program)

    with pytest.raises(AssemblyVerifierError, match="uninitialized register r0"):
        _run(program)
    with pytest.raises(AssemblyVerifierError, match="uninitialized register r0"):
        _run(candidate)
    assert report.candidate_noop_moves == 1

    native = _native(program)
    body = _main_block(native)
    assert "cmp byte ptr" in body
    assert "uninitialized register" in native
    assert body.count("inc qword ptr [rip + __s3_instruction_count]") == 3


def test_instruction_limit_counts_logical_self_move() -> None:
    program = parse_assembly(
        ".function main -> i64\n"
        "    .register r0, i64\n"
        ".label entry\n"
        "    TCONST r0, 7\n"
        "    TMOV r0, r0\n"
        "    TRET r0\n"
        ".end\n"
    )
    candidate, report = analyze_redundant_noop_moves(program)

    with pytest.raises(AssemblyVerifierError, match="instruction limit 2 exceeded"):
        _run(program, max_instructions=2)
    with pytest.raises(AssemblyVerifierError, match="instruction limit 2 exceeded"):
        _run(candidate, max_instructions=2)
    assert report.input_instruction_count == report.output_instruction_count == 3


def test_candidate_analysis_and_native_text_are_deterministic() -> None:
    program = _initialized_self_move()
    first = analyze_redundant_noop_moves(program)
    second = analyze_redundant_noop_moves(program)

    assert first == second
    assert _native(program) == _native(first[0])


def test_non_self_tmov_is_not_analyzed_as_a_noop_candidate() -> None:
    program = parse_assembly(
        ".function main -> i64\n"
        "    .register r0, i64\n"
        "    .register r1, i64\n"
        ".label entry\n"
        "    TCONST r0, 7\n"
        "    TMOV r1, r0\n"
        "    TRET r1\n"
        ".end\n"
    )
    candidate, report = analyze_redundant_noop_moves(program)

    assert candidate is program
    assert report.candidate_noop_moves == 0
    assert candidate.render() == program.render()


def test_f64_self_move_keeps_logical_instruction_and_native_safety() -> None:
    program = parse_assembly(
        ".function main -> f64\n"
        "    .register r0, f64\n"
        ".label entry\n"
        "    TCONST r0, 1.5\n"
        "    TMOV r0, r0\n"
        "    TRET r0\n"
        ".end\n"
    )
    candidate, report = analyze_redundant_noop_moves(program)
    native = _native(program)

    assert candidate is program
    assert report.candidate_noop_moves == 1
    assert _run(program) == _run(candidate) == pytest.approx(1.5)
    assert _main_block(native).count("inc qword ptr [rip + __s3_instruction_count]") == 3


def _address_taken_program() -> AssemblyProgram:
    function = AssemblyFunction(
        "main",
        AssemblyType.TRYTE,
        (),
        ((0, AssemblyType.TRYTE), (1, AssemblyType.REFERENCE)),
        (
            AssemblyBlock(
                "entry",
                (
                    AssemblyInstruction(AssemblyOpcode.TCONST, (0,), immediate=7),
                    AssemblyInstruction(
                        AssemblyOpcode.TADDR,
                        (1, 0),
                        reference_target=AssemblyType.TRYTE,
                    ),
                    AssemblyInstruction(AssemblyOpcode.TMOV, (0, 0)),
                    AssemblyInstruction(AssemblyOpcode.TRET, (0,)),
                ),
            ),
        ),
        reference_targets=((1, AssemblyType.TRYTE, True),),
    )
    return AssemblyProgram((function,))


def test_address_taken_register_fails_closed_for_self_move_elision() -> None:
    program = _address_taken_program()
    function = program.functions[0]
    candidate, report = analyze_redundant_noop_moves(program)
    native = _native(program)

    assert candidate is program
    assert report.candidate_noop_moves == 1
    assert not proven_initialized_register_reads(function)
    assert "uninitialized register" in native


def _branch_program(*, initialize_all_paths: bool) -> AssemblyProgram:
    def block(label: str, value: int | None) -> AssemblyBlock:
        instructions = () if value is None else (
            AssemblyInstruction(AssemblyOpcode.TCONST, (0,), immediate=value),
        )
        return AssemblyBlock(
            label,
            instructions + (AssemblyInstruction(AssemblyOpcode.TJMP, labels=("join",)),),
        )

    function = AssemblyFunction(
        "main",
        AssemblyType.I64,
        (),
        ((0, AssemblyType.I64), (1, AssemblyType.TRIT)),
        (
            AssemblyBlock(
                "entry",
                (
                    AssemblyInstruction(AssemblyOpcode.TCONST, (1,), immediate=0),
                    AssemblyInstruction(
                        AssemblyOpcode.TBR3,
                        (1,),
                        labels=("left", "right", "third"),
                    ),
                ),
            ),
            block("left", 1),
            block("right", 2),
            block("third", 3 if initialize_all_paths else None),
            AssemblyBlock(
                "join",
                (
                    AssemblyInstruction(AssemblyOpcode.TMOV, (0, 0)),
                    AssemblyInstruction(AssemblyOpcode.TRET, (0,)),
                ),
            ),
        ),
    )
    return AssemblyProgram((function,))


def test_branch_join_requires_definite_initialization_on_every_path() -> None:
    complete = _branch_program(initialize_all_paths=True).functions[0]
    partial = _branch_program(initialize_all_paths=False).functions[0]

    complete_sites = proven_initialized_register_reads(complete)
    partial_sites = proven_initialized_register_reads(partial)
    assert ("join", 0, 0) in complete_sites
    assert ("join", 0, 0) not in partial_sites
    assert "cmp byte ptr" not in _main_block(_native(AssemblyProgram((complete,))))
    assert "cmp byte ptr" in _main_block(_native(AssemblyProgram((partial,))))


def _call_program() -> AssemblyProgram:
    helper = AssemblyFunction(
        "helper",
        AssemblyType.I64,
        (AssemblyParameter(0, AssemblyType.I64),),
        ((0, AssemblyType.I64),),
        (AssemblyBlock("entry", (AssemblyInstruction(AssemblyOpcode.TRET, (0,)),)),),
    )
    main = AssemblyFunction(
        "main",
        AssemblyType.I64,
        (),
        ((0, AssemblyType.I64), (1, AssemblyType.I64)),
        (
            AssemblyBlock(
                "entry",
                (
                    AssemblyInstruction(AssemblyOpcode.TCONST, (0,), immediate=7),
                    AssemblyInstruction(
                        AssemblyOpcode.TCALL,
                        (1, 0),
                        callee="helper",
                        result_width=1,
                    ),
                    AssemblyInstruction(AssemblyOpcode.TMOV, (1, 1)),
                    AssemblyInstruction(AssemblyOpcode.TRET, (1,)),
                ),
            ),
        ),
    )
    return AssemblyProgram((helper, main))


def test_calls_keep_initialization_proof_conservative() -> None:
    program = _call_program()
    main = program.functions[1]

    assert not proven_initialized_register_reads(main)
    assert "uninitialized register" in _native(program)


def test_aarch64_keeps_self_move_in_assembly_lowering() -> None:
    program = _initialized_self_move()
    candidate, report = analyze_redundant_noop_moves(program)
    text = LinuxAArch64NativeAssemblyBackend().generate(program)

    assert candidate is program
    assert report.candidate_noop_moves == 1
    assert text.count("ldr x9") >= 1
    assert text.count("str x9") >= 1
