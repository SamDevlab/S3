"""Focused contracts for V2 mechanism activation and fail-closed search."""

from __future__ import annotations

from bootstrap.s3.assembly import parse_assembly
from bootstrap.s3.backends.x86_64 import X8664Backend
from bootstrap.s3.backends.x86_64.allocation import analyze_allocation
from bootstrap.s3.backends.x86_64.policy import policy_with
from tools.native_policy_search_v2 import _canonical_id, _evaluate_candidate, _candidate


def _memory_program():
    return parse_assembly(
        """
.function main -> tryte
    .register r0, tryte
    .register r1, tryte
    .register r2, tryte
    .memory m0, tryte, 1, mutable
.label entry
    TCONST r0, 0
    TCONST r1, 7
    TSTORE m0, r0, r1
    TLOAD r2, m0, r0
    TRET r2
.end
"""
    )


def test_scalar_promotion_removes_only_the_proven_adjacent_pair() -> None:
    program = _memory_program()
    policy = policy_with(name="test_scalar", scalar_promotion="conservative_mem2reg")
    assembly = X8664Backend(native_policy=policy).generate(program)
    assert "mov word ptr [rbp + rdi*2" not in assembly
    assert "cmp byte ptr [rbp + r10 -" in assembly


def test_loop_split_plan_is_deterministic_and_region_aware_spill_has_costs() -> None:
    program = parse_assembly(
        """
.function main -> tryte
    .register r0, trit
    .register r1, tryte
.label entry
    TCONST r0, 0
    TCONST r1, 1
    TJMP loop
.label loop
    TBR3 r0, body, exit, exit
.label body
    TCONST r0, 1
    TJMP loop
.label exit
    TRET r1
.end
"""
    )
    policy = policy_with(
        name="test_region_loop",
        spill_policy="region_aware",
        live_range_split="loop_boundary",
    )
    first = analyze_allocation(program.functions[0], policy)
    second = analyze_allocation(program.functions[0], policy)
    assert first.spill_costs == second.spill_costs
    assert first.split_points == second.split_points


def test_unsupported_v2_candidate_is_not_evaluated() -> None:
    candidate = _candidate(
        "future",
        "A",
        "LIVE_RANGE",
        None,
        supported=False,
        unsupported_reason="future",
    )
    record = _evaluate_candidate(candidate, ())
    assert record["correctness"] == "NOT_EVALUATED"
    assert record["status"] == "UNSUPPORTED_FAIL_CLOSED"
    assert record["performance_evaluation"] == "PROHIBITED"
    assert _canonical_id(None, "future") == candidate.policy_id
