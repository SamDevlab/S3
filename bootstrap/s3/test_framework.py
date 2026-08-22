"""Deterministic project-level discovery over the bounded S3 test runner."""

from __future__ import annotations

import fnmatch
from dataclasses import replace
from pathlib import Path

from .test_runner import S3TestManifest, S3TestRunner, TestRunnerError


def discover_manifests(root: str | Path) -> tuple[Path, ...]:
    project_root = Path(root).resolve()
    if not project_root.is_dir():
        raise TestRunnerError(f"test root is not a directory: {project_root}")
    return tuple(sorted(path for path in project_root.rglob("s3-test.toml") if path.is_file()))


def run_project_tests(
    root: str | Path,
    *,
    mode: str | None = None,
    name_pattern: str | None = None,
) -> dict[str, object]:
    """Discover, order and execute manifests with one stable aggregate result."""

    if name_pattern is not None and not isinstance(name_pattern, str):
        raise TestRunnerError("test name pattern must be text")
    manifests = discover_manifests(root)
    reports: list[dict[str, object]] = []
    for manifest_path in manifests:
        manifest = S3TestManifest.load(manifest_path)
        if name_pattern is not None:
            tests = tuple(
                test for test in manifest.tests if fnmatch.fnmatchcase(test.name, name_pattern)
            )
            if not tests:
                continue
            manifest = replace(manifest, tests=tests)
        reports.append(S3TestRunner(manifest).run(mode))
    if not reports:
        raise TestRunnerError("test discovery selected no tests")
    summaries = [report["summary"] for report in reports]
    failed = sum(int(summary["failed"]) for summary in summaries)
    skipped = sum(int(summary["skipped"]) for summary in summaries)
    timed_out = sum(int(summary["timed_out"]) for summary in summaries)
    infrastructure_failed = sum(int(summary["infrastructure_failed"]) for summary in summaries)
    capability_denied = sum(int(summary["capability_denied"]) for summary in summaries)
    resource_limited = sum(int(summary["resource_limited"]) for summary in summaries)
    passed = sum(int(summary["passed"]) for summary in summaries)
    status = "PASS"
    if infrastructure_failed:
        status = "INFRASTRUCTURE_FAILURE"
    elif timed_out:
        status = "TIMEOUT"
    elif resource_limited:
        status = "RESOURCE_LIMIT"
    elif capability_denied:
        status = "CAPABILITY_DENIED"
    elif failed:
        status = "FAIL"
    elif skipped and not passed:
        status = "SKIP"
    return {
        "schema": "s3-project-test-report",
        "schema_version": "1",
        "manifests": [str(path.relative_to(Path(root).resolve()).as_posix()) for path in manifests],
        "reports": reports,
        "summary": {
            "status": status,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "timed_out": timed_out,
            "capability_denied": capability_denied,
            "resource_limited": resource_limited,
            "infrastructure_failed": infrastructure_failed,
        },
        "exit_status": 0 if status in {"PASS", "SKIP"} else (2 if status == "INFRASTRUCTURE_FAILURE" else 1),
    }
