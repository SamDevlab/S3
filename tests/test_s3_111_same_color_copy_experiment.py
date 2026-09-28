"""Tests for the isolated same-color-copy emitter prototype."""

from bootstrap.s3.assembly import parse_assembly
from bootstrap.s3.backends.x86_64.emitter import X8664Emitter
from tools.s3_111_same_color_copy_experiment import emit_same_color_candidate


def _origin_lines(text: str, origins, opcode: str) -> list[str]:
    row = next(
        item
        for item in origins
        if item.get("function") == "main" and opcode in item.get("assembly_opcodes", [])
    )
    start, end = row["native_assembly_line_range"]
    return text.splitlines()[start - 1 : end]


def test_same_color_copy_omission_keeps_per_instruction_budget_tick() -> None:
    program = parse_assembly(
        """
        .function main -> tryte
            .register r0, tryte
            .register r1, tryte
        .label entry
            TCONST r0, 1
            TMOV r1, r0
            TRET r1
        .end
        """
    )
    ordinary = X8664Emitter(
        program,
        max_frames=1024,
        max_instructions=1_000_000_000,
        register_allocation=True,
        instruction_budget_mode="per-instruction",
    )
    baseline_text, baseline_origins = ordinary.emit_with_origins()
    candidate_text, candidate_origins = emit_same_color_candidate(
        program, max_instructions=1_000_000_000
    )

    baseline_copy = _origin_lines(baseline_text, baseline_origins, "TMOV")
    candidate_copy = _origin_lines(candidate_text, candidate_origins, "TMOV")
    assert baseline_copy == candidate_copy
    assert sum(
        line.strip().startswith("mov ") and "ptr" not in line
        for line in baseline_copy
    ) == 0
    assert sum(line.strip() == "dec r15" for line in baseline_copy) == 1
    assert sum(line.strip() == "dec r15" for line in candidate_copy) == 1
