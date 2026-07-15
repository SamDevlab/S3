from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
GOLDEN_ROOT = REPO_ROOT / "tests" / "golden" / "inspect"


def _golden_paths() -> tuple[Path, ...]:
    return tuple(sorted(GOLDEN_ROOT.glob("*.assembly.txt")))


def _scan_goldens() -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    directives: set[str] = set()
    opcodes: set[str] = set()
    goldens = tuple(path.name for path in _golden_paths())

    for path in _golden_paths():
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            stripped = raw_line.strip()
            if not stripped:
                continue
            if stripped.startswith("."):
                directives.add(stripped.split(maxsplit=1)[0])
                continue
            opcodes.add(stripped.split(maxsplit=1)[0])

    return goldens, tuple(sorted(directives)), tuple(sorted(opcodes))


def main() -> int:
    goldens, directives, opcodes = _scan_goldens()

    print("S3 Assembly renderer subset")
    print()
    print("goldens:")
    for name in goldens:
        print(f"  {name}")
    print()
    print("directives:")
    for directive in directives:
        print(f"  {directive}")
    print()
    print("opcodes:")
    for opcode in opcodes:
        print(f"  {opcode}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
