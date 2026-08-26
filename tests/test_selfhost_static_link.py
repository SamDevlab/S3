from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import tools.selfhost_static_link as static_link


pytestmark = pytest.mark.s3_fast


def test_static_link_recipe_includes_freestanding_deterministic_flags(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    commands: list[list[str]] = []

    def fake_run(command: list[str], *, cwd: Path, input_bytes=None, env=None):
        del cwd, input_bytes, env
        commands.append(command)
        # Simulate assembler output so the link command has a plausible path.
        if "-c" in command:
            output = Path(command[command.index("-o") + 1])
            output.write_bytes(b"object")
        else:
            output = Path(command[command.index("-o") + 1])
            output.write_bytes(b"elf")
        return subprocess.CompletedProcess(command, 0, stdout=b"", stderr=b"")

    monkeypatch.setattr(static_link, "_run", fake_run)
    monkeypatch.setattr(static_link, "_require_ok", lambda completed, label: None)
    host = tmp_path / "host.o"
    host.write_bytes(b"host")
    output = static_link.assemble_link_static(
        b"assembly",
        cc="cc",
        host_object=host,
        directory=tmp_path / "build",
        output_name="program",
    )
    assert output.is_file()
    assert len(commands) == 2
    link = commands[1]
    for flag in ("-static", "-nostdlib", "-no-pie", "-s", "-Wl,--build-id=none"):
        assert flag in link
    assert link.index("-static") < link.index(str(host))
    assert static_link.STATIC_LINK_FLAGS == (
        "-static",
        "-nostdlib",
        "-no-pie",
        "-s",
        "-Wl,--build-id=none",
    )
