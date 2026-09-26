from __future__ import annotations

import ctypes
import hashlib
import json
import math
import platform
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
WORKLOADS = ROOT / "benchmarks" / "workloads" / "real_world"
FIXTURE_PATH = WORKLOADS / "public-fixtures-v1" / "s3-1.6-public-compute-samples-v1.json"
MANIFEST_PATH = WORKLOADS / "public-fixtures-v1" / "public-datasets-v1.json"
AGENT_KERNELS = WORKLOADS / "agent-kernels-v2-qualified"
AGENT_TASKS_PATH = WORKLOADS / "agent-kernel-tasks-v2.json"


def _documents() -> tuple[dict, dict]:
    fixture_bytes = FIXTURE_PATH.read_bytes()
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    fixture = json.loads(fixture_bytes)
    assert hashlib.sha256(fixture_bytes).hexdigest() == manifest["fixture_sha256"]
    return fixture, manifest


def test_public_dataset_fixture_is_hash_pinned_and_semantically_scoped() -> None:
    fixture, manifest = _documents()
    assert manifest["manifest_id"] == "s3-1.6-public-datasets-v1"
    assert {source["dataset_id"] for source in manifest["sources"]} == {
        "open3d-demo-icp-cloud-bin-0",
        "usgs-elliott-park-pa-7.5min-drg-o41078a5",
    }
    point_cloud = fixture["point_cloud"]
    assert point_cloud["sample_count"] == 121
    assert len(point_cloud["coordinates_xyz"]) == 363
    raster = fixture["raster"]
    assert raster["window"]["width"] * raster["window"]["height"] == 256
    assert len(raster["values"]) == len(raster["valid_mask"]) == 256
    assert set(raster["valid_mask"]) == {1}
    assert "not elevation" in raster["pixel_semantics"]
    assert fixture["reference"]["engine"] == "NumPy"


def test_agent_kernel_task_corpus_matches_qualified_sources() -> None:
    corpus = json.loads(AGENT_TASKS_PATH.read_text(encoding="utf-8"))
    assert corpus["corpus_id"] == "s3-1.6-agent-kernel-tasks-v2"
    assert len(corpus["tasks"]) == 5
    assert corpus["status_codes"] == {
        "success": 0,
        "invalid_input_or_shape": 1,
        "insufficient_output_capacity": 2,
    }
    assert all((WORKLOADS / task["source"]).is_file() for task in corpus["tasks"])


def _compile_kernel(tmp_path: Path, name: str) -> ctypes.CDLL:
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        pytest.skip("S3 1.6 agent kernel native gate requires Linux x86-64")
    source = AGENT_KERNELS / f"{name}.s3"
    library_path = tmp_path / f"{name}.so"
    subprocess.run(
        [sys.executable, "-m", "bootstrap.s3.cli", "check", str(source)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "bootstrap.s3.cli",
            "ffi-build",
            str(source),
            "-O",
            "1",
            "--native-policy",
            "baseline",
            "-o",
            str(library_path),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return ctypes.CDLL(str(library_path))


def _f64(values: list[float]):
    return (ctypes.c_double * len(values))(*values)


def _i64(values: list[int]):
    return (ctypes.c_int64 * len(values))(*values)


def test_agent_point_centroid_matches_open3d_sample_and_rejects_bad_shapes(tmp_path: Path) -> None:
    fixture, _ = _documents()
    data = fixture["point_cloud"]
    points = data["sample_count"]
    coordinates = _f64(data["coordinates_xyz"])
    output = (ctypes.c_double * 3)(-9.0, -9.0, -9.0)
    kernel = _compile_kernel(tmp_path, "agent_point_centroid").agent_point_centroid
    kernel.argtypes = [ctypes.POINTER(ctypes.c_double), ctypes.c_int64,
                       ctypes.c_int64, ctypes.POINTER(ctypes.c_double), ctypes.c_int64]
    kernel.restype = ctypes.c_int64

    assert kernel(coordinates, len(coordinates), points, output, len(output)) == 0
    for actual, expected in zip(output, data["expected"]["centroid_xyz"], strict=True):
        assert math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-10)
    assert kernel(coordinates, len(coordinates), 0, output, len(output)) == 1
    assert kernel(coordinates, len(coordinates), 122, output, len(output)) == 1
    assert kernel(coordinates, len(coordinates) - 1, points, output, len(output)) == 1
    short_output = (ctypes.c_double * 2)(-9.0, -9.0)
    assert kernel(coordinates, len(coordinates), points, short_output, 2) == 2
    assert list(short_output) == [-9.0, -9.0]
    large_output = (ctypes.c_double * 4)(*([-9.0] * 4))
    assert kernel(coordinates, len(coordinates), points, large_output, 4) == 1
    assert list(large_output) == [-9.0] * 4


def test_agent_point_bounds_matches_open3d_sample_and_rejects_bad_shapes(tmp_path: Path) -> None:
    fixture, _ = _documents()
    data = fixture["point_cloud"]
    coordinates = _f64(data["coordinates_xyz"])
    output = (ctypes.c_double * 6)(*([-9.0] * 6))
    kernel = _compile_kernel(tmp_path, "agent_point_bounds").agent_point_bounds
    kernel.argtypes = [ctypes.POINTER(ctypes.c_double), ctypes.c_int64,
                       ctypes.c_int64, ctypes.POINTER(ctypes.c_double), ctypes.c_int64]
    kernel.restype = ctypes.c_int64

    assert kernel(coordinates, len(coordinates), data["sample_count"], output, 6) == 0
    expected = data["expected"]["minimum_xyz"] + data["expected"]["maximum_xyz"]
    assert list(output) == expected
    assert kernel(coordinates, len(coordinates), 0, output, 6) == 1
    assert kernel(coordinates, len(coordinates), 122, output, 6) == 1
    assert kernel(coordinates, len(coordinates) - 1, data["sample_count"], output, 6) == 1
    short_output = (ctypes.c_double * 5)(*([-9.0] * 5))
    assert kernel(coordinates, len(coordinates), data["sample_count"], short_output, 5) == 2
    assert list(short_output) == [-9.0] * 5
    large_output = (ctypes.c_double * 7)(*([-9.0] * 7))
    assert kernel(coordinates, len(coordinates), data["sample_count"], large_output, 7) == 1
    assert list(large_output) == [-9.0] * 7


def test_agent_raster_threshold_count_matches_usgs_window(tmp_path: Path) -> None:
    fixture, _ = _documents()
    data = fixture["raster"]
    values = _f64(data["values"])
    mask = _i64(data["valid_mask"])
    output = (ctypes.c_int64 * 1)(-9)
    kernel = _compile_kernel(tmp_path, "agent_raster_threshold_count").agent_raster_threshold_count
    kernel.argtypes = [ctypes.POINTER(ctypes.c_double), ctypes.c_int64,
                       ctypes.POINTER(ctypes.c_int64), ctypes.c_int64, ctypes.c_int64,
                       ctypes.c_double, ctypes.POINTER(ctypes.c_int64), ctypes.c_int64]
    kernel.restype = ctypes.c_int64

    count = len(values)
    assert kernel(values, count, mask, count, count,
                  data["threshold_strictly_greater_than"], output, 1) == 0
    assert output[0] == data["expected"]["count_greater_than_threshold"]
    assert kernel(values, count, mask, count, 365,
                  data["threshold_strictly_greater_than"], output, 1) == 1
    assert kernel(values, count, mask, count - 1, count,
                  data["threshold_strictly_greater_than"], output, 1) == 1
    assert kernel(values, count, mask, count, count,
                  data["threshold_strictly_greater_than"], output, 0) == 2
    large_output = (ctypes.c_int64 * 2)(-9, -9)
    assert kernel(values, count, mask, count, count,
                  data["threshold_strictly_greater_than"], large_output, 2) == 1
    assert list(large_output) == [-9, -9]


def test_agent_raster_valid_mean_matches_usgs_window_and_empty_mask_status(tmp_path: Path) -> None:
    fixture, _ = _documents()
    data = fixture["raster"]
    values = _f64(data["values"])
    mask = _i64(data["valid_mask"])
    output = (ctypes.c_double * 1)(-9.0)
    kernel = _compile_kernel(tmp_path, "agent_raster_valid_mean").agent_raster_valid_mean
    kernel.argtypes = [ctypes.POINTER(ctypes.c_double), ctypes.c_int64,
                       ctypes.POINTER(ctypes.c_int64), ctypes.c_int64, ctypes.c_int64,
                       ctypes.POINTER(ctypes.c_double), ctypes.c_int64]
    kernel.restype = ctypes.c_int64

    count = len(values)
    assert kernel(values, count, mask, count, count, output, 1) == 0
    assert math.isclose(output[0], data["expected"]["valid_mean"], rel_tol=0.0, abs_tol=1e-12)
    empty_mask = _i64([0] * count)
    output[0] = -9.0
    assert kernel(values, count, empty_mask, count, count, output, 1) == 1
    assert output[0] == -9.0
    large_output = (ctypes.c_double * 2)(-9.0, -9.0)
    assert kernel(values, count, mask, count, count, large_output, 2) == 1
    assert list(large_output) == [-9.0, -9.0]


def test_agent_energy_residual_matches_independent_reference_at_max_bound(tmp_path: Path) -> None:
    count = 364
    actual_values = [float((index % 17) * 8) / 64.0 for index in range(count)]
    load_values = [float((index % 13) * 4) / 64.0 for index in range(count)]
    differences = [actual - load for actual, load in zip(actual_values, load_values, strict=True)]
    expected = [
        math.fsum(differences),
        max(abs(value) for value in differences),
        math.fsum(abs(value) for value in differences) / count,
    ]
    actual = _f64(actual_values)
    load = _f64(load_values)
    output = (ctypes.c_double * 3)(-9.0, -9.0, -9.0)
    kernel = _compile_kernel(tmp_path, "agent_energy_residual").agent_energy_residual
    kernel.argtypes = [ctypes.POINTER(ctypes.c_double), ctypes.c_int64,
                       ctypes.POINTER(ctypes.c_double), ctypes.c_int64, ctypes.c_int64,
                       ctypes.POINTER(ctypes.c_double), ctypes.c_int64]
    kernel.restype = ctypes.c_int64

    assert kernel(actual, count, load, count, count, output, 3) == 0
    for got, want in zip(output, expected, strict=True):
        assert math.isclose(got, want, rel_tol=0.0, abs_tol=1e-12)
    assert kernel(actual, count, load, count, 365, output, 3) == 1
    assert kernel(actual, count, load, count - 1, count, output, 3) == 1
    short_output = (ctypes.c_double * 2)(-9.0, -9.0)
    assert kernel(actual, count, load, count, count, short_output, 2) == 2
    assert list(short_output) == [-9.0, -9.0]
    large_output = (ctypes.c_double * 4)(*([-9.0] * 4))
    assert kernel(actual, count, load, count, count, large_output, 4) == 1
    assert list(large_output) == [-9.0] * 4
