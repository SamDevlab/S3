import json
import subprocess
import sys
from pathlib import Path

import pytest


def run_cli(*args: str | Path, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "bootstrap.s3.cli", *(str(a) for a in args)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=cwd,
    )


def test_cli_source_syntax_default_v0_6(tmp_path: Path) -> None:
    source = tmp_path / "test.s3"
    source.write_text("fn main() -> tryte:\n    return 2\n", encoding="utf-8")

    result = run_cli("run", source)
    assert result.returncode == 0
    assert "program returned: 2" in result.stdout


def test_cli_source_syntax_explicit_v0_5(tmp_path: Path) -> None:
    source = tmp_path / "test.s3"
    source.write_text("fn main() -> tryte {\n    return 1;\n}\n", encoding="utf-8")

    result = run_cli("--source-syntax", "0.5", "run", source)
    assert result.returncode == 0
    assert "program returned: 1" in result.stdout


def test_cli_source_syntax_explicit_v0_6(tmp_path: Path) -> None:
    source = tmp_path / "test.s3"
    source.write_text("fn main() -> tryte:\n    return 2\n", encoding="utf-8")

    result = run_cli("--source-syntax", "0.6", "run", source)
    assert result.returncode == 0
    assert "program returned: 2" in result.stdout


def test_cli_source_syntax_help_reports_v0_6_default() -> None:
    result = run_cli("--help")
    assert result.returncode == 0
    assert "Source syntax version (default: 0.6)" in result.stdout
    assert result.stderr == ""


def test_cli_source_syntax_invalid_value(tmp_path: Path) -> None:
    source = tmp_path / "test.s3"
    source.write_text("fn main() -> tryte:\n    return 2\n", encoding="utf-8")

    result = run_cli("--source-syntax", "0.7", "run", source)
    assert result.returncode == 2
    assert "invalid choice: '0.7'" in result.stderr


def test_cli_source_syntax_missing_value(tmp_path: Path) -> None:
    source = tmp_path / "test.s3"
    source.write_text("fn main() -> tryte:\n    return 2\n", encoding="utf-8")

    result = run_cli("--source-syntax", "run", source)
    assert result.returncode == 2
    assert "invalid choice: 'run'" in result.stderr


def test_cli_source_syntax_position_before_command(tmp_path: Path) -> None:
    source = tmp_path / "test.s3"
    source.write_text("fn main() -> tryte:\n    return 3\n", encoding="utf-8")

    result = run_cli("--source-syntax", "0.6", "run", source)
    assert result.returncode == 0
    assert "program returned: 3" in result.stdout


def test_cli_source_syntax_position_after_command(tmp_path: Path) -> None:
    source = tmp_path / "test.s3"
    source.write_text("fn main() -> tryte:\n    return 3\n", encoding="utf-8")

    result = run_cli("run", "--source-syntax", "0.6", source)
    assert result.returncode == 0
    assert "program returned: 3" in result.stdout


@pytest.mark.parametrize("source_code, expected_output", [
    ("fn main() -> tryte:\n    return 4\n", "4"),
    ("fn foo() -> tryte:\n    return 5\nfn main() -> tryte:\n    return foo()\n", "5"),
    ("fn main() -> tryte:\n    value: tryte = 6\n    return value\n", "6"),
    ("fn main() -> tryte:\n    mut value: tryte = 7\n    value = 8\n    return value\n", "8"),
    ("fn main() -> tryte:\n    match 0:\n        0:\n            return 9\n        1:\n            return 0\n        -1:\n            return 0\n", "9"),
    ("fn main() -> tryte:\n    values: tryte[3] = [1, 2, 3]\n    return values[1]\n", "2"),
    ("fn main() -> tryte:\n    mut values: tryte[3] = [1, 2, 3]\n    values[1] = 4\n    return values[1]\n", "4"),
    ("fn sum(n: trit) -> tryte:\n    match n:\n        0:\n            return 0\n        1:\n            return sum(0) + 1\n        -1:\n            return 0\nfn main() -> tryte:\n    return sum(1)\n", "1"),
])
def test_cli_v0_6_features(tmp_path: Path, source_code: str, expected_output: str) -> None:
    source = tmp_path / "test.s3"
    source.write_text(source_code, encoding="utf-8")

    result = run_cli("--source-syntax", "0.6", "run", source)
    assert result.returncode == 0
    assert f"program returned: {expected_output}" in result.stdout


def test_cli_v0_6_ir_emission(tmp_path: Path) -> None:
    source = tmp_path / "test.s3"
    source.write_text("fn main() -> tryte:\n    return 1\n", encoding="utf-8")

    result = run_cli("--source-syntax", "0.6", "ir", source)
    assert result.returncode == 0
    assert '"name": "main"' in result.stdout


def test_cli_v0_6_asm_emission(tmp_path: Path) -> None:
    source = tmp_path / "test.s3"
    source.write_text("fn main() -> tryte:\n    return 1\n", encoding="utf-8")

    result = run_cli("--source-syntax", "0.6", "asm", source)
    assert result.returncode == 0
    assert ".function main" in result.stdout


def test_cli_artifact_parity(tmp_path: Path) -> None:
    import re
    source_5 = tmp_path / "test5.s3"
    source_5.write_text("fn main() -> tryte {\n    tryte[3] a = [1, 2, 3];\n    return a[1];\n}\n", encoding="utf-8")

    source_6 = tmp_path / "test6.s3"
    source_6.write_text("fn main() -> tryte:\n    a: tryte[3] = [1, 2, 3]\n    return a[1]\n", encoding="utf-8")

    # AST parity
    ast5 = run_cli("--source-syntax", "0.5", "ast", source_5).stdout
    ast6 = run_cli("--source-syntax", "0.6", "ast", source_6).stdout

    def normalize_ast(ast_json: str) -> str:
        # Remove location entries
        ast_json = re.sub(r'"line": \d+,', '', ast_json)
        ast_json = re.sub(r'"column": \d+', '', ast_json)
        ast_json = re.sub(r'"offset": \d+', '', ast_json)
        # Remove empty location objects that might be left over if needed, though they don't break JSON structure for basic string compare if done right.
        # Actually better to parse JSON and delete recursively
        return ast_json

    import json
    def remove_loc(obj: object) -> object:
        if isinstance(obj, dict):
            obj.pop("line", None)
            obj.pop("column", None)
            obj.pop("offset", None)
            obj.pop("location", None)
            for k, v in list(obj.items()):
                obj[k] = remove_loc(v)
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                obj[i] = remove_loc(v)
        return obj

    dict5 = remove_loc(json.loads(ast5))
    dict6 = remove_loc(json.loads(ast6))
    assert dict5 == dict6

    # IR parity
    ir5 = json.loads(run_cli("--source-syntax", "0.5", "ir-json", source_5).stdout)
    ir6 = json.loads(run_cli("--source-syntax", "0.6", "ir-json", source_6).stdout)
    assert remove_loc(ir5) == remove_loc(ir6)

    # ASM parity
    asm5 = run_cli("--source-syntax", "0.5", "asm", source_5).stdout
    asm6 = run_cli("--source-syntax", "0.6", "asm", source_6).stdout

    def normalize_asm(asm_text: str) -> str:
        return re.sub(r'source=\d+:\d+:\d+', 'source=X', asm_text)

    assert normalize_asm(asm5) == normalize_asm(asm6)

    # Run parity
    run5 = run_cli("--source-syntax", "0.5", "run", source_5)
    run6 = run_cli("--source-syntax", "0.6", "run", source_6)
    assert run5.returncode == run6.returncode
    assert run5.stdout == run6.stdout
    assert run5.stderr == run6.stderr


def test_cli_v0_5_source_in_v0_6_mode(tmp_path: Path) -> None:
    source = tmp_path / "test.s3"
    source.write_text("fn main() -> tryte {\n    return 1;\n}\n", encoding="utf-8")

    result = run_cli("run", source)
    assert result.returncode == 1
    assert "error: obsolete brace syntax" in result.stderr


def test_cli_v0_6_source_in_v0_5_mode(tmp_path: Path) -> None:
    source = tmp_path / "test.s3"
    source.write_text("fn main() -> tryte:\n    return 1\n", encoding="utf-8")

    result = run_cli("--source-syntax", "0.5", "run", source)
    assert result.returncode == 1
    assert "expected '{'" in result.stderr


def test_cli_diagnostic_text(tmp_path: Path) -> None:
    source = tmp_path / "test.s3"
    source.write_text("fn main() -> tryte:\n    return\n", encoding="utf-8")

    result = run_cli("--source-syntax", "0.6", "--diagnostic-format", "text", "run", source)
    assert result.returncode == 1
    assert "expected expression" in result.stderr


def test_cli_diagnostic_json(tmp_path: Path) -> None:
    source = tmp_path / "test.s3"
    source.write_text("fn main() -> tryte:\n    return\n", encoding="utf-8")

    result = run_cli("--source-syntax", "0.6", "--diagnostic-format", "json", "run", source)
    assert result.returncode == 1
    diagnostic = json.loads(result.stderr)
    assert diagnostic["code"] == "S3E_PARSE_SYNTAX"


def test_cli_diagnostic_json_and_debug(tmp_path: Path) -> None:
    source = tmp_path / "test.s3"
    source.write_text("fn main() -> tryte:\n    return\n", encoding="utf-8")

    result = run_cli("--source-syntax", "0.6", "--diagnostic-format", "json", "--debug", "run", source)
    assert result.returncode == 2
    diagnostic = json.loads(result.stderr)
    assert "--debug cannot be combined with --diagnostic-format json" in diagnostic["message"]


def test_cli_path_with_spaces(tmp_path: Path) -> None:
    source_dir = tmp_path / "my folder"
    source_dir.mkdir()
    source = source_dir / "test space.s3"
    source.write_text("fn main() -> tryte:\n    return 1\n", encoding="utf-8")

    result = run_cli("--source-syntax", "0.6", "run", source)
    assert result.returncode == 0
    assert "program returned: 1" in result.stdout


def test_cli_utf8_source(tmp_path: Path) -> None:
    source = tmp_path / "test_utf8.s3"
    source.write_text("fn main() -> tryte:\n    # comentário com acentuação çãó\n    return 1\n", encoding="utf-8")

    result = run_cli("--source-syntax", "0.6", "run", source)
    assert result.returncode == 0
    assert "program returned: 1" in result.stdout


def test_cli_crlf_source(tmp_path: Path) -> None:
    source = tmp_path / "test_crlf.s3"
    source.write_bytes(b"fn main() -> tryte:\r\n    return 1\r\n")

    result = run_cli("--source-syntax", "0.6", "run", source)
    assert result.returncode == 0
    assert "program returned: 1" in result.stdout


def test_cli_missing_final_newline(tmp_path: Path) -> None:
    source = tmp_path / "test_no_nl.s3"
    source.write_bytes(b"fn main() -> tryte:\n    return 1")

    result = run_cli("--source-syntax", "0.6", "run", source)
    assert result.returncode == 0
    assert "program returned: 1" in result.stdout


def test_cli_io_error(tmp_path: Path) -> None:
    source = tmp_path / "does_not_exist.s3"
    result = run_cli("--source-syntax", "0.6", "run", source)
    assert result.returncode == 1
    assert "error:" in result.stderr


def test_cli_verify_ir_ignores_source_syntax(tmp_path: Path) -> None:
    source_5 = tmp_path / "test5.s3"
    source_5.write_text("fn main() -> tryte {\n    return 6;\n}\n", encoding="utf-8")
    ir_path = tmp_path / "test5.s3ir.json"

    # Generate IR
    result_ir = run_cli("--source-syntax", "0.5", "ir-json", source_5, "-o", ir_path)
    assert result_ir.returncode == 0

    # Verify IR with V0.6 syntax mode (should be ignored, verify-ir only consumes JSON and IR is always 0.5.0)
    result_verify = run_cli("--source-syntax", "0.6", "verify-ir", ir_path)
    assert result_verify.returncode == 0
    assert "IR verified:" in result_verify.stdout


def test_source_syntax_modes_exhaustive() -> None:
    from bootstrap.s3.cli import _SOURCE_SYNTAX_MODES
    from bootstrap.s3.pipeline import SyntaxMode

    assert _SOURCE_SYNTAX_MODES["0.5"] == SyntaxMode.V0_5
    assert _SOURCE_SYNTAX_MODES["0.6"] == SyntaxMode.V0_6

    with pytest.raises(KeyError):
        _ = _SOURCE_SYNTAX_MODES["invalid"]


