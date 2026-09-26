"""Generate pinned external-engine results for the S3 1.5 fixtures."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import open3d as o3d
import pandas as pd
import pvlib
import rasterio
from rasterio.io import MemoryFile
from rasterio.transform import Affine


ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = ROOT / "benchmarks/workloads/real_world/datasets-v1.json"
RESULT_PATH = ROOT / "benchmarks/references/s3-1.5/reference-results-v1.json"


def _canonical_json(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _dataset_sha256(workload: dict[str, object]) -> str:
    identity = {
        key: workload[key]
        for key in ("dataset_id", "input", "input_shape", "georeferencing", "site")
        if key in workload
    }
    return _sha256(_canonical_json(identity))


def _rounded(value: float) -> float:
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("reference result is not finite")
    return round(value, 10)


def _point_cloud(config: dict[str, Any]) -> dict[str, object]:
    count = int(config["point_count"])
    width = int(config["grid_width"])
    points = np.asarray(
        [
            [
                (index % width) - float(config["x_offset"]),
                (index // width) - float(config["y_offset"]),
                ((index * int(config["z_multiplier"])) % int(config["z_modulus"]))
                - float(config["z_offset"]),
            ]
            for index in range(count)
        ],
        dtype=np.float64,
    )
    cloud = o3d.geometry.PointCloud()
    cloud.points = o3d.utility.Vector3dVector(points)
    center = np.asarray(cloud.get_center(), dtype=np.float64)
    bounds = cloud.get_axis_aligned_bounding_box()
    minimum = np.asarray(bounds.min_bound, dtype=np.float64)
    maximum = np.asarray(bounds.max_bound, dtype=np.float64)
    squared_radius_sum = float(np.square(points - center).sum())
    radius_of_gyration = math.sqrt(squared_radius_sum / count)
    outputs = {
        "centroid_x": _rounded(center[0]),
        "centroid_y": _rounded(center[1]),
        "centroid_z": _rounded(center[2]),
        "minimum_x": _rounded(minimum[0]),
        "minimum_y": _rounded(minimum[1]),
        "minimum_z": _rounded(minimum[2]),
        "maximum_x": _rounded(maximum[0]),
        "maximum_y": _rounded(maximum[1]),
        "maximum_z": _rounded(maximum[2]),
        "radius_of_gyration": _rounded(radius_of_gyration),
    }
    return {
        "workload_id": "engineering.point-cloud-summary.v1",
        "domain": "point-cloud-geometry",
        "dataset_id": config["dataset_id"],
        "input_shape": {"points": count, "coordinates": count * 3},
        "logical_operations": ["centroid", "axis-aligned-bounds", "radius-of-gyration"],
        "reference_engine": "Open3D",
        "reference_engine_version": o3d.__version__,
        "reference_method": "Open3D PointCloud.get_center and AxisAlignedBoundingBox; radius of gyration is NumPy squared-distance reduction about the Open3D center",
        "input": {"coordinates": points.reshape(-1).tolist(), "point_count": count},
        "expected_output": outputs,
        "numerical_tolerance": {"absolute": 1e-9, "relative": 1e-9},
        "output_sha256": _sha256(_canonical_json(outputs)),
    }


def _raster(config: dict[str, Any]) -> dict[str, object]:
    width = int(config["width"])
    height = int(config["height"])
    nodata = int(config["nodata"])
    values = np.empty((height, width), dtype=np.int16)
    for row in range(height):
        for column in range(width):
            if (row * width + column) % int(config["nodata_modulus"]) == 0:
                values[row, column] = nodata
            else:
                values[row, column] = (
                    row * int(config["row_multiplier"])
                    + column * int(config["column_multiplier"])
                    + row * column * int(config["product_multiplier"])
                ) % int(config["value_modulus"]) - int(config["value_offset"])
    transform = Affine(*config["transform"])
    profile = {
        "driver": "GTiff",
        "height": height,
        "width": width,
        "count": 1,
        "dtype": "int16",
        "crs": config["crs"],
        "transform": transform,
        "nodata": nodata,
    }
    with MemoryFile() as memory_file:
        with memory_file.open(**profile) as dataset:
            dataset.write(values, 1)
        with memory_file.open() as dataset:
            masked = dataset.read(1, masked=True)
            valid = ~np.ma.getmaskarray(masked)
            raster_values = np.asarray(masked.data, dtype=np.float64)
            valid_values = raster_values[valid]
            differences: list[float] = []
            for row in range(height):
                pair_valid = valid[row, :-1] & valid[row, 1:]
                differences.extend(
                    np.abs(raster_values[row, 1:][pair_valid] - raster_values[row, :-1][pair_valid]).tolist()
                )
            outputs = {
                "valid_sum": _rounded(valid_values.sum()),
                "valid_mean": _rounded(valid_values.mean()),
                "valid_minimum": _rounded(valid_values.min()),
                "valid_maximum": _rounded(valid_values.max()),
                "threshold_count": float(np.count_nonzero(valid_values > int(config["threshold"]))),
                "horizontal_abs_gradient_mean": _rounded(float(np.mean(differences))),
            }
            serialized_values = raster_values.reshape(-1).tolist()
            serialized_mask = valid.astype(np.int64).reshape(-1).tolist()
    return {
        "workload_id": "geospatial.raster-window-statistics.v1",
        "domain": "raster-geospatial",
        "dataset_id": config["dataset_id"],
        "input_shape": {"width": width, "height": height, "cells": width * height},
        "logical_operations": ["nodata-mask", "window-sum", "mean", "min-max", "threshold-count", "horizontal-gradient"],
        "reference_engine": "Rasterio",
        "reference_engine_version": rasterio.__version__,
        "reference_method": "Rasterio in-memory GeoTIFF read with CRS, affine transform and nodata mask; NumPy masked reductions and valid horizontal-neighbor gradient",
        "input": {
            "values": serialized_values,
            "valid_mask": serialized_mask,
            "width": width,
            "height": height,
            "threshold": int(config["threshold"]),
        },
        "georeferencing": {
            "crs": config["crs"],
            "transform": config["transform"],
            "nodata": nodata,
        },
        "expected_output": outputs,
        "numerical_tolerance": {"absolute": 1e-9, "relative": 1e-9},
        "output_sha256": _sha256(_canonical_json(outputs)),
    }


def _energy(config: dict[str, Any]) -> dict[str, object]:
    periods = int(config["periods"])
    times = pd.date_range(
        config["start_local"], periods=periods, freq=config["frequency"], tz=config["timezone"]
    )
    hour = np.asarray(times.hour, dtype=np.float64)
    day = np.asarray((times.dayofyear - times.dayofyear[0]), dtype=np.float64)
    day_of_week = np.asarray(times.dayofweek, dtype=np.int64)
    solar_shape = np.maximum(0.0, np.sin(np.pi * (hour - 6.0) / 12.0))
    cloud = np.asarray(config["cloud_sequence"], dtype=np.float64)[day_of_week]
    ghi = 950.0 * solar_shape * cloud
    dni = 780.0 * solar_shape * cloud
    dhi = np.maximum(0.0, ghi - dni * 0.72)
    temp_air = 22.0 + 7.0 * np.sin(2.0 * np.pi * (hour - 8.0) / 24.0) + 0.25 * day
    wind_speed = 1.5 + (day_of_week % 3) * 0.35
    location = pvlib.location.Location(
        float(config["latitude"]),
        float(config["longitude"]),
        tz=config["timezone"],
        altitude=float(config["altitude_m"]),
    )
    solar_position = location.get_solarposition(times)
    plane_of_array = pvlib.irradiance.get_total_irradiance(
        surface_tilt=float(config["surface_tilt_degrees"]),
        surface_azimuth=float(config["surface_azimuth_degrees"]),
        dni=dni,
        ghi=ghi,
        dhi=dhi,
        dni_extra=pvlib.irradiance.get_extra_radiation(times),
        solar_zenith=solar_position["apparent_zenith"],
        solar_azimuth=solar_position["azimuth"],
        model="haydavies",
    )["poa_global"].fillna(0.0)
    cell_temperature = pvlib.temperature.faiman(plane_of_array, temp_air, wind_speed)
    dc_power = pvlib.pvsystem.pvwatts_dc(
        plane_of_array,
        cell_temperature,
        pdc0=float(config["dc_capacity_w"]),
        gamma_pdc=float(config["gamma_pdc_per_c"]),
    )
    ac_power = pvlib.inverter.pvwatts(
        dc_power,
        pdc0=float(config["dc_capacity_w"]),
        eta_inv_nom=float(config["inverter_efficiency_nominal"]),
    )
    ac = np.maximum(0.0, np.nan_to_num(np.asarray(ac_power, dtype=np.float64)))
    load = (
        float(config["load_base_w"])
        + float(config["load_hour_amplitude_w"]) * (1.0 + np.sin(2.0 * np.pi * (hour - 7.0) / 24.0))
        + float(config["load_day_amplitude_w"]) * (day_of_week.astype(np.float64) / 6.0)
    )
    net = ac - load
    outputs = {
        "ac_energy_wh": _rounded(ac.sum()),
        "ac_peak_w": _rounded(ac.max()),
        "net_energy_wh": _rounded(net.sum()),
        "capacity_factor": _rounded(ac.sum() / (float(config["dc_capacity_w"]) * periods)),
        "mean_absolute_balance_w": _rounded(np.abs(net).mean()),
    }
    inputs = {"ac_power_w": [_rounded(item) for item in ac], "load_w": [_rounded(item) for item in load]}
    return {
        "workload_id": "energy.pv-timeseries-aggregation.v1",
        "domain": "energy-solar-time-series",
        "dataset_id": config["dataset_id"],
        "input_shape": {"hours": periods, "series": 2},
        "logical_operations": ["pvlib-model-output-aggregation", "peak", "capacity-factor", "power-balance"],
        "reference_engine": "pvlib",
        "reference_engine_version": pvlib.__version__,
        "inputs_generated_by": "pvlib solar position, Hay-Davies transposition, Faiman temperature, PVWatts DC/AC",
        "reference_method": "pvlib PV model for hourly AC generation; NumPy aggregation and deterministic synthetic load balance",
        "input": inputs,
        "site": {
            "latitude": config["latitude"],
            "longitude": config["longitude"],
            "altitude_m": config["altitude_m"],
            "timezone": config["timezone"],
        },
        "expected_output": outputs,
        "numerical_tolerance": {"absolute": 1e-6, "relative": 1e-9},
        "output_sha256": _sha256(_canonical_json(outputs)),
    }


def build_document() -> dict[str, object]:
    dataset_bytes = DATASET_PATH.read_bytes()
    configs = json.loads(dataset_bytes)
    workloads = [
        _point_cloud(configs["point_cloud"]),
        _raster(configs["raster"]),
        _energy(configs["energy"]),
    ]
    for workload in workloads:
        workload["dataset_sha256"] = _dataset_sha256(workload)
    return {
        "schema_version": "1.0.0",
        "campaign": "S3_1_5_REAL_WORLD_COMPUTE_QUALIFICATION_AND_NATIVE_GAP_CLOSURE",
        "dataset_manifest": {
            "path": DATASET_PATH.relative_to(ROOT).as_posix(),
            "sha256": _sha256(dataset_bytes),
            "version": configs["dataset_version"],
        },
        "reference_runtime": {
            "python": pd.__version__ and __import__("platform").python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
        "workloads": workloads,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    document = build_document()
    content = _canonical_json(document)
    if args.check:
        if not RESULT_PATH.is_file():
            raise SystemExit(f"missing reference results: {RESULT_PATH}")
        existing = RESULT_PATH.read_bytes()
        if existing != content:
            raise SystemExit("pinned external-engine reference results differ")
        print(f"REFERENCE_RESULTS=PASS sha256={_sha256(content)}")
        return 0
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_bytes(content)
    print(f"REFERENCE_RESULTS_WRITTEN={RESULT_PATH}")
    print(f"REFERENCE_RESULTS_SHA256={_sha256(content)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
