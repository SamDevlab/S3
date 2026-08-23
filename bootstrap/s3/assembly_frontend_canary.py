"""M2.69 explicit Assembly frontend canary with Python fallback."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .assembly_frontend_closure_candidate import (
    reference_assembly_frontend_fingerprint,
    run_assembly_frontend_closure,
)


class FrontendExecutionMode(StrEnum):
    """Supported frontend execution paths."""

    PYTHON_REFERENCE = "python-reference"
    S3_CANARY = "s3-canary"


class FrontendCanaryError(ValueError):
    """Raised when the frontend execution mode is invalid."""


@dataclass(frozen=True, slots=True)
class FrontendExecutionResult:
    """Observable result of one explicitly selected frontend path."""

    source: str
    requested_mode: FrontendExecutionMode
    selected_mode: FrontendExecutionMode
    reference_fingerprint: int
    selected_fingerprint: int
    candidate_fingerprint: int | None
    used_fallback: bool
    fallback_reason: str | None

    @property
    def candidate_selected(self) -> bool:
        return self.selected_mode is FrontendExecutionMode.S3_CANARY


def _normalize_mode(mode: FrontendExecutionMode | str | None) -> FrontendExecutionMode:
    if mode is None:
        return FrontendExecutionMode.PYTHON_REFERENCE
    try:
        return FrontendExecutionMode(mode)
    except ValueError as error:
        raise FrontendCanaryError(f"unsupported frontend execution mode: {mode!r}") from error


def _python_result(
    source: str,
    requested_mode: FrontendExecutionMode,
    reference_fingerprint: int,
    *,
    candidate_fingerprint: int | None = None,
    fallback_reason: str | None = None,
) -> FrontendExecutionResult:
    return FrontendExecutionResult(
        source,
        requested_mode,
        FrontendExecutionMode.PYTHON_REFERENCE,
        reference_fingerprint,
        reference_fingerprint,
        candidate_fingerprint,
        requested_mode is FrontendExecutionMode.S3_CANARY,
        fallback_reason,
    )


def run_assembly_frontend(
    source: str,
    *,
    mode: FrontendExecutionMode | str | None = None,
) -> FrontendExecutionResult:
    """Run the frontend with an explicit canary and immediate Python fallback."""

    requested_mode = _normalize_mode(mode)
    reference_fingerprint = reference_assembly_frontend_fingerprint(source)
    if requested_mode is FrontendExecutionMode.PYTHON_REFERENCE:
        return _python_result(source, requested_mode, reference_fingerprint)

    try:
        evidence = run_assembly_frontend_closure(source)
    except Exception as error:
        return _python_result(
            source,
            requested_mode,
            reference_fingerprint,
            fallback_reason=f"candidate_error:{type(error).__name__}",
        )

    if evidence.reference_fingerprint != reference_fingerprint:
        return _python_result(
            source,
            requested_mode,
            reference_fingerprint,
            candidate_fingerprint=evidence.candidate_fingerprint,
            fallback_reason="reference_changed_during_canary",
        )
    if not evidence.match:
        return _python_result(
            source,
            requested_mode,
            reference_fingerprint,
            candidate_fingerprint=evidence.candidate_fingerprint,
            fallback_reason="candidate_differential_mismatch",
        )
    return FrontendExecutionResult(
        source,
        requested_mode,
        FrontendExecutionMode.S3_CANARY,
        reference_fingerprint,
        evidence.candidate_fingerprint,
        evidence.candidate_fingerprint,
        False,
        None,
    )
