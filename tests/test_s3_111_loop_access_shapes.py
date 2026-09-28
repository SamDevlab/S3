from __future__ import annotations

from tools.s3_111_loop_access_shapes import analyze_workloads


def test_real_world_loop_access_shapes_preserve_unknown_legality() -> None:
    report = analyze_workloads()
    loops = report["loops"]

    assert report["summary"] == {
        "loops": 5,
        "loops_with_slice_accesses": 5,
        "access_bounds_proven": 0,
        "dependence_proofs": 0,
        "vectorization_authorized": False,
    }
    assert all(loop["all_bounds_unknown"] for loop in loops)
    assert all(loop["all_dependence_unknown"] for loop in loops)
    assert all(
        access["direction"] == "READ"
        for loop in loops
        for access in loop["slice_accesses"]
    )

    point_outer = loops[1]
    assert point_outer["slice_access_counts"] == {"slice_load:READ": 3}
    assert [
        access["affine_shape_ignoring_conversion_barriers"]
        for access in point_outer["slice_accesses"]
    ] == [
        {"coefficient": 3, "offset": 0},
        {"coefficient": 3, "offset": 1},
        {"coefficient": 3, "offset": 2},
    ]
    assert all(
        access["conversion_barriers"] == ["tryte"]
        for access in point_outer["slice_accesses"]
    )
