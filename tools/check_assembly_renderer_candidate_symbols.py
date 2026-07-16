from __future__ import annotations

import difflib
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from tools.compare_assembly_renderer import (  # noqa: E402
    load_candidate_status,
    render_candidate_symbols,
)


GOLDEN_PATH = REPO_ROOT / "tests" / "golden" / "assembly_renderer_candidate_symbols.txt"


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
    if not GOLDEN_PATH.exists():
        print(f"missing golden: {_display_path(GOLDEN_PATH)}")
        return 1

    expected = GOLDEN_PATH.read_text(encoding="utf-8")
    if not expected.endswith("\n"):
        print(f"golden missing final newline: {_display_path(GOLDEN_PATH)}")
        return 1

    try:
        actual = render_candidate_symbols(load_candidate_status())
    except ValueError as error:
        print(f"assembly renderer candidate symbols invalid: {error}")
        return 1

    if expected != actual:
        _print_diff(GOLDEN_PATH, expected, actual)
        return 1

    print("assembly renderer candidate symbols: ok")
    return 0


def main() -> int:
    return check()


if __name__ == "__main__":
    raise SystemExit(main())
