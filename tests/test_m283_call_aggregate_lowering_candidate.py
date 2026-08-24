"""M2.83 call and aggregate-result lowering contracts."""

from pathlib import Path

import pytest

from bootstrap.s3.call_aggregate_lowering_candidate import (
    CallLoweringError,
    CallLoweringInput,
    lower_call_reference,
    run_call_lowering_differential,
)
from bootstrap.s3.ir import IRType, IROpcode


ROOT = Path(__file__).parents[1]
SELFHOST_SOURCE = (
    ROOT / "selfhost" / "lowering" / "call_aggregate_lowering_candidate.s3"
).read_text(encoding="utf-8")


def test_candidate_source_has_one_call_entrypoint_and_no_main() -> None:
    assert "fn lower_call" in SELFHOST_SOURCE
    assert "fn main" not in SELFHOST_SOURCE
    assert "tryte[4]" in SELFHOST_SOURCE


@pytest.mark.parametrize(
    "result_types",
    [(), (IRType.TRYTE,), (IRType.I64, IRType.F64, IRType.TRYTE)],
)
def test_scalar_and_aggregate_result_shapes_are_ordered(result_types: tuple[IRType, ...]) -> None:
    value = CallLoweringInput(
        callee_id=17,
        argument_types=(IRType.TRYTE, IRType.I64),
        argument_registers=(0, 1),
        result_types=result_types,
    )
    plan = lower_call_reference(value)
    assert plan.opcode is IROpcode.CALL
    assert plan.argument_registers == (0, 1)
    assert plan.result_registers == tuple(range(2, 2 + len(result_types)))
    assert plan.result_types == result_types


def test_reference_and_s3_call_lowering_match_for_aggregate_results() -> None:
    value = CallLoweringInput(
        callee_id=17,
        argument_types=(IRType.TRYTE, IRType.I64),
        argument_registers=(0, 1),
        result_types=(IRType.I64, IRType.F64, IRType.TRYTE),
    )
    evidence = run_call_lowering_differential(value)
    assert evidence.match


def test_call_lowering_rejects_mismatched_argument_shapes() -> None:
    value = CallLoweringInput(
        callee_id=17,
        argument_types=(IRType.TRYTE,),
        argument_registers=(),
        result_types=(),
    )
    with pytest.raises(CallLoweringError, match="equal length"):
        run_call_lowering_differential(value)
