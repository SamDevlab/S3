from __future__ import annotations

import json
from pathlib import Path

import pytest

import bootstrap.s3.cli as cli
from bootstrap.s3 import ast
from bootstrap.s3.assembly import ASSEMBLY_FORMAT_VERSION
from bootstrap.s3.diagnostics import DiagnosticCode, ParseError
from bootstrap.s3.ir_serialization import IR_FORMAT_VERSION, serialize_ir
from bootstrap.s3.lexer import Lexer, SyntaxMode, TokenKind, tokenize
from bootstrap.s3.parser import Parser, parse, parse_tokens
from bootstrap.s3.pipeline import compile_source, run_source


SOURCE_V0_6 = "fn main() -> tryte:\n    return 6\n"
SOURCE_V0_5 = "fn main() -> tryte {\n    return 6;\n}\n"


def _write_source(path: Path, source: str) -> Path:
    path.write_text(source, encoding="utf-8")
    return path


def test_lexer_defaults_to_v0_6() -> None:
    tokens = Lexer(SOURCE_V0_6).tokenize()
    assert TokenKind.INDENT in {token.kind for token in tokens}
    assert tokens == Lexer(SOURCE_V0_6, mode=SyntaxMode.V0_6).tokenize()


def test_tokenize_defaults_to_v0_6() -> None:
    assert tokenize(SOURCE_V0_6) == tokenize(
        SOURCE_V0_6,
        mode=SyntaxMode.V0_6,
    )


def test_parser_defaults_to_v0_6() -> None:
    tokens = tokenize(SOURCE_V0_6, mode=SyntaxMode.V0_6)
    default = Parser(tokens).parse_program()
    explicit = Parser(tokens, SyntaxMode.V0_6).parse_program()
    assert ast.to_dict(default) == ast.to_dict(explicit)


def test_parse_tokens_defaults_to_v0_6() -> None:
    tokens = tokenize(SOURCE_V0_6, mode=SyntaxMode.V0_6)
    assert ast.to_dict(parse_tokens(tokens)) == ast.to_dict(
        parse_tokens(tokens, mode=SyntaxMode.V0_6)
    )


def test_parse_defaults_to_v0_6() -> None:
    assert ast.to_dict(parse(SOURCE_V0_6)) == ast.to_dict(
        parse(SOURCE_V0_6, mode=SyntaxMode.V0_6)
    )


def test_compile_source_defaults_to_v0_6() -> None:
    default = compile_source(SOURCE_V0_6)
    explicit = compile_source(SOURCE_V0_6, mode=SyntaxMode.V0_6)
    assert default.ast == explicit.ast
    assert default.ir == explicit.ir
    assert default.assembly == explicit.assembly


def test_run_source_defaults_to_v0_6() -> None:
    assert run_source(SOURCE_V0_6) == 6
    assert run_source(SOURCE_V0_6, mode=SyntaxMode.V0_6) == 6


def test_cli_defaults_to_v0_6(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = _write_source(tmp_path / "default.s3", SOURCE_V0_6)
    assert cli.main(["run", str(source)]) == 0
    output = capsys.readouterr()
    assert output.out == "program returned: 6\n"
    assert output.err == ""


@pytest.mark.parametrize(
    ("source", "expected"),
    (
        ("fn main() -> tryte:\n    return 6\n", 6),
        (
            "fn add(a: tryte, b: tryte) -> tryte:\n"
            "    return a + b\n"
            "fn main() -> tryte:\n"
            "    return add(2, 3)\n",
            5,
        ),
        (
            "fn main() -> tryte:\n"
            "    mut value: tryte = 1\n"
            "    value = value + 2\n"
            "    return value\n",
            3,
        ),
        (
            "fn main() -> tryte:\n"
            "    match 0:\n"
            "        -1:\n"
            "            return -1\n"
            "        0:\n"
            "            return 0\n"
            "        1:\n"
            "            return 1\n",
            0,
        ),
        (
            "fn main() -> tryte:\n"
            "    values: tryte[3] = [1, 2, 3]\n"
            "    return values[1]\n",
            2,
        ),
        (
            "fn main() -> tryte:\n"
            "    mut values: tryte[2] = [1, 2]\n"
            "    values[0] = 4\n"
            "    return values[0]\n",
            4,
        ),
        (
            "fn recurse(value: trit) -> tryte:\n"
            "    match value:\n"
            "        -1:\n"
            "            return 0\n"
            "        0:\n"
            "            return 0\n"
            "        1:\n"
            "            return recurse(0) + 1\n"
            "fn main() -> tryte:\n"
            "    return recurse(1)\n",
            1,
        ),
    ),
    ids=(
        "return",
        "call",
        "mutability",
        "match",
        "array",
        "indexed-assignment",
        "recursion",
    ),
)
def test_default_and_explicit_v0_6_have_full_pipeline_parity(
    source: str,
    expected: int,
) -> None:
    default = compile_source(source)
    explicit = compile_source(source, mode=SyntaxMode.V0_6)

    assert ast.to_dict(default.ast) == ast.to_dict(explicit.ast)
    assert default.ir == explicit.ir
    assert default.assembly.render() == explicit.assembly.render()
    assert run_source(source) == expected
    assert run_source(source, mode=SyntaxMode.V0_6) == expected


def test_default_and_explicit_v0_6_have_cli_error_parity(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = _write_source(
        tmp_path / "invalid-v0.6.s3",
        "fn main() -> tryte:\n    return\n",
    )

    default_status = cli.main(
        ["--diagnostic-format", "json", "run", str(source)]
    )
    default_output = capsys.readouterr()
    explicit_status = cli.main(
        [
            "--source-syntax",
            "0.6",
            "--diagnostic-format",
            "json",
            "run",
            str(source),
        ]
    )
    explicit_output = capsys.readouterr()

    assert default_status == explicit_status == 1
    assert default_output == explicit_output
    assert default_output.out == ""
    assert json.loads(default_output.err)["code"] == "S3E_PARSE_SYNTAX"


def test_v0_5_without_mode_is_rejected() -> None:
    with pytest.raises(ParseError) as captured:
        parse(SOURCE_V0_5)
    assert captured.value.diagnostic_code is DiagnosticCode.PARSE_OBSOLETE_BRACE


def test_lexer_explicit_v0_5() -> None:
    tokens = Lexer(SOURCE_V0_5, mode=SyntaxMode.V0_5).tokenize()
    kinds = {token.kind for token in tokens}
    assert TokenKind.LEFT_BRACE in kinds
    assert TokenKind.SEMICOLON in kinds
    assert TokenKind.INDENT not in kinds


def test_parser_explicit_v0_5() -> None:
    tokens = tokenize(SOURCE_V0_5, mode=SyntaxMode.V0_5)
    program = Parser(tokens, SyntaxMode.V0_5).parse_program()
    assert program.functions[0].name == "main"
    assert ast.to_dict(program) == ast.to_dict(
        parse_tokens(tokens, mode=SyntaxMode.V0_5)
    )


def test_pipeline_explicit_v0_5() -> None:
    compilation = compile_source(SOURCE_V0_5, mode=SyntaxMode.V0_5)
    assert compilation.ast.functions[0].name == "main"
    assert run_source(SOURCE_V0_5, mode=SyntaxMode.V0_5) == 6


def test_cli_explicit_v0_5(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = _write_source(tmp_path / "legacy.s3", SOURCE_V0_5)
    assert cli.main(["--source-syntax", "0.5", "run", str(source)]) == 0
    output = capsys.readouterr()
    assert output.out == "program returned: 6\n"
    assert output.err == ""


def test_default_does_not_fallback_to_v0_5(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = _write_source(tmp_path / "no-fallback.s3", SOURCE_V0_5)
    assert cli.main(["run", str(source)]) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "obsolete brace syntax" in output.err
    assert "Traceback" not in output.err


def test_help_reports_v0_6_default(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as captured:
        cli.main(["--help"])
    assert captured.value.code == 0
    output = capsys.readouterr()
    assert "Source syntax version (default: 0.6)" in output.out
    assert output.err == ""


def test_invalid_source_syntax_returns_status_2(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = _write_source(tmp_path / "invalid-option.s3", SOURCE_V0_6)
    assert cli.main(
        ["--source-syntax", "0.7", "run", str(source)]
    ) == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert "invalid choice: '0.7'" in output.err


def test_json_and_debug_remain_incompatible(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = _write_source(tmp_path / "debug.s3", SOURCE_V0_6)
    assert cli.main(
        [
            "--diagnostic-format",
            "json",
            "--debug",
            "run",
            str(source),
        ]
    ) == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert output.err.count("\n") == 1
    diagnostic = json.loads(output.err)
    assert diagnostic["code"] == "S3E_CLI_USAGE"
    assert "cannot be combined" in diagnostic["message"]
    assert "Traceback" not in output.err


@pytest.mark.parametrize(
    "source_args",
    (
        (),
        ("--source-syntax", "0.5"),
        ("--source-syntax", "0.6"),
    ),
    ids=("default", "v0.5", "v0.6"),
)
def test_verify_ir_is_independent_of_source_syntax(
    source_args: tuple[str, ...],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    artifact = tmp_path / "module.s3ir.json"
    artifact.write_text(
        serialize_ir(compile_source(SOURCE_V0_6).ir),
        encoding="utf-8",
    )
    assert cli.main([*source_args, "verify-ir", str(artifact)]) == 0
    output = capsys.readouterr()
    assert output.out == "IR verified: 1 function(s)\n"
    assert output.err == ""


def test_artifact_versions_remain_v0_5() -> None:
    compilation = compile_source(SOURCE_V0_6)
    assert IR_FORMAT_VERSION == "0.6.0"
    assert ASSEMBLY_FORMAT_VERSION == "0.5.0"
    assert json.loads(serialize_ir(compilation.ir))["version"] == "0.6.0"
    assert compilation.assembly.version == "0.5.0"


@pytest.mark.parametrize(
    ("source", "code", "message", "line", "column"),
    (
        (
            "fn main() -> tryte {\n    return 1;\n}\n",
            "S3E_PARSE_OBSOLETE_BRACE",
            "obsolete brace syntax",
            1,
            20,
        ),
        (
            "fn main() -> tryte:\n    return 1;\n",
            "S3E_PARSE_OBSOLETE_SEMICOLON",
            "obsolete ';' syntax",
            2,
            13,
        ),
        (
            "fn main() -> tryte:\n"
            "    switch 0:\n"
            "        -1:\n"
            "            return -1\n",
            "S3E_PARSE_OBSOLETE_SWITCH",
            "obsolete 'switch' syntax, use 'match'",
            2,
            5,
        ),
    ),
    ids=("brace", "semicolon", "switch"),
)
def test_default_reports_structured_migration_diagnostics(
    source: str,
    code: str,
    message: str,
    line: int,
    column: int,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = _write_source(tmp_path / f"{code}.s3", source)

    assert cli.main(["run", str(path)]) == 1
    text = capsys.readouterr()
    assert text.out == ""
    assert f"{line}:{column}: parse error: {message}" in text.err
    assert "Traceback" not in text.err

    assert cli.main(
        ["--diagnostic-format", "json", "run", str(path)]
    ) == 1
    structured = capsys.readouterr()
    assert structured.out == ""
    assert structured.err.count("\n") == 1
    assert "Traceback" not in structured.err
    diagnostic = json.loads(structured.err)
    assert diagnostic["category"] == "syntax"
    assert diagnostic["phase"] == "parsing"
    assert diagnostic["code"] == code
    assert diagnostic["message"] == message
    assert diagnostic["file"] == str(path)
    assert diagnostic["source"]["line"] == line
    assert diagnostic["source"]["column"] == column
