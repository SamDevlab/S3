"""Remove the redundant lexical-numeric value-record writer from Stage1.

The four ``ir_value_records_*`` banks are intended to become the physical
storage for the explicit IR-v2 semantic value namespace.  In the legacy Stage1
scanner they are instead populated once for every numeric source token and are
never consumed by the later verifier/emitter path; only ``ir_value_count`` is
checked/audited.  Full-source token coverage can therefore overflow a temporary
lexical-token representation that IR-v2 is going to replace anyway.

This candidate removes only the scanner-side numeric-record writer and its bank
cursor locals.  The four physical arrays remain declared and untouched so a
later qualified semantic-value transform can rebuild them deliberately.  With
no semantic value namespace populated yet, ``ir_value_count`` remains zero,
which is more accurate than treating lexical numeric occurrences as SSA values.

The transform expects the wide numeric token-lane repair to have been applied
first and is candidate-only until native Linux qualification proves that AST,
call/control and trivial compilation behavior are preserved.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from tools.patch_stage1_token_lane_wide_literals import (
    BASELINE_SOURCE_SHA256,
    SOURCE,
    transform as repair_token_lane,
)


VALUE_BANK_DECL = "    mut value_bank: tryte = 0\n"
VALUE_SLOT_DECL = "    mut value_slot: i64 = 0\n"

WRITER_START = (
    "        match kind == 2:\n"
    "            -1:\n"
    "                match array_initializer_depth >= 0:\n"
    "                    -1:\n"
    "                        match ir_value_count < 1460:\n"
)
WRITER_END = (
    "        match kind == 1:\n"
    "            -1:\n"
    "                match value == 352:\n"
)


def _sha256(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def transform_after_token_lane(token_lane_source: str) -> str:
    if "return pack_token(position, 2, 0)" not in token_lane_source:
        raise ValueError("legacy numeric-record removal requires wide token-lane repair first")
    if "ir_value_records_0[value_slot]" not in token_lane_source:
        raise ValueError("legacy numeric-record writer appears already removed")

    source = token_lane_source
    if source.count(VALUE_BANK_DECL) != 1 or source.count(VALUE_SLOT_DECL) != 1:
        raise ValueError("legacy value-bank cursor declarations are not unique")
    source = source.replace(VALUE_BANK_DECL, "", 1).replace(VALUE_SLOT_DECL, "", 1)

    start = source.find(WRITER_START)
    if start < 0:
        raise ValueError("legacy numeric-record writer start anchor not found")
    if source.find(WRITER_START, start + 1) >= 0:
        raise ValueError("legacy numeric-record writer start anchor is ambiguous")
    end = source.find(WRITER_END, start)
    if end < 0:
        raise ValueError("legacy numeric-record writer end anchor not found")
    if source.find(WRITER_END, end + 1) >= 0:
        raise ValueError("legacy numeric-record writer end anchor is ambiguous")
    source = source[:start] + source[end:]

    for bank in range(4):
        name = f"ir_value_records_{bank}"
        if source.count(name) != 1:
            raise ValueError(
                f"{name} must remain declaration-only after legacy writer removal; "
                f"found {source.count(name)} references"
            )
    if "value_bank" in source or "value_slot" in source:
        raise ValueError("legacy value-bank cursor references remain after transform")
    if "mut ir_value_count: i64 = 0" not in source:
        raise ValueError("semantic value count scalar was unexpectedly removed")
    return source


def build_candidate(canonical_source: str) -> str:
    return transform_after_token_lane(repair_token_lane(canonical_source))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    source_path = args.source.resolve()
    canonical = source_path.read_text(encoding="utf-8")
    before_sha = _sha256(canonical)
    if before_sha != BASELINE_SOURCE_SHA256:
        parser.error("legacy numeric-record candidate requires the frozen canonical source")

    token_lane = repair_token_lane(canonical)
    candidate = transform_after_token_lane(token_lane)
    destination = (
        args.output.resolve()
        if args.output is not None
        else source_path.with_suffix(".wide-token-lane.no-legacy-values.s3")
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(candidate, encoding="utf-8", newline="\n")

    print(f"CANONICAL_SHA256={before_sha}")
    print(f"TOKEN_LANE_SHA256={_sha256(token_lane)}")
    print(f"CANDIDATE_SHA256={_sha256(candidate)}")
    print(f"TOKEN_LANE_BYTES={len(token_lane.encode('utf-8'))}")
    print(f"CANDIDATE_BYTES={len(candidate.encode('utf-8'))}")
    print("LEGACY_NUMERIC_VALUE_RECORD_WRITER=REMOVED")
    print("IR_VALUE_RECORD_BANKS=DECLARATION_ONLY_RESERVED_FOR_SEMANTIC_IR_V2")
    print("IR_VALUE_COUNT_INITIAL=0")
    print("NATIVE_QUALIFICATION_REQUIRED=True")
    print("CANONICAL_SOURCE_MUTATED=False")
    print(f"OUTPUT={destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
