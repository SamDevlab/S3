from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import bootstrap.s3.cli as cli
from bootstrap.s3.compiler_provider import CompilerKind
import bootstrap.s3.native_compiler as native_compiler
from bootstrap.s3.native_compiler import inspect_s3c_ng_executable


SOURCE_TEXT = "fn main() -> i64:\n    return 7\n"


def _write_source(path: Path) -> Path:
    path.write_text(SOURCE_TEXT, encoding="utf-8")
    return path


def _candidate_or_skip() -> Path:
    availability = inspect_s3c_ng_executable()
    if not availability.available:
        pytest.skip(
            "S3C-NG CLI comparison skipped: "
            f"{availability.reason or 'candidate unavailable'}"
        )
    return availability.executable


def _provider_args(
    command: str,
    source: Path,
    compiler: CompilerKind,
    executable: Path | None,
    *extra: str,
) -> list[str]:
    args = [command, str(source), "--compiler", compiler.value]
    if executable is not None:
        args.extend(("--s3c-ng-executable", str(executable)))
    args.extend(extra)
    return args


@pytest.mark.parametrize(
    ("command", "extra", "expected"),
    (
        ("check", (), "status: ok"),
        ("ir", (), '"module"'),
        ("asm", (), ".s3asm "),
        ("native-asm", (), ".intel_syntax noprefix"),
        ("run", (), "program returned: 7"),
        ("inspect", (), "S3 inspect"),
        ("inspect", ("--emit", "ir"), '"module"'),
        ("inspect", ("--emit", "assembly"), ".s3asm "),
    ),
)
def test_python_provider_cli_compile_workflows(
    command: str,
    extra: tuple[str, ...],
    expected: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = _write_source(tmp_path / "program.s3")

    assert cli.main(_provider_args(command, source, CompilerKind.PYTHON, None, *extra)) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert expected in captured.out


def test_python_provider_ir_json_writes_the_compiled_module(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = _write_source(tmp_path / "program.s3")
    output = tmp_path / "out" / "program.ir.json"

    assert cli.main(
        _provider_args(
            "ir-json", source, CompilerKind.PYTHON, None, "--output", str(output)
        )
    ) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["module"]["functions"][0]["name"] == "main"


class _RecordingToolchain:
    def __init__(self) -> None:
        self.assemblies: list[str] = []
        self.executables: list[Path] = []

    def build(
        self,
        assembly: str,
        output: Path,
        *,
        keep_assembly: Path | None = None,
    ) -> Path:
        del keep_assembly
        self.assemblies.append(assembly)
        return output

    def run(self, executable: Path) -> subprocess.CompletedProcess[str]:
        self.executables.append(executable)
        return subprocess.CompletedProcess([str(executable)], 0, "native result: 7\n", "")


@pytest.mark.parametrize("command", ("build", "run-native"))
def test_python_provider_native_workflows_keep_real_compile_and_codegen(
    command: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _write_source(tmp_path / "program.s3")
    toolchain = _RecordingToolchain()
    monkeypatch.setattr(
        cli.NativeToolchain,
        "detect",
        classmethod(lambda cls: toolchain),
    )

    args = _provider_args(
        command,
        source,
        CompilerKind.PYTHON,
        None,
        "--output",
        str(tmp_path / "program.native"),
    )
    assert cli.main(args) == 0

    captured = capsys.readouterr()
    assert captured.err == ""
    assert len(toolchain.assemblies) == 1
    assert ".intel_syntax noprefix" in toolchain.assemblies[0]
    if command == "run-native":
        assert captured.out == "native result: 7\n"
        assert len(toolchain.executables) == 1
    else:
        assert captured.out == f"{tmp_path / 'program.native'}\n"


@pytest.mark.parametrize(
    ("command", "extra"),
    (
        ("check", ()),
        ("ir", ()),
        ("ir-json", ()),
        ("asm", ()),
        ("run", ()),
        ("native-asm", ()),
        ("inspect", ()),
        ("inspect", ("--emit", "ir")),
        ("inspect", ("--emit", "assembly")),
        ("build", ()),
        ("run-native", ()),
    ),
)
def test_s3c_ng_provider_fails_closed_for_unavailable_candidate(
    command: str,
    extra: tuple[str, ...],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(native_compiler.platform, "system", lambda: "Linux")
    monkeypatch.setattr(native_compiler.platform, "machine", lambda: "x86_64")
    source = _write_source(tmp_path / "program.s3")
    missing = tmp_path / "missing" / "s3c-ng"

    def forbidden(*_args, **_kwargs):
        pytest.fail("explicit S3C-NG selection must not fall back to Python")

    monkeypatch.setattr(cli, "compile_source", forbidden)
    monkeypatch.setattr(cli, "generate_native_assembly", forbidden)
    monkeypatch.setattr(cli.NativeToolchain, "detect", classmethod(forbidden))
    args = _provider_args(
        command,
        source,
        CompilerKind.S3C_NG,
        missing,
        *extra,
    )

    assert cli.main(args) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "S3C-NG" in captured.err
    assert "not found" in captured.err


@pytest.mark.parametrize(
    ("command", "extra"),
    (
        ("check", ()),
        ("ir", ()),
        ("ir-json", ()),
        ("asm", ()),
        ("native-asm", ()),
        ("run", ()),
        ("inspect", ()),
        ("inspect", ("--emit", "ir")),
        ("inspect", ("--emit", "assembly")),
        ("build", ()),
        ("run-native", ()),
    ),
)
def test_s3c_ng_cli_matches_python_provider_workflows_when_candidate_exists(
    command: str,
    extra: tuple[str, ...],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable = _candidate_or_skip()
    source = _write_source(tmp_path / "program.s3")
    toolchains = [_RecordingToolchain(), _RecordingToolchain()]
    active_toolchain = [toolchains[0]]
    if command in {"build", "run-native"}:
        monkeypatch.setattr(
            cli.NativeToolchain,
            "detect",
            classmethod(lambda cls: active_toolchain[0]),
        )

    python_args = _provider_args(command, source, CompilerKind.PYTHON, None, *extra)
    ng_args = _provider_args(
        command,
        source,
        CompilerKind.S3C_NG,
        executable,
        *extra,
    )
    python_status = cli.main(python_args)
    python_output = capsys.readouterr()
    if command in {"build", "run-native"}:
        active_toolchain[0] = toolchains[1]
    ng_status = cli.main(ng_args)
    ng_output = capsys.readouterr()

    assert (ng_status, ng_output.out, ng_output.err) == (
        python_status,
        python_output.out,
        python_output.err,
    )
    if command in {"build", "run-native"}:
        assert len(toolchains[0].assemblies) == len(toolchains[1].assemblies) == 1
        assert toolchains[0].assemblies == toolchains[1].assemblies
        if command == "run-native":
            assert len(toolchains[0].executables) == len(toolchains[1].executables) == 1
