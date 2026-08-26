"""Build packed parameter IR-v2 after wide-token-lane repair and compaction.

This wrapper preserves the already-reviewed parameter metadata transform but
changes its prerequisite source sequence to the corrected pre-IR-v2 foundation:

    frozen canonical
      -> wide numeric token-lane repair
      -> redundant discard aggregate-event compaction
      -> packed parameter metadata

It is candidate-only.  Native token-lane and rebased-compaction reports must be
PASS before a native parameter qualifier may consume this source.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from tools.patch_stage1_codegen_ir_v2_parameters import transform_parameters
from tools.patch_stage1_compaction_after_token_lane import build_compacted_candidate
from tools.patch_stage1_token_lane_wide_literals import (
    BASELINE_SOURCE_SHA256,
    SOURCE,
)


def _sha256(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def build_candidate(source: str) -> str:
    compacted = build_compacted_candidate(source)
    candidate = transform_parameters(compacted)
    if "return pack_token(position, 2, 0)" not in candidate:
        raise ValueError("parameter candidate lost wide numeric token-lane repair")
    if "ir_ast_event_opcode = 5" in candidate:
        raise ValueError("parameter candidate lost discard-event compaction")
    if "mut ir_parameter_records: i64[64]" not in candidate:
        raise ValueError("parameter candidate missing packed parameter lane")
    return candidate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    source_path = args.source.resolve()
    source = source_path.read_text(encoding="utf-8")
    before_sha = _sha256(source)
    if before_sha != BASELINE_SOURCE_SHA256:
        parser.error("rebased parameter candidate requires the frozen canonical source")

    candidate = build_candidate(source)
    destination = (
        args.output.resolve()
        if args.output is not None
        else source_path.with_suffix(".wide-token-lane.compacted.parameters.s3")
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(candidate, encoding="utf-8", newline="\n")

    print(f"CANONICAL_SHA256={before_sha}")
    print(f"PARAMETER_CANDIDATE_SHA256={_sha256(candidate)}")
    print(f"CANONICAL_BYTES={len(source.encode('utf-8'))}")
    print(f"PARAMETER_CANDIDATE_BYTES={len(candidate.encode('utf-8'))}")
    print("TRANSFORM_ORDER=WIDE_TOKEN_LANE,DISCARD_EVENT_COMPACTION,PACKED_PARAMETER_IR_V2")
    print("NATIVE_QUALIFICATION_REQUIRED=True")
    print("CANONICAL_SOURCE_MUTATED=False")
    print(f"OUTPUT={destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
