"""Tests for research-only TMOV allocation-location classification."""

from bootstrap.s3.assembly import parse_assembly
from tools.s3_111_move_coalesce_scan import summarize_move_locations


def test_copy_to_dead_source_can_share_a_physical_register() -> None:
    function = parse_assembly(
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
    ).functions[0]

    result = summarize_move_locations(function)

    assert result["tmov_count"] == 1
    assert result["allocated_same_physical_count"] == 1
    assert result["candidate_sites"][0]["location_relation"] == "SAME_PHYSICAL_REGISTER"


def test_copy_is_not_coalescible_when_source_and_destination_are_both_live() -> None:
    function = parse_assembly(
        """
        .function main -> tryte
            .register r0, tryte
            .register r1, tryte
            .register r2, tryte
        .label entry
            TCONST r0, 1
            TMOV r1, r0
            TADD r2, r0, r1
            TRET r2
        .end
        """
    ).functions[0]

    result = summarize_move_locations(function)

    assert result["tmov_count"] == 1
    assert result["allocated_same_physical_count"] == 0
    assert result["candidate_sites"][0]["location_relation"] == "DISTINCT_PHYSICAL_REGISTERS"
