from __future__ import annotations

from pathlib import Path

from bootstrap.s3.test_framework import discover_manifests, run_project_tests


def test_project_test_framework_discovers_in_stable_order_and_filters(tmp_path: Path) -> None:
    for directory, name in (("z", "z_case"), ("a", "a_case")):
        root = tmp_path / directory
        root.mkdir()
        (root / "case.s3").write_text("fn main() -> tryte:\n    return 2\n", encoding="utf-8")
        (root / "s3-test.toml").write_text(
            f"[[test]]\nname = \"{name}\"\nsource = \"case.s3\"\nexpected = 2\n",
            encoding="utf-8",
        )
    assert [item.relative_to(tmp_path).as_posix() for item in discover_manifests(tmp_path)] == ["a/s3-test.toml", "z/s3-test.toml"]
    report = run_project_tests(tmp_path, name_pattern="a_*")
    assert report["summary"] == {
        "status": "PASS", "passed": 1, "failed": 0, "skipped": 0,
        "timed_out": 0, "capability_denied": 0, "resource_limited": 0,
        "infrastructure_failed": 0,
    }
