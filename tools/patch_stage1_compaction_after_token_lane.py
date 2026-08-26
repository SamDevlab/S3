"""Compose the wide-token-lane repair with discard-event compaction.

The previous compaction qualifier operated directly on the legacy canonical
source, whose self-source traversal is now known to be incomplete because wide
numeric literals spill into ``pack_token``'s cursor/kind lanes.  This module
creates the only compaction candidate that should be considered after the token
lane is natively qualified:

    frozen canonical -> wide token lane -> discard aggregate-event compaction

It is a pure in-memory/file transform and makes no native PASS claim.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from tools.patch_stage1_codegen_ir_v2_capacity import transform as compact_discard_event
from tools.patch_stage1_token_lane_wide_literals import (
    BASELINE_SOURCE_SHA256,
    SOURCE,
    transform as repair_token_lane,
)


def _sha256_text(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def build_token_lane_candidate(source: str) -> str:
    return repair_token_lane(source)


def build_compacted_candidate(source: str) -> str:
    token_lane = build_token_lane_candidate(source)
    return compact_discard_event(token_lane)


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
    compacted = build_compacted_candidate(source)
    destination = (
        args.output.resolve()
        if args.output is not None
        else source_path.with_suffix(".wide-token-lane.compacted.s3")
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(compacted, encoding="utf-8", newline="\n")

    print(f"CANONICAL_SHA256={before_sha}")
    print(f"TOKEN_LANE_SHA256={_sha256_text(token_lane)}")
    print(f"COMPACTED_SHA256={_sha256_text(compacted)}")
    print(f"CANONICAL_BYTES={len(source.encode('utf-8'))}")
    print(f"TOKEN_LANE_BYTES={len(token_lane.encode('utf-8'))}")
    print(f"COMPACTED_BYTES={len(compacted.encode('utf-8'))}")
    print("ORDER=WIDE_TOKEN_LANE_THEN_DROP_REDUNDANT_DISCARD_EVENT")
    print("NATIVE_QUALIFICATION_REQUIRED=True")
    print("CANONICAL_SOURCE_MUTATED=False")
    print(f"OUTPUT={destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
