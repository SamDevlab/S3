"""Linux x86-64 assembler/linker discovery and subprocess execution."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from ...diagnostics import DiagnosticCode
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
                "no GNU assembly driver found; install cc, gcc, or clang",
                diagnostic_code=DiagnosticCode.TOOLCHAIN_NOT_FOUND,
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

    def build_shared(
        self,
        assembly: str,
        output: Path,
        *,
        extra_objects: tuple[Path, ...] = (),
        keep_assembly: Path | None = None,
    ) -> Path:
        """Assemble and link a real Linux shared object for FFI clients."""

        output = output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="s3-ffi-") as temporary:
            source_path = Path(temporary) / "program.s"
            source_path.write_text(assembly, encoding="utf-8", newline="\n")
            object_path = Path(temporary) / "program.o"
            self._compile_assembly(source_path, object_path)
            command = [self.compiler, "-shared", "-nostdlib", "-Wl,--build-id=none", str(object_path)]
            command.extend(str(path.resolve()) for path in extra_objects)
            command.extend(("-o", str(output)))
            self._run_command(command, cwd=Path(temporary))
        if keep_assembly is not None:
            keep_assembly.parent.mkdir(parents=True, exist_ok=True)
            keep_assembly.write_text(assembly, encoding="utf-8", newline="\n")
        if not output.is_file():
            raise NativeToolchainError("shared linker reported success without an output file")
        return output

    def _compile_assembly(self, source: Path, object_path: Path) -> None:
        self._run_command(
            [self.compiler, "-x", "assembler", "-c", str(source), "-o", str(object_path)],
            cwd=source.parent,
        )

    def _run_command(self, command: list[str], *, cwd: Path) -> None:
        try:
            completed = subprocess.run(command, cwd=str(cwd), check=False, capture_output=True, text=True, shell=False, timeout=30.0)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise NativeToolchainError(f"native toolchain command failed: {error}") from error
        if completed.returncode != 0:
            details = completed.stderr.strip() or completed.stdout.strip()
            raise NativeToolchainError(f"native toolchain failed with status {completed.returncode}: {details}")

    def _invoke(self, source: Path, output: Path, *, timeout: float = 30.0) -> None:
        obj_name = source.with_suffix(".o").name
        
        compile_command = [
            self.compiler,
            "-x",
            "assembler",
            "-c",
            source.name,
            "-o",
            obj_name,
        ]
        
        link_command = [
            self.compiler,
            "-nostdlib",
            "-no-pie",
            "-Wl,--build-id=none",
            obj_name,
            "-o",
            str(output),
        ]
        
        for command in (compile_command, link_command):
            try:
                completed = subprocess.run(
                    command,
                    cwd=str(source.parent),
                    check=False,
                    capture_output=True,
                    text=True,
                    shell=False,
                    timeout=timeout,
                )
            except subprocess.TimeoutExpired as error:
                raise NativeToolchainError(
                    f"native toolchain '{self.compiler}' timed out after {timeout}s"
                ) from error
            except OSError as error:
                raise NativeToolchainError(
                    f"could not start native toolchain '{self.compiler}': {error}"
                ) from error
            if completed.returncode != 0:
                details = completed.stderr.strip() or completed.stdout.strip()
                raise NativeToolchainError(
                    f"native assembler/linker failed with status "
                    f"{completed.returncode}: {details}",
                    diagnostic_context={
                        "exit_code": completed.returncode,
                        "notes": (details,) if details else (),
                    },
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
        timeout: float = 30.0,
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
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as error:
            raise NativeToolchainError(
                f"native executable timed out after {timeout}s: '{executable}'"
            ) from error
        except OSError as error:
            raise NativeToolchainError(
                f"could not execute native program '{executable}': {error}"
            ) from error
        if check and completed.returncode != 0:
            details = completed.stderr.strip() or completed.stdout.strip()
            raise NativeToolchainError(
                f"native program exited with status {completed.returncode}: "
                f"{details}",
                diagnostic_context={
                    "exit_code": completed.returncode,
                    "notes": (details,) if details else (),
                },
            )
        return completed

