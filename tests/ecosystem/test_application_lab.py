from __future__ import annotations

import platform

import pytest

from ecosystem.application_lab import (
    PINNED_COMPILER_REVISION,
    discover_applications,
    run_application,
)
from ecosystem.application_lab.lab import (
    ApplicationLabError,
    _ffi_source_signature_error,
    _validate_ffi_manifest,
)


def test_real_applications_compile_run_and_match_pinned_outputs() -> None:
    reports = [run_application(item["path"]) for item in discover_applications()]
    hosted = [item for item in reports if item["execution_mode"] == "HOSTED_EXECUTION"]
    ffi = [item for item in reports if item["execution_mode"] == "FFI_INTEGRATION"]
    assert len(hosted) == 5
    assert len(ffi) == 1
    assert ffi[0]["status"] == "NOT_APPLICABLE"
    assert {item["status"] for item in hosted} == {"PASS"}
    assert all(item["compiler_revision"] == PINNED_COMPILER_REVISION for item in reports)
    assert all(item["actual_output"] == item["expected_output"] for item in hosted)
    assert all(len(item["source_sha256"]) == 64 for item in hosted)
    assert all(len(item["fixture_sha256"]) == 64 for item in hosted)


def test_two_offline_packages_are_reused_by_independent_applications() -> None:
    by_name = {item["name"]: item for item in discover_applications()}
    data = run_application(by_name["data-quality-report"]["path"])
    graph = run_application(by_name["graph-path-report"]["path"])
    ternary = run_application(by_name["balanced-state-audit"]["path"])
    assert {"s3-balanced-ternary", "s3-integer-summary"}.issubset(
        {item["name"] for item in data["package_lock"]["packages"]}
    )
    assert "s3-integer-summary" in graph["package_source_sha256"]
    assert "s3-balanced-ternary" in ternary["package_source_sha256"]


def test_unsupported_modes_are_never_reported_as_pass() -> None:
    application = discover_applications()[0]["path"]
    ffi = run_application(application, mode="ffi")
    assert ffi["status"] == "FFI_NOT_APPLICABLE"
    assert ffi["execution_mode"] == "FFI_INTEGRATION"
    native = run_application(application, mode="native")
    if platform.system() != "Linux":
        assert native["status"] == "UNSUPPORTED_ENVIRONMENT"
        assert native["execution_mode"] == "NATIVE_EXECUTION"


def test_ffi_mode_is_explicitly_unsupported_outside_linux_x86_64() -> None:
    application = next(
        item for item in discover_applications() if item["name"] == "ffi-native-library"
    )
    report = run_application(application["path"], mode="ffi")
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        assert report["status"] == "FFI_UNSUPPORTED_ENVIRONMENT"
        assert "requires Linux x86_64" in report["reason"]


def test_ffi_manifest_rejects_path_escape_and_library_traversal() -> None:
    manifest = {
        "schema": "s3.ffi-app.v1",
        "source": "src/main.s3",
        "library_filename": "libs3.so",
        "symbol": "s3_add_i64",
        "parameters": ["i64", "i64"],
        "result": "i64",
        "calling_convention": "sysv-amd64",
        "supported_os": "Linux",
        "supported_arch": "x86_64",
        "timeout_ms": 10000,
        "cases": [
            {"name": f"case-{index}", "arguments": [index, 0], "expected": index}
            for index in range(5)
        ],
    }
    assert _validate_ffi_manifest(manifest, "test") is manifest
    for field, value in (
        ("source", "../../outside.s3"),
        ("source", "C:/outside.s3"),
        ("library_filename", "../outside.so"),
        ("library_filename", r"..\outside.so"),
    ):
        with pytest.raises(ApplicationLabError):
            _validate_ffi_manifest({**manifest, field: value}, "test")


def test_ffi_source_signature_is_verified_before_a_native_load() -> None:
    contract = {
        "symbol": "s3_add_i64",
        "parameters": ["i64", "i64"],
        "result": "i64",
    }
    matching = """\
export fn s3_add_i64(left: i64, right: i64) -> i64:
    return left + right
fn main() -> i64:
    return 0
"""
    mismatched = """\
export fn s3_add_i64(left: i64) -> i64:
    return left
fn main() -> i64:
    return 0
"""
    missing = """\
export fn another_symbol(left: i64, right: i64) -> i64:
    return left + right
fn main() -> i64:
    return 0
"""
    assert _ffi_source_signature_error(matching, contract) is None
    assert _ffi_source_signature_error(mismatched, contract)[0] == "FFI_ABI_FAILURE"
    assert _ffi_source_signature_error(missing, contract)[0] == "FFI_ABI_FAILURE"


@pytest.mark.skipif(
    platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"},
    reason="requires Linux x86_64 shared linker and ctypes loader",
)
def test_real_ffi_library_is_built_loaded_and_called_by_external_process() -> None:
    application = next(
        item for item in discover_applications() if item["name"] == "ffi-native-library"
    )
    report = run_application(application["path"], mode="ffi")
    assert report["status"] == "FFI_PASS"
    assert report["symbol_exported"] is True
    assert report["external_caller"] == "python ctypes subprocess"
    assert report["external_caller_exit_status"] == 0
    assert len(report["library_sha256"]) == 64
    assert report["elf"]["verified"] is True
    assert {case["status"] for case in report["cases"]} == {"PASS"}
    assert all(report["negative_cases"].values())


@pytest.mark.skipif(
    platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"},
    reason="requires Linux x86_64 native toolchain",
)
def test_native_applications_emit_verified_elf_and_match_hosted_results() -> None:
    applications = [
        item for item in discover_applications()
        if item["execution_mode"] in {"HOSTED_EXECUTION", "NATIVE_EXECUTION"}
    ]
    hosted_by_name = {item["name"]: run_application(item["path"]) for item in applications}
    native_by_name = {item["name"]: run_application(item["path"], mode="native") for item in applications}
    assert len(native_by_name) == 5
    for name, report in native_by_name.items():
        assert report["status"] == "PASS"
        assert report["actual_output"] == hosted_by_name[name]["actual_output"]
        assert report["native_artifact"]["elf"]["verified"] is True
        assert len(report["native_artifact"]["artifact_sha256"]) == 64
        assert report["native_artifact"]["deterministic_result"] is True


def test_compile_only_is_distinct_from_hosted_execution() -> None:
    application = next(
        item for item in discover_applications() if item["name"] == "graph-path-report"
    )
    report = run_application(application["path"], mode="compile-only")
    assert report["status"] == "PASS"
    assert report["execution_mode"] == "COMPILE_ONLY"
    assert report["compile_report"]["compiled_sources"] > 1


def test_application_path_must_remain_inside_the_repository() -> None:
    with pytest.raises(ApplicationLabError, match="outside|inside|escapes"):
        run_application("../../outside")
    with pytest.raises(ApplicationLabError, match="relative|application"):
        run_application(".")
