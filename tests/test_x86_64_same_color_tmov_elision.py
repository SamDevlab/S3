from __future__ import annotations

import re

import pytest

from bootstrap.s3.assembly import parse_assembly
from bootstrap.s3.backends.x86_64 import X8664Backend, generate_native_assembly
from bootstrap.s3.backends.x86_64.allocation import analyze_allocation
from bootstrap.s3.backends.x86_64.emitter import X8664Emitter
from bootstrap.s3.backends.x86_64.instruction_budget import InstructionBudgetMode


MAX_INSTRUCTIONS = 1_000_000_000


def _emit(source: str, mode: InstructionBudgetMode = InstructionBudgetMode.PER_INSTRUCTION):
    program = parse_assembly(source)
    emitter = X8664Emitter(
        program,
        max_frames=1024,
        max_instructions=MAX_INSTRUCTIONS,
        register_allocation=True,
        instruction_budget_mode=mode,
    )
    text, origins = emitter.emit_with_origins()
    return program, emitter, text, origins


def _tmov_lines(text: str, origins: tuple[dict[str, object], ...]) -> list[str]:
    row = next(
        item
        for item in origins
        if item.get("function") == "main"
        and "TMOV" in item.get("assembly_opcodes", [])
    )
    line_range = row["native_assembly_line_range"]
    if line_range is None:
        return []
    start, end = line_range
    return text.splitlines()[start - 1 : end]


def _register_moves(lines: list[str]) -> list[str]:
    return [
        line.strip()
        for line in lines
        if re.fullmatch(r"mov\s+[a-z0-9]+,\s*[a-z0-9]+", line.strip())
    ]


SAME_COLOR = """
.function main -> tryte
    .register r0, tryte
    .register r1, tryte
.label entry
    TCONST r0, 1
    TMOV r1, r0
    TRET r1
.end
"""


@pytest.mark.parametrize("mode", list(InstructionBudgetMode))
def test_same_color_tmov_elides_data_move_through_backend(mode: InstructionBudgetMode) -> None:
    program, _emitter, text, origins = _emit(SAME_COLOR, mode)
    plan = analyze_allocation(
        program.functions[0],
        reserved_registers=(
            frozenset({"r15"}) if mode is InstructionBudgetMode.PER_INSTRUCTION else frozenset()
        ),
    )
    assert plan.physical_register(0) is not None
    assert plan.physical_register(0) == plan.physical_register(1)
    assert _register_moves(_tmov_lines(text, origins)) == []

    backend_text = X8664Backend(
        max_frames=1024,
        max_instructions=MAX_INSTRUCTIONS,
        instruction_budget_mode=mode,
    ).generate(program)
    assert backend_text == text
    if mode is InstructionBudgetMode.PER_INSTRUCTION:
        assert sum(line.strip() == "dec r15" for line in _tmov_lines(text, origins)) == 1
        assert generate_native_assembly(
            program, max_frames=1024, max_instructions=MAX_INSTRUCTIONS
        ) == text


def test_different_color_tmov_still_emits_a_data_move() -> None:
    source = """
    .function main -> tryte
        .register r0, tryte
        .register r1, tryte
        .register r2, tryte
    .label entry
        TCONST r0, 3
        TMOV r1, r0
        TADD r2, r0, r1
        TRET r2
    .end
    """
    program, _emitter, text, origins = _emit(source)
    plan = analyze_allocation(program.functions[0], reserved_registers=frozenset({"r15"}))

    assert plan.physical_register(0) != plan.physical_register(1)
    assert len(_register_moves(_tmov_lines(text, origins))) == 2


def test_same_color_tmov_after_call_uses_call_aware_allocation_plan() -> None:
    source = """
        .function helper -> tryte
            .param r0, tryte
        .label entry
            TRET r0
        .end
        .function main -> tryte
            .register r0, tryte
            .register r1, tryte
            .register r2, tryte
        .label entry
            TCONST r0, 7
            TCALL r2, helper, r0
            TMOV r1, r2
            TRET r1
        .end
        """
    program = parse_assembly(source)
    function = program.functions[1]
    plan = analyze_allocation(function, reserved_registers=frozenset({"r15"}))
    _program, _emitter, text, origins = _emit(source)

    assert plan.physical_register(1) == plan.physical_register(2)
    assert "call s3_helper" in text
    assert _register_moves(_tmov_lines(text, origins)) == []


@pytest.mark.parametrize(
    ("address_taken", "expected_stack_register"),
    [(0, 0), (1, 1)],
    ids=["stack-source", "stack-destination"],
)
def test_stack_endpoint_tmov_is_not_elided(address_taken: int, expected_stack_register: int) -> None:
    source = f"""
    .function main -> tryte
        .register r0, tryte
        .register r1, tryte
        .register r2, reference
    .label entry
        TADDR r2, r{address_taken}
        TCONST r0, 1
        TMOV r1, r0
        TRET r1
    .end
    """
    program, _emitter, text, origins = _emit(source)
    plan = analyze_allocation(program.functions[0], reserved_registers=frozenset({"r15"}))
    move_lines = _tmov_lines(text, origins)

    assert plan.physical_register(expected_stack_register) is None
    assert any("ptr" in line for line in move_lines)


def test_same_color_elision_keeps_uninitialized_source_failure_check() -> None:
    source = """
    .function main -> tryte
        .register r0, tryte
        .register r1, tryte
    .label entry
        TMOV r1, r0
        TRET r1
    .end
    """
    program, emitter, text, origins = _emit(source)
    plan = analyze_allocation(program.functions[0], reserved_registers=frozenset({"r15"}))
    move_lines = _tmov_lines(text, origins)

    assert plan.physical_register(0) == plan.physical_register(1)
    assert any("cmp byte ptr" in line for line in move_lines)
    assert any("uninitialized register" in site.prefix for site in emitter.failure_sites)


def test_same_color_elision_keeps_tracked_destination_initialization_write() -> None:
    source = """
    .function main -> tryte
        .register r0, tryte
        .register r1, tryte
        .register r2, tryte
    .label entry
        TADD r2, r1, r1
        TCONST r0, 1
        TMOV r1, r0
        TRET r1
    .end
    """
    program, _emitter, text, origins = _emit(source)
    plan = analyze_allocation(program.functions[0], reserved_registers=frozenset({"r15"}))
    move_lines = _tmov_lines(text, origins)

    assert plan.physical_register(0) == plan.physical_register(1)
    assert any(
        "mov byte ptr" in line and line.rstrip().endswith(", 1")
        for line in move_lines
    )
