from __future__ import annotations

import json

import pytest

from tools.audit_stage1_codegen_ir_v2_call_arguments import (
    CLOSURE,
    MODEL_CHUNK_SIZE,
    SOURCE,
    TOTAL_ARGUMENT_MODEL_LIMIT,
    TOTAL_CALL_MODEL_LIMIT,
    audit,
    collect_call_argument_trace,
    collect_call_argument_model,
    evaluate_model_capacity,
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


def test_grouped_expression_parenthesis_does_not_open_a_call() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut value: i64 = (1 + 2)\n"
        "    return 0\n"
    )
    model = collect_call_argument_model(source)
    assert model["calls"] == 0
    assert model["total_call_arguments"] == 0
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


@pytest.mark.parametrize(
    ("source", "calls", "arguments", "max_arity"),
    [
        (
            "fn main() -> tryte:\n"
            "    discard helper(1)\n",
            1,
            1,
            1,
        ),
        (
            "fn main() -> tryte:\n"
            "    discard outer(inner(1), 2)\n",
            2,
            3,
            2,
        ),
        (
            "fn main() -> tryte:\n"
            "    mut value: i64 = (1 + 2)\n",
            0,
            0,
            0,
        ),
        (
            "fn main() -> tryte:\n"
            "    mut value: i64 = array[index]\n",
            0,
            0,
            0,
        ),
        (
            "fn helper(a: i64) -> i64:\n"
            "    return a\n",
            0,
            0,
            0,
        ),
        (
            "foreign fn helper(a: i64) -> i64:\n",
            0,
            0,
            0,
        ),
        (
            "fn main() -> tryte:\n"
            "    discard helper((1 + 2))\n",
            1,
            2,
            2,
        ),
        (
            "fn main() -> tryte:\n"
            "    discard helper(value)\n",
            1,
            1,
            1,
        ),
        (
            "fn main() -> tryte:\n"
            "    discard helper(other(value))\n",
            2,
            2,
            1,
        ),
        (
            "fn main() -> tryte:\n"
            "    discard helper()\n",
            1,
            0,
            0,
        ),
    ],
)
def test_stage1_call_shapes_match_execution_model(
    source: str,
    calls: int,
    arguments: int,
    max_arity: int,
) -> None:
    model = collect_call_argument_model(source)
    assert model["calls"] == calls
    assert model["total_call_arguments"] == arguments
    assert model["max_call_arity"] == max_arity
    assert model["active_calls_at_eof"] == 0


def test_wide_numeric_token_terminates_like_native_packed_scan() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut value: i64 = 1000000000000\n"
        "    discard helper(1)\n"
    )
    trace = collect_call_argument_trace(source)
    model = collect_call_argument_model(source)
    assert model["calls"] == 0
    assert model["total_call_arguments"] == 0
    assert trace["last_token_offset"] == source.index("1000000000000")


def test_mutation_fixtures_are_not_calibrated_to_canonical_totals() -> None:
    fixtures = (
        (
            "fn main() -> tryte:\n"
            "    discard first(1)\n"
            "    discard second(2)\n",
            2,
            2,
        ),
        (
            "fn main() -> tryte:\n"
            "    discard outer(inner(1), leaf(2))\n",
            3,
            4,
        ),
        (
            "fn main() -> tryte:\n"
            "    mut value: i64 = array[index]\n"
            "    discard target((1 + 2))\n",
            1,
            2,
        ),
    )
    for source, expected_calls, expected_arguments in fixtures:
        model = collect_call_argument_model(source)
        assert model["calls"] == expected_calls
        assert model["total_call_arguments"] == expected_arguments


@pytest.mark.parametrize(
    ("call_count", "fits"),
    [(729, True), (730, True), (731, True)],
)
def test_noncanonical_call_metadata_separates_total_and_resident_capacity(
    call_count: int,
    fits: bool,
) -> None:
    calls = [f"    discard helper({index})\n" for index in range(call_count)]
    source = "fn main() -> tryte:\n" + "".join(calls)
    model = collect_call_argument_model(source)

    assert model["calls"] == call_count
    assert model["fits_call_capacity"] is fits
    assert model["fits_call_resident_capacity"] is fits
    assert model["fits_total_call_model"] is True
    assert model["call_max_resident"] == 730
    assert model["call_total_headroom"] == TOTAL_CALL_MODEL_LIMIT - call_count


@pytest.mark.parametrize(
    ("argument_count", "fits"),
    [(745, True), (746, True), (747, False)],
)
def test_noncanonical_argument_pool_capacity_is_bounded(
    argument_count: int,
    fits: bool,
) -> None:
    arguments = ", ".join(["value"] * argument_count)
    source = f"fn main() -> tryte:\n    discard helper({arguments})\n"
    model = collect_call_argument_model(source)

    assert model["calls"] == 1
    assert model["total_call_arguments"] == argument_count
    assert model["fits_call_argument_capacity"] is fits
    assert model["fits_argument_resident_capacity"] is fits
    assert model["fits_total_argument_model"] is True
    assert model["argument_max_resident"] == 746


@pytest.mark.parametrize(
    ("calls", "arguments", "expected_call_chunks", "expected_argument_chunks"),
    [
        (MODEL_CHUNK_SIZE - 1, MODEL_CHUNK_SIZE - 1, 1, 1),
        (MODEL_CHUNK_SIZE, MODEL_CHUNK_SIZE, 1, 1),
        (MODEL_CHUNK_SIZE + 1, MODEL_CHUNK_SIZE + 1, 2, 2),
        (2 * MODEL_CHUNK_SIZE, 2 * MODEL_CHUNK_SIZE, 2, 2),
        (3 * MODEL_CHUNK_SIZE + 1, 3 * MODEL_CHUNK_SIZE + 1, 4, 4),
    ],
)
def test_total_model_capacity_supports_chunk_and_replay_boundaries(
    calls: int,
    arguments: int,
    expected_call_chunks: int,
    expected_argument_chunks: int,
) -> None:
    capacity = evaluate_model_capacity(
        calls=calls,
        total_arguments=arguments,
        maximum_active_call_records=1,
        maximum_active_argument_records=1,
        active_calls_at_eof=0,
    )

    assert capacity["fits_total_call_model"] is True
    assert capacity["fits_total_argument_model"] is True
    assert capacity["call_replay_chunks"] == expected_call_chunks
    assert capacity["argument_replay_chunks"] == expected_argument_chunks
    assert capacity["capacity_safe"] is True


@pytest.mark.parametrize(
    ("calls", "arguments", "expected"),
    [
        (TOTAL_CALL_MODEL_LIMIT - 1, TOTAL_ARGUMENT_MODEL_LIMIT - 1, True),
        (TOTAL_CALL_MODEL_LIMIT, TOTAL_ARGUMENT_MODEL_LIMIT, True),
        (TOTAL_CALL_MODEL_LIMIT + 1, TOTAL_ARGUMENT_MODEL_LIMIT, False),
        (TOTAL_CALL_MODEL_LIMIT, TOTAL_ARGUMENT_MODEL_LIMIT + 1, False),
    ],
)
def test_total_model_limit_is_independent_from_resident_capacity(
    calls: int,
    arguments: int,
    expected: bool,
) -> None:
    capacity = evaluate_model_capacity(
        calls=calls,
        total_arguments=arguments,
        maximum_active_call_records=2,
        maximum_active_argument_records=5,
        active_calls_at_eof=0,
    )

    assert capacity["fits_total_call_model"] is (calls <= TOTAL_CALL_MODEL_LIMIT)
    assert capacity["fits_total_argument_model"] is (
        arguments <= TOTAL_ARGUMENT_MODEL_LIMIT
    )
    assert capacity["fits_call_resident_capacity"] is True
    assert capacity["fits_argument_resident_capacity"] is True
    assert capacity["capacity_safe"] is expected


def test_invalid_call_argument_relation_is_rejected_fail_closed() -> None:
    capacity = evaluate_model_capacity(
        calls=2,
        total_arguments=3,
        maximum_active_call_records=3,
        maximum_active_argument_records=4,
        active_calls_at_eof=0,
    )

    assert capacity["call_argument_count_relation_valid"] is False
    assert capacity["capacity_safe"] is False


def test_malformed_unclosed_call_unit_is_rejected_fail_closed() -> None:
    capacity = evaluate_model_capacity(
        calls=1,
        total_arguments=1,
        maximum_active_call_records=1,
        maximum_active_argument_records=1,
        active_calls_at_eof=1,
    )

    assert capacity["complete_call_units"] is False
    assert capacity["capacity_safe"] is False


def test_historical_native_736_argument_closure_is_explicit_snapshot() -> None:
    closure = json.loads(CLOSURE.read_text(encoding="utf-8"))
    clean = closure["clean_source_gate"]
    runtime = closure["runtime_measurement"]
    pool = closure["pool"]
    assert clean["source_sha256"] == (
        "20fddbb73eee9ae09de911493f2f2da01ab582c7a6de879ea2e557946716a341"
    )
    assert clean["source_size_bytes"] == 166984
    assert runtime["total_calls"] == 656
    assert runtime["total_call_arguments"] == 736
    assert runtime["max_call_arity"] == 4
    assert pool["selected_capacity"] == 746

    _, guards = validate_canonical_model(SOURCE.read_bytes(), closure=closure)
    assert guards["source_sha_matches_native_closure"] is False
    assert guards["source_bytes_match_native_closure"] is False


def test_advanced_canonical_does_not_reuse_historical_parameter_projection() -> None:
    closure = json.loads(CLOSURE.read_text(encoding="utf-8"))
    result = audit(
        canonical_source=SOURCE.read_text(encoding="utf-8"),
        closure=closure,
    )
    assert result["status"] == (
        "CURRENT_TOTAL_MODEL_SUPPORTED_REQUIRES_FRESH_NATIVE_CALL_ARGUMENT_RECONCILIATION"
    )
    assert result["canonical"]["model_validated_against_native_closure"] is False
    assert result["canonical"]["capacity_safe_under_current_limits"] is True
    snapshot = result["canonical"]["historical_snapshot"]
    assert snapshot["classification"] == "HISTORICAL_SNAPSHOT_CONTRACT"
    assert snapshot["source_match_current_canonical"] is False
    assert snapshot["bytes_match_current_canonical"] is False
    parameter = result["parameter_candidate"]
    assert parameter["status"] == "NOT_APPLICABLE_HISTORICAL_PARAMETER_TRANSFORM"
    assert parameter["model"] is None
    assert parameter["safe_under_current_call_and_argument_capacities"] is None
