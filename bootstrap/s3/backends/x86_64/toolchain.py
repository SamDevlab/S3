"""Linux x86-64 assembler/linker discovery and subprocess execution."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .diagnostics import NativePlatformError, NativeToolchainError


@dataclass(frozen=True, slots=True)
class NativeToolchain:
    compiler: str
    assembler: str | None
    linker: str | None

    @classmethod
    def detect(cls) -> NativeToolchain:
        system = platform.system()
        machine = platform.machine().lower()
        if system != "Linux" or machine not in {"x86_64", "amd64"}:
            raise NativePlatformError(
                "native build requires a Linux x86-64 host; "
                f"detected {system} {platform.machine()}"
            )
        compiler = next(
            (
                path
                for command in ("cc", "gcc", "clang")
                if (path := shutil.which(command)) is not None
            ),
            None,
        )
        if compiler is None:
            raise NativeToolchainError(
                "no GNU assembly driver found; install cc, gcc, or clang"
            )
        return cls(compiler, shutil.which("as"), shutil.which("ld"))

    def build(
        self,
        assembly: str,
        output: Path,
        *,
        keep_assembly: Path | None = None,
    ) -> Path:
        output = output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        if keep_assembly is not None:
            source_path = keep_assembly.resolve()
            if source_path == output:
                raise NativeToolchainError(
                    "assembly and executable outputs must be different paths"
                )
            source_path.parent.mkdir(parents=True, exist_ok=True)
            source_path.write_text(assembly, encoding="utf-8", newline="\n")
            self._invoke(source_path, output)
        else:
            with tempfile.TemporaryDirectory(prefix="s3-native-") as temporary:
                source_path = Path(temporary) / "program.s"
                source_path.write_text(assembly, encoding="utf-8", newline="\n")
                self._invoke(source_path, output)
        return output

    def _invoke(self, source: Path, output: Path) -> None:
        command = [
            self.compiler,
            "-x",
            "assembler",
            "-nostdlib",
            "-no-pie",
            "-Wl,--build-id=none",
            str(source),
            "-o",
            str(output),
        ]
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                shell=False,
            )
        except OSError as error:
            raise NativeToolchainError(
                f"could not start native toolchain '{self.compiler}': {error}"
            ) from error
        if completed.returncode != 0:
            details = completed.stderr.strip() or completed.stdout.strip()
            raise NativeToolchainError(
                f"native assembler/linker failed with status "
                f"{completed.returncode}: {details}"
            )
        if not output.is_file():
            raise NativeToolchainError(
                "native assembler/linker reported success without an output file"
            )
        output.chmod(output.stat().st_mode | 0o111)

    def run(
        self,
        executable: Path,
        *,
        check: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        executable = executable.resolve()
        if not executable.is_file():
            raise NativeToolchainError(
                f"native executable does not exist: {executable}"
            )
        try:
            completed = subprocess.run(
                [os.fspath(executable)],
                check=False,
                capture_output=True,
                text=True,
                shell=False,
            )
        except OSError as error:
            raise NativeToolchainError(
                f"could not execute native program '{executable}': {error}"
            ) from error
        if check and completed.returncode != 0:
            details = completed.stderr.strip() or completed.stdout.strip()
            raise NativeToolchainError(
                f"native program exited with status {completed.returncode}: "
                f"{details}"
            )
        return completed

