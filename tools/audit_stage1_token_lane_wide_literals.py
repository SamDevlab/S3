"""Static differential audit for the Stage1 wide-numeric token-lane candidate.

This tool keeps two concepts separate:

* ``legacy`` reproduces the current packed-token ABI, where numeric values are
  inserted directly into a 1000-state value lane and can spill into kind/cursor;
* ``recovered`` models the candidate produced by
  :mod:`tools.patch_stage1_token_lane_wide_literals`, where numeric tokens pack
  zero and their exact signed i64 value is reconstructed from the source range
  after the cursor/kind fields have been decoded.

The audit is static evidence only.  Native Linux must still build/run the exact
candidate and prove full-source coverage before canonical promotion.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from tools.patch_stage1_token_lane_wide_literals import (
    BASELINE_SOURCE_SHA256,
    SOURCE,
    transform,
)
from tools.preflight_stage1_codegen_ir_v2_locals import Stage1Token, stage1_tokens


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = (
    ROOT / "reports" / "selfhost" / "stage1" /
    "packed-token-lane-static-audit.json"
)

TOKEN_CURSOR_SCALE = 1_000_000
TOKEN_KIND_SCALE = 1_000
TOKEN_VALUE_OFFSET = 500
CALL_CAPACITY = 730
CALL_ARGUMENT_CAPACITY = 746


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _trunc_div(numerator: int, denominator: int) -> int:
    quotient = abs(numerator) // denominator
    return -quotient if numerator < 0 else quotient


def _token_positions(source: str) -> list[tuple[Stage1Token, int, int]]:
    """Attach source start/end offsets to the shared Stage1 lexical model."""

    result: list[tuple[Stage1Token, int, int]] = []
    cursor = 0
    for token in stage1_tokens(source):
        while cursor < len(source) and source[cursor] in " \t\r":
            cursor += 1
        start = cursor
        end = cursor + len(token.text)
        result.append((token, start, end))
        cursor = end
    return result


def _decode_packed(next_cursor: int, kind: int, value: int) -> tuple[int, int, int, int]:
    packed = (
        next_cursor * TOKEN_CURSOR_SCALE
        + kind * TOKEN_KIND_SCALE
        + value
        + TOKEN_VALUE_OFFSET
    )
    decoded_next = _trunc_div(packed, TOKEN_CURSOR_SCALE)
    remainder = packed - decoded_next * TOKEN_CURSOR_SCALE
    decoded_kind = _trunc_div(remainder, TOKEN_KIND_SCALE)
    decoded_value = remainder - decoded_kind * TOKEN_KIND_SCALE - TOKEN_VALUE_OFFSET
    return packed, decoded_next, decoded_kind, decoded_value


def _execute(source: str, *, recover_numeric: bool) -> dict[str, object]:
    positioned = _token_positions(source)
    execution: list[tuple[Stage1Token, int]] = []
    first_lane_spill: dict[str, object] | None = None
    first_cursor_mismatch: dict[str, object] | None = None
    terminating_spill: dict[str, object] | None = None
    final_cursor = 0
    numeric_spills = 0

    # The legacy Stage1 execution model advances its own decoded cursor.  The
    # positioned lexical stream supplies token text/order while the decoded
    # cursor supplies the native loop's effective source position, matching the
    # already-qualified call-model oracle.
    effective_cursor = 0
    for token, lexical_start, lexical_end in positioned:
        while effective_cursor < len(source) and source[effective_cursor] in " \t\r":
            effective_cursor += 1
        actual_start = effective_cursor
        nominal_next = effective_cursor + len(token.text)
        packed_value = 0 if recover_numeric and token.kind == 2 else token.value
        packed, decoded_next, decoded_kind, decoded_value = _decode_packed(
            nominal_next, token.kind, packed_value
        )
        effective_value = token.value if recover_numeric and token.kind == 2 else decoded_value

        if token.kind == 2 and not (-500 <= token.value <= 499):
            numeric_spills += 1
            if first_lane_spill is None:
                first_lane_spill = {
                    "lexical_start": lexical_start,
                    "lexical_end": lexical_end,
                    "text": token.text,
                    "value": token.value,
                    "legacy_packed": _decode_packed(nominal_next, token.kind, token.value)[0],
                }

        if decoded_next != nominal_next and first_cursor_mismatch is None:
            first_cursor_mismatch = {
                "effective_start": actual_start,
                "lexical_start": lexical_start,
                "text": token.text,
                "value": token.value,
                "nominal_next": nominal_next,
                "decoded_next": decoded_next,
            }

        execution.append(
            (Stage1Token(decoded_kind, effective_value, token.text), actual_start)
        )
        final_cursor = decoded_next
        if decoded_next <= effective_cursor or decoded_next >= len(source):
            if decoded_next != nominal_next or decoded_next > len(source):
                terminating_spill = {
                    "effective_start": actual_start,
                    "lexical_start": lexical_start,
                    "text": token.text,
                    "value": token.value,
                    "nominal_next": nominal_next,
                    "decoded_next": decoded_next,
                    "packed": packed,
                }
            effective_cursor = decoded_next
            break
        effective_cursor = decoded_next

    if recover_numeric and positioned:
        # Candidate decoding should walk all lexical tokens.  Account for any
        # trailing Stage1 whitespace after the final token when reporting source
        # coverage.
        final_cursor = effective_cursor
        while final_cursor < len(source) and source[final_cursor] in " \t\r\n":
            final_cursor += 1

    return {
        "execution": execution,
        "lexical_token_count": len(positioned),
        "executed_token_count": len(execution),
        "numeric_lane_spill_count": numeric_spills,
        "first_numeric_lane_spill": first_lane_spill,
        "first_cursor_mismatch": first_cursor_mismatch,
        "terminating_spill": terminating_spill,
        "final_cursor": final_cursor,
        "source_bytes": len(source.encode("utf-8")),
        "source_characters": len(source),
        "full_character_coverage": final_cursor >= len(source),
    }


def _is_signature(tokens: list[Stage1Token], index: int) -> bool:
    return (
        index >= 2
        and tokens[index].kind == 4
        and tokens[index].value == 1
        and tokens[index - 1].kind == 1
        and tokens[index - 2].kind == 1
        and tokens[index - 2].text == "fn"
    )


def _call_model(execution: list[tuple[Stage1Token, int]]) -> dict[str, object]:
    tokens = [item[0] for item in execution]
    arities: list[int] = []
    active: list[int] = []
    identifier_open_candidates = 0
    signatures = 0
    maximum_depth = 0

    for index, token in enumerate(tokens):
        if token.kind in (1, 2) and active:
            arities[active[-1]] += 1

        if token.kind == 4 and token.value == 1:
            if index > 0 and tokens[index - 1].kind == 1:
                identifier_open_candidates += 1
                if _is_signature(tokens, index):
                    signatures += 1
                else:
                    active.append(len(arities))
                    arities.append(0)
                    maximum_depth = max(maximum_depth, len(active))
            continue
        if token.kind == 4 and token.value == 2:
            if active:
                active.pop()

    total_arguments = sum(arities)
    return {
        "identifier_open_candidates": identifier_open_candidates,
        "function_signatures": signatures,
        "calls": len(arities),
        "total_call_arguments": total_arguments,
        "max_call_arity": max(arities, default=0),
        "maximum_active_call_depth": maximum_depth,
        "active_calls_at_eof": len(active),
        "fits_current_call_capacity": len(arities) <= CALL_CAPACITY,
        "fits_current_call_argument_capacity": total_arguments <= CALL_ARGUMENT_CAPACITY,
        "required_call_capacity": len(arities),
        "required_call_argument_capacity": total_arguments,
    }


def audit(source: str) -> dict[str, object]:
    source_bytes = source.encode("utf-8")
    if _sha256(source_bytes) != BASELINE_SOURCE_SHA256:
        raise ValueError("token-lane audit requires the frozen canonical source")

    candidate = transform(source)
    legacy = _execute(source, recover_numeric=False)
    repaired_baseline = _execute(source, recover_numeric=True)
    repaired_candidate = _execute(candidate, recover_numeric=True)

    legacy_call_model = _call_model(legacy["execution"])
    repaired_baseline_call_model = _call_model(repaired_baseline["execution"])
    repaired_candidate_call_model = _call_model(repaired_candidate["execution"])

    guards = {
        "canonical_sha_matches": _sha256(source_bytes) == BASELINE_SOURCE_SHA256,
        "candidate_changes_no_function_signatures": source.count("fn ") == candidate.count("fn "),
        "candidate_changes_no_mut_declarations": source.count("mut ") == candidate.count("mut "),
        "legacy_has_numeric_lane_spill": int(legacy["numeric_lane_spill_count"]) > 0,
        "legacy_does_not_cover_full_source": legacy["full_character_coverage"] is False,
        "repaired_baseline_covers_full_source": repaired_baseline["full_character_coverage"] is True,
        "repaired_candidate_covers_full_source": repaired_candidate["full_character_coverage"] is True,
        "repaired_baseline_no_terminating_spill": repaired_baseline["terminating_spill"] is None,
        "repaired_candidate_no_terminating_spill": repaired_candidate["terminating_spill"] is None,
        "repaired_calls_close": repaired_candidate_call_model["active_calls_at_eof"] == 0,
    }
    static_pass = all(guards.values())

    if not static_pass:
        status = "STATIC_WIDE_TOKEN_LANE_FAIL"
        next_gate = "FIX_WIDE_TOKEN_LANE_STATIC_MODEL"
    elif not repaired_candidate_call_model["fits_current_call_capacity"]:
        status = "STATIC_WIDE_TOKEN_LANE_PASS_CALL_CAPACITY_ROUTE_REQUIRED"
        next_gate = "EXPAND_CALL_CAPACITY_FROM_FULL_SOURCE_TOKEN_LANE_MODEL"
    elif not repaired_candidate_call_model["fits_current_call_argument_capacity"]:
        status = "STATIC_WIDE_TOKEN_LANE_PASS_CALL_ARGUMENT_CAPACITY_ROUTE_REQUIRED"
        next_gate = "EXPAND_CALL_ARGUMENT_CAPACITY_FROM_FULL_SOURCE_TOKEN_LANE_MODEL"
    else:
        status = "STATIC_WIDE_TOKEN_LANE_PASS_NATIVE_QUALIFICATION_REQUIRED"
        next_gate = "QUALIFY_WIDE_TOKEN_LANE_NATIVE"

    return {
        "schema": "s3.selfhost.packed-token-lane-static-audit.v1",
        "status": status,
        "native_evidence": False,
        "canonical_source_mutated": False,
        "canonical": {
            "source_sha256": _sha256(source_bytes),
            "source_bytes": len(source_bytes),
        },
        "candidate": {
            "source_sha256": _sha256(candidate.encode("utf-8")),
            "source_bytes": len(candidate.encode("utf-8")),
            "new_function_signatures": candidate.count("fn ") - source.count("fn "),
            "new_mut_declarations": candidate.count("mut ") - source.count("mut "),
        },
        "legacy": {
            key: value for key, value in legacy.items() if key != "execution"
        },
        "repaired_baseline_model": {
            **{key: value for key, value in repaired_baseline.items() if key != "execution"},
            "call_model": repaired_baseline_call_model,
        },
        "repaired_candidate_model": {
            **{key: value for key, value in repaired_candidate.items() if key != "execution"},
            "call_model": repaired_candidate_call_model,
        },
        "legacy_call_model": legacy_call_model,
        "guards": guards,
        "next": next_gate,
        "qualification_rule": (
            "Static full-source coverage is necessary but not native evidence. "
            "The exact candidate must be built and executed on Linux x86-64, and "
            "all newly exposed full-source capacity requirements must be resolved "
            "without truncation before compaction/IR-v2 qualification resumes."
        ),
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
    print(f"LEGACY_FINAL_CURSOR={result['legacy']['final_cursor']}")
    print(f"LEGACY_FULL_COVERAGE={result['legacy']['full_character_coverage']}")
    print(f"REPAIRED_FULL_COVERAGE={result['repaired_candidate_model']['full_character_coverage']}")
    model = result["repaired_candidate_model"]["call_model"]
    print(f"FULL_SOURCE_CALLS={model['calls']}")
    print(f"FULL_SOURCE_CALL_ARGUMENTS={model['total_call_arguments']}")
    print(f"FULL_SOURCE_MAX_ARITY={model['max_call_arity']}")
    print(f"NEXT={result['next']}")
    print("CANONICAL_SOURCE_MUTATED=False")
    return 0 if str(result["status"]).startswith("STATIC_WIDE_TOKEN_LANE_PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())
