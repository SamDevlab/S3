"""M2.80 semantic self-hosting checkpoint contracts."""

from pathlib import Path

from bootstrap.s3.control_flow_candidate import FlowStatement, M277_RETURN
from bootstrap.s3.experiment_promotion import PromotionStatus
from bootstrap.s3.function_call_candidate import FunctionSignature
from bootstrap.s3.semantic_canary import run_semantic_canary
from bootstrap.s3.semantic_closure_candidate import SemanticClosureInput
from tools.s3test import ImpactMap, _profile_selection


ROOT = Path(__file__).parents[1]
IMPACT = ImpactMap.load(ROOT / "tests" / "test-impact.json")
EXPECTED = (
    "tests/test_m271_symbol_table_candidate.py",
    "tests/test_m272_name_resolution_candidate.py",
    "tests/test_m273_scalar_type_checking.py",
    "tests/test_m274_place_reference_candidate.py",
    "tests/test_m275_function_call_candidate.py",
    "tests/test_m276_fixed_layout_candidate.py",
    "tests/test_m277_control_flow_candidate.py",
    "tests/test_m278_semantic_closure_candidate.py",
    "tests/test_m279_semantic_canary.py",
)


def _case() -> SemanticClosureInput:
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
        function_signatures=(FunctionSignature(20, (1,), 2),),
        function_query=20,
        argument_types=(1,),
        record_types=(1, 2),
        enum_variants=((1,), (2, 3)),
        flow_statements=(FlowStatement(M277_RETURN),),
        flow_requires_return=True,
    )


def test_semantic_level_c_profile_covers_m271_through_m279_in_order() -> None:
    selections, tests = _profile_selection(ROOT, IMPACT, "level-c-semantic", None, None)
    assert tests == EXPECTED
    assert tuple(selection.test for selection in selections) == EXPECTED
    assert all(selection.tiers == ("LEVEL-C",) for selection in selections)


def test_semantic_level_c_profile_is_not_t4() -> None:
    selections, _ = _profile_selection(ROOT, IMPACT, "level-c-semantic", None, None)
    assert all("T4" not in selection.tiers for selection in selections)


def test_semantic_candidate_remains_explicitly_opt_in_at_checkpoint() -> None:
    result = run_semantic_canary(
        _case(), source_lock_sha="a" * 40, observed_source_sha="a" * 40
    )
    assert result.decision.status is PromotionStatus.OFF_BY_DEFAULT
    assert result.decision.selected is False
    assert result.selected_output == result.reference_output
