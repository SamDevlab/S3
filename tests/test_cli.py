from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import bootstrap.s3.cli as cli
from bootstrap.s3.ir_serialization import serialize_ir
from bootstrap.s3.pipeline import compile_source


def _write_source(path: Path, source: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return path


def _json_stderr(capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.count("\n") == 1
    return json.loads(captured.err)


def test_native_policy_is_explicitly_forwarded_by_native_asm_cli(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = _write_source(
        tmp_path / "policy.s3",
        "fn main() -> tryte:\n    return 0\n",
    )
    received: list[object] = []

    def fake_generate(program, **kwargs: object) -> str:
        del program
        received.append(kwargs["native_policy"])
        return ".text\n"

    monkeypatch.setattr(cli, "generate_native_assembly", fake_generate)

    assert cli.main(
        ["native-asm", str(source), "--native-policy", "compact-ea"]
    ) == 0
    assert capsys.readouterr().out == ".text\n"
    assert received == ["compact-ea"]


def test_ffi_build_forwards_explicit_instruction_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = _write_source(
        tmp_path / "ffi-budget.s3",
        "fn main() -> tryte { return 0; }\n",
    )
    received: list[dict[str, object]] = []

    def fake_build_shared_library(_source, output, **kwargs: object) -> Path:
        received.append(kwargs)
        return output

    monkeypatch.setattr(cli, "build_shared_library", fake_build_shared_library)

    assert cli.main(
        [
            "ffi-build",
            str(source),
            "--max-instructions",
            "100000000",
            "-O",
            "1",
            "--source-syntax",
            "0.5",
        ]
    ) == 0
    assert received[0]["max_instructions"] == 100_000_000
    assert received[0]["optimization"] == cli.OptimizationLevel.O1
    assert received[0]["mode"] is cli.SyntaxMode.V0_5
    assert capsys.readouterr().out.endswith("libffi-budget.so\n")


def test_ffi_build_rejects_nonpositive_instruction_limit(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = _write_source(
        tmp_path / "ffi-budget.s3",
        "fn main() -> tryte:\n    return 0\n",
    )

    assert cli.main(
        ["ffi-build", str(source), "--max-instructions", "0"]
    ) == 2
    assert "--max-instructions must be at least 1" in capsys.readouterr().err


def test_text_is_default_and_explicit_text_preserves_the_same_message(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = _write_source(
        tmp_path / "invalid.s3",
        "fn main() -> tryte:\n    return\n",
    )
    assert cli.main(["run", str(source)]) == 1
    default = capsys.readouterr()
    assert default.out == ""
    assert default.err.startswith("error: ")
    assert "parse error: expected expression" in default.err
    assert "Traceback" not in default.err

    assert cli.main(
        ["run", str(source), "--diagnostic-format", "text"]
    ) == 1
    explicit = capsys.readouterr()
    assert explicit == default


def test_expected_io_error_keeps_legacy_text_without_internal_prefix(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "missing.s3"
    assert cli.main(["run", str(source)]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("error: ")
    assert "internal error:" not in captured.err
    assert source.name in captured.err
    assert "Traceback" not in captured.err


def test_parser_json_diagnostic_is_one_object_on_stderr_with_source_and_file(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = _write_source(
        tmp_path / "diretório com espaços" / "fonte inválida.s3",
        "fn main() -> tryte:\n    return\n",
    )
    assert cli.main(
        ["run", str(source), "--diagnostic-format", "json"]
    ) == 1
    payload = _json_stderr(capsys)
    assert payload["schema"] == "s3-diagnostic"
    assert payload["schema_version"] == "1.0.0"
    assert payload["severity"] == "error"
    assert payload["category"] == "syntax"
    assert payload["phase"] == "parsing"
    assert payload["code"] == "S3E_PARSE_SYNTAX"
    assert payload["file"] == str(source)
    assert payload["source"] == {"offset": 30, "line": 2, "column": 11}


def test_lexer_json_diagnostic_has_lexical_code(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = _write_source(tmp_path / "lexical.s3", "fn\n    @\n")
    assert cli.main(
        ["tokens", str(source), "--diagnostic-format", "json"]
    ) == 1
    payload = _json_stderr(capsys)
    assert payload["category"] == "syntax"
    assert payload["phase"] == "lexing"
    assert payload["code"] == "S3E_LEX_INVALID_CHARACTER"
    assert payload["source"] == {"offset": 7, "line": 2, "column": 5}


def test_semantic_json_diagnostic_has_stable_code_and_function(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = _write_source(
        tmp_path / "semantic.s3",
        "fn main() -> tryte:\n    return missing\n",
    )
    assert cli.main(
        ["run", str(source), "--diagnostic-format=json"]
    ) == 1
    payload = _json_stderr(capsys)
    assert payload["category"] == "semantic"
    assert payload["phase"] == "semantic"
    assert payload["code"] == "S3E_SEMANTIC_INVALID_PROGRAM"
    assert payload["function"] == "main"
    assert payload["source"] == {"offset": 31, "line": 2, "column": 12}


def test_verifier_json_diagnostic_keeps_ir_context(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    artifact = json.loads(
        serialize_ir(compile_source("fn main() -> tryte:\n    return 0\n").ir)
    )
    artifact["module"]["functions"][0]["return_type"] = "trit"
    path = tmp_path / "invalid.s3ir.json"
    path.write_text(json.dumps(artifact), encoding="utf-8")
    assert cli.main(
        ["verify-ir", str(path), "--diagnostic-format", "json"]
    ) == 1
    payload = _json_stderr(capsys)
    assert payload["category"] == "verification"
    assert payload["phase"] == "verification"
    assert payload["code"] == "S3E_VERIFY_INVALID_IR"
    assert payload["function"] == "main"
    assert payload["block"] == "entry"
    assert payload["opcode"] == "return"


def test_artifact_json_and_version_errors_have_distinct_codes(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    malformed = tmp_path / "malformed.json"
    malformed.write_text('{\n  "format":', encoding="utf-8")
    assert cli.main(
        ["verify-ir", str(malformed), "--diagnostic-format", "json"]
    ) == 1
    invalid_json = _json_stderr(capsys)
    assert invalid_json["category"] == "artifact"
    assert invalid_json["code"] == "S3E_ARTIFACT_INVALID_JSON"
    assert invalid_json["source"] == {
        "offset": 13,
        "line": 2,
        "column": 12,
    }

    future = tmp_path / "future.json"
    future.write_text(
        '{"format":"s3-ir","version":"0.7.0","module":{"functions":[]}}',
        encoding="utf-8",
    )
    assert cli.main(
        ["verify-ir", str(future), "--diagnostic-format", "json"]
    ) == 1
    version = _json_stderr(capsys)
    assert version["category"] == "version"
    assert version["code"] == "S3E_ARTIFACT_UNSUPPORTED_VERSION"
    assert "source" not in version


def test_json_mode_preserves_normal_stdout_on_success(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = _write_source(
        tmp_path / "success.s3",
        "fn main() -> tryte:\n    return 6\n",
    )
    assert cli.main(
        ["run", str(source), "--diagnostic-format", "json"]
    ) == 0
    captured = capsys.readouterr()
    assert captured.out == "program returned: 6\n"
    assert captured.err == ""


@pytest.mark.parametrize(
    ("name", "source_text", "extra_args", "category", "code"),
    (
        (
            "overflow",
            """\
fn increment(value: tryte) -> tryte:
    return value + 1
fn main() -> tryte:
    return increment(364)
""",
            (),
            "overflow",
            "S3E_RUNTIME_OVERFLOW",
        ),
        (
            "bounds",
            """\
fn read(index: tryte) -> tryte:
    values: tryte[1] = [1]
    return values[index]
fn main() -> tryte:
    return read(-1)
""",
            (),
            "bounds",
            "S3E_RUNTIME_BOUNDS",
        ),
        (
            "frame",
            """\
fn recurse() -> tryte:
    return recurse()
fn main() -> tryte:
    return recurse()
""",
            ("--max-frames", "2"),
            "frame-limit",
            "S3E_RUNTIME_FRAME_LIMIT",
        ),
    ),
)
def test_runtime_failures_flow_through_the_cli_schema(
    name: str,
    source_text: str,
    extra_args: tuple[str, ...],
    category: str,
    code: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = _write_source(tmp_path / f"{name}.s3", source_text)
    assert cli.main(
        [
            "run",
            str(source),
            *extra_args,
            "--diagnostic-format",
            "json",
        ]
    ) == 1
    payload = _json_stderr(capsys)
    assert payload["category"] == category
    assert payload["code"] == code
    assert payload["phase"] == "emulation"
    assert payload["file"] == str(source)


def test_constant_overflow_flows_through_cli_schema_before_backend(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = _write_source(
        tmp_path / "constant-overflow.s3",
        "fn main() -> tryte:\n    return 364 + 1\n",
    )

    for command in ("check", "inspect", "run"):
        assert cli.main(
            [
                command,
                str(source),
                "--diagnostic-format",
                "json",
            ]
        ) == 1
        payload = _json_stderr(capsys)
        assert payload["category"] == "semantic"
        assert payload["phase"] == "semantic"
        assert payload["code"] == "S3E_SEMANTIC_INVALID_PROGRAM"
        assert payload["message"] == "tryte overflow: 364 + 1 = 365"
        assert payload["function"] == "main"
        assert payload["file"] == str(source)
        assert payload["source"] == {"offset": 35, "line": 2, "column": 16}


def test_json_mode_covers_cli_usage_without_mixing_argparse_text(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert cli.main(
        ["unknown", "source.s3", "--diagnostic-format", "json"]
    ) == 2
    payload = _json_stderr(capsys)
    assert payload["category"] == "syntax"
    assert payload["phase"] == "cli"
    assert payload["code"] == "S3E_CLI_USAGE"
    assert "usage:" not in payload["message"]


@pytest.mark.parametrize(
    "arguments",
    (
        ("--diagnostic-format", "json", "run"),
        (
            "--diagnostic-format",
            "json",
            "run",
            "source.s3",
            "--unknown-option",
        ),
    ),
)
def test_json_mode_covers_argparse_errors_when_format_is_known(
    arguments: tuple[str, ...],
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert cli.main(arguments) == 2
    payload = _json_stderr(capsys)
    assert payload["category"] == "syntax"
    assert payload["phase"] == "cli"
    assert payload["code"] == "S3E_CLI_USAGE"
    assert "usage:" not in payload["message"]


def test_invalid_diagnostic_format_remains_a_text_argparse_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert cli.main(
        ["run", "source.s3", "--diagnostic-format", "yaml"]
    ) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("usage: s3 ")
    assert "invalid choice: 'yaml'" in captured.err
    assert "Traceback" not in captured.err


def test_json_option_is_accepted_before_command_and_after_source(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = _write_source(
        tmp_path / "position.s3",
        "fn main() -> tryte:\n    return missing\n",
    )
    payloads = []
    for arguments in (
        ("--diagnostic-format", "json", "run", str(source)),
        ("run", str(source), "--diagnostic-format", "json"),
    ):
        assert cli.main(arguments) == 1
        payloads.append(_json_stderr(capsys))
    assert payloads[0] == payloads[1]


def test_internal_error_is_structured_and_debug_mode_reraises(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _write_source(
        tmp_path / "internal.s3",
        "fn main() -> tryte:\n    return 0\n",
    )

    def fail(
        _source: str,
        _optimization: object,
        *,
        mode: cli.SyntaxMode,
    ) -> object:
        assert mode == cli.SyntaxMode.V0_6
        raise RuntimeError("developer detail")

    monkeypatch.setattr(cli, "compile_source", fail)
    assert cli.main(
        ["run", str(source), "--diagnostic-format", "json"]
    ) == 1
    payload = _json_stderr(capsys)
    assert payload["category"] == "internal"
    assert payload["code"] == "S3E_INTERNAL"
    assert payload["message"] == "developer detail"

    assert cli.main(["run", str(source)]) == 1
    text = capsys.readouterr()
    assert text.out == ""
    assert text.err == "error: internal error: developer detail\n"

    with pytest.raises(RuntimeError, match="developer detail"):
        cli.main(["run", str(source), "--debug"])


def test_json_and_debug_are_rejected_with_one_structured_diagnostic(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = _write_source(
        tmp_path / "debug.s3",
        "fn main() -> tryte:\n    return 0\n",
    )
    assert cli.main(
        [
            "run",
            str(source),
            "--diagnostic-format",
            "json",
            "--debug",
        ]
    ) == 2
    payload = _json_stderr(capsys)
    assert payload["category"] == "syntax"
    assert payload["phase"] == "cli"
    assert payload["code"] == "S3E_CLI_USAGE"
    assert payload["message"] == (
        "--debug cannot be combined with --diagnostic-format json"
    )


def test_help_remains_on_stdout(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as captured_exit:
        cli.main(["--help"])
    assert captured_exit.value.code == 0
    captured = capsys.readouterr()
    assert captured.out.startswith("usage: s3 ")
    assert captured.err == ""


def test_targets_command_lists_internal_architecture_deterministically(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert cli.main(["targets"]) == 0
    first = capsys.readouterr()

    assert first.err == ""
    assert "Targets:\n  linux-x86_64\n" in first.out
    assert "Hosted execution:\n  hosted-emulator\n" in first.out
    assert "Native assembly:\n  linux-x86_64\n" in first.out

    assert cli.main(["targets"]) == 0
    second = capsys.readouterr()
    assert second == first


def test_doctor_command_reports_environment_and_internal_architecture(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert cli.main(["doctor"]) == 0
    captured = capsys.readouterr()

    assert captured.err == ""
    assert captured.out.startswith("S3 doctor\n")
    assert "\nPython:\n" in captured.out
    assert "\n  version: " in captured.out
    assert "\n  executable: " in captured.out
    assert "\nHost:\n" in captured.out
    assert "\n  system: " in captured.out
    assert "\n  machine: " in captured.out
    assert "\nTargets:\n  linux-x86_64\n" in captured.out
    assert "\nHosted execution:\n  hosted-emulator\n" in captured.out
    assert "\nNative assembly:\n  linux-x86_64\n" in captured.out
    assert "\nNative toolchain:\n" in captured.out
    assert "\n  available: " in captured.out


def test_inspect_command_reports_compilation_summary_without_running(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = _write_source(
        tmp_path / "valid.s3",
        "fn main() -> tryte:\n    return 364\n",
    )

    assert cli.main(["inspect", str(source)]) == 0
    captured = capsys.readouterr()

    assert captured.err == ""
    assert captured.out.startswith("S3 inspect\n")
    assert f"  path: {source}" in captured.out
    assert "\nCompilation:\n" in captured.out
    assert "\n  syntax: 0.6\n" in captured.out
    assert "\n  optimization: O0\n" in captured.out
    assert "\nProgram:\n" in captured.out
    assert "\n  functions: 1\n" in captured.out
    assert "\n  entry: main\n" in captured.out
    assert "\nIR:\n" in captured.out
    assert "\nAssembly:\n" in captured.out
    assert "\nEmit:\n" not in captured.out
    assert "program returned" not in captured.out


def test_inspect_command_explicit_summary_reports_compilation_summary(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = _write_source(
        tmp_path / "valid.s3",
        "fn main() -> tryte:\n    return 364\n",
    )

    assert cli.main(["inspect", str(source), "--emit", "summary"]) == 0
    captured = capsys.readouterr()

    assert captured.err == ""
    assert captured.out.startswith("S3 inspect\n")
    assert f"  path: {source}" in captured.out
    assert "\nCompilation:\n" in captured.out
    assert "\nIR:\n" in captured.out
    assert "\nAssembly:\n" in captured.out
    assert "\nEmit:\n" not in captured.out
    assert "program returned" not in captured.out


@pytest.mark.parametrize(
    ("emit", "expected_artifact"),
    (
        ("ir", '"module"'),
        ("assembly", ".s3asm "),
    ),
)
def test_inspect_command_emits_requested_artifact_without_running(
    emit: str,
    expected_artifact: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = _write_source(
        tmp_path / "valid.s3",
        "fn main() -> tryte:\n    return 364\n",
    )

    assert cli.main(["inspect", str(source), "--emit", emit]) == 0
    captured = capsys.readouterr()

    assert captured.err == ""
    assert captured.out.startswith("S3 inspect\n")
    assert "\nEmit:\n" in captured.out
    assert f"\n  kind: {emit}\n" in captured.out
    assert expected_artifact in captured.out
    assert "program returned" not in captured.out


def test_check_command_reports_ok_without_running(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = _write_source(
        tmp_path / "valid.s3",
        "fn main() -> tryte:\n    return 364\n",
    )

    assert cli.main(["check", str(source)]) == 0
    captured = capsys.readouterr()

    assert captured.err == ""
    assert captured.out.startswith("S3 check\n")
    assert f"  path: {source}" in captured.out
    assert "  status: ok\n" in captured.out
    assert "program returned" not in captured.out


def test_unsupported_target_and_missing_toolchain_are_distinct(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _write_source(
        tmp_path / "native.s3",
        "fn main() -> tryte:\n    return 0\n",
    )
    monkeypatch.setattr(
        "bootstrap.s3.backends.x86_64.toolchain.platform.system",
        lambda: "Windows",
    )
    monkeypatch.setattr(
        "bootstrap.s3.backends.x86_64.toolchain.platform.machine",
        lambda: "AMD64",
    )
    assert cli.main(
        ["build", str(source), "--diagnostic-format", "json"]
    ) == 1
    target = _json_stderr(capsys)
    assert target["category"] == "unsupported-target"
    assert target["code"] == "S3E_UNSUPPORTED_TARGET"

    monkeypatch.setattr(
        "bootstrap.s3.backends.x86_64.toolchain.platform.system",
        lambda: "Linux",
    )
    monkeypatch.setattr(
        "bootstrap.s3.backends.x86_64.toolchain.platform.machine",
        lambda: "x86_64",
    )
    monkeypatch.setattr(
        "bootstrap.s3.backends.x86_64.toolchain.shutil.which",
        lambda _command: None,
    )
    assert cli.main(
        ["build", str(source), "--diagnostic-format", "json"]
    ) == 1
    toolchain = _json_stderr(capsys)
    assert toolchain["category"] == "toolchain"
    assert toolchain["code"] == "S3E_TOOLCHAIN_NOT_FOUND"


def test_native_runtime_json_is_a_wrapper_not_parsed_elf_diagnostics(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _write_source(
        tmp_path / "native-runtime.s3",
        "fn main() -> tryte:\n    return 0\n",
    )
    native_stderr = (
        "runtime error [bounds] in function 'main'\n"
        "at source unknown (block entry, TLOAD): index -1 outside [0, 1)\n"
    )

    class FakeToolchain:
        def build(
            self,
            _assembly: str,
            output: Path,
            *,
            keep_assembly: Path | None = None,
        ) -> Path:
            del keep_assembly
            return output

        def run(
            self,
            executable: Path,
        ) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(
                [str(executable)],
                1,
                "",
                native_stderr,
            )

    monkeypatch.setattr(
        cli.NativeToolchain,
        "detect",
        classmethod(lambda cls: FakeToolchain()),
    )
    assert cli.main(
        ["run-native", str(source), "--diagnostic-format", "json"]
    ) == 1
    payload = _json_stderr(capsys)
    assert payload["category"] == "native-runtime"
    assert payload["code"] == "S3E_NATIVE_PROCESS_FAILED"
    assert payload["exit_code"] == 1
    assert payload["message"] == "standalone native program exited with status 1"


def test_cli_mode_propagation_default_v0_6(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _write_source(
        tmp_path / "prog.s3",
        "fn main() -> tryte:\n    return 0\n",
    )
    received_modes = []

    def fake_compile(
        _source: str,
        _optimization: object,
        *,
        mode: cli.SyntaxMode,
    ) -> object:
        received_modes.append(mode)
        raise RuntimeError("stop")

    monkeypatch.setattr(cli, "compile_source", fake_compile)

    cli.main(["ir", str(source)])
    assert received_modes == [cli.SyntaxMode.V0_6]


def test_cli_mode_propagation_explicit_v0_5(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _write_source(tmp_path / "prog.s3", "fn main() -> tryte { return 0; }\n")
    received_modes = []

    def fake_compile(
        _source: str,
        _optimization: object,
        *,
        mode: cli.SyntaxMode,
    ) -> object:
        received_modes.append(mode)
        raise RuntimeError("stop")

    monkeypatch.setattr(cli, "compile_source", fake_compile)

    cli.main(["--source-syntax", "0.5", "ast", str(source)])
    assert received_modes == [cli.SyntaxMode.V0_5]


def test_cli_mode_propagation_explicit_v0_6(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _write_source(tmp_path / "prog.s3", "fn main() -> tryte: return 0\n")
    received_modes = []

    def fake_compile(
        _source: str,
        _optimization: object,
        *,
        mode: cli.SyntaxMode,
    ) -> object:
        received_modes.append(mode)
        raise RuntimeError("stop")

    monkeypatch.setattr(cli, "compile_source", fake_compile)

    cli.main(["--source-syntax", "0.6", "build", str(source)])
    assert received_modes == [cli.SyntaxMode.V0_6]


def test_cli_run_command_propagates_mode_to_emulator(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _write_source(tmp_path / "prog.s3", "fn main() -> tryte: return 0\n")
    received_modes = []

    # 'run' uses compile_source then Emulator, we check if compile_source received it.
    def fake_compile(
        _source: str,
        _optimization: object,
        *,
        mode: cli.SyntaxMode,
    ) -> object:
        received_modes.append(mode)
        raise RuntimeError("stop")

    monkeypatch.setattr(cli, "compile_source", fake_compile)

    cli.main(["--source-syntax", "0.6", "run", str(source)])
    assert received_modes == [cli.SyntaxMode.V0_6]
