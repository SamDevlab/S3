from __future__ import annotations

from pathlib import Path

from bootstrap.s3.cli import main


def test_cli_exposes_format_docs_check_and_execute_paths(tmp_path: Path, capsys) -> None:
    source = tmp_path / "main.s3"
    source.write_text("fn main() -> i64:  \n    return 0  \n", encoding="utf-8")
    assert main(["format", str(source)]) == 0
    assert "return 0\n" in capsys.readouterr().out
    assert main(["check", str(source)]) == 0
    assert "status: ok" in capsys.readouterr().out
    assert main(["docs", str(source), "--json"]) == 0
    assert '"schema": "s3-api-documentation"' in capsys.readouterr().out
    assert main(["run", str(source)]) == 0
    assert "program returned: 0" in capsys.readouterr().out
