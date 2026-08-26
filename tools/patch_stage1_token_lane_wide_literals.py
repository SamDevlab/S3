"""Prepare a Stage1 token-lane candidate that preserves wide numeric literals.

The legacy ``pack_token`` layout dedicates only 1000 states to the packed value
lane::

    next_cursor * 1_000_000 + kind * 1_000 + value + 500

so it is lossless only for values in ``[-500, 499]``.  The canonical compiler
source contains much wider i64 literals (including ``1_000_000_000_000``),
which spill into the kind/cursor lanes and terminate the native self-source
scan early.

This candidate keeps the compact return ABI without adding a new S3 function or
new local: numeric tokens carry zero in the packed value lane, then ``main``
reconstructs their exact signed i64 value from the already-known source range
before storing/using the token.  Identifier and punctuation values remain in
lane because their domains are already bounded below 500.

The transformation is candidate-only.  It never mutates the canonical source
unless ``--in-place`` is explicitly requested; native Linux qualification is
required before any promotion.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "selfhost" / "compiler" / "s3c_stage1.s3"
BASELINE_SOURCE_SHA256 = "20fddbb73eee9ae09de911493f2f2da01ab582c7a6de879ea2e557946716a341"

LEGACY_NUMERIC_PACK = "            return pack_token(position, 2, number * negative)\n"
SAFE_NUMERIC_PACK = "            return pack_token(position, 2, 0)\n"

LEGACY_SLOT_ANCHOR = """        mut slot: i64 = token_count
        while slot > 15:
"""

RECOVERY_SLOT_BLOCK = """        mut slot: i64 = actual_start
        match kind == 2:
            -1:
                value = 0
                simple_value = 1
                match read_at(slot) == 45:
                    -1:
                        simple_value = -1
                        slot += 1
                    0:
                        discard 0
                    1:
                        discard 0
                while slot < next_cursor:
                    value = value * 10 + (to_i64(read_at(slot)) - 48)
                    slot += 1
                value = value * simple_value
            0:
                discard 0
            1:
                discard 0
        slot = token_count
        while slot > 15:
"""


def sha256_text(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _replace_exactly_once(source: str, old: str, new: str, *, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise ValueError(f"expected exactly one {label} anchor; found {count}")
    return source.replace(old, new, 1)


def transform(source: str) -> str:
    """Return the exact wide-numeric token-lane candidate source."""

    if SAFE_NUMERIC_PACK in source or "mut slot: i64 = actual_start" in source:
        raise ValueError("wide-numeric token-lane candidate appears already applied")

    before_functions = source.count("fn ")
    before_mut = source.count("mut ")

    transformed = _replace_exactly_once(
        source,
        LEGACY_NUMERIC_PACK,
        SAFE_NUMERIC_PACK,
        label="legacy numeric pack",
    )
    transformed = _replace_exactly_once(
        transformed,
        LEGACY_SLOT_ANCHOR,
        RECOVERY_SLOT_BLOCK,
        label="main token-slot",
    )

    if transformed.count("fn ") != before_functions:
        raise ValueError("token-lane candidate unexpectedly changed function signatures")
    if transformed.count("mut ") != before_mut:
        raise ValueError("token-lane candidate unexpectedly changed local declarations")
    if LEGACY_NUMERIC_PACK in transformed:
        raise ValueError("legacy wide numeric payload is still packed")
    if transformed.count(SAFE_NUMERIC_PACK) != 1:
        raise ValueError("safe numeric pack marker is not unique")
    if transformed.count("slot = token_count") != 1:
        raise ValueError("numeric recovery does not restore token ring slot exactly once")
    if transformed.count("simple_value = -1") != 1:
        raise ValueError("numeric sign recovery marker is not unique")
    return transformed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--in-place", action="store_true")
    parser.add_argument(
        "--allow-nonbaseline",
        action="store_true",
        help="allow an exact-anchor transform on a reviewed nonbaseline source",
    )
    args = parser.parse_args(argv)

    source_path = args.source.resolve()
    source = source_path.read_text(encoding="utf-8")
    before_sha = sha256_text(source)
    if before_sha != BASELINE_SOURCE_SHA256 and not args.allow_nonbaseline:
        parser.error(
            "source SHA does not match the frozen pre-token-lane baseline; "
            "use --allow-nonbaseline only after reviewing the source diff"
        )

    candidate = transform(source)
    after_sha = sha256_text(candidate)

    if args.in_place and args.output is not None:
        parser.error("choose either --in-place or --output, not both")
    if args.in_place:
        destination = source_path
    elif args.output is not None:
        destination = args.output.resolve()
    else:
        destination = source_path.with_suffix(".wide-token-lane.s3")

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(candidate, encoding="utf-8", newline="\n")

    print(f"SOURCE_BEFORE_SHA256={before_sha}")
    print(f"SOURCE_AFTER_SHA256={after_sha}")
    print(f"SOURCE_BEFORE_BYTES={len(source.encode('utf-8'))}")
    print(f"SOURCE_AFTER_BYTES={len(candidate.encode('utf-8'))}")
    print("TRANSFORM=NUMERIC_TOKEN_VALUE_RECOVERED_FROM_SOURCE_RANGE")
    print("PACKED_NUMERIC_PAYLOAD=0")
    print("RECOVERY_SIGN_TEMP=EXISTING_SIMPLE_VALUE_LOCAL")
    print("NEW_FUNCTION_SIGNATURES=0")
    print("NEW_MUT_DECLARATIONS=0")
    print("CANONICAL_SOURCE_MUTATED=" + str(args.in_place))
    print(f"OUTPUT={destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
