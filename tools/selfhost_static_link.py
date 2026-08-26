"""Shared deterministic static ELF link recipe for final self-hosting gates."""

from __future__ import annotations

from pathlib import Path

from tools.qualify_stage2_stage3_fixed_point import _require_ok, _run


STATIC_LINK_FLAGS = (
    "-static",
    "-nostdlib",
    "-no-pie",
    "-s",
    "-Wl,--build-id=none",
)


def assemble_link_static(
    assembly: bytes,
    *,
    cc: str,
    host_object: Path,
    directory: Path,
    output_name: str,
) -> Path:
    """Assemble and link one compiler/program as a deterministic static ELF."""

    directory.mkdir(parents=True, exist_ok=True)
    assembly_path = directory / "compiler.s"
    object_path = directory / "compiler.o"
    output = directory / output_name
    assembly_path.write_bytes(assembly)
    assembled = _run(
        [cc, "-x", "assembler", "-c", str(assembly_path), "-o", str(object_path)],
        cwd=directory,
    )
    _require_ok(assembled, f"assemble {output_name}")
    linked = _run(
        [
            cc,
            *STATIC_LINK_FLAGS,
            str(object_path),
            str(host_object),
            "-o",
            str(output),
        ],
        cwd=directory,
    )
    _require_ok(linked, f"static link {output_name}")
    return output
