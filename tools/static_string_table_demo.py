from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from bootstrap.s3.lexer import SyntaxMode  # noqa: E402
from bootstrap.s3.parser import parse  # noqa: E402
from bootstrap.s3.static_strings import collect_static_string_literals  # noqa: E402


SOURCE = """\
fn main() -> tryte:
    first: tryte = "hello"
    second: tryte = "world"
    third: tryte = "hello"
    return 0
"""


def main() -> int:
    table = collect_static_string_literals(parse(SOURCE, mode=SyntaxMode.V0_6))
    print("S3 static string literal table")
    print()
    for entry in table.entries:
        print(
            f'{entry.id}: "{entry.value}" '
            f"bytes={entry.byte_count} lines={entry.line_count} "
            f"sha256={entry.sha256}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
