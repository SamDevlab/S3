from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bootstrap.s3.pipeline import CompilationResult, compile_source  # noqa: E402


REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True, slots=True)
class S3Program:
    path: Path
    purpose: str
    expected: str = "compiles"


PROGRAMS = (
    S3Program(REPO_ROOT / "examples" / "first.s3", "baseline example"),
    S3Program(REPO_ROOT / "examples" / "simple_call.s3", "call example"),
    S3Program(REPO_ROOT / "examples" / "sign.s3", "ternary/sign behavior example"),
    S3Program(
        REPO_ROOT / "examples" / "self_hosting" / "assembly_renderer_stub.s3",
        "future Assembly renderer stub",
    ),
)


def _display_path(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _instruction_counts(compilation: CompilationResult) -> tuple[int, int]:
    ir_count = sum(
        len(block.instructions)
        for function in compilation.ir.functions
        for block in function.blocks
    )
    assembly_count = sum(
        len(block.instructions)
        for function in compilation.assembly.functions
        for block in function.blocks
    )
    return ir_count, assembly_count


def list_programs() -> int:
    print("S3 program check inventory")
    print()
    for program in PROGRAMS:
        print(_display_path(program.path))
        print(f"  purpose: {program.purpose}")
        print(f"  expected: {program.expected}")
        print()
    return 0


def check_programs() -> int:
    ok = True
    for program in PROGRAMS:
        try:
            source = program.path.read_text(encoding="utf-8")
            compilation = compile_source(source)
        except Exception as error:
            ok = False
            print(f"failed: {_display_path(program.path)}")
            print(f"  error: {error}")
            continue

        ir_count, assembly_count = _instruction_counts(compilation)
        print(f"ok: {_display_path(program.path)}")
        print(f"  ir instructions: {ir_count}")
        print(f"  assembly instructions: {assembly_count}")

    if ok:
        print(f"s3 program check: checked {len(PROGRAMS)} program(s)")
        return 0
    return 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="List or check S3 programs used by migration prep"
    )
    parser.add_argument("command", choices=("list", "check"))
    args = parser.parse_args(argv)

    if args.command == "list":
        return list_programs()
    return check_programs()


if __name__ == "__main__":
    raise SystemExit(main())
