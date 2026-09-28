from __future__ import annotations

from tools.s3_111_loop_predicate_diagnostics import analyze_workloads


def test_real_world_loop_first_failed_induction_predicates_are_reported() -> None:
    report = analyze_workloads()
    loops = report["loops"]

    assert report["summary"] == {
        "loops": 5,
        "condition_recognized": 5,
        "induction_predicates_passed": 0,
        "unknown_vector_legality_retained": 5,
        "simd_authorized": False,
    }
    assert [loop["loop_header"] for loop in loops] == [
        "while_condition_32",
        "while_condition_29",
        "while_condition_62",
        "while_condition_59",
        "while_condition_68",
    ]
    assert [loop["first_induction_predicate_failure"] for loop in loops] == [
        "BACKEDGE_TAIL_DIFFERS_FROM_SELECTED_BODY",
        "BACKEDGE_TAIL_DIFFERS_FROM_SELECTED_BODY",
        "INDUCTION_STORE_COUNT_NOT_TWO",
        "BACKEDGE_TAIL_DIFFERS_FROM_SELECTED_BODY",
        "BACKEDGE_TAIL_DIFFERS_FROM_SELECTED_BODY",
    ]
    assert all(loop["condition_recognizer"] == "CONDITION_RECOGNIZED" for loop in loops)
    assert all(not loop["induction_recognized_by_analyzer"] for loop in loops)
    assert all(loop["vector_bounds_proofs_for_function"] == 0 for loop in loops)

    point_inner = loops[2]["induction_memory_census"]
    assert point_inner["store_count_function_wide"] == 4
    assert point_inner["store_count_in_loop"] == 1
    assert point_inner["store_count_in_preheader"] == 1
    assert point_inner["positive_constant_update_count_in_loop"] == 1

    raster_inner = loops[4]["induction_memory_census"]
    assert raster_inner["positive_constant_update_count_in_loop"] == 2
