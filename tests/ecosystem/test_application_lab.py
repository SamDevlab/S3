from __future__ import annotations

import platform

import pytest

from ecosystem.application_lab import (
    PINNED_COMPILER_REVISION,
    discover_applications,
    run_application,
)
from ecosystem.application_lab.lab import ApplicationLabError


def test_real_applications_compile_run_and_match_pinned_outputs() -> None:
    reports = [run_application(item["path"]) for item in discover_applications()]
    assert len(reports) == 5
    assert {item["status"] for item in reports} == {"PASS"}
    assert all(item["execution_mode"] == "HOSTED_EXECUTION" for item in reports)
    assert all(item["compiler_revision"] == PINNED_COMPILER_REVISION for item in reports)
    assert all(item["actual_output"] == item["expected_output"] for item in reports)
    assert all(len(item["source_sha256"]) == 64 for item in reports)
    assert all(len(item["fixture_sha256"]) == 64 for item in reports)


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
    assert ffi["status"] == "UNSUPPORTED_ENVIRONMENT"
    assert ffi["execution_mode"] == "FFI_INTEGRATION"
    native = run_application(application, mode="native")
    if platform.system() != "Linux":
        assert native["status"] == "UNSUPPORTED_ENVIRONMENT"
        assert native["execution_mode"] == "UNSUPPORTED_ENVIRONMENT"


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
