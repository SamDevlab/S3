"""Focused contracts for conservative cross-block scalar residence."""

from __future__ import annotations

from bootstrap.s3.assembly import parse_assembly
from bootstrap.s3.backends.x86_64.residence import analyze_cross_block_residence
from bootstrap.s3.backends.x86_64 import generate_native_assembly


def _function(source: str):
    return parse_assembly(source).functions[0]


def test_single_edge_scalar_uses_existing_safe_physical_color() -> None:
    function = _function(
        """
        .function main -> tryte
            .register r0, tryte
            .register r1, tryte
            .register r2, trit
        .label entry
            TCONST r0, 10
            TCONST r1, 1
            TCONST r2, 1
            TBR3 r2, next, alt, exit
        .label next
            TADD r1, r0, r1
            TRET r1
        .label alt
            TRET r0
        .label exit
            TRET r0
        .end
        """
    )
    plan = analyze_cross_block_residence(function)
    assert plan.physical_register(0) is not None


def test_conflicting_join_value_is_not_made_resident_from_last_predecessor() -> None:
    function = _function(
        """
        .function main -> tryte
            .register r0, tryte
            .register r1, tryte
        .label entry
            TCONST r0, 0
            TBR3 r0, left, right, left
        .label left
            TCONST r1, 10
            TJMP join
        .label right
            TCONST r1, 20
            TJMP join
        .label join
            TRET r1
        .end
        """
    )
    plan = analyze_cross_block_residence(function)
    assert plan.physical_register(1) is None


def test_address_taken_referent_remains_canonical() -> None:
    function = _function(
        """
        .function main -> tryte
            .register r0, tryte
            .register r1, reference
        .label entry
            TCONST r0, 10
            TADDR r1, r0
            TJMP next
        .label next
            TRET r0
        .end
        """
    )
    plan = analyze_cross_block_residence(function)
    assert plan.physical_register(0) is None


def test_default_backend_emits_cross_block_residence_without_ra_redesign() -> None:
    program = parse_assembly(
        """
        .function main -> tryte
            .register r0, tryte
            .register r1, tryte
            .register r2, trit
        .label entry
            TCONST r0, 10
            TCONST r1, 1
            TCONST r2, 1
            TBR3 r2, next, alt, exit
        .label next
            TADD r1, r0, r1
            TRET r1
        .label alt
            TRET r0
        .label exit
            TRET r0
        .end
        """
    )
    native = generate_native_assembly(program)
    assert "Generated deterministically" in native
    assert "jmp .L_s3_f4_main_b5_entry" in native


def test_call_barrier_tracks_cross_block_resident_survivor() -> None:
    program = parse_assembly(
        """
        .function main -> tryte
            .register r0, tryte
            .register r1, tryte
            .register r2, trit
        .label entry
            TCONST r0, 10
            TCONST r2, 1
            TBR3 r2, call_block, alt, exit
        .label call_block
            TCALL r1, helper, r0
            TADD r1, r0, r1
            TRET r1
        .label alt
            TRET r0
        .label exit
            TRET r0
        .end
        .function helper -> tryte
            .param r0, tryte
        .label entry
            TRET r0
        .end
        """
    )
    function = program.functions[0]
    plan = analyze_cross_block_residence(function)
    assert plan.physical_register(0) is not None
    assert plan.call_survivors
    native = generate_native_assembly(program)
    assert "caller_saved_spill" not in native
