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

from bootstrap.s3.backends.x86_64 import NativeToolchain, generate_ffi_assembly
from bootstrap.s3.ir_emulator import execute_ir
from bootstrap.s3.optimizer import OptimizationLevel
from bootstrap.s3.pipeline import compile_source, compile_sources
from bootstrap.s3.stdlib import standard_library_sources


ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = ROOT / "benchmarks/workloads/real_world/datasets-v1.json"
REFERENCE_PATH = ROOT / "benchmarks/references/s3-1.5/reference-results-v1.json"
MANIFEST_PATH = ROOT / "benchmarks/manifests/s3bench-1.5-real-world.json"
WORKLOAD_DIR = ROOT / "benchmarks/workloads/real_world"
AGENT_CORPUS_PATH = WORKLOAD_DIR / "agent-kernel-corpus-v1.json"
TOLERANCES = {
    "engineering.point-cloud-summary.v1": (1e-9, 1e-9),
    "geospatial.raster-window-statistics.v1": (1e-9, 1e-9),
    "energy.pv-timeseries-aggregation.v1": (1e-6, 1e-9),
}
MAX_NATIVE_INSTRUCTIONS = 100_000_000


def _documents() -> tuple[dict, dict, dict]:
    return tuple(
        json.loads(path.read_text(encoding="utf-8"))
        for path in (DATASET_PATH, REFERENCE_PATH, MANIFEST_PATH)
    )  # type: ignore[return-value]


def _literal(value: int | float) -> str:
    if isinstance(value, int):
        return str(value) + ".0"
    return repr(float(value))


def _push_vector(name: str, element_type: str, values: list[int | float]) -> list[str]:
    lines = [f"    mut {name}: {element_type}_vector = {element_type}_vector_new({len(values)})"]
    for value in values:
        rendered = _literal(value) if element_type == "f64" else str(int(value))
        lines.append(f"    discard {element_type}_vector_push(&mut {name}, {rendered})")
    return lines


_ASSERTION_HELPERS = """\
fn mismatch(value: trit) -> i64:
    match value:
        -1:
            return 0
        0:
            return 1
        1:
            return 1

fn close_enough(actual: f64, expected: f64, tolerance: f64) -> trit:
    match actual < expected - tolerance:
        -1:
            return 1
        0:
            match actual > expected + tolerance:
                -1:
                    return 1
                0:
                    return -1
                1:
                    return -1
        1:
            return 1
"""


def _hosted_source(workload: dict) -> tuple[str, tuple[str, ...]]:
    inputs = workload["input"]
    outputs = workload["expected_output"]
    workload_id = workload["workload_id"]
    if workload_id == "engineering.point-cloud-summary.v1":
        source = (
            "module main\n"
            "from s3.v1.geometry import point_cloud_centroid\n"
            "from s3.v1.geometry import point_cloud_bounds\n"
            "from s3.v1.geometry import point_cloud_radius_of_gyration\n"
            "from s3.v1.geometry import GeometryVec3Result\n"
            "from s3.v1.geometry import GeometryBounds3\n"
            "from s3.v1.geometry import GeometryScalarResult\n"
            + _ASSERTION_HELPERS
            + "fn main() -> i64:\n"
            + "\n".join(_push_vector("coordinates", "f64", inputs["coordinates"]))
            + "\n"
            + f"    center: GeometryVec3Result = point_cloud_centroid(&coordinates, {inputs['point_count']})\n"
            + f"    bounds: GeometryBounds3 = point_cloud_bounds(&coordinates, {inputs['point_count']})\n"
            + f"    radius: GeometryScalarResult = point_cloud_radius_of_gyration(&coordinates, {inputs['point_count']})\n"
            + "    mut failures: i64 = mismatch(center.status == 0)\n"
            + "    failures = failures + mismatch(bounds.status == 0)\n"
            + "    failures = failures + mismatch(radius.status == 0)\n"
            + f"    failures = failures + mismatch(close_enough(center.value.x, {_literal(outputs['centroid_x'])}, 0.000000001))\n"
            + f"    failures = failures + mismatch(close_enough(center.value.y, {_literal(outputs['centroid_y'])}, 0.000000001))\n"
            + f"    failures = failures + mismatch(close_enough(center.value.z, {_literal(outputs['centroid_z'])}, 0.000000001))\n"
        )
        for field, component in (
            ("minimum_x", "minimum.x"), ("minimum_y", "minimum.y"), ("minimum_z", "minimum.z"),
            ("maximum_x", "maximum.x"), ("maximum_y", "maximum.y"), ("maximum_z", "maximum.z"),
        ):
            source += f"    failures = failures + mismatch(close_enough(bounds.{component}, {_literal(outputs[field])}, 0.000000001))\n"
        source += f"    failures = failures + mismatch(close_enough(radius.value, {_literal(outputs['radius_of_gyration'])}, 0.000000001))\n"
        source += "    return failures\n"
        return source, ("s3.v1.geometry",)

    if workload_id == "geospatial.raster-window-statistics.v1":
        source = (
            "module main\n"
            + _ASSERTION_HELPERS
            + "fn absolute_f64(value: f64) -> f64:\n"
            + "    match value < 0.0:\n"
            + "        -1:\n            return 0.0 - value\n"
            + "        0:\n            return value\n"
            + "        1:\n            return value\n"
            + "fn minimum_f64(left: f64, right: f64) -> f64:\n"
            + "    match right < left:\n"
            + "        -1:\n            return right\n"
            + "        0:\n            return left\n"
            + "        1:\n            return right\n"
            + "fn maximum_f64(left: f64, right: f64) -> f64:\n"
            + "    match left < right:\n"
            + "        -1:\n            return right\n"
            + "        0:\n            return left\n"
            + "        1:\n            return left\n"
            + "fn main() -> i64:\n"
            + "\n".join(_push_vector("values", "f64", inputs["values"]))
            + "\n"
            + "\n".join(_push_vector("valid", "i64", inputs["valid_mask"]))
            + "\n"
            + f"    mut raster_width: i64 = {inputs['width']}\n    mut raster_height: i64 = {inputs['height']}\n    mut row: i64 = 0\n    mut valid_count: i64 = 0\n    mut gradient_count: i64 = 0\n"
            + "    mut total: f64 = 0.0\n    mut minimum: f64 = 0.0\n    mut maximum: f64 = 0.0\n"
            + "    mut threshold_count: i64 = 0\n    mut gradient_total: f64 = 0.0\n    mut first_valid: i64 = 0\n"
            + "    while row < raster_height:\n"
            + "        mut column: i64 = 0\n"
            + "        while column < raster_width:\n"
            + "            mut index: i64 = row * raster_width + column\n"
            + "            match i64_vector_get(&valid, index) == 1:\n"
            + "                -1:\n"
            + "                    mut value: f64 = f64_vector_get(&values, index)\n"
            + "                    match first_valid == 0:\n"
            + "                        -1:\n                            minimum = value\n                            maximum = value\n                            first_valid = 1\n"
            + "                        0:\n                            first_valid = first_valid\n"
            + "                        1:\n                            first_valid = first_valid\n"
            + "                    total = total + value\n                    valid_count = valid_count + 1\n"
            + f"                    match value > {_literal(inputs['threshold'])}:\n"
            + "                        -1:\n                            threshold_count = threshold_count + 1\n"
            + "                        0:\n                            threshold_count = threshold_count\n"
            + "                        1:\n                            threshold_count = threshold_count\n"
            + "                    minimum = minimum_f64(minimum, value)\n                    maximum = maximum_f64(maximum, value)\n"
            + "                    match to_tryte(column + 1) < to_tryte(raster_width):\n"
            + "                        -1:\n"
            + "                            match i64_vector_get(&valid, index + 1) == 1:\n"
            + "                                -1:\n                                    gradient_total = gradient_total + absolute_f64(f64_vector_get(&values, index + 1) - value)\n                                    gradient_count = gradient_count + 1\n"
            + "                                0:\n                                    gradient_count = gradient_count\n"
            + "                                1:\n                                    gradient_count = gradient_count\n"
            + "                        0:\n                            gradient_count = gradient_count\n"
            + "                        1:\n                            gradient_count = gradient_count\n"
            + "                0:\n                    valid_count = valid_count\n"
            + "                1:\n                    valid_count = valid_count\n"
            + "            column = column + 1\n        row = row + 1\n"
            + "    mut failures: i64 = mismatch(valid_count == " + str(sum(inputs["valid_mask"])) + ")\n"
            + f"    failures = failures + mismatch(close_enough(total, {_literal(outputs['valid_sum'])}, 0.000000001))\n"
            + f"    failures = failures + mismatch(close_enough(total / to_f64(valid_count), {_literal(outputs['valid_mean'])}, 0.000000001))\n"
            + f"    failures = failures + mismatch(close_enough(minimum, {_literal(outputs['valid_minimum'])}, 0.000000001))\n"
            + f"    failures = failures + mismatch(close_enough(maximum, {_literal(outputs['valid_maximum'])}, 0.000000001))\n"
            + f"    failures = failures + mismatch(threshold_count == {int(outputs['threshold_count'])})\n"
            + f"    failures = failures + mismatch(gradient_count == {sum(1 for r in range(inputs['height']) for c in range(inputs['width'] - 1) if inputs['valid_mask'][r * inputs['width'] + c] and inputs['valid_mask'][r * inputs['width'] + c + 1])})\n"
            + f"    failures = failures + mismatch(close_enough(gradient_total / to_f64(gradient_count), {_literal(outputs['horizontal_abs_gradient_mean'])}, 0.000000001))\n"
            + "    return failures\n"
        )
        return source, ()

    if workload_id == "energy.pv-timeseries-aggregation.v1":
        source = (
            "module main\n"
            + _ASSERTION_HELPERS
            + "fn absolute_f64(value: f64) -> f64:\n"
            + "    match value < 0.0:\n"
            + "        -1:\n            return 0.0 - value\n"
            + "        0:\n            return value\n"
            + "        1:\n            return value\n"
            + "fn main() -> i64:\n"
            + "\n".join(_push_vector("ac_power", "f64", inputs["ac_power_w"]))
            + "\n"
            + "\n".join(_push_vector("load", "f64", inputs["load_w"]))
            + "\n"
            + f"    mut period: i64 = 0\n    mut ac_energy: f64 = 0.0\n    mut net_energy: f64 = 0.0\n    mut peak: f64 = 0.0\n    mut balance: f64 = 0.0\n    mut first: i64 = 1\n"
            + f"    while period < {len(inputs['ac_power_w'])}:\n"
            + "        mut ac: f64 = f64_vector_get(&ac_power, period)\n        mut load_value: f64 = f64_vector_get(&load, period)\n"
            + "        ac_energy = ac_energy + ac\n        net_energy = net_energy + ac - load_value\n        balance = balance + absolute_f64(ac - load_value)\n"
            + "        match first == 1:\n            -1:\n                peak = ac\n                first = 0\n            0:\n                first = first\n            1:\n                first = first\n"
            + "        peak = maximum_f64(peak, ac)\n        period = period + 1\n"
            + "    mut failures: i64 = 0\n"
            + f"    failures = failures + mismatch(close_enough(ac_energy, {_literal(outputs['ac_energy_wh'])}, 0.000001))\n"
            + f"    failures = failures + mismatch(close_enough(peak, {_literal(outputs['ac_peak_w'])}, 0.000001))\n"
            + f"    failures = failures + mismatch(close_enough(net_energy, {_literal(outputs['net_energy_wh'])}, 0.000001))\n"
            + f"    failures = failures + mismatch(close_enough(ac_energy / (5000.0 * to_f64({len(inputs['ac_power_w'])})), {_literal(outputs['capacity_factor'])}, 0.000000001))\n"
            + f"    failures = failures + mismatch(close_enough(balance / to_f64({len(inputs['ac_power_w'])}), {_literal(outputs['mean_absolute_balance_w'])}, 0.000001))\n"
            + "    return failures\n"
        )
        source = source.replace(
            "fn main() -> i64:",
            "fn maximum_f64(left: f64, right: f64) -> f64:\n"
            "    match left < right:\n"
            "        -1:\n            return right\n"
            "        0:\n            return left\n"
            "        1:\n            return left\n\nfn main() -> i64:",
        )
        return source, ()
    raise AssertionError(f"unhandled workload: {workload_id}")


def test_real_world_reference_bundle_is_pinned_and_manifested() -> None:
    datasets, references, manifest = _documents()
    dataset_bytes = DATASET_PATH.read_bytes()
    assert hashlib.sha256(dataset_bytes).hexdigest() == references["dataset_manifest"]["sha256"]
    assert manifest["dataset_manifest"] == "workloads/real_world/datasets-v1.json"
    assert manifest["reference_results"] == "references/s3-1.5/reference-results-v1.json"
    assert len(references["workloads"]) == 3
    assert {item["reference_engine"] for item in references["workloads"]} == {"Open3D", "Rasterio", "pvlib"}
    assert {item["workload_id"] for item in references["workloads"]} == set(TOLERANCES)
    assert datasets["dataset_version"] == references["dataset_manifest"]["version"]
    declared = {item["workload_id"]: item for item in manifest["workloads"]}
    for workload in references["workloads"]:
        workload_id = workload["workload_id"]
        spec = declared[workload_id]
        assert spec["dataset_id"] == workload["dataset_id"]
        assert spec["reference_engine"] == workload["reference_engine"]
        assert spec["reference_engine_version"] == workload["reference_engine_version"]
        assert spec["reference_method"] == workload["reference_method"]
        assert spec["dataset_sha256"] == workload["dataset_sha256"]
        assert spec["expected_output_sha256"] == workload["output_sha256"]
        assert spec["workload_version"] == "1.0.0"
        assert spec["s3_source"]
        assert (WORKLOAD_DIR / Path(spec["s3_source"]).name).is_file()
        encoded_output = (json.dumps(workload["expected_output"], sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
        assert hashlib.sha256(encoded_output).hexdigest() == workload["output_sha256"]
        dataset_identity = {
            key: workload[key]
            for key in ("dataset_id", "input", "input_shape", "georeferencing", "site")
            if key in workload
        }
        encoded_dataset = (json.dumps(dataset_identity, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
        assert hashlib.sha256(encoded_dataset).hexdigest() == workload["dataset_sha256"]
        assert spec["tolerance"]["absolute"] == TOLERANCES[workload_id][0]
        assert spec["tolerance"]["relative"] == TOLERANCES[workload_id][1]


def test_agent_kernel_corpus_pins_multiple_bounded_task_to_source_contracts() -> None:
    corpus = json.loads(AGENT_CORPUS_PATH.read_text(encoding="utf-8"))
    _, references, _ = _documents()
    references_by_id = {item["workload_id"]: item for item in references["workloads"]}

    assert len(corpus["tasks"]) >= 2
    assert corpus["execution_contract"]["default_instruction_budget_mode"] == "per-instruction"
    for task in corpus["tasks"]:
        source_path = ROOT / task["source"]
        source_bytes = source_path.read_bytes()
        reference = references_by_id[task["workload_id"]]
        assert hashlib.sha256(source_bytes).hexdigest() == task["source_sha256"]
        assert hashlib.sha256(
            (json.dumps(reference["expected_output"], sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
        ).hexdigest() == task["reference_result_sha256"]
        assert task["check_command"].startswith("python -m bootstrap.s3.cli check ")
        assert task["compile_command"].startswith("python -m bootstrap.s3.cli ffi-build ")
        assert task["bounded_execution"]


@pytest.mark.parametrize("optimization", [OptimizationLevel.O0, OptimizationLevel.O1])
@pytest.mark.parametrize("workload_index", [0, 1, 2])
def test_hosted_real_world_workload_matches_external_reference(optimization, workload_index: int) -> None:
    _, references, manifest = _documents()
    workload = references["workloads"][workload_index]
    source, modules = _hosted_source(workload)
    compilation_sources = standard_library_sources(modules=modules)
    compilation_sources["main.s3"] = source
    compilation = compile_sources(compilation_sources, optimization=optimization)
    assert execute_ir(compilation.ir) == 0


def _as_double_array(values: list[float]):
    return (ctypes.c_double * len(values))(*values)


def _assert_outputs(actual: list[float], expected: dict[str, float], keys: tuple[str, ...], workload_id: str) -> None:
    absolute, relative = TOLERANCES[workload_id]
    for value, key in zip(actual, keys, strict=True):
        assert math.isclose(value, expected[key], rel_tol=relative, abs_tol=absolute), key


@pytest.mark.skipif(platform.system() != "Linux", reason="native shared-library workload gate requires Linux")
@pytest.mark.parametrize("workload_index", [0, 1, 2])
@pytest.mark.parametrize("optimization", [OptimizationLevel.O0, OptimizationLevel.O1])
def test_linux_native_real_world_workload_matches_external_reference(
    tmp_path: Path, workload_index: int, optimization: OptimizationLevel
) -> None:
    _, references, _ = _documents()
    workload = references["workloads"][workload_index]
    _, _, manifest = _documents()
    spec = next(item for item in manifest["workloads"] if item["workload_id"] == workload["workload_id"])
    source_path = ROOT / "benchmarks" / spec["s3_source"]
    source = source_path.read_text(encoding="utf-8")
    compilation = compile_source(source, optimization=optimization)
    _, ordinary_assembly = compilation.require_ordinary_artifacts()
    native_assembly = generate_ffi_assembly(ordinary_assembly, max_instructions=MAX_NATIVE_INSTRUCTIONS)
    library_path = NativeToolchain.detect().build_shared(
        native_assembly, tmp_path / f"{workload_index}-{optimization.value}.so"
    )
    library = ctypes.CDLL(str(library_path))
    expected = workload["expected_output"]
    if workload_index == 0:
        kernel = library.point_cloud_summary
        kernel.argtypes = [
            ctypes.POINTER(ctypes.c_double), ctypes.c_int64,
            ctypes.c_int64,
            ctypes.POINTER(ctypes.c_double), ctypes.c_int64,
        ]
        kernel.restype = ctypes.c_int64
        coordinates = _as_double_array(workload["input"]["coordinates"])
        output = (ctypes.c_double * 10)()
        assert kernel(coordinates, len(coordinates), workload["input"]["point_count"], output, 10) == 0
        _assert_outputs(list(output), expected, (
            "centroid_x", "centroid_y", "centroid_z", "minimum_x", "minimum_y", "minimum_z",
            "maximum_x", "maximum_y", "maximum_z", "radius_of_gyration",
        ), workload["workload_id"])
        assert kernel(coordinates, len(coordinates), 122, output, 10) == 1
        assert kernel(coordinates, len(coordinates) - 1, workload["input"]["point_count"], output, 10) == 2
    elif workload_index == 1:
        kernel = library.raster_window_statistics
        kernel.argtypes = [
            ctypes.POINTER(ctypes.c_double), ctypes.c_int64,
            ctypes.POINTER(ctypes.c_int64), ctypes.c_int64,
            ctypes.c_int64, ctypes.c_int64, ctypes.c_double,
            ctypes.POINTER(ctypes.c_double), ctypes.c_int64,
        ]
        kernel.restype = ctypes.c_int64
        values = _as_double_array(workload["input"]["values"])
        mask = (ctypes.c_int64 * len(workload["input"]["valid_mask"]))(*workload["input"]["valid_mask"])
        output = (ctypes.c_double * 6)()
        assert kernel(values, len(values), mask, len(mask), workload["input"]["width"], workload["input"]["height"], workload["input"]["threshold"], output, 6) == 0
        _assert_outputs(list(output), expected, (
            "valid_sum", "valid_mean", "valid_minimum", "valid_maximum", "threshold_count", "horizontal_abs_gradient_mean",
        ), workload["workload_id"])
        assert kernel(values, len(values), mask, len(mask), 9, workload["input"]["height"], workload["input"]["threshold"], output, 6) == 2
    else:
        kernel = library.energy_series_aggregation
        kernel.argtypes = [
            ctypes.POINTER(ctypes.c_double), ctypes.c_int64,
            ctypes.POINTER(ctypes.c_double), ctypes.c_int64,
            ctypes.c_double, ctypes.POINTER(ctypes.c_double), ctypes.c_int64,
        ]
        kernel.restype = ctypes.c_int64
        ac = _as_double_array(workload["input"]["ac_power_w"])
        load = _as_double_array(workload["input"]["load_w"])
        output = (ctypes.c_double * 5)()
        kernel_config = _documents()[0]["energy"]
        assert kernel(ac, len(ac), load, len(load), kernel_config["dc_capacity_w"], output, 5) == 0
        _assert_outputs(list(output), expected, (
            "ac_energy_wh", "ac_peak_w", "net_energy_wh", "capacity_factor", "mean_absolute_balance_w",
        ), workload["workload_id"])
        assert kernel(ac, len(ac), load, len(load) - 1, kernel_config["dc_capacity_w"], output, 5) == 2


@pytest.mark.skipif(platform.system() != "Linux", reason="agent-kernel native CLI gate requires Linux")
@pytest.mark.parametrize("task_index", [0, 1, 2])
def test_agent_kernel_cli_check_ffi_compile_and_bounded_run(tmp_path: Path, task_index: int) -> None:
    corpus = json.loads(AGENT_CORPUS_PATH.read_text(encoding="utf-8"))
    _, references, _ = _documents()
    task = corpus["tasks"][task_index]
    workload = next(item for item in references["workloads"] if item["workload_id"] == task["workload_id"])
    source_path = ROOT / task["source"]
    library_path = tmp_path / f"agent-kernel-{task_index}.so"

    subprocess.run(
        [sys.executable, "-m", "bootstrap.s3.cli", "check", str(source_path)],
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
            str(source_path),
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
    library = ctypes.CDLL(str(library_path))
    data = workload["input"]
    expected = workload["expected_output"]

    if task_index == 0:
        kernel = getattr(library, task["native_symbol"])
        kernel.argtypes = [ctypes.POINTER(ctypes.c_double), ctypes.c_int64, ctypes.c_int64,
                           ctypes.POINTER(ctypes.c_double), ctypes.c_int64]
        kernel.restype = ctypes.c_int64
        coordinates = _as_double_array(data["coordinates"])
        output = (ctypes.c_double * 10)()
        assert kernel(coordinates, len(coordinates), data["point_count"], output, 10) == 0
        keys = (
            "centroid_x", "centroid_y", "centroid_z", "minimum_x", "minimum_y", "minimum_z",
            "maximum_x", "maximum_y", "maximum_z", "radius_of_gyration",
        )
    elif task_index == 1:
        kernel = getattr(library, task["native_symbol"])
        kernel.argtypes = [ctypes.POINTER(ctypes.c_double), ctypes.c_int64,
                           ctypes.POINTER(ctypes.c_int64), ctypes.c_int64, ctypes.c_int64, ctypes.c_int64,
                           ctypes.c_double, ctypes.POINTER(ctypes.c_double), ctypes.c_int64]
        kernel.restype = ctypes.c_int64
        values = _as_double_array(data["values"])
        mask = (ctypes.c_int64 * len(data["valid_mask"]))(*data["valid_mask"])
        output = (ctypes.c_double * 6)()
        assert kernel(values, len(values), mask, len(mask), data["width"], data["height"], data["threshold"], output, 6) == 0
        keys = (
            "valid_sum", "valid_mean", "valid_minimum", "valid_maximum", "threshold_count",
            "horizontal_abs_gradient_mean",
        )
    else:
        kernel = getattr(library, task["native_symbol"])
        kernel.argtypes = [ctypes.POINTER(ctypes.c_double), ctypes.c_int64,
                           ctypes.POINTER(ctypes.c_double), ctypes.c_int64, ctypes.c_double,
                           ctypes.POINTER(ctypes.c_double), ctypes.c_int64]
        kernel.restype = ctypes.c_int64
        ac = _as_double_array(data["ac_power_w"])
        load = _as_double_array(data["load_w"])
        capacity = json.loads(DATASET_PATH.read_text(encoding="utf-8"))["energy"]["dc_capacity_w"]
        output = (ctypes.c_double * 5)()
        assert kernel(ac, len(ac), load, len(load), capacity, output, 5) == 0
        keys = (
            "ac_energy_wh", "ac_peak_w", "net_energy_wh", "capacity_factor", "mean_absolute_balance_w",
        )
    _assert_outputs(list(output), expected, keys, task["workload_id"])
