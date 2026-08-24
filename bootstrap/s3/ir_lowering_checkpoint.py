"""M2.90 consolidated checkpoint for the bounded IR/lowering candidates."""

from __future__ import annotations

from dataclasses import dataclass

from .ir_verifier_canary import IRCanaryResult, run_ir_canary
from .lowering_canary import LoweringCanaryResult, run_lowering_canary
from .lowering_checkpoint_candidate import LoweringCheckpointInput


@dataclass(frozen=True, slots=True)
class IRLoweringCheckpointResult:
    ir: IRCanaryResult
    lowering: LoweringCanaryResult
    candidate_selected: bool


def run_ir_lowering_checkpoint(
    value: LoweringCheckpointInput,
    *,
    source_lock_sha: str,
    observed_source_sha: str,
    explicit_opt_in: bool = False,
) -> IRLoweringCheckpointResult:
    """Observe the verifier and lowering canaries under one bounded policy."""

    ir = run_ir_canary(
        value.ir,
        source_lock_sha=source_lock_sha,
        observed_source_sha=observed_source_sha,
        explicit_opt_in=explicit_opt_in,
    )
    lowering = run_lowering_canary(
        value,
        source_lock_sha=source_lock_sha,
        observed_source_sha=observed_source_sha,
        explicit_opt_in=explicit_opt_in,
    )
    return IRLoweringCheckpointResult(
        ir=ir,
        lowering=lowering,
        candidate_selected=ir.decision.selected and lowering.decision.selected,
    )
