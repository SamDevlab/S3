"""Compose the corrected pre-IR-v2 foundation with discard-event compaction.

The authoritative candidate order is now:

    frozen canonical
      -> wide numeric token-lane repair
      -> remove unused legacy lexical-numeric value-record writer
      -> discard aggregate-event compaction

The value-record cleanup and discard compaction are separately native-gated so a
single qualification step never hides two behavior changes.  This module only
builds exact sources; it makes no native PASS claim.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from tools.patch_stage1_codegen_ir_v2_capacity import transform as compact_discard_event
from tools.patch_stage1_drop_legacy_numeric_value_records import (
    transform_after_token_lane as drop_legacy_numeric_records,
)
from tools.patch_stage1_token_lane_wide_literals import (
    BASELINE_SOURCE_SHA256,
    SOURCE,
    transform as repair_token_lane,
)


def _sha256_text(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def build_token_lane_candidate(source: str) -> str:
    return repair_token_lane(source)


def build_pre_compaction_candidate(source: str) -> str:
    return drop_legacy_numeric_records(build_token_lane_candidate(source))


def build_compacted_candidate(source: str) -> str:
    return compact_discard_event(build_pre_compaction_candidate(source))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    source_path = args.source.resolve()
    source = source_path.read_text(encoding="utf-8")
    before_sha = _sha256_text(source)
    if before_sha != BASELINE_SOURCE_SHA256:
        parser.error(
            "composition requires the frozen canonical source; rebase the "
            "candidate explicitly if the canonical source is later promoted"
        )

    token_lane = build_token_lane_candidate(source)
    pre_compaction = build_pre_compaction_candidate(source)
    compacted = build_compacted_candidate(source)
    destination = (
        args.output.resolve()
        if args.output is not None
        else source_path.with_suffix(".pre-ir-v2.compacted.s3")
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(compacted, encoding="utf-8", newline="\n")

    print(f"CANONICAL_SHA256={before_sha}")
    print(f"TOKEN_LANE_SHA256={_sha256_text(token_lane)}")
    print(f"PRE_COMPACTION_SHA256={_sha256_text(pre_compaction)}")
    print(f"COMPACTED_SHA256={_sha256_text(compacted)}")
    print(f"CANONICAL_BYTES={len(source.encode('utf-8'))}")
    print(f"TOKEN_LANE_BYTES={len(token_lane.encode('utf-8'))}")
    print(f"PRE_COMPACTION_BYTES={len(pre_compaction.encode('utf-8'))}")
    print(f"COMPACTED_BYTES={len(compacted.encode('utf-8'))}")
    print("ORDER=WIDE_TOKEN_LANE,DROP_LEGACY_NUMERIC_RECORD_WRITER,DROP_REDUNDANT_DISCARD_EVENT")
    print("SEPARATE_NATIVE_GATES_REQUIRED=True")
    print("CANONICAL_SOURCE_MUTATED=False")
    print(f"OUTPUT={destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
