"""M2.88 bounded closure over the qualified lowering checkpoint."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .lowering_checkpoint_candidate import (
    LoweringCheckpointInput,
    LoweringCheckpointResult,
    lower_checkpoint_reference,
)
from .lexer import SyntaxMode
from .pipeline import run_source


M288_STAGE_IDENTITY = 288
_ROOT = Path(__file__).resolve().parents[2]
_CANDIDATE_SOURCE = (
    _ROOT / "selfhost" / "lowering" / "composed_lowering_closure_candidate.s3"
).read_text(encoding="utf-8")


class ComposedLoweringError(ValueError):
    """Raised when the bounded composed lowering closure cannot run safely."""


@dataclass(frozen=True, slots=True)
class ComposedLoweringResult:
    checkpoint: LoweringCheckpointResult
    composed_identity: int


def _add_mod(left: int, right: int) -> int:
    value = left + right
    while value > 364:
        value -= 729
    while value < -364:
        value += 729
    return value


def _fold(values: tuple[int, ...]) -> int:
    result = 0
    for value in values:
        result = _add_mod(result, value)
        while result < 0:
            result += 181
        while result > 180:
            result -= 181
    return result


def compose_lowering_reference(value: LoweringCheckpointInput) -> ComposedLoweringResult:
    checkpoint = lower_checkpoint_reference(value)
    return ComposedLoweringResult(
        checkpoint=checkpoint,
        composed_identity=_fold((checkpoint.checkpoint_identity, M288_STAGE_IDENTITY)),
    )


def _candidate(value: LoweringCheckpointInput) -> ComposedLoweringResult:
    reference = compose_lowering_reference(value)
    source = (
        _CANDIDATE_SOURCE
        + "\nfn main() -> tryte:\n"
        + f"    return compose_lowering({reference.checkpoint.checkpoint_identity})\n"
    )
    try:
        composed_identity = run_source(source, optimization="O0", mode=SyntaxMode.V0_6)
    except Exception as error:
        raise ComposedLoweringError("S3 composed lowering candidate failed") from error
    if not 0 <= composed_identity < 181:
        raise ComposedLoweringError("S3 composed lowering returned invalid identity")
    return ComposedLoweringResult(reference.checkpoint, composed_identity)


def run_composed_lowering_differential(
    value: LoweringCheckpointInput,
) -> tuple[ComposedLoweringResult, ComposedLoweringResult]:
    return compose_lowering_reference(value), _candidate(value)
