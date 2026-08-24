"""Build the canonical S3 Stage1 compiler with the Python Stage0 boundary."""

from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
from pathlib import Path

from bootstrap.s3.backends.x86_64 import generate_native_assembly
from bootstrap.s3.pipeline import compile_source


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "selfhost" / "compiler" / "s3c_stage1.s3"
DEFAULT_HOST_IO = ROOT / "selfhost" / "compiler" / "stage1_host_io.c"


class Stage1BuildError(RuntimeError):
    """Raised when the real Stage0-to-Stage1 build cannot be completed."""


def _run(command: list[str], *, cwd: Path) -> None:
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        check=False,
        capture_output=True,
        text=True,
        shell=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise Stage1BuildError(
            f"command failed with status {completed.returncode}: {detail}"
        )


def build_stage1(
    output: Path,
    *,
    source: Path = DEFAULT_SOURCE,
    host_io: Path = DEFAULT_HOST_IO,
    assembly_output: Path | None = None,
) -> Path:
    """Compile S3 source with Stage0 and link a freestanding Linux process."""

    if platform.system() != "Linux" or platform.machine().lower() not in {
        "x86_64",
        "amd64",
    }:
        raise Stage1BuildError("Stage1 native execution requires Linux x86-64")
    compiler = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    if compiler is None:
        raise Stage1BuildError("Stage1 native execution requires cc, gcc, or clang")
    source = source.resolve()
    host_io = host_io.resolve()
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    assembly = generate_native_assembly(compile_source(source.read_text(encoding="utf-8")).assembly)
    assembly_path = (assembly_output or output.with_suffix(".s")).resolve()
    assembly_path.parent.mkdir(parents=True, exist_ok=True)
    assembly_path.write_text(assembly, encoding="utf-8", newline="\n")
    stage1_object = output.with_suffix(".stage1.o")
    host_object = output.with_suffix(".host.o")
    _run(
        [compiler, "-x", "assembler", "-c", str(assembly_path), "-o", str(stage1_object)],
        cwd=output.parent,
    )
    _run(
        [
            compiler,
            "-std=c11",
            "-ffreestanding",
            "-fno-builtin",
            "-fno-pie",
            "-fno-stack-protector",
            "-fno-asynchronous-unwind-tables",
            "-c",
            str(host_io),
            "-o",
            str(host_object),
        ],
        cwd=output.parent,
    )
    _run(
        [
            compiler,
            "-nostdlib",
            "-no-pie",
            "-Wl,--build-id=none",
            str(stage1_object),
            str(host_object),
            "-o",
            str(output),
        ],
        cwd=output.parent,
    )
    stage1_object.unlink(missing_ok=True)
    host_object.unlink(missing_ok=True)
    output.chmod(output.stat().st_mode | 0o111)
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--host-io", type=Path, default=DEFAULT_HOST_IO)
    parser.add_argument("--assembly", type=Path)
    args = parser.parse_args(argv)
    try:
        built = build_stage1(
            args.output,
            source=args.source,
            host_io=args.host_io,
            assembly_output=args.assembly,
        )
    except Stage1BuildError as error:
        parser.exit(1, f"stage1 build failed: {error}\n")
    print(built)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
