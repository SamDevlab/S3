from __future__ import annotations

from pathlib import Path

import pytest

from bootstrap.s3.cli import main as cli_main
from bootstrap.s3.compiler_provider import CompilerKind, NativeCompilationResult
from bootstrap.s3.ir_serialization import serialize_ir
from bootstrap.s3.native_compiler import inspect_s3c_ng_executable
from bootstrap.s3.project_container import ProjectTooling
from bootstrap.s3.test_framework import discover_manifests, run_project_tests


_MAIN_SOURCE = """\
module main
from mathlib import add_one

fn main() -> i64:
    return add_one(41)
"""

_LIBRARY_SOURCE = """\
module mathlib
export fn add_one(value: i64) -> i64:
    return value + 1
"""


def _project(root: Path) -> Path:
    (root / "src").mkdir(parents=True)
    (root / "shared").mkdir()
    (root / "ignored").mkdir()
    (root / "shared" / "mathlib.s3").write_text(
        _LIBRARY_SOURCE, encoding="utf-8", newline="\n"
    )
    (root / "src" / "main.s3").write_text(
        _MAIN_SOURCE, encoding="utf-8", newline="\n"
    )
    (root / "ignored" / "not_in_manifest.s3").write_text(
        "module ignored\nfn unused() -> i64:\n    return 999\n",
        encoding="utf-8",
        newline="\n",
    )
    (root / "s3.toml").write_text(
        "[project]\n"
        "name = 'tooling-parity'\n"
        "version = '1'\n"
        "entrypoint = 'main'\n"
        "source_roots = ['src', 'shared']\n"
        "profile = 'hosted'\n",
        encoding="utf-8",
        newline="\n",
    )
    return root


def _native_executable() -> Path:
    availability = inspect_s3c_ng_executable()
    if not availability.available:
        pytest.skip(f"S3C-NG parity requires its qualified Linux x86-64 artifact: {availability.reason}")
    return availability.executable


def _write_test_manifest(directory: Path, name: str, expected: int) -> None:
    directory.mkdir(parents=True)
    (directory / "case.s3").write_text(
        f"fn main() -> i64:\n    return {expected}\n",
        encoding="ascii",
        newline="\n",
    )
    (directory / "s3-test.toml").write_text(
        "[runner]\nmode = 'hosted'\n"
        "[[test]]\n"
        f"name = '{name}'\n"
        "source = 'case.s3'\n"
        f"expected = {expected}\n",
        encoding="ascii",
        newline="\n",
    )


def _test_manifests(root: Path) -> tuple[str, ...]:
    _write_test_manifest(root / "z" / "suite", "z_smoke", 7)
    _write_test_manifest(root / "a" / "suite", "a_smoke", 11)
    return tuple(
        path.relative_to(root).as_posix() for path in discover_manifests(root)
    )


def _stable_test_results(report: dict[str, object]) -> list[tuple[object, ...]]:
    return [
        (
            case["name"],
            case["status"],
            case["hosted"]["status"],
            case["hosted"].get("value"),
        )
        for manifest in report["reports"]
        for case in manifest["tests"]
    ]


def test_project_tooling_manifest_roots_filter_and_python_hosted_run(tmp_path: Path) -> None:
    root = _project(tmp_path / "project")
    tooling = ProjectTooling(root, compiler=CompilerKind.PYTHON)

    assert tooling.check().source_roots == ("shared", "src")
    assert tooling.inspect()["sources"] == ("shared/mathlib.s3", "src/main.s3")
    assert tooling.run() == 42


def test_project_tooling_and_cli_match_explicit_native_provider(tmp_path: Path, capsys) -> None:
    executable = _native_executable()
    root = _project(tmp_path / "project")
    python_project = ProjectTooling(root, compiler=CompilerKind.PYTHON)
    native_project = ProjectTooling(
        root, compiler=CompilerKind.S3C_NG, executable=executable
    )

    python_compilation = python_project.build()
    native_compilation = native_project.build()
    assert isinstance(native_compilation, NativeCompilationResult)
    assert serialize_ir(native_compilation.ir) == serialize_ir(python_compilation.ir)
    assert native_compilation.assembly_text == python_compilation.assembly_text
    assert python_project.run() == native_project.run() == 42
    assert "ignored/not_in_manifest.s3" not in python_project.inspect()["sources"]

    cli_outputs: list[str] = []
    for compiler, extra in (
        (CompilerKind.PYTHON, ()),
        (
            CompilerKind.S3C_NG,
            ("--s3c-ng-executable", str(executable)),
        ),
    ):
        assert cli_main(
            [
                "run",
                str(root),
                "--compiler",
                compiler.value,
                *extra,
            ]
        ) == 0
        cli_outputs.append(capsys.readouterr().out)
    assert cli_outputs == ["program returned: 42\n"] * 2

    missing_executable = root / "missing-s3c-ng"
    assert cli_main(
        [
            "run",
            str(root),
            "--compiler",
            CompilerKind.S3C_NG.value,
            "--s3c-ng-executable",
            str(missing_executable),
        ]
    ) == 1
    assert "S3C-NG executable not found" in capsys.readouterr().err


def test_project_test_manifest_discovery_and_filter_are_deterministic(
    tmp_path: Path,
) -> None:
    root = tmp_path / "checks"
    discovered = _test_manifests(root)
    assert discovered == ("a/suite/s3-test.toml", "z/suite/s3-test.toml")

    report = run_project_tests(root, compiler=CompilerKind.PYTHON)
    assert report["manifests"] == list(discovered)
    assert report["summary"]["status"] == "PASS"
    assert _stable_test_results(report) == [
        ("a_smoke", "PASS", "PASS", 11),
        ("z_smoke", "PASS", "PASS", 7),
    ]

    filtered = run_project_tests(
        root, name_pattern="a_*", compiler=CompilerKind.PYTHON
    )
    assert filtered["manifests"] == ["a/suite/s3-test.toml"]
    assert _stable_test_results(filtered) == [("a_smoke", "PASS", "PASS", 11)]


def test_project_test_manifests_match_explicit_native_hosted_provider(
    tmp_path: Path,
) -> None:
    executable = _native_executable()
    root = tmp_path / "checks"
    discovered = _test_manifests(root)

    reference = run_project_tests(root, compiler=CompilerKind.PYTHON)
    native = run_project_tests(
        root,
        compiler=CompilerKind.S3C_NG,
        executable=executable,
    )
    assert reference["manifests"] == native["manifests"] == list(discovered)
    assert reference["summary"] == native["summary"]
    assert reference["summary"]["status"] == "PASS"
    assert _stable_test_results(reference) == _stable_test_results(native)

    filtered_reference = run_project_tests(
        root, name_pattern="a_*", compiler=CompilerKind.PYTHON
    )
    filtered_native = run_project_tests(
        root,
        name_pattern="a_*",
        compiler=CompilerKind.S3C_NG,
        executable=executable,
    )
    assert filtered_reference["manifests"] == filtered_native["manifests"] == [
        "a/suite/s3-test.toml"
    ]
    assert filtered_reference["summary"] == filtered_native["summary"]
    assert _stable_test_results(filtered_reference) == _stable_test_results(
        filtered_native
    )


def test_project_tooling_source_discovery_is_stable_across_creation_order(
    tmp_path: Path,
) -> None:
    first = _project(tmp_path / "first")
    second = tmp_path / "second"
    (second / "ignored").mkdir(parents=True)
    (second / "shared").mkdir()
    (second / "src").mkdir()
    (second / "ignored" / "not_in_manifest.s3").write_text(
        "module ignored\nfn unused() -> i64:\n    return 999\n",
        encoding="utf-8",
        newline="\n",
    )
    (second / "src" / "main.s3").write_text(
        _MAIN_SOURCE, encoding="utf-8", newline="\n"
    )
    (second / "shared" / "mathlib.s3").write_text(
        _LIBRARY_SOURCE, encoding="utf-8", newline="\n"
    )
    (second / "s3.toml").write_text(
        (first / "s3.toml").read_text(encoding="utf-8"),
        encoding="utf-8",
        newline="\n",
    )

    first_tooling = ProjectTooling(first, compiler=CompilerKind.PYTHON)
    second_tooling = ProjectTooling(second, compiler=CompilerKind.PYTHON)
    assert first_tooling.inspect()["sources"] == second_tooling.inspect()["sources"] == (
        "shared/mathlib.s3",
        "src/main.s3",
    )
    assert serialize_ir(first_tooling.build().ir) == serialize_ir(
        second_tooling.build().ir
    )
