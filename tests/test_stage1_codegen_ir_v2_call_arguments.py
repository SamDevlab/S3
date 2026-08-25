from __future__ import annotations

import json

from tools.audit_stage1_codegen_ir_v2_call_arguments import (
    CLOSURE,
    SOURCE,
    audit,
    collect_call_argument_model,
    validate_canonical_model,
)


def test_simple_call_argument_model_tracks_bootstrap_occurrences() -> None:
    source = (
        "fn helper(a: i64, b: i64) -> i64:\n"
        "    return a\n"
        "fn main() -> tryte:\n"
        "    mut value: i64 = helper(1, 2)\n"
        "    return 0\n"
    )
    model = collect_call_argument_model(source)
    assert model["calls"] == 1
    assert model["total_call_arguments"] == 2
    assert model["max_call_arity"] == 2
    assert model["arity_distribution"] == {
        "0": 0,
        "1": 0,
        "2": 1,
        "3": 0,
        "4_plus": 0,
    }
    assert model["active_calls_at_eof"] == 0


def test_nested_callee_identifier_is_parent_structural_argument_occurrence() -> None:
    source = (
        "fn inner(a: i64) -> i64:\n"
        "    return a\n"
        "fn outer(a: i64, b: i64) -> i64:\n"
        "    return a\n"
        "fn main() -> tryte:\n"
        "    mut value: i64 = outer(inner(1), 2)\n"
        "    return 0\n"
    )
    model = collect_call_argument_model(source)
    assert model["calls"] == 2
    # Stage1 structurally stores `inner` as one occurrence in the active outer
    # call, then stores 1 in inner and 2 in outer.
    assert model["total_call_arguments"] == 3
    assert model["arity_distribution"]["1"] == 1
    assert model["arity_distribution"]["2"] == 1
    assert model["maximum_active_call_depth"] == 2


def test_canonical_model_must_reproduce_native_736_argument_closure() -> None:
    closure = json.loads(CLOSURE.read_text(encoding="utf-8"))
    model, guards = validate_canonical_model(SOURCE.read_bytes(), closure=closure)
    assert all(guards.values())
    assert model["calls"] == 656
    assert model["total_call_arguments"] == 736
    assert model["max_call_arity"] == 4
    assert model["call_argument_headroom"] == 10


def test_parameter_candidate_must_not_silently_overflow_current_argument_pool() -> None:
    closure = json.loads(CLOSURE.read_text(encoding="utf-8"))
    result = audit(
        canonical_source=SOURCE.read_text(encoding="utf-8"),
        closure=closure,
    )
    assert result["canonical"]["model_validated_against_native_closure"] is True
    parameter = result["parameter_candidate"]
    assert parameter["model"]["calls"] <= parameter["model"]["call_capacity"]
    assert (
        parameter["model"]["total_call_arguments"]
        <= parameter["model"]["call_argument_capacity"]
    )
    assert parameter["safe_under_current_call_and_argument_capacities"] is True
