"""Exact static preflight for the Stage1 IR-v2 local-metadata candidate.

The preflight consumes a PASS native packed-parameter report before it will even
construct the local candidate. It rebuilds the exact parameter source, validates
its SHA, mirrors the Stage1 lexical/hash model, checks that native counts agree
with that model, builds the local candidate in memory, selects the smallest exact
bounded local-record capacity, and projects the candidate against *native*
parameter headroom.

No source is promoted and no native PASS is claimed here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools.audit_stage1_codegen_ir_v2_local_metadata import (
    EXTENT_DOMAIN,
    MAX_LOCAL_RECORDS,
    audit as audit_local_design,
)
from tools.patch_stage1_codegen_ir_v2_locals import (
    LocalCandidateError,
    SOURCE,
    _load_report,
    transform_locals,
    validate_parameter_prerequisite,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PARAMETER_REPORT = (
    ROOT / "reports" / "selfhost" / "stage1" /
    "codegen-ir-v2-parameters-native-candidate.json"
)
DEFAULT_REPORT = (
    ROOT / "reports" / "selfhost" / "stage1" /
    "codegen-ir-v2-locals-static-preflight.json"
)

EVENT_CAPACITY = 1460
VALUE_CAPACITY = 1460
BLOCK_CAPACITY = 365
CALL_CAPACITY = 730
PARAMETER_VALUE_DOMAIN = 64

# Stage1 source-level identifier hashes used as structural keywords.
KEYWORD_HASHES = {
    342: "return",
    162: "while",
    135: "match",
    37: "break",
    220: "discard",
    87: "mut",
    352: "fn",
    311: "foreign",
}
EVENT_IDENTIFIER_HASHES_AFTER_DISCARD_COMPACTION = {342, 162, 135, 37, 87}
EVENT_PUNCT_VALUES = {5, 6, 7, 8, 9, 13, 14, 15, 16, 17}
VALID_TYPE_HASHES = {66, 313, 76}


@dataclass(frozen=True)
class Stage1Token:
    kind: int
    value: int
    text: str


def identifier_hash_text(text: str) -> int:
    result = 0
    for char in text:
        result = result * 31 + ord(char)
        while result >= 365:
            result -= 365
    return result


def _identifier_start(char: str) -> bool:
    return char.isascii() and (char.isalpha() or char == "_")


def _identifier_continue(char: str) -> bool:
    return _identifier_start(char) or (char.isascii() and char.isdigit())


def stage1_tokens(source: str) -> list[Stage1Token]:
    """Mirror the S3 Stage1 ``scan_token`` subset used by the canonical source."""

    tokens: list[Stage1Token] = []
    position = 0
    length = len(source)
    while position < length:
        while position < length and source[position] in " \t\r":
            position += 1
        if position >= length:
            break
        char = source[position]
        if char == "\n":
            tokens.append(Stage1Token(3, 0, "\n"))
            position += 1
            continue
        if _identifier_start(char):
            end = position + 1
            while end < length and _identifier_continue(source[end]):
                end += 1
            text = source[position:end]
            tokens.append(Stage1Token(1, identifier_hash_text(text), text))
            position = end
            continue

        negative = 1
        number_position = position
        if char == "-" and position + 1 < length and source[position + 1].isdigit():
            negative = -1
            number_position += 1
        if number_position < length and source[number_position].isdigit():
            end = number_position
            number = 0
            while end < length and source[end].isdigit():
                number = number * 10 + (ord(source[end]) - 48)
                end += 1
            text = source[position:end]
            tokens.append(Stage1Token(2, number * negative, text))
            position = end
            continue

        if source.startswith("->", position):
            tokens.append(Stage1Token(4, 12, "->"))
            position += 2
            continue
        if source.startswith("==", position):
            tokens.append(Stage1Token(4, 13, "=="))
            position += 2
            continue
        if source.startswith("+=", position):
            tokens.append(Stage1Token(4, 14, "+="))
            position += 2
            continue
        if source.startswith("<=>", position):
            tokens.append(Stage1Token(4, 15, "<=>"))
            position += 3
            continue

        punctuation = {
            "(": 1,
            ")": 2,
            ":": 3,
            ",": 4,
            "=": 5,
            "+": 6,
            "-": 7,
            "*": 8,
            "/": 9,
            "[": 10,
            "]": 11,
            "<": 16,
            ">": 17,
        }
        value = punctuation.get(char)
        if value is None:
            tokens.append(Stage1Token(9, ord(char), char))
        else:
            tokens.append(Stage1Token(4, value, char))
        position += 1
    return tokens


def _call_count(tokens: list[Stage1Token]) -> int:
    count = 0
    for index, token in enumerate(tokens):
        if token.kind != 4 or token.value != 1 or index == 0:
            continue
        previous = tokens[index - 1]
        if previous.kind != 1:
            continue
        # Function declaration: fn <name>( ... ) is not a call.
        if index >= 2:
            before_name = tokens[index - 2]
            if before_name.kind == 1 and before_name.value == 352:
                continue
        count += 1
    return count


def _declarations(tokens: list[Stage1Token]) -> tuple[list[dict[str, object]], list[str]]:
    declarations: list[dict[str, object]] = []
    errors: list[str] = []
    current_function = "<none>"
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token.kind == 1 and token.text == "fn":
            if index + 1 < len(tokens) and tokens[index + 1].kind == 1:
                current_function = tokens[index + 1].text
        if token.kind == 1 and token.text == "foreign":
            if index + 1 < len(tokens) and tokens[index + 1].kind == 1 and tokens[index + 1].text == "fn":
                current_function = "<foreign>"

        if token.kind != 1 or token.text != "mut":
            index += 1
            continue
        start = index
        if index + 4 >= len(tokens):
            errors.append(f"truncated mut declaration at token {start}")
            index += 1
            continue
        name = tokens[index + 1]
        colon = tokens[index + 2]
        type_token = tokens[index + 3]
        if name.kind != 1 or colon.kind != 4 or colon.value != 3 or type_token.kind != 1:
            errors.append(f"unsupported mut declaration shape at token {start}")
            index += 1
            continue
        if type_token.value not in VALID_TYPE_HASHES:
            errors.append(f"invalid local type identity at token {start}: {type_token.text}")
            index += 1
            continue
        shape = tokens[index + 4]
        storage_kind = "SCALAR"
        extent = 1
        end = index + 4
        if shape.kind == 4 and shape.value == 5:
            pass
        elif shape.kind == 4 and shape.value == 10:
            if index + 7 >= len(tokens):
                errors.append(f"truncated fixed-array declaration at token {start}")
                index += 1
                continue
            extent_token = tokens[index + 5]
            right = tokens[index + 6]
            equal = tokens[index + 7]
            if (
                extent_token.kind != 2
                or extent_token.value <= 0
                or extent_token.value >= EXTENT_DOMAIN
                or right.kind != 4
                or right.value != 11
                or equal.kind != 4
                or equal.value != 5
            ):
                errors.append(f"unsupported fixed-array declaration shape at token {start}")
                index += 1
                continue
            storage_kind = "FIXED_ARRAY"
            extent = extent_token.value
            end = index + 7
        else:
            errors.append(f"local declaration missing '=' or fixed-array extent at token {start}")
            index += 1
            continue
        declarations.append(
            {
                "owner": current_function,
                "name": name.text,
                "name_hash": name.value,
                "type": type_token.text,
                "type_hash": type_token.value,
                "storage_kind": storage_kind,
                "extent": extent,
            }
        )
        index = end + 1
    return declarations, errors


def source_metrics(source: str) -> dict[str, object]:
    tokens = stage1_tokens(source)
    declarations, declaration_errors = _declarations(tokens)
    identifier_collisions: list[dict[str, object]] = []
    for token in tokens:
        if token.kind != 1:
            continue
        expected = KEYWORD_HASHES.get(token.value)
        if expected is not None and token.text != expected:
            identifier_collisions.append(
                {"text": token.text, "hash": token.value, "collides_with": expected}
            )

    local_name_collisions: list[dict[str, object]] = []
    seen_names: dict[tuple[str, int], str] = {}
    for declaration in declarations:
        key = (str(declaration["owner"]), int(declaration["name_hash"]))
        existing = seen_names.get(key)
        current = str(declaration["name"])
        if existing is not None and existing != current:
            local_name_collisions.append(
                {
                    "owner": key[0],
                    "hash": key[1],
                    "first": existing,
                    "second": current,
                }
            )
        else:
            seen_names[key] = current

    calls = _call_count(tokens)
    identifier_events = sum(
        1
        for token in tokens
        if token.kind == 1 and token.value in EVENT_IDENTIFIER_HASHES_AFTER_DISCARD_COMPACTION
    )
    punctuation_events = sum(
        1 for token in tokens if token.kind == 4 and token.value in EVENT_PUNCT_VALUES
    )
    hash87 = sum(1 for token in tokens if token.kind == 1 and token.value == 87)
    literal_mut = sum(1 for token in tokens if token.kind == 1 and token.text == "mut")
    matches = sum(1 for token in tokens if token.kind == 1 and token.value == 135)
    whiles = sum(1 for token in tokens if token.kind == 1 and token.value == 162)
    numeric = sum(1 for token in tokens if token.kind == 2)
    invalid = [token.text for token in tokens if token.kind == 9]
    function_signatures = sum(1 for token in tokens if token.kind == 1 and token.value == 352)
    maximum_extent = max((int(item["extent"]) for item in declarations), default=1)

    return {
        "token_count": len(tokens),
        "numeric_tokens": numeric,
        "match_hash_tokens": matches,
        "while_hash_tokens": whiles,
        "mut_hash_tokens": hash87,
        "literal_mut_tokens": literal_mut,
        "function_signature_hash_tokens": function_signatures,
        "call_syntax_count": calls,
        "structural_event_tokens": identifier_events + punctuation_events + calls,
        "identifier_keyword_hash_collisions": identifier_collisions,
        "local_name_hash_collisions_within_owner": local_name_collisions,
        "local_declarations": declarations,
        "local_declaration_count": len(declarations),
        "local_declaration_errors": declaration_errors,
        "maximum_local_extent": maximum_extent,
        "invalid_stage1_tokens": invalid,
    }


def _delta(after: dict[str, object], before: dict[str, object], key: str) -> int:
    left = after.get(key)
    right = before.get(key)
    if not isinstance(left, int) or isinstance(left, bool):
        raise LocalCandidateError(f"invalid after metric: {key}")
    if not isinstance(right, int) or isinstance(right, bool):
        raise LocalCandidateError(f"invalid before metric: {key}")
    return left - right


def build_preflight(parameter_report: dict[str, Any], *, canonical_source: str) -> dict[str, object]:
    parameter_source, native = validate_parameter_prerequisite(
        parameter_report,
        canonical_source=canonical_source,
    )
    design = audit_local_design(parameter_source)
    base = source_metrics(parameter_source)

    native_model_guards = {
        "local_count_matches_stage1_hash87_tokens": native["local_count"] == base["mut_hash_tokens"],
        "value_count_matches_stage1_numeric_tokens": native["ir_value_count"] == base["numeric_tokens"],
        "instruction_count_matches_stage1_event_model": (
            native["ir_instruction_count"] == base["structural_event_tokens"]
        ),
        "call_count_matches_stage1_call_model": native["ast_call_count"] == base["call_syntax_count"],
    }
    declaration_guards = {
        "literal_mut_equals_hash87": base["literal_mut_tokens"] == base["mut_hash_tokens"],
        "every_literal_mut_has_supported_declaration_shape": (
            base["local_declaration_count"] == base["literal_mut_tokens"]
            and not base["local_declaration_errors"]
        ),
        "no_stage1_keyword_hash_collisions": not base["identifier_keyword_hash_collisions"],
        "no_local_name_hash_collisions_within_owner": not base[
            "local_name_hash_collisions_within_owner"
        ],
        "no_invalid_stage1_tokens": not base["invalid_stage1_tokens"],
        "local_design_contract_pass": design.get("status") == "STATIC_LOCAL_METADATA_DESIGN_PASS",
    }

    # Build once at the maximum single-bank capacity to learn the exact number of
    # local declarations introduced by the candidate itself. Capacity changes the
    # zero initializer length but not the number of `mut` declarations.
    provisional = transform_locals(parameter_source, local_capacity=MAX_LOCAL_RECORDS)
    provisional_metrics = source_metrics(provisional)
    required_records = int(provisional_metrics["mut_hash_tokens"])
    required_fits_single_bank = 0 < required_records <= MAX_LOCAL_RECORDS

    selected_capacity: int | None = required_records if required_fits_single_bank else None
    final_candidate: str | None = None
    final_metrics: dict[str, object] | None = None
    if selected_capacity is not None:
        final_candidate = transform_locals(parameter_source, local_capacity=selected_capacity)
        final_metrics = source_metrics(final_candidate)
        if final_metrics["mut_hash_tokens"] != required_records:
            raise LocalCandidateError("local candidate local-count changed after exact capacity selection")

    if final_metrics is None:
        exact_delta: dict[str, int | None] = {
            key: None
            for key in (
                "token_count",
                "numeric_tokens",
                "match_hash_tokens",
                "while_hash_tokens",
                "mut_hash_tokens",
                "function_signature_hash_tokens",
                "call_syntax_count",
                "structural_event_tokens",
            )
        }
    else:
        exact_delta = {
            key: _delta(final_metrics, base, key)
            for key in (
                "token_count",
                "numeric_tokens",
                "match_hash_tokens",
                "while_hash_tokens",
                "mut_hash_tokens",
                "function_signature_hash_tokens",
                "call_syntax_count",
                "structural_event_tokens",
            )
        }

    projections: dict[str, int | None] = {
        "events": None,
        "values": None,
        "blocks": None,
        "calls": None,
    }
    capacity_guards: dict[str, bool] = {
        "required_local_records_fit_single_365_bank": required_fits_single_bank,
        "candidate_local_value_ids_fit_value_domain": (
            required_fits_single_bank and PARAMETER_VALUE_DOMAIN + required_records < VALUE_CAPACITY
        ),
        "candidate_fixed_extents_fit_record_domain": (
            final_metrics is not None
            and int(final_metrics["maximum_local_extent"]) < EXTENT_DOMAIN
        ),
        "candidate_function_signature_delta_is_zero": (
            exact_delta["function_signature_hash_tokens"] == 0
        ),
        "candidate_declarations_are_all_supported": (
            final_metrics is not None
            and not final_metrics["local_declaration_errors"]
            and final_metrics["local_declaration_count"] == final_metrics["literal_mut_tokens"]
        ),
        "candidate_has_no_keyword_hash_collisions": (
            final_metrics is not None and not final_metrics["identifier_keyword_hash_collisions"]
        ),
        "candidate_has_no_local_name_hash_collisions": (
            final_metrics is not None
            and not final_metrics["local_name_hash_collisions_within_owner"]
        ),
        "candidate_has_no_invalid_stage1_tokens": (
            final_metrics is not None and not final_metrics["invalid_stage1_tokens"]
        ),
    }

    if final_metrics is not None:
        projections = {
            "events": native["ir_instruction_count"] + int(exact_delta["structural_event_tokens"]),
            "values": native["ir_value_count"] + int(exact_delta["numeric_tokens"]),
            "blocks": native["ir_block_count"]
            + 3
            * (
                int(exact_delta["match_hash_tokens"])
                + int(exact_delta["while_hash_tokens"])
            ),
            "calls": native["ast_call_count"] + int(exact_delta["call_syntax_count"]),
        }
        capacity_guards.update(
            {
                "projected_events_below_1460": int(projections["events"]) < EVENT_CAPACITY,
                "projected_values_below_1460": int(projections["values"]) < VALUE_CAPACITY,
                "projected_blocks_below_365": int(projections["blocks"]) < BLOCK_CAPACITY,
                "projected_calls_below_730": int(projections["calls"]) < CALL_CAPACITY,
            }
        )
    else:
        capacity_guards.update(
            {
                "projected_events_below_1460": False,
                "projected_values_below_1460": False,
                "projected_blocks_below_365": False,
                "projected_calls_below_730": False,
            }
        )

    model_pass = all(native_model_guards.values())
    declarations_pass = all(declaration_guards.values())
    candidate_shape_pass = all(
        capacity_guards[key]
        for key in (
            "required_local_records_fit_single_365_bank",
            "candidate_local_value_ids_fit_value_domain",
            "candidate_fixed_extents_fit_record_domain",
            "candidate_function_signature_delta_is_zero",
            "candidate_declarations_are_all_supported",
            "candidate_has_no_keyword_hash_collisions",
            "candidate_has_no_local_name_hash_collisions",
            "candidate_has_no_invalid_stage1_tokens",
        )
    )

    if not model_pass:
        status = "BLOCKED_STAGE1_NATIVE_LEXICAL_MODEL_MISMATCH"
        next_gate = "RECONCILE_NATIVE_LOCAL_VALUE_EVENT_CALL_COUNTS_BEFORE_LOCAL_IR_V2"
    elif not declarations_pass:
        status = "BLOCKED_LOCAL_DECLARATION_IDENTITY_MODEL"
        next_gate = "REPAIR_LOCAL_DECLARATION_OR_HASH_IDENTITY_MODEL"
    elif not candidate_shape_pass:
        if not required_fits_single_bank:
            status = "BLOCKED_LOCAL_RECORDS_EXCEED_SINGLE_365_BANK"
            next_gate = "DESIGN_BANKED_LOCAL_RECORD_STORAGE_FROM_EXACT_REQUIRED_COUNT"
        else:
            status = "BLOCKED_LOCAL_CANDIDATE_SHAPE_OR_IDENTITY"
            next_gate = "REPAIR_LOCAL_CANDIDATE_BEFORE_NATIVE_QUALIFICATION"
    elif not capacity_guards["projected_blocks_below_365"]:
        status = "ROUTE_PACKED_730_BLOCK_CAPACITY_BEFORE_LOCAL_METADATA"
        next_gate = "PACKED_730_BLOCK_CAPACITY_CANDIDATE"
    elif not capacity_guards["projected_values_below_1460"]:
        status = "ROUTE_VALUE_CAPACITY_BEFORE_LOCAL_METADATA"
        next_gate = "QUALIFY_ZERO_INIT_OR_VALUE_NAMESPACE_CAPACITY_REDUCTION"
    elif not capacity_guards["projected_events_below_1460"]:
        status = "ROUTE_EVENT_CAPACITY_BEFORE_LOCAL_METADATA"
        next_gate = "QUALIFY_ADDITIONAL_EVENT_COMPACTION"
    elif not capacity_guards["projected_calls_below_730"]:
        status = "ROUTE_CALL_CAPACITY_BEFORE_LOCAL_METADATA"
        next_gate = "EXTEND_CALL_CAPACITY_FROM_MEASURED_LOCAL_CANDIDATE_REQUIREMENT"
    else:
        status = "PASS_STATIC_LOCAL_CANDIDATE_NATIVE_QUALIFICATION_REQUIRED"
        next_gate = "NATIVE_LOCAL_METADATA_CANDIDATE"

    candidate_sha = (
        hashlib.sha256(final_candidate.encode("utf-8")).hexdigest()
        if final_candidate is not None
        else None
    )
    candidate_bytes = len(final_candidate.encode("utf-8")) if final_candidate is not None else None

    return {
        "schema": "s3.selfhost.codegen-ir-v2-locals-static-preflight.v1",
        "status": status,
        "native_evidence": False,
        "native_parameter_evidence_consumed": True,
        "canonical_source_mutated": False,
        "parameter_candidate": {
            "source_sha256": hashlib.sha256(parameter_source.encode("utf-8")).hexdigest(),
            "source_bytes": len(parameter_source.encode("utf-8")),
            "native_audit": native,
            "stage1_lexical_metrics": base,
        },
        "native_model_guards": native_model_guards,
        "declaration_guards": declaration_guards,
        "local_candidate": {
            "selected_capacity": selected_capacity,
            "required_records_including_candidate_self_source": required_records,
            "capacity_headroom": (
                selected_capacity - required_records if selected_capacity is not None else None
            ),
            "source_sha256": candidate_sha,
            "source_bytes": candidate_bytes,
            "metrics": final_metrics,
            "exact_source_delta": exact_delta,
            "record_fields": [
                "owner_function_id",
                "name_identity",
                "type_id",
                "mutability",
                "storage_kind",
                "local_ordinal",
                "fixed_extent",
                "semantic_value_id",
            ],
            "storage_kind_preserved": True,
            "fixed_array_extent_preserved": True,
            "physical_frame_offset_deferred_to_emitter": True,
        },
        "native_headroom_projection": {
            "capacities": {
                "events": EVENT_CAPACITY,
                "values": VALUE_CAPACITY,
                "blocks": BLOCK_CAPACITY,
                "calls": CALL_CAPACITY,
            },
            "projected_candidate_counts": projections,
            "projection_uses_native_parameter_baseline_plus_exact_lexical_delta": True,
        },
        "capacity_guards": capacity_guards,
        "local_native_qualification_allowed": (
            status == "PASS_STATIC_LOCAL_CANDIDATE_NATIVE_QUALIFICATION_REQUIRED"
        ),
        "canonical_commit_allowed": False,
        "next": next_gate,
        "general_emitter": "BLOCKED_IR_V2_INCOMPLETE",
        "self_emit": "NOT_STARTED",
        "stage2": "NOT_STARTED",
        "stage3": "NOT_STARTED",
        "full_self_hosting": False,
        "qualification_rule": (
            "This report can route the next bounded gate, but never promotes source. A local candidate may run natively only when the native parameter report and the Stage1 lexical model agree exactly and all current capacities are projected safe."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parameter-report", type=Path, default=DEFAULT_PARAMETER_REPORT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument(
        "--candidate-output",
        type=Path,
        help="optional; write the exact in-memory local candidate only when static preflight PASSes",
    )
    args = parser.parse_args(argv)

    canonical = SOURCE.read_text(encoding="utf-8")
    report_value = _load_report(args.parameter_report.resolve())
    result = build_preflight(report_value, canonical_source=canonical)

    destination = args.report.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if args.candidate_output is not None:
        if not result["local_native_qualification_allowed"]:
            parser.error("candidate output refused because local static preflight did not PASS")
        parameter_source, _ = validate_parameter_prerequisite(
            report_value,
            canonical_source=canonical,
        )
        selected = result["local_candidate"]["selected_capacity"]
        if not isinstance(selected, int):
            parser.error("candidate output refused because selected capacity is unavailable")
        candidate = transform_locals(parameter_source, local_capacity=selected)
        output = args.candidate_output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(candidate, encoding="utf-8", newline="\n")
        print(f"LOCAL_CANDIDATE_OUTPUT={output}")

    print(f"REPORT={destination}")
    print(f"STATUS={result['status']}")
    print(f"NATIVE_PARAMETER_EVIDENCE_CONSUMED={result['native_parameter_evidence_consumed']}")
    print(f"NATIVE_MODEL_GUARDS_PASS={all(result['native_model_guards'].values())}")
    print(f"DECLARATION_GUARDS_PASS={all(result['declaration_guards'].values())}")
    print(f"REQUIRED_LOCAL_RECORDS={result['local_candidate']['required_records_including_candidate_self_source']}")
    print(f"SELECTED_LOCAL_CAPACITY={result['local_candidate']['selected_capacity']}")
    projection = result["native_headroom_projection"]["projected_candidate_counts"]
    print(f"PROJECTED_EVENTS={projection['events']}")
    print(f"PROJECTED_VALUES={projection['values']}")
    print(f"PROJECTED_BLOCKS={projection['blocks']}")
    print(f"PROJECTED_CALLS={projection['calls']}")
    print(f"LOCAL_NATIVE_QUALIFICATION_ALLOWED={result['local_native_qualification_allowed']}")
    print(f"NEXT={result['next']}")
    print("CANONICAL_SOURCE_MUTATED=False")
    return 0 if result["local_native_qualification_allowed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
