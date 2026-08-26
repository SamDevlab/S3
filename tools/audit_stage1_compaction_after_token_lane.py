"""Static 2x2 semantic differential for compaction after token-lane repair.

The old compaction qualifier conflated two independent effects:

* compiler behavior: whether a ``discard`` keyword emits aggregate event opcode 5;
* self-source input: the compacted compiler source itself no longer contains the
  two assignments that used to populate that aggregate event.

This model evaluates both compiler behaviors against both source inputs. The
strong invariant is same-input equivalence after filtering only opcode 5, not a
blind expectation that every textual source delta appears in a capped native IR
counter. It also exposes the exact source-level function/match/while inputs used
by Stage1's current synthetic block-reconstruction formula so capacity planning
can distinguish CFG pressure from event pressure.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from tools.patch_stage1_compaction_after_token_lane import (
    build_compacted_candidate,
    build_token_lane_candidate,
)
from tools.patch_stage1_token_lane_wide_literals import SOURCE
from tools.preflight_stage1_codegen_ir_v2_locals import Stage1Token, stage1_tokens


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = (
    ROOT / "reports" / "selfhost" / "stage1" /
    "compaction-after-token-lane-static-differential.json"
)

_IDENTIFIER_EVENT = {
    342: 1,  # return
    162: 2,  # while
    135: 3,  # match
    37: 4,   # break
    220: 5,  # discard
    87: 6,   # mut/local declaration
}
_PUNCT_EVENT = {
    5: 7,    # =
    14: 7,   # +=
    6: 8,    # +
    7: 9,    # -
    8: 10,   # *
    9: 11,   # /
    13: 12,  # ==
    15: 13,  # <=>
    16: 14,  # <
    17: 15,  # >
}


def _sha256(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _is_signature(tokens: list[Stage1Token], index: int) -> bool:
    return (
        index >= 2
        and tokens[index].kind == 4
        and tokens[index].value == 1
        and tokens[index - 1].kind == 1
        and tokens[index - 2].kind == 1
        and tokens[index - 2].text == "fn"
    )


def _events(source: str, *, compact_discard_behavior: bool) -> list[tuple[int, int, int]]:
    """Return ``(token_index, opcode, operand)`` in Stage1 token order."""

    tokens = stage1_tokens(source)
    events: list[tuple[int, int, int]] = []
    for index, token in enumerate(tokens):
        opcode = 0
        operand = token.value
        if token.kind == 1:
            opcode = _IDENTIFIER_EVENT.get(token.value, 0)
            if compact_discard_behavior and opcode == 5:
                opcode = 0
        elif token.kind == 4:
            opcode = _PUNCT_EVENT.get(token.value, 0)
            if token.value == 1 and index > 0 and tokens[index - 1].kind == 1:
                if not _is_signature(tokens, index):
                    opcode = 16
                    operand = tokens[index - 1].value
        if opcode != 0:
            events.append((index, opcode, operand))
    return events


def _source_counts(source: str) -> dict[str, int]:
    tokens = stage1_tokens(source)
    identifiers = [token.value for token in tokens if token.kind == 1]
    punctuation = [token.value for token in tokens if token.kind == 4]
    function_signatures = sum(1 for value in identifiers if value == 352)
    foreign_declarations = sum(1 for value in identifiers if value == 311)
    return {
        "tokens": len(tokens),
        "numeric_tokens": sum(1 for token in tokens if token.kind == 2),
        "function_signature_tokens": function_signatures,
        "foreign_declaration_tokens": foreign_declarations,
        "local_function_count": function_signatures - foreign_declarations,
        "local_declaration_tokens": sum(1 for value in identifiers if value == 87),
        "assignment_observation_tokens": (
            sum(1 for value in identifiers if value == 87)
            + sum(1 for value in punctuation if value in {5, 14})
        ),
        "discard_keyword_tokens": sum(1 for value in identifiers if value == 220),
        "return_tokens": sum(1 for value in identifiers if value == 342),
        "match_tokens": sum(1 for value in identifiers if value == 135),
        "while_tokens": sum(1 for value in identifiers if value == 162),
        "break_tokens": sum(1 for value in identifiers if value == 37),
    }


def audit(source: str) -> dict[str, object]:
    token_lane = build_token_lane_candidate(source)
    compacted = build_compacted_candidate(source)

    e0_s0 = _events(token_lane, compact_discard_behavior=False)
    e0_s1 = _events(compacted, compact_discard_behavior=False)
    e1_s0 = _events(token_lane, compact_discard_behavior=True)
    e1_s1 = _events(compacted, compact_discard_behavior=True)

    e0_s0_without_discard = [event for event in e0_s0 if event[1] != 5]
    e0_s1_without_discard = [event for event in e0_s1 if event[1] != 5]

    counts_s0 = _source_counts(token_lane)
    counts_s1 = _source_counts(compacted)

    same_input_s0_semantic = e0_s0_without_discard == e1_s0
    same_input_s1_semantic = e0_s1_without_discard == e1_s1
    block_driving_s0 = [event for event in e0_s0 if event[1] in {2, 3, 4}]
    block_driving_e1_s0 = [event for event in e1_s0 if event[1] in {2, 3, 4}]
    block_driving_preserved = block_driving_s0 == block_driving_e1_s0

    source_delta = {
        key: counts_s1[key] - counts_s0[key]
        for key in counts_s0
    }
    guards = {
        "same_input_s0_diff_is_discard_only": same_input_s0_semantic,
        "same_input_s1_diff_is_discard_only": same_input_s1_semantic,
        "block_driving_events_preserved_same_input": block_driving_preserved,
        "compacted_source_removes_two_assignment_observation_tokens": (
            source_delta["assignment_observation_tokens"] == -2
        ),
        "compacted_source_removes_one_numeric_token": source_delta["numeric_tokens"] == -1,
        "compacted_source_keeps_function_signatures": source_delta["function_signature_tokens"] == 0,
        "compacted_source_keeps_foreign_declarations": source_delta["foreign_declaration_tokens"] == 0,
        "compacted_source_keeps_local_declarations": source_delta["local_declaration_tokens"] == 0,
        "compacted_source_keeps_discard_keywords": source_delta["discard_keyword_tokens"] == 0,
        "compacted_source_keeps_return_tokens": source_delta["return_tokens"] == 0,
        "compacted_source_keeps_match_tokens": source_delta["match_tokens"] == 0,
        "compacted_source_keeps_while_tokens": source_delta["while_tokens"] == 0,
        "compacted_source_keeps_break_tokens": source_delta["break_tokens"] == 0,
    }
    static_pass = all(guards.values())

    return {
        "schema": "s3.selfhost.compaction-after-token-lane-static-differential.v2",
        "status": (
            "STATIC_COMPACTION_SEMANTIC_DIFFERENTIAL_PASS_NATIVE_2X2_REQUIRED"
            if static_pass
            else "STATIC_COMPACTION_SEMANTIC_DIFFERENTIAL_FAIL"
        ),
        "native_evidence": False,
        "canonical_source_mutated": False,
        "token_lane_source": {
            "sha256": _sha256(token_lane),
            "bytes": len(token_lane.encode("utf-8")),
            "counts": counts_s0,
        },
        "compacted_source": {
            "sha256": _sha256(compacted),
            "bytes": len(compacted.encode("utf-8")),
            "counts": counts_s1,
        },
        "source_input_delta": source_delta,
        "matrix": {
            "E0_S0_events": len(e0_s0),
            "E0_S1_events": len(e0_s1),
            "E1_S0_events": len(e1_s0),
            "E1_S1_events": len(e1_s1),
            "E0_S0_discard_events": sum(1 for event in e0_s0 if event[1] == 5),
            "E0_S1_discard_events": sum(1 for event in e0_s1 if event[1] == 5),
            "E1_S0_discard_events": sum(1 for event in e1_s0 if event[1] == 5),
            "E1_S1_discard_events": sum(1 for event in e1_s1 if event[1] == 5),
        },
        "cfg_reconstruction_model": {
            "formula": "local_function_count + 3*(match_tokens + while_tokens)",
            "S0_required_blocks": (
                counts_s0["local_function_count"]
                + 3 * (counts_s0["match_tokens"] + counts_s0["while_tokens"])
            ),
            "S1_required_blocks": (
                counts_s1["local_function_count"]
                + 3 * (counts_s1["match_tokens"] + counts_s1["while_tokens"])
            ),
            "note": (
                "This mirrors the current synthetic Stage1 block reconstruction: "
                "one entry block per local function and three additional blocks "
                "for each recorded match/while event. Native qualification remains required."
            ),
        },
        "guards": guards,
        "root_cause_model": (
            "Textual source counters and compiler-behavior event compaction are "
            "separate axes. Native qualification must compare same-input event "
            "streams and treat source deltas separately; capped IR value/event "
            "counters cannot be assumed to equal textual token deltas."
        ),
        "next": (
            "RUN_NATIVE_COMPACTION_2X2_AFTER_TOKEN_LANE_PASS"
            if static_pass
            else "FIX_STATIC_COMPACTION_SEMANTIC_MODEL"
        ),
        "general_emitter": "BLOCKED_IR_V2_INCOMPLETE",
        "stage2": "NOT_STARTED",
        "stage3": "NOT_STARTED",
        "full_self_hosting": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)

    result = audit(args.source.resolve().read_text(encoding="utf-8"))
    destination = args.report.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"REPORT={destination}")
    print(f"STATUS={result['status']}")
    print(f"E0_S0_EVENTS={result['matrix']['E0_S0_events']}")
    print(f"E1_S0_EVENTS={result['matrix']['E1_S0_events']}")
    print(f"S0_REQUIRED_BLOCKS={result['cfg_reconstruction_model']['S0_required_blocks']}")
    print(f"S1_REQUIRED_BLOCKS={result['cfg_reconstruction_model']['S1_required_blocks']}")
    print(f"SOURCE_ASSIGNMENT_DELTA={result['source_input_delta']['assignment_observation_tokens']}")
    print(f"SOURCE_NUMERIC_DELTA={result['source_input_delta']['numeric_tokens']}")
    print(f"NEXT={result['next']}")
    return 0 if result["status"].startswith("STATIC_COMPACTION_SEMANTIC_DIFFERENTIAL_PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())
