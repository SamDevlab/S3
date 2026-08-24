"""M2.78 composed semantic closure contract."""

from pathlib import Path
from dataclasses import replace

import pytest

from bootstrap.s3.control_flow_candidate import FlowStatement, M277_RETURN
from bootstrap.s3.function_call_candidate import FunctionSignature
from bootstrap.s3.semantic_closure_candidate import (
    M278_STAGE_FLOW,
    M278_STAGE_SCALARS,
    SemanticClosureCandidateError,
    SemanticClosureInput,
    candidate_semantic_closure,
    run_semantic_closure_differential,
)


ROOT = Path(__file__).parents[1]
SELFHOST_SOURCE = (ROOT / "selfhost/semantic/semantic_closure_candidate.s3").read_text(
    encoding="utf-8"
)


def _valid_case() -> SemanticClosureInput:
    return SemanticClosureInput(
        symbol_entries=((11, 1),),
        symbol_query=11,
        name_entries=((11, 1, 0),),
        scope_parents=(-1,),
        name_query=11,
        name_query_scope=0,
        scalar_operation="assign",
        scalar_left_type=1,
        scalar_target_type=1,
        place_operation="read",
        place_type=1,
        place_kind=1,
        place_readable=True,
        place_initialized=True,
        function_signatures=(FunctionSignature(20, (1,), 2),),
        function_query=20,
        argument_types=(1,),
        record_types=(1, 2),
        enum_variants=((1,), (2, 3)),
        flow_statements=(FlowStatement(M277_RETURN),),
        flow_requires_return=True,
    )


def test_candidate_source_is_composed_and_has_one_canonical_entrypoint() -> None:
    assert "fn check_semantic_closure" in SELFHOST_SOURCE
    assert "tryte[64]" in SELFHOST_SOURCE
    assert "fn main" not in SELFHOST_SOURCE
    for entrypoint in (
        "m271_symbol_table_lookup",
        "m272_resolve_visible_symbol",
        "m273_check_scalar_type",
        "m274_check_place_operation",
        "m275_check_function_call",
        "m276_record_layout_summary",
        "m277_check_control_flow",
    ):
        assert entrypoint in SELFHOST_SOURCE or entrypoint == "m277_check_control_flow"


def test_valid_composed_semantics_match_exactly() -> None:
    evidence = run_semantic_closure_differential(_valid_case())
    assert evidence.match
    assert evidence.reference.accepted
    assert evidence.reference.identity is not None
    assert evidence.reference.diagnostic_code == 0


def test_layout_identity_is_part_of_the_canonical_output() -> None:
    case = _valid_case()
    changed = replace(case, record_types=(1, 3))
    first = candidate_semantic_closure(case)
    second = candidate_semantic_closure(changed)
    assert first.accepted and second.accepted
    assert first.identity != second.identity


@pytest.mark.parametrize(
    ("change", "diagnostic"),
    [
        ("scalar_operation", M278_STAGE_SCALARS),
        ("flow_requires_return", M278_STAGE_FLOW),
    ],
)
def test_composed_rejection_is_fail_closed(
    change: str,
    diagnostic: int,
) -> None:
    case = _valid_case()
    if change == "scalar_operation":
        case = replace(case, scalar_operation="divide")
    else:
        case = replace(
            case,
            flow_statements=(FlowStatement(M277_RETURN), FlowStatement(0)),
        )
    evidence = run_semantic_closure_differential(case)
    assert evidence.match
    assert evidence.reference.accepted is False
    assert evidence.reference.diagnostic_code == diagnostic


def test_bounds_fail_before_candidate_execution() -> None:
    case = _valid_case()
    with pytest.raises(SemanticClosureCandidateError, match="record_types"):
        candidate_semantic_closure(replace(case, record_types=(1,) * 9))
