"""Static Stage1 call-argument pressure model for IR-v2 candidate planning.

The current canonical source has an authoritative native closure measurement:
656 calls, 736 stored call-argument occurrences, maximum observed call arity 4,
with physical capacity 746. This tool mirrors the current Stage1 bootstrap
collector, including its structural rule that every identifier or integer token
encountered while a call is active is stored in the top call's argument lane.

The canonical model must reproduce the native closure before projections are
trusted for parameter/local candidates. Static agreement is preflight only; it
never replaces native Linux qualification after a source change.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from tools.patch_stage1_codegen_ir_v2_parameters import build_candidate as build_parameter_candidate
from tools.preflight_stage1_codegen_ir_v2_locals import Stage1Token, stage1_tokens


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "selfhost" / "compiler" / "s3c_stage1.s3"
CLOSURE = ROOT / "reports" / "selfhost" / "stage1" / "call-argument-pool-closure.json"
DEFAULT_REPORT = (
    ROOT / "reports" / "selfhost" / "stage1" /
    "codegen-ir-v2-call-argument-static-audit.json"
)

CALL_CAPACITY = 730
CALL_ARGUMENT_CAPACITY = 746
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


def collect_call_argument_model(source: str) -> dict[str, object]:
    """Mirror Stage1's bounded call stack/argument occurrence accounting."""

    tokens = stage1_tokens(source)
    arities: list[int] = []
    active: list[int] = []
    maximum_depth = 0

    for index, token in enumerate(tokens):
        # Stage1 computes argument_possible from the current token and stores an
        # identifier/integer in the currently active call before processing a
        # later ')' close. A nested callee identifier is therefore an argument
        # occurrence of its parent call, exactly as in the bootstrap collector.
        if token.kind in (1, 2) and active:
            arities[active[-1]] += 1

        if token.kind == 4 and token.value == 1:
            if not _is_function_signature_open(tokens, index):
                call_id = len(arities)
                arities.append(0)
                active.append(call_id)
                maximum_depth = max(maximum_depth, len(active))
            continue

        if token.kind == 4 and token.value == 2:
            if active:
                active.pop()
            # A function-signature ')' has no active call; that is not an error.
            continue

    total_arguments = sum(arities)
    distribution = {
        "0": sum(1 for value in arities if value == 0),
        "1": sum(1 for value in arities if value == 1),
        "2": sum(1 for value in arities if value == 2),
        "3": sum(1 for value in arities if value == 3),
        "4_plus": sum(1 for value in arities if value >= 4),
    }
    return {
        "calls": len(arities),
        "total_call_arguments": total_arguments,
        "max_call_arity": max(arities, default=0),
        "arity_distribution": distribution,
        "maximum_active_call_depth": maximum_depth,
        "active_calls_at_eof": len(active),
        "call_capacity": CALL_CAPACITY,
        "call_argument_capacity": CALL_ARGUMENT_CAPACITY,
        "call_headroom": CALL_CAPACITY - len(arities),
        "call_argument_headroom": CALL_ARGUMENT_CAPACITY - total_arguments,
        "fits_call_capacity": len(arities) <= CALL_CAPACITY,
        "fits_call_argument_capacity": total_arguments <= CALL_ARGUMENT_CAPACITY,
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
        "closure_pool_capacity_is_746": pool.get("selected_capacity") == CALL_ARGUMENT_CAPACITY,
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

    parameter_source = build_parameter_candidate(canonical_source)
    parameter_model = collect_call_argument_model(parameter_source)
    parameter_safe = bool(
        canonical_pass
        and parameter_model["fits_call_capacity"]
        and parameter_model["fits_call_argument_capacity"]
        and int(parameter_model["maximum_active_call_depth"]) <= 16
        and parameter_model["active_calls_at_eof"] == 0
    )

    local_model: dict[str, object] | None = None
    local_safe: bool | None = None
    if local_candidate is not None:
        local_model = collect_call_argument_model(local_candidate)
        local_safe = bool(
            canonical_pass
            and local_model["fits_call_capacity"]
            and local_model["fits_call_argument_capacity"]
            and int(local_model["maximum_active_call_depth"]) <= 16
            and local_model["active_calls_at_eof"] == 0
        )

    if not canonical_pass:
        status = "BLOCKED_CANONICAL_CALL_ARGUMENT_MODEL_DOES_NOT_MATCH_NATIVE_CLOSURE"
        next_gate = "RECONCILE_CALL_ARGUMENT_MODEL_WITH_NATIVE_CLOSURE"
    elif not parameter_safe:
        status = "ROUTE_CALL_ARGUMENT_CAPACITY_BEFORE_PARAMETER_NATIVE"
        next_gate = "EXTEND_CALL_ARGUMENT_POOL_FROM_EXACT_PARAMETER_CANDIDATE_REQUIREMENT"
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
        },
        "parameter_candidate": {
            "source_sha256": _sha256(parameter_source.encode("utf-8")),
            "source_bytes": len(parameter_source.encode("utf-8")),
            "model": parameter_model,
            "safe_under_current_call_and_argument_capacities": parameter_safe,
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
            "Static projections are trusted only because the unchanged canonical source must reproduce the existing native 656-call/736-argument closure exactly. Any transformed candidate still requires native Linux qualification before promotion."
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
