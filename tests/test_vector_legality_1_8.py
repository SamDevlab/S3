from __future__ import annotations

from pathlib import Path

from bootstrap.s3.optimizer import OptimizationLevel
from bootstrap.s3.pipeline import compile_source
from bootstrap.s3.vector_legality import analyze_vector_legality


ROOT = Path(__file__).resolve().parents[1]
WORKLOADS = (
    "point_cloud_summary.s3",
    "raster_window_statistics.s3",
    "energy_series_aggregation.s3",
)


def test_real_world_loop_vector_legality_fails_closed_without_proofs() -> None:
    reports = []
    for name in WORKLOADS:
        source = (ROOT / "benchmarks/workloads/real_world" / name).read_text(encoding="utf-8")
        ir, _assembly = compile_source(source, OptimizationLevel.O1).require_ordinary_artifacts()
        reports.extend(analyze_vector_legality(function) for function in ir.functions)

    loops = [loop for report in reports for loop in report["loops"]]
    assert len(loops) == 5
    assert all(loop["status"] == "UNKNOWN" for loop in loops)
    assert all(loop["dependence"] == "UNKNOWN" for loop in loops)
    assert all(loop["memory_pattern"] == "UNKNOWN" for loop in loops)
    assert sum(report["summary"]["vector_bounds_proofs"] for report in reports) == 0
    assert sum(report["summary"]["vectorizable_loops"] for report in reports) == 0
    assert sum(report["summary"]["unknown_loops"] for report in reports) == 5
