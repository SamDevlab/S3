from __future__ import annotations

import argparse
import difflib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bootstrap.s3.diagnostics import diagnostic_from_exception  # noqa: E402
from bootstrap.s3.pipeline import compile_source  # noqa: E402


REPO_ROOT = Path(__file__).resolve().parent.parent
GOLDEN_ROOT = REPO_ROOT / "tests" / "golden" / "diagnostics"


@dataclass(frozen=True, slots=True)
class GoldenDiagnosticCase:
    name: str
    source_path: Path


GOLDEN_CASES = (
    GoldenDiagnosticCase(
        "out_of_range_literal",
        GOLDEN_ROOT / "out_of_range_literal.s3",
    ),
    GoldenDiagnosticCase(
        "static_bounds",
        GOLDEN_ROOT / "static_bounds.s3",
    ),
    GoldenDiagnosticCase(
        "missing_match_case",
        GOLDEN_ROOT / "missing_match_case.s3",
    ),
    GoldenDiagnosticCase(
        "unsupported_string_literal",
        GOLDEN_ROOT / "unsupported_string_literal.s3",
    ),
    GoldenDiagnosticCase(
        "unterminated_string_literal",
        GOLDEN_ROOT / "unterminated_string_literal.s3",
    ),
)


def _display_path(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _stable_diagnostics(case: GoldenDiagnosticCase) -> str:
    source = case.source_path.read_text(encoding="utf-8")
    try:
        compile_source(source)
    except Exception as error:
        diagnostics = [diagnostic_from_exception(error).to_dict()]
    else:
        raise RuntimeError(f"expected {_display_path(case.source_path)} to fail")
    return json.dumps(
        diagnostics,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"


def _golden_outputs(case: GoldenDiagnosticCase) -> dict[Path, str]:
    return {
        GOLDEN_ROOT / f"{case.name}.json": _stable_diagnostics(case),
    }


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
        print(f"golden diagnostics: checked {len(GOLDEN_CASES)} case(s)")
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
        description="Check or update S3 diagnostic golden outputs"
    )
    parser.add_argument("command", choices=("check", "update"))
    args = parser.parse_args(argv)

    if args.command == "check":
        return check()
    return update()


if __name__ == "__main__":
    raise SystemExit(main())
