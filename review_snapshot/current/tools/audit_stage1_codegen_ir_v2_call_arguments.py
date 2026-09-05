"""Static Stage1 call-argument pressure model for IR-v2 planning.

The closure file is a historical native snapshot, not a claim about every
future canonical source. This tool keeps that snapshot auditable while also
reporting the current source's independent structural capacity model. The
historical agreement gate is never promoted to current-source native evidence;
fresh native closure evidence is required after the source identity changes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from tools.preflight_stage1_codegen_ir_v2_locals import Stage1Token, stage1_tokens


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "selfhost" / "compiler" / "s3c_stage1.s3"
CLOSURE = ROOT / "reports" / "selfhost" / "stage1" / "call-argument-pool-closure.json"
DEFAULT_REPORT = (
    ROOT / "reports" / "selfhost" / "stage1" /
    "codegen-ir-v2-call-argument-static-audit.json"
)

# These are the physical resident capacities of the historical two-lane
# closure. They are not limits on the number of call/argument occurrences in
# a streamed source model.
CALL_MAX_RESIDENT = 730
ARG_MAX_RESIDENT = 746

# The host loads at most this many source bytes. Every modeled call and every
# modeled argument consumes source, so this is a finite structural upper
# bound for totals without deriving support from today's canonical counts.
STAGE1_MAX_SOURCE_BYTES = 262_144
TOTAL_CALL_MODEL_LIMIT = STAGE1_MAX_SOURCE_BYTES
TOTAL_ARGUMENT_MODEL_LIMIT = STAGE1_MAX_SOURCE_BYTES
MODEL_CHUNK_SIZE = 365

# Keep the historical names import-compatible, but make their resident
# meaning explicit in the model fields below.
CALL_CAPACITY = CALL_MAX_RESIDENT
CALL_ARGUMENT_CAPACITY = ARG_MAX_RESIDENT
EXPECTED_CANONICAL_CALLS = 656
EXPECTED_CANONICAL_ARGUMENTS = 736
EXPECTED_CANONICAL_MAX_ARITY = 4
EXPECTED_CANONICAL_ARITY_DISTRIBUTION = {
    "0": 1,
    "1": 617,
    "2": 15,
    "3": 3,
    "4_plus": 20,
}

_TOKEN_CURSOR_SCALE = 1_000_000
_TOKEN_KIND_SCALE = 1_000
_TOKEN_VALUE_OFFSET = 500


class CallArgumentModelError(RuntimeError):
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_function_signature_open(tokens: list[Stage1Token], index: int) -> bool:
    """Return True for the `(` in `fn name(` / `foreign fn name(`."""

    if index < 2:
        return False
    token = tokens[index]
    if token.kind != 4 or token.value != 1:
        return False
    name = tokens[index - 1]
    before_name = tokens[index - 2]
    return (
        name.kind == 1
        and before_name.kind == 1
        and before_name.text == "fn"
    )


def _truncating_division(numerator: int, denominator: int) -> int:
    """Mirror S3 integer division, which truncates toward zero."""

    quotient = abs(numerator) // denominator
    return -quotient if numerator < 0 else quotient


def _stage1_execution_tokens(source: str) -> list[tuple[Stage1Token, int]]:
    """Reproduce the token values the native Stage1 loop actually receives.

    ``scan_token`` returns one packed integer.  Its cursor/kind/value lanes are
    only lossless while the token value fits the value lane.  The canonical
    source currently reaches a wide numeric literal in ``pack_ir_record``;
    native decoding then advances past the remaining input.  Modeling the pack
    and decode step here keeps the static oracle aligned with that real Stage1
    contract and prevents it from inventing events after native scanning has
    terminated.
    """

    lexical_tokens = stage1_tokens(source)
    execution_tokens: list[tuple[Stage1Token, int]] = []
    cursor = 0
    for token in lexical_tokens:
        while cursor < len(source) and source[cursor] in " \t\r":
            cursor += 1
        actual_start = cursor
        next_cursor = cursor + len(token.text)
        packed = (
            next_cursor * _TOKEN_CURSOR_SCALE
            + token.kind * _TOKEN_KIND_SCALE
            + token.value
            + _TOKEN_VALUE_OFFSET
        )
        decoded_next_cursor = _truncating_division(packed, _TOKEN_CURSOR_SCALE)
        remainder = packed - decoded_next_cursor * _TOKEN_CURSOR_SCALE
        decoded_kind = _truncating_division(remainder, _TOKEN_KIND_SCALE)
        decoded_value = (
            remainder - decoded_kind * _TOKEN_KIND_SCALE - _TOKEN_VALUE_OFFSET
        )
        execution_tokens.append(
            (Stage1Token(decoded_kind, decoded_value, token.text), actual_start)
        )
        if decoded_next_cursor <= cursor:
            break
        cursor = decoded_next_cursor
        if cursor >= len(source):
            break
    return execution_tokens


def collect_call_argument_trace(source: str) -> dict[str, object]:
    """Collect decisions and bounded call metadata from the Stage1 token flow."""

    execution_tokens = _stage1_execution_tokens(source)
    tokens = [token for token, _ in execution_tokens]
    arities: list[int] = []
    active: list[int] = []
    events: list[tuple[int, int, int, int, int]] = []
    identifier_open_candidates = 0
    function_signatures = 0
    maximum_depth = 0
    maximum_active_argument_records = 0

    for index, token in enumerate(tokens):
        actual_start = execution_tokens[index][1]
        if token.kind in (1, 2) and active:
            arities[active[-1]] += 1
            active_argument_records = 0
            for call_id in active:
                active_argument_records += arities[call_id]
            maximum_active_argument_records = max(
                maximum_active_argument_records,
                active_argument_records,
            )
            events.append((2, actual_start, token.kind, token.value, len(active)))

        if token.kind == 4 and token.value == 1:
            previous_is_identifier = index > 0 and tokens[index - 1].kind == 1
            if previous_is_identifier:
                identifier_open_candidates += 1
                if _is_function_signature_open(tokens, index):
                    function_signatures += 1
                else:
                    call_id = len(arities)
                    arities.append(0)
                    events.append(
                        (1, actual_start, tokens[index - 1].kind, tokens[index - 1].value, len(active))
                    )
                    active.append(call_id)
                    maximum_depth = max(maximum_depth, len(active))
            continue

        if token.kind == 4 and token.value == 2:
            if active:
                active.pop()
            # Stage1 closes one active call level for every ')' even when a
            # grouping parenthesis did not open a call level.
            continue

    return {
        "arities": arities,
        "events": events,
        "identifier_open_candidates": identifier_open_candidates,
        "function_signatures": function_signatures,
        "maximum_active_call_depth": maximum_depth,
        "maximum_active_call_records": maximum_depth,
        "maximum_active_argument_records": maximum_active_argument_records,
        "active_calls_at_eof": len(active),
        "last_token_offset": execution_tokens[-1][1] if execution_tokens else None,
    }


def collect_call_argument_model(source: str) -> dict[str, object]:
    """Mirror Stage1's bounded call stack/argument occurrence accounting."""

    trace = collect_call_argument_trace(source)
    arities = trace["arities"]
    assert isinstance(arities, list)
    total_arguments = sum(arities)
    distribution = {"0": 0, "1": 0, "2": 0, "3": 0, "4_plus": 0}
    for value in arities:
        if value == 0:
            distribution["0"] += 1
        elif value == 1:
            distribution["1"] += 1
        elif value == 2:
            distribution["2"] += 1
        elif value == 3:
            distribution["3"] += 1
        else:
            distribution["4_plus"] += 1
    capacity = evaluate_model_capacity(
        calls=len(arities),
        total_arguments=total_arguments,
        maximum_active_call_records=int(trace["maximum_active_call_records"]),
        maximum_active_argument_records=int(
            trace["maximum_active_argument_records"]
        ),
        active_calls_at_eof=int(trace["active_calls_at_eof"]),
    )
    return {
        "calls": len(arities),
        "total_call_arguments": total_arguments,
        "max_call_arity": max(arities, default=0),
        "arity_distribution": distribution,
        "maximum_active_call_depth": trace["maximum_active_call_depth"],
        "maximum_active_call_records": trace["maximum_active_call_records"],
        "maximum_active_argument_records": trace[
            "maximum_active_argument_records"
        ],
        "active_calls_at_eof": trace["active_calls_at_eof"],
        **capacity,
    }


def evaluate_model_capacity(
    *,
    calls: int,
    total_arguments: int,
    maximum_active_call_records: int,
    maximum_active_argument_records: int,
    active_calls_at_eof: int,
) -> dict[str, object]:
    """Evaluate total support separately from physical resident occupancy."""

    nonnegative = (
        calls >= 0
        and total_arguments >= 0
        and maximum_active_call_records >= 0
        and maximum_active_argument_records >= 0
        and active_calls_at_eof >= 0
    )
    total_call_supported = nonnegative and calls <= TOTAL_CALL_MODEL_LIMIT
    total_argument_supported = (
        nonnegative and total_arguments <= TOTAL_ARGUMENT_MODEL_LIMIT
    )
    resident_call_supported = (
        nonnegative and maximum_active_call_records <= CALL_MAX_RESIDENT
    )
    resident_argument_supported = (
        nonnegative and maximum_active_argument_records <= ARG_MAX_RESIDENT
    )
    count_relation_valid = (
        nonnegative
        and maximum_active_call_records <= calls
        and maximum_active_argument_records <= total_arguments
    )
    complete_call_units = active_calls_at_eof == 0
    call_replay_chunks = (
        0
        if calls == 0
        else (calls + MODEL_CHUNK_SIZE - 1) // MODEL_CHUNK_SIZE
    )
    argument_replay_chunks = (
        0
        if total_arguments == 0
        else (total_arguments + MODEL_CHUNK_SIZE - 1) // MODEL_CHUNK_SIZE
    )
    return {
        "call_capacity": CALL_MAX_RESIDENT,
        "call_argument_capacity": ARG_MAX_RESIDENT,
        "call_max_resident": CALL_MAX_RESIDENT,
        "argument_max_resident": ARG_MAX_RESIDENT,
        "total_call_model_limit": TOTAL_CALL_MODEL_LIMIT,
        "total_argument_model_limit": TOTAL_ARGUMENT_MODEL_LIMIT,
        "model_chunk_size": MODEL_CHUNK_SIZE,
        "call_replay_chunks": call_replay_chunks,
        "argument_replay_chunks": argument_replay_chunks,
        "call_total_headroom": TOTAL_CALL_MODEL_LIMIT - calls,
        "argument_total_headroom": TOTAL_ARGUMENT_MODEL_LIMIT - total_arguments,
        "call_resident_headroom": CALL_MAX_RESIDENT
        - maximum_active_call_records,
        "argument_resident_headroom": ARG_MAX_RESIDENT
        - maximum_active_argument_records,
        "call_headroom": CALL_MAX_RESIDENT - maximum_active_call_records,
        "call_argument_headroom": ARG_MAX_RESIDENT
        - maximum_active_argument_records,
        "fits_total_call_model": total_call_supported,
        "fits_total_argument_model": total_argument_supported,
        "fits_call_resident_capacity": resident_call_supported,
        "fits_argument_resident_capacity": resident_argument_supported,
        "fits_call_capacity": resident_call_supported,
        "fits_call_argument_capacity": resident_argument_supported,
        "call_argument_count_relation_valid": count_relation_valid,
        "complete_call_units": complete_call_units,
        "capacity_safe": (
            total_call_supported
            and total_argument_supported
            and resident_call_supported
            and resident_argument_supported
            and count_relation_valid
            and complete_call_units
        ),
    }


def _load_closure(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CallArgumentModelError("call-argument closure must be a JSON object")
    return value


def validate_canonical_model(
    source_bytes: bytes,
    *,
    closure: dict[str, Any],
) -> tuple[dict[str, object], dict[str, bool]]:
    clean = closure.get("clean_source_gate")
    runtime = closure.get("runtime_measurement")
    pool = closure.get("pool")
    if not isinstance(clean, dict) or not isinstance(runtime, dict) or not isinstance(pool, dict):
        raise CallArgumentModelError("call-argument closure is missing required sections")

    model = collect_call_argument_model(source_bytes.decode("utf-8"))
    guards = {
        "source_sha_matches_native_closure": clean.get("source_sha256") == _sha256(source_bytes),
        "source_bytes_match_native_closure": clean.get("source_size_bytes") == len(source_bytes),
        "closure_pool_capacity_is_746": pool.get("selected_capacity") == ARG_MAX_RESIDENT,
        "model_calls_match_native": model["calls"] == runtime.get("total_calls") == EXPECTED_CANONICAL_CALLS,
        "model_arguments_match_native": (
            model["total_call_arguments"]
            == runtime.get("total_call_arguments")
            == EXPECTED_CANONICAL_ARGUMENTS
        ),
        "model_max_arity_matches_native": (
            model["max_call_arity"]
            == runtime.get("max_call_arity")
            == EXPECTED_CANONICAL_MAX_ARITY
        ),
        "model_distribution_matches_native": (
            model["arity_distribution"]
            == runtime.get("arity_distribution")
            == EXPECTED_CANONICAL_ARITY_DISTRIBUTION
        ),
        "model_call_depth_within_stage1_bound": int(model["maximum_active_call_depth"]) <= 16,
        "model_has_no_unclosed_calls": model["active_calls_at_eof"] == 0,
        "model_total_call_capacity_supported": model["fits_total_call_model"] is True,
        "model_total_argument_capacity_supported": model["fits_total_argument_model"] is True,
        "model_call_resident_capacity_supported": model["fits_call_resident_capacity"] is True,
        "model_argument_resident_capacity_supported": model["fits_argument_resident_capacity"] is True,
        "model_call_argument_count_relation_valid": model[
            "call_argument_count_relation_valid"
        ] is True,
    }
    return model, guards


def audit(
    *,
    canonical_source: str,
    closure: dict[str, Any],
    local_candidate: str | None = None,
) -> dict[str, object]:
    canonical_bytes = canonical_source.encode("utf-8")
    canonical_model, canonical_guards = validate_canonical_model(
        canonical_bytes,
        closure=closure,
    )
    canonical_pass = all(canonical_guards.values())
    current_source_safe = bool(
        canonical_model["fits_total_call_model"]
        and canonical_model["fits_total_argument_model"]
        and canonical_model["fits_call_resident_capacity"]
        and canonical_model["fits_argument_resident_capacity"]
        and canonical_model["call_argument_count_relation_valid"]
        and int(canonical_model["maximum_active_call_depth"]) <= 16
        and canonical_model["active_calls_at_eof"] == 0
    )

    clean = closure["clean_source_gate"]
    runtime = closure["runtime_measurement"]
    pool = closure["pool"]
    historical_snapshot = {
        "classification": "HISTORICAL_SNAPSHOT_CONTRACT",
        "source_sha256": clean["source_sha256"],
        "source_bytes": clean["source_size_bytes"],
        "calls": runtime["total_calls"],
        "total_call_arguments": runtime["total_call_arguments"],
        "max_call_arity": runtime["max_call_arity"],
        "arity_distribution": runtime["arity_distribution"],
        "selected_capacity": pool["selected_capacity"],
        "source_match_current_canonical": canonical_guards[
            "source_sha_matches_native_closure"
        ],
        "bytes_match_current_canonical": canonical_guards[
            "source_bytes_match_native_closure"
        ],
    }

    local_model: dict[str, object] | None = None
    local_safe: bool | None = None
    if local_candidate is not None:
        local_model = collect_call_argument_model(local_candidate)
        local_safe = bool(
            local_model["fits_total_call_model"]
            and local_model["fits_total_argument_model"]
            and local_model["fits_call_resident_capacity"]
            and local_model["fits_argument_resident_capacity"]
            and local_model["call_argument_count_relation_valid"]
            and int(local_model["maximum_active_call_depth"]) <= 16
            and local_model["active_calls_at_eof"] == 0
        )

    if not current_source_safe:
        status = "BLOCKED_CURRENT_CANONICAL_CALL_ARGUMENT_CAPACITY"
        next_gate = "EXTEND_CALL_ARGUMENT_POOL_FROM_CURRENT_SOURCE_REQUIREMENT"
    elif not canonical_pass:
        status = "CURRENT_TOTAL_MODEL_SUPPORTED_REQUIRES_FRESH_NATIVE_CALL_ARGUMENT_RECONCILIATION"
        next_gate = "FRESH_NATIVE_CALL_ARGUMENT_CLOSURE_FOR_CURRENT_CANONICAL_SOURCE"
    elif local_candidate is not None and local_safe is False:
        status = "ROUTE_CALL_ARGUMENT_CAPACITY_BEFORE_LOCAL_NATIVE"
        next_gate = "EXTEND_CALL_ARGUMENT_POOL_FROM_EXACT_LOCAL_CANDIDATE_REQUIREMENT"
    else:
        status = "PASS_STATIC_CALL_ARGUMENT_MODEL"
        next_gate = "CONTINUE_PREPARED_NATIVE_CANDIDATE_CHAIN"

    return {
        "schema": "s3.selfhost.codegen-ir-v2-call-argument-static-audit.v1",
        "status": status,
        "native_evidence": False,
        "canonical_source_mutated": False,
        "canonical": {
            "source_sha256": _sha256(canonical_bytes),
            "source_bytes": len(canonical_bytes),
            "model": canonical_model,
            "native_closure_guards": canonical_guards,
            "model_validated_against_native_closure": canonical_pass,
            "historical_snapshot": historical_snapshot,
            "capacity_safe_under_current_limits": current_source_safe,
        },
        "parameter_candidate": {
            "status": "NOT_APPLICABLE_HISTORICAL_PARAMETER_TRANSFORM",
            "source_sha256": None,
            "source_bytes": None,
            "model": None,
            "safe_under_current_call_and_argument_capacities": None,
            "reason": (
                "The historical compaction+parameter transformation depends on "
                "anchors absent from the current canonical source; it is not "
                "reapplied to manufacture a candidate."
            ),
        },
        "local_candidate": None
        if local_model is None
        else {
            "source_sha256": _sha256(local_candidate.encode("utf-8")),
            "source_bytes": len(local_candidate.encode("utf-8")),
            "model": local_model,
            "safe_under_current_call_and_argument_capacities": local_safe,
        },
        "next": next_gate,
        "qualification_rule": (
            "The closure is a historical source-identified snapshot. Current-source capacity is reported independently, and any changed source requires fresh native call/argument closure evidence before promotion. Historical parameter transforms are not reapplied when their anchors are absent."
        ),
        "stage2": "NOT_STARTED",
        "stage3": "NOT_STARTED",
        "full_self_hosting": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--closure", type=Path, default=CLOSURE)
    parser.add_argument("--local-candidate", type=Path)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)

    canonical = args.source.resolve().read_text(encoding="utf-8")
    closure = _load_closure(args.closure.resolve())
    local_candidate = (
        args.local_candidate.resolve().read_text(encoding="utf-8")
        if args.local_candidate is not None
        else None
    )
    result = audit(
        canonical_source=canonical,
        closure=closure,
        local_candidate=local_candidate,
    )
    destination = args.report.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    print(f"REPORT={destination}")
    print(f"STATUS={result['status']}")
    canonical_model = result["canonical"]["model"]
    parameter_model = result["parameter_candidate"]["model"]
    print(f"CANONICAL_CALLS={canonical_model['calls']}")
    print(f"CANONICAL_CALL_ARGUMENTS={canonical_model['total_call_arguments']}")
    if parameter_model is None:
        print("PARAMETER_CALLS=NOT_APPLICABLE")
        print("PARAMETER_CALL_ARGUMENTS=NOT_APPLICABLE")
        print("PARAMETER_CALL_ARGUMENT_HEADROOM=NOT_APPLICABLE")
    else:
        print(f"PARAMETER_CALLS={parameter_model['calls']}")
        print(f"PARAMETER_CALL_ARGUMENTS={parameter_model['total_call_arguments']}")
        print(f"PARAMETER_CALL_ARGUMENT_HEADROOM={parameter_model['call_argument_headroom']}")
    if result["local_candidate"] is not None:
        local_model = result["local_candidate"]["model"]
        print(f"LOCAL_CALLS={local_model['calls']}")
        print(f"LOCAL_CALL_ARGUMENTS={local_model['total_call_arguments']}")
        print(f"LOCAL_CALL_ARGUMENT_HEADROOM={local_model['call_argument_headroom']}")
    print(f"NEXT={result['next']}")
    print("CANONICAL_SOURCE_MUTATED=False")
    return 0 if result["status"] == "PASS_STATIC_CALL_ARGUMENT_MODEL" else 2


if __name__ == "__main__":
    raise SystemExit(main())
