"""Prepare the first codegen-IR-v2 capacity patch for the S3 Stage1 source.

The transformation is intentionally narrow: keep the discard audit counter but
stop serializing the redundant aggregate discard-keyword event. Side-effecting
calls/stores remain represented by their own IR records. This tool does not
claim the projected count as native evidence; Linux qualification is required
after the transformed source is committed.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "selfhost" / "compiler" / "s3c_stage1.s3"
BASELINE_SOURCE_SHA256 = "20fddbb73eee9ae09de911493f2f2da01ab582c7a6de879ea2e557946716a341"

OLD_DISCARD_EVENT_BLOCK = """                match value == 220:\n                    -1:\n                        ast_discard_count += 1\n                        ir_ast_event_opcode = 5\n                        ir_ast_event_operand = value\n                    0:\n                        discard 0\n                    1:\n                        discard 0\n"""

NEW_DISCARD_EVENT_BLOCK = """                match value == 220:\n                    -1:\n                        ast_discard_count += 1\n                    0:\n                        discard 0\n                    1:\n                        discard 0\n"""


def sha256_text(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def transform(source: str) -> str:
    occurrences = source.count(OLD_DISCARD_EVENT_BLOCK)
    if occurrences != 1:
        raise ValueError(
            "expected exactly one Stage1 discard-event block; "
            f"found {occurrences}"
        )
    transformed = source.replace(
        OLD_DISCARD_EVENT_BLOCK,
        NEW_DISCARD_EVENT_BLOCK,
        1,
    )
    if "ast_discard_count += 1" not in transformed:
        raise ValueError("discard audit counter was unexpectedly removed")
    if "ir_ast_event_opcode = 5" in transformed:
        raise ValueError("redundant discard event opcode still present after transform")
    return transformed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--in-place", action="store_true")
    parser.add_argument(
        "--allow-nonbaseline",
        action="store_true",
        help="allow applying when the source SHA differs but the exact target block still matches",
    )
    args = parser.parse_args(argv)

    source_path = args.source.resolve()
    source = source_path.read_text(encoding="utf-8")
    before_sha = sha256_text(source)
    if before_sha != BASELINE_SOURCE_SHA256 and not args.allow_nonbaseline:
        parser.error(
            "source SHA does not match the qualified pre-IR-v2 baseline; "
            "use --allow-nonbaseline only after reviewing the intervening source diff"
        )

    transformed = transform(source)
    after_sha = sha256_text(transformed)

    if args.in_place and args.output is not None:
        parser.error("choose either --in-place or --output, not both")
    if args.in_place:
        destination = source_path
    elif args.output is not None:
        destination = args.output.resolve()
    else:
        destination = source_path.with_suffix(".ir-v2-capacity.s3")

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(transformed, encoding="utf-8", newline="\n")

    print(f"SOURCE_BEFORE_SHA256={before_sha}")
    print(f"SOURCE_AFTER_SHA256={after_sha}")
    print("TRANSFORM=DROP_REDUNDANT_DISCARD_KEYWORD_EVENT")
    print("NATIVE_BASELINE_EVENTS=1460")
    print("NATIVE_BASELINE_DISCARD_EVENTS=699")
    print("PROJECTED_EVENTS=761")
    print("PROJECTED_HEADROOM=699")
    print("PROJECTION_STATUS=NATIVE_REMEASUREMENT_REQUIRED")
    print(f"OUTPUT={destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
