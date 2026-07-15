from __future__ import annotations

import argparse
import difflib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bootstrap.s3.pipeline import CompilationResult, compile_source  # noqa: E402


REPO_ROOT = Path(__file__).resolve().parent.parent
GOLDEN_ROOT = REPO_ROOT / "tests" / "golden" / "inspect"


@dataclass(frozen=True, slots=True)
class GoldenCase:
    name: str
    source_path: Path


GOLDEN_CASES = (
    GoldenCase("first", REPO_ROOT / "examples" / "first.s3"),
)


def _stable_ir(compilation: CompilationResult) -> str:
    return json.dumps(compilation.ir.to_dict(), indent=2, sort_keys=True) + "\n"


def _stable_assembly(compilation: CompilationResult) -> str:
    text = compilation.assembly_text.replace("\r\n", "\n").replace("\r", "\n")
    return text if text.endswith("\n") else f"{text}\n"


def _golden_outputs(case: GoldenCase) -> dict[Path, str]:
    source = case.source_path.read_text(encoding="utf-8")
    compilation = compile_source(source)
    return {
        GOLDEN_ROOT / f"{case.name}.ir.json": _stable_ir(compilation),
        GOLDEN_ROOT / f"{case.name}.assembly.txt": _stable_assembly(compilation),
    }


def _display_path(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _print_diff(path: Path, expected: str, actual: str) -> None:
    print(f"golden mismatch: {_display_path(path)}")
    diff = difflib.unified_diff(
        expected.splitlines(),
        actual.splitlines(),
        fromfile=f"expected/{_display_path(path)}",
        tofile=f"actual/{_display_path(path)}",
        lineterm="",
    )
    for line in diff:
        print(line)


def check() -> int:
    ok = True
    for case in GOLDEN_CASES:
        for path, actual in _golden_outputs(case).items():
            if not path.exists():
                print(f"missing golden: {_display_path(path)}")
                ok = False
                continue
            expected = path.read_text(encoding="utf-8")
            if expected != actual:
                _print_diff(path, expected, actual)
                ok = False
    if ok:
        print(f"golden inspect: checked {len(GOLDEN_CASES)} example(s)")
        return 0
    return 1


def update() -> int:
    GOLDEN_ROOT.mkdir(parents=True, exist_ok=True)
    for case in GOLDEN_CASES:
        for path, content in _golden_outputs(case).items():
            path.write_text(content, encoding="utf-8", newline="\n")
            print(f"updated: {_display_path(path)}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check or update S3 inspect golden outputs"
    )
    parser.add_argument("command", choices=("check", "update"))
    args = parser.parse_args(argv)

    if args.command == "check":
        return check()
    return update()


if __name__ == "__main__":
    raise SystemExit(main())
