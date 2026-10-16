from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from bootstrap.s3.developer_experience import init_project


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "ecosystem.devtools", *args],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )


def test_cli_shows_actual_pinned_compiler_commands_and_machine_diagnostics(tmp_path: Path) -> None:
    commands = _run("commands")
    assert commands.returncode == 0
    for command in ("check", "run", "build", "format", "docs", "test"):
        assert command in commands.stdout

    source = tmp_path / "invalid.s3"
    source.write_text("fn main() -> i64:\n    return missing(1)\n", encoding="utf-8")
    checked = _run("source", "check", str(source))
    diagnostic = json.loads(checked.stdout)
    assert checked.returncode == 1
    assert diagnostic["status"] == "ERROR"
    assert diagnostic["category"] == "semantic"
    assert diagnostic["code"].startswith("S3E_")
    assert diagnostic["line"] == 2
    assert "missing" in diagnostic["excerpt"]


def test_project_inspection_compile_and_explicit_hosted_run(tmp_path: Path) -> None:
    project = tmp_path / "sample"
    init_project(project, "sample")
    (project / "src" / "main.s3").write_text(
        "module main\nfn main() -> i64:\n    return 42\n", encoding="utf-8"
    )
    inspect = _run("project", "inspect", str(project))
    assert inspect.returncode == 0
    assert json.loads(inspect.stdout)["sources"] == ["src/main.s3"]
    build = _run("project", "build", str(project))
    assert build.returncode == 0
    assert json.loads(build.stdout)["execution_mode"] == "COMPILE_ONLY"
    run = _run("project", "run", str(project))
    assert run.returncode == 0
    report = json.loads(run.stdout)
    assert report["execution_mode"] == "HOSTED_EXECUTION"
    assert report["actual_output"] == 42
