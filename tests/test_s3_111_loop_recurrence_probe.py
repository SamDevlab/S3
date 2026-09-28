from __future__ import annotations

from tools.s3_111_loop_recurrence_probe import analyze_workloads


def test_continuation_cfg_probe_counts_updates_without_claiming_vector_legality() -> None:
    report = analyze_workloads()
    loops = report["loops"]

    assert report["summary"] == {
        "loops": 5,
        "loops_with_one_update_on_all_reachable_abstract_backedge_states": 5,
        "vectorization_authorized": False,
    }
    assert all(
        loop["all_reachable_abstract_backedge_states_one_update"]
        for loop in loops
    )
    assert all(
        loop["probe_status"] == "ONE_UPDATE_ON_ALL_REACHABLE_ABSTRACT_BACKEDGE_STATES"
        for loop in loops
    )
    assert all(loop["abstract_backedge_states"] for loop in loops)

    point_inner = loops[2]
    assert point_inner["function_wide_store_count"] == 4
    assert point_inner["in_loop_store_count"] == 1
    assert point_inner["preheader_store_count"] == 1

    raster_inner = loops[4]
    assert len(raster_inner["recurrence_store_sites_in_loop"]) == 1
    assert raster_inner["probe_status"] == "ONE_UPDATE_ON_ALL_REACHABLE_ABSTRACT_BACKEDGE_STATES"
