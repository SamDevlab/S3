from __future__ import annotations

from pathlib import Path

import tools.s3_111_guarded_slice_bounds as guarded_slice_bounds
from bootstrap.s3 import ast
from tools.s3_111_guarded_slice_bounds import (
    Affine,
    Interval,
    State,
    _bounds_binary,
    _case_is_unreachable,
    _refine,
    _analyze_function,
    _length_relation,
    analyze_workloads,
)
from tools.s3_111_loop_predicate_diagnostics import WORKLOADS


def test_guarded_workload_slice_bounds_are_proven_fail_closed() -> None:
    report = analyze_workloads()

    assert report["experiment_control_sha"] == "832b1cc04fe1f6174e482eb3a245e08af3d53211"
    assert report["experiment_control_tree"] == "dc1138890655169088f9371ce32a9050cfc3af8d"
    assert report["summary"] == {
        "dependence_proofs": 0,
        "functions": 2,
        "slice_bounds_proven": 11,
        "slice_bounds_unknown": 0,
        "slice_reads": 11,
        "vectorization_authorized": False,
    }

    energy, point = report["functions"]
    assert energy["source_sha256"] == "a146f2ec7bd7f9bf72ea35c04026174874012acdb31541d805bf5f0a4a613c84"
    assert point["source_sha256"] == "59e752e91159ece4e3a813bc8586f338544ddac52e4b5e755a219d85779238e9"
    assert energy["loops"][0]["bound_interval"] == [1, 364]
    assert [item["index_interval"] for item in energy["slice_reads"]] == [[0, 363], [0, 363]]
    assert all(item["proof_kind"] == "COUNTED_LOOP_SAME_LENGTH" for item in energy["slice_reads"])

    assert [row["bound_interval"] for row in point["loops"]] == [[1, 121], [1, 121]]
    assert [item["index_interval"] for item in point["slice_reads"]] == [
        [0, 0], [1, 1], [2, 2],
        [0, 360], [1, 361], [2, 362],
        [0, 360], [1, 361], [2, 362],
    ]
    assert all(item["bounds_status"] == "PROVEN" for item in point["slice_reads"])
    assert all(loop["ir_recurrence"]["status"] == "PASS" for loop in point["loops"])


def test_synthetic_pr_checkout_does_not_replace_experiment_control(monkeypatch) -> None:
    checkout_sha = "88ab58f807cdb5c23b99f32d8b6569295c9ef60e"
    checkout_tree = "a" * 40
    monkeypatch.setattr(
        guarded_slice_bounds,
        "_checkout_identity",
        lambda: (checkout_sha, checkout_tree),
    )

    report = analyze_workloads()

    assert report["experiment_control_sha"] == "832b1cc04fe1f6174e482eb3a245e08af3d53211"
    assert report["experiment_control_tree"] == "dc1138890655169088f9371ce32a9050cfc3af8d"
    assert report["checkout_sha"] == checkout_sha
    assert report["checkout_tree"] == checkout_tree
    assert report["checkout_sha"] != report["experiment_control_sha"]
    assert report["summary"]["slice_bounds_proven"] == 11
    assert report["summary"]["slice_bounds_unknown"] == 0
    assert report["summary"]["vectorization_authorized"] is False


def test_grouped_slice_bound_requires_the_length_equality_guard() -> None:
    state = State(
        affines={
            "coordinate_count": Affine.variable("coordinate_count"),
            "point_count": Affine.variable("point_count"),
        }
    )
    index = Affine(2, (("point", 3),))
    assert _length_relation(
        state,
        "coordinate_count",
        Affine.variable("point_count"),
        index,
        "point",
    ) is None

    state.equalities.add((
        Affine.variable("coordinate_count"),
        Affine(0, (("point_count", 3),)),
    ))
    assert _length_relation(
        state,
        "coordinate_count",
        Affine.variable("point_count"),
        index,
        "point",
    ) == (3, 2)


def test_checked_interval_math_and_relational_case_contract() -> None:
    from tools.s3_111_guarded_slice_bounds import _I64_MAX

    assert _bounds_binary("+", Interval(_I64_MAX, _I64_MAX), Interval(1, 1)) is None
    expression = ast.BinaryExpression(
        ast.BinaryOperator.EQUAL,
        ast.Identifier("left", None),
        ast.Identifier("right", None),
        None,
    )
    assert _case_is_unreachable(expression, 1)
    assert not _case_is_unreachable(expression, 0)


def test_unmodeled_product_equality_keeps_path_as_symbolic_fact_only() -> None:
    state = State(
        intervals={
            "cell_count": Interval(1, 364),
            "width": Interval(1, 364),
            "height": Interval(1, 364),
        },
        affines={
            "cell_count": Affine.variable("cell_count"),
            "width": Affine.variable("width"),
            "height": Affine.variable("height"),
        },
    )
    product = ast.BinaryExpression(
        ast.BinaryOperator.MULTIPLY,
        ast.Identifier("width", None),
        ast.Identifier("height", None),
        None,
    )
    equality = ast.BinaryExpression(
        ast.BinaryOperator.EQUAL,
        ast.Identifier("cell_count", None),
        product,
        None,
    )

    refined = _refine(state, equality, True)

    assert refined is not None
    assert refined.equalities == set()
    assert refined.product_equalities == {("cell_count", "height", "width")}
    assert refined.intervals["cell_count"] == Interval(1, 364)


def test_bounds_revert_to_unknown_when_energy_guard_exceeds_tryte_domain() -> None:
    workload, source_path, function_name = next(item for item in WORKLOADS if item[0] == "energy")
    source = (Path(__file__).resolve().parents[1] / source_path).read_text(encoding="utf-8")
    changed = source.replace("period_count > 364", "period_count > 10000", 1)
    assert changed != source

    result = _analyze_function(workload, source_path, function_name, changed.encode("utf-8"))
    assert result["loops"][0]["bound_interval"] == [1, 10000]
    assert all(item["bounds_status"] == "UNKNOWN" for item in result["slice_reads"])


def test_bounds_revert_to_unknown_without_point_length_equality_guard() -> None:
    workload, source_path, function_name = next(item for item in WORKLOADS if item[0] == "point-cloud")
    source = (Path(__file__).resolve().parents[1] / source_path).read_text(encoding="utf-8")
    changed = source.replace(
        "coordinate_count == bounded_point_count * 3",
        "coordinate_count != bounded_point_count * 3",
        1,
    )
    assert changed != source

    result = _analyze_function(workload, source_path, function_name, changed.encode("utf-8"))
    assert result["loops"]
    assert all(item["bounds_status"] == "UNKNOWN" for item in result["slice_reads"])


def test_raster_proves_base_and_guarded_neighbor_reads() -> None:
    workload, source_path, function_name = next(item for item in WORKLOADS if item[0] == "raster")
    source = (Path(__file__).resolve().parents[1] / source_path).read_bytes()

    result = _analyze_function(workload, source_path, function_name, source)

    assert [row.get("induction") for row in result["loops"]] == ["row", "column"]
    assert all(row["ir_recurrence"]["status"] == "PASS" for row in result["loops"])
    assert len(result["slice_reads"]) == 4
    assert all(item["bounds_status"] == "PROVEN" for item in result["slice_reads"])
    assert [item["proof_kind"] for item in result["slice_reads"]] == [
        "GUARDED_RECTANGULAR_ROW_MAJOR_INDEX",
        "GUARDED_RECTANGULAR_ROW_MAJOR_INDEX",
        "GUARDED_RECTANGULAR_ROW_MAJOR_NEIGHBOR",
        "GUARDED_RECTANGULAR_ROW_MAJOR_NEIGHBOR",
    ]


def test_raster_row_major_proof_requires_the_product_equality_guard() -> None:
    workload, source_path, function_name = next(item for item in WORKLOADS if item[0] == "raster")
    source = (Path(__file__).resolve().parents[1] / source_path).read_text(encoding="utf-8")
    changed = source.replace(
        "cell_count == bounded_width * bounded_height",
        "cell_count != bounded_width * bounded_height",
        1,
    )
    assert changed != source

    result = _analyze_function(workload, source_path, function_name, changed.encode("utf-8"))

    assert [row.get("induction") for row in result["loops"]] == ["row", "column"]
    assert all(item["bounds_status"] == "UNKNOWN" for item in result["slice_reads"])


def test_raster_neighbor_proof_requires_strict_column_guard() -> None:
    workload, source_path, function_name = next(item for item in WORKLOADS if item[0] == "raster")
    source = (Path(__file__).resolve().parents[1] / source_path).read_text(encoding="utf-8")
    changed = source.replace(
        "to_tryte(column + 1) < to_tryte(bounded_width)",
        "to_tryte(column + 1) <= to_tryte(bounded_width)",
        1,
    )
    assert changed != source

    result = _analyze_function(workload, source_path, function_name, changed.encode("utf-8"))

    assert [item["bounds_status"] for item in result["slice_reads"]] == [
        "PROVEN", "PROVEN", "UNKNOWN", "UNKNOWN"
    ]


def test_raster_product_fact_is_invalidated_by_dimension_assignment() -> None:
    workload, source_path, function_name = next(item for item in WORKLOADS if item[0] == "raster")
    source = (Path(__file__).resolve().parents[1] / source_path).read_text(encoding="utf-8")
    needle = "match mask_count == cell_count:"
    offset = source.index(needle)
    line_start = source.rfind("\n", 0, offset) + 1
    indentation = source[line_start:offset]
    changed = source[:line_start] + indentation + "bounded_width = bounded_width\n" + source[line_start:]

    result = _analyze_function(workload, source_path, function_name, changed.encode("utf-8"))

    assert [item["bounds_status"] for item in result["slice_reads"]] == [
        "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"
    ]
