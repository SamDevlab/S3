from __future__ import annotations

import json
import shutil
import subprocess
import zipfile
from pathlib import Path

from ecosystem.editors.vscode_s3.package_vsix import package_vsix


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
EXTENSION_ROOT = REPOSITORY_ROOT / "ecosystem" / "editors" / "vscode-s3"


def test_extension_assets_are_valid_json_and_package_without_external_runtime_dependencies(tmp_path: Path) -> None:
    package = json.loads((EXTENSION_ROOT / "package.json").read_text(encoding="utf-8"))
    grammar = json.loads((EXTENSION_ROOT / "syntaxes" / "s3.tmLanguage.json").read_text(encoding="utf-8"))
    assert ".s3" in package["contributes"]["languages"][0]["extensions"]
    assert grammar["scopeName"] == "source.s3"
    assert not package.get("dependencies")

    archive_path = package_vsix(tmp_path / "s3-language.vsix")
    with zipfile.ZipFile(archive_path) as archive:
        names = set(archive.namelist())
        assert "[Content_Types].xml" in names
        assert "extension.vsixmanifest" in names
        assert "extension/package.json" in names
        assert "extension/extension.js" in names
        assert "extension/client.js" in names
        assert not any("node_modules" in name for name in names)


def test_real_stdio_client_and_server_protocol_and_javascript_syntax() -> None:
    node = shutil.which("node")
    if node is None:
        import pytest

        pytest.skip("Node.js is not installed")
    tests = subprocess.run(
        [node, "--test", str(EXTENSION_ROOT / "client.test.js")],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert tests.returncode == 0, tests.stdout + tests.stderr
    for filename in ("client.js", "positions.js", "extension.js", "client.test.js"):
        checked = subprocess.run(
            [node, "--check", str(EXTENSION_ROOT / filename)],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        assert checked.returncode == 0, checked.stdout + checked.stderr
