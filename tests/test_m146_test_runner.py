from __future__ import annotations

import json

import pytest

from bootstrap.s3.cli import main as cli_main
from bootstrap.s3.test_runner import (
    S3TestManifest,
    TestRunnerError,
    render_test_report,
    run_test_manifest,
)


PASS_SOURCE = """\
fn main() -> tryte:
    return 2
"""


RESOURCE_SOURCE = """\
fn main() -> i64:
    capability: host_capability = host_capability_grant(1)
    mut handle: resource_handle = resource_open(capability)
    mut result: i64 = resource_kind(&handle)
    one: i64 = 1
    zero: i64 = 0
    match resource_is_open(&handle):
        -1:
            result = result + one
        0:
            result = result + zero
        1:
            result = result + zero
    discard resource_close(&mut handle)
    return result
"""


def _manifest(path, body: str, *, source: str = PASS_SOURCE):
    (path / "case.s3").write_text(source, encoding="utf-8")
    manifest = path / "s3-test.toml"
    manifest.write_text(body, encoding="utf-8")
    return manifest


def test_hosted_runner_is_deterministic_and_orders_cases(tmp_path) -> None:
    manifest = _manifest(
        tmp_path,
        """\
[runner]
seed = 17
timeout_ms = 5000
mode = "hosted"
optimization = "O1"

[[test]]
name = "z_case"
source = "case.s3"
expected = 2

[[test]]
name = "a_case"
source = "case.s3"
expected = 2
""",
    )

    first = run_test_manifest(manifest)
    second = run_test_manifest(manifest)

    first_for_identity = json.loads(json.dumps(first))
    second_for_identity = json.loads(json.dumps(second))
    for report in first_for_identity["tests"] + second_for_identity["tests"]:
        report.pop("duration_ms")
    assert first_for_identity == second_for_identity
    assert [case["name"] for case in first["tests"]] == ["a_case", "z_case"]
    assert first["schema_version"] == "s3.test-report.v1"
    assert first["summary"] == {
        "status": "PASS",
        "passed": 2,
        "failed": 0,
        "skipped": 0,
        "timed_out": 0,
        "capability_denied": 0,
        "resource_limited": 0,
        "infrastructure_failed": 0,
    }
    assert render_test_report(first).endswith("\n")


def test_cli_test_writes_the_same_machine_report(tmp_path, capsys) -> None:
    manifest = _manifest(
        tmp_path,
        """\
[runner]
mode = "hosted"
timeout_ms = 5000

[[test]]
name = "main"
source = "case.s3"
expected = 2
""",
    )
    report_path = tmp_path / "out" / "result.json"

    assert cli_main(["test", str(manifest), "--report", str(report_path)]) == 0
    output = capsys.readouterr().out
    assert json.loads(output)["schema"] == "s3-test-report"
    assert report_path.read_text(encoding="utf-8") == output


def test_expected_value_mismatch_is_a_failure(tmp_path) -> None:
    manifest = _manifest(
        tmp_path,
        """\
[runner]
mode = "hosted"
timeout_ms = 5000

[[test]]
name = "wrong"
source = "case.s3"
expected = 3
""",
    )

    report = run_test_manifest(manifest)
    assert report["summary"]["status"] == "FAIL"
    assert report["tests"][0]["hosted"]["error"] == "expected 3, got 2"


def test_resource_limit_failure_is_reported_not_hung(tmp_path) -> None:
    source = """\
fn recurse() -> tryte:
    return recurse()
fn main() -> tryte:
    return recurse()
"""
    manifest = _manifest(
        tmp_path,
        """\
[runner]
mode = "hosted"
timeout_ms = 5000
max_frames = 2

[[test]]
name = "frame_limit"
source = "case.s3"
expected = 0
""",
        source=source,
    )

    report = run_test_manifest(manifest)
    assert report["summary"]["status"] == "RESOURCE_LIMIT"
    assert report["tests"][0]["status"] == "RESOURCE_LIMIT"
    assert "frame" in report["tests"][0]["hosted"]["error"].lower()


def test_capability_use_requires_an_explicit_manifest_declaration(tmp_path) -> None:
    manifest = _manifest(
        tmp_path,
        """\
[runner]
mode = "hosted"
timeout_ms = 5000

[[test]]
name = "undeclared_resource"
source = "case.s3"
expected = 2
""",
        source=RESOURCE_SOURCE,
    )

    report = run_test_manifest(manifest)
    assert report["summary"]["status"] == "CAPABILITY_DENIED"
    assert report["tests"][0]["status"] == "CAPABILITY_DENIED"
    assert report["tests"][0]["capability_denials"] == ["resource"]
    assert report["tests"][0]["hosted"]["error"] == "undeclared capability: resource"


def test_declared_resource_fixture_runs_hosted_and_native_has_explicit_skip_or_pass(tmp_path) -> None:
    manifest = _manifest(
        tmp_path,
        """\
[runner]
mode = "both"
timeout_ms = 5000

[[test]]
name = "resource_fixture"
source = "case.s3"
expected = 2
capabilities = ["resource"]
""",
        source=RESOURCE_SOURCE,
    )

    report = run_test_manifest(manifest)
    assert report["tests"][0]["hosted"]["status"] == "PASS"
    assert report["tests"][0]["native"]["status"] in {"PASS", "SKIP"}


def test_invalid_manifest_mode_is_rejected(tmp_path) -> None:
    manifest = _manifest(
        tmp_path,
        """\
[runner]
mode = "not-a-mode"

[[test]]
name = "main"
source = "case.s3"
expected = 2
""",
    )
    with pytest.raises(TestRunnerError, match="unsupported test runner mode"):
        S3TestManifest.load(manifest)
