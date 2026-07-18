from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bootstrap.s3.pipeline import CompilationResult, compile_source, run_source  # noqa: E402


REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True, slots=True)
class S3Program:
    path: Path
    purpose: str
    expected: str = "compiles"
    hosted_expected_return: int | None = None


PROGRAMS = (
    S3Program(REPO_ROOT / "examples" / "first.s3", "baseline example"),
    S3Program(REPO_ROOT / "examples" / "simple_call.s3", "call example"),
    S3Program(REPO_ROOT / "examples" / "sign.s3", "ternary/sign behavior example"),
    S3Program(
        REPO_ROOT / "examples" / "self_hosting" / "assembly_renderer_stub.s3",
        "future Assembly renderer stub",
        hosted_expected_return=-1,
    ),
    S3Program(
        REPO_ROOT / "examples" / "self_hosting" / "assembly_renderer_bootstrap.s3",
        "Assembly renderer bootstrap spike",
        hosted_expected_return=0,
    ),
    S3Program(
        REPO_ROOT / "examples" / "self_hosting" / "assembly_renderer_output_model.s3",
        "Assembly renderer output model",
        hosted_expected_return=0,
    ),
    S3Program(
        REPO_ROOT / "examples" / "self_hosting" / "assembly_renderer_text_segments.s3",
        "Assembly renderer text segment model",
        hosted_expected_return=0,
    ),
    S3Program(
        REPO_ROOT
        / "examples"
        / "self_hosting"
        / "assembly_renderer_line_blueprints.s3",
        "Assembly renderer line blueprint model",
        hosted_expected_return=0,
    ),
)


def get_program_inventory() -> tuple[S3Program, ...]:
    return PROGRAMS


def _display_path(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _program_key(path: str | Path) -> str:
    path_obj = Path(path)
    if not path_obj.is_absolute():
        return path_obj.as_posix()

    try:
        return path_obj.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path_obj.as_posix()


def find_program(path: str | Path) -> S3Program | None:
    expected = _program_key(path)
    for program in get_program_inventory():
        if _display_path(program.path) == expected:
            return program
    return None


def run_hosted_check(program: S3Program, *, entry: str = "main") -> int:
    if program.hosted_expected_return is None:
        raise ValueError(f"{_display_path(program.path)} is not hosted opt-in")

    source = program.path.read_text(encoding="utf-8")
    return run_source(source, entry=entry)


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
    for program in get_program_inventory():
        print(_display_path(program.path))
        print(f"  purpose: {program.purpose}")
        print(f"  expected: {program.expected}")
        if program.hosted_expected_return is not None:
            print(f"  hosted expected return: {program.hosted_expected_return}")
        print()
    return 0


def check_programs() -> int:
    ok = True
    hosted_checked = 0
    programs = get_program_inventory()
    for program in programs:
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
        if program.hosted_expected_return is None:
            continue

        hosted_checked += 1
        try:
            actual = run_hosted_check(program)
        except Exception as error:
            ok = False
            print("  hosted execution: failed")
            print(f"  error: {error}")
            continue

        print(f"  hosted expected return: {program.hosted_expected_return}")
        print(f"  hosted actual return: {actual}")
        if actual != program.hosted_expected_return:
            ok = False
            print("  hosted execution: unexpected return")

    if ok:
        print(f"s3 program check: checked {len(programs)} program(s)")
        print(
            "s3 program check: hosted execution checked "
            f"{hosted_checked} program(s)"
        )
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
