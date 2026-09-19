"""Hosted source-frontend integration with the whole-program control plane.

This module advances a WholeProgramContext through INPUT, SYNTAX, and
REGISTRATION using the independent GenericLexer/GenericParser path.  It stops
before TYPE/SEMANTIC on purpose; no fake semantic, lowering, or emission phase
is created.
"""

from __future__ import annotations

from dataclasses import dataclass

from .diagnostics import S3Error
from .compiler_substrate import SubstrateError
from .frontend_registration import (
    FrontendRegistrationError,
    FrontendRegistrationPlan,
    build_registration_plan,
)
from .lexer import SyntaxMode
from .source_frontend import (
    SourceBundleFrontendResult,
    parse_source_bundle_independent,
)
from .whole_program import (
    CompositionError,
    DiagnosticRecord,
    ModuleRecord,
    PhaseKind,
    PhaseStatus,
    PhaseTransitionError,
    WholeProgramContext,
)


@dataclass(frozen=True, slots=True)
class FrontendControlPlaneResult:
    success: bool
    frontend: SourceBundleFrontendResult | None
    registration_plan: FrontendRegistrationPlan | None
    modules: tuple[ModuleRecord, ...]
    diagnostics: tuple[DiagnosticRecord, ...]
    phase_trace: tuple[str, ...]
    next_phase: PhaseKind | None


def _diagnostic_code(error: BaseException) -> str:
    if isinstance(error, S3Error):
        return error.diagnostic_code.value
    text = str(error)
    if text.startswith("S3E_") and ":" in text:
        return text.split(":", 1)[0]
    if isinstance(error, FrontendRegistrationError):
        return "S3E_FRONTEND_REGISTRATION"
    return "S3E_FRONTEND_FAILURE"


def _diagnostic_message(error: BaseException) -> str:
    if isinstance(error, S3Error):
        return error.message
    return str(error)


def ingest_source_frontend(
    context: WholeProgramContext,
    *,
    mode: SyntaxMode = SyntaxMode.V0_6,
) -> FrontendControlPlaneResult:
    """Run real source through frontend + registration, then stop before TYPE.

    A context is single-use for this entry point.  On success, the next legal
    control-plane phase is TYPE.  On failure, the active phase records a
    structured diagnostic and all dependent phases are suppressed by the
    existing PhaseOrchestrator.
    """

    if context.phases._active is not None or context.phases.records.checkpoint() != 0:
        raise PhaseTransitionError(
            "frontend ingestion requires a fresh WholeProgramContext"
        )

    frontend: SourceBundleFrontendResult | None = None
    plan: FrontendRegistrationPlan | None = None
    modules: tuple[ModuleRecord, ...] = ()

    try:
        context.phases.begin(PhaseKind.INPUT)
        context.phases.commit()

        context.phases.begin(PhaseKind.SYNTAX)
        frontend = parse_source_bundle_independent(
            context.sources,
            mode=mode,
        )
        for unit in frontend.units:
            unit.syntax_arena.validate()
        context.syntax = frontend
        context.phases.commit()

        context.phases.begin(PhaseKind.REGISTRATION)
        plan = build_registration_plan(frontend)
        modules = context.registry.register(plan.modules)
        context.phases.commit()

        return FrontendControlPlaneResult(
            True,
            frontend,
            plan,
            modules,
            context.diagnostics.ordered(),
            context.phases.trace(),
            context.phases.next_phase,
        )
    except (
        S3Error,
        FrontendRegistrationError,
        CompositionError,
        SubstrateError,
        ValueError,
        KeyError,
    ) as error:
        if context.phases._active is not None:
            context.phases.fail(
                _diagnostic_code(error),
                _diagnostic_message(error),
            )
        else:
            context.diagnostics.append(
                PhaseKind.SYNTAX,
                _diagnostic_code(error),
                _diagnostic_message(error),
            )
        return FrontendControlPlaneResult(
            False,
            frontend,
            plan,
            (),
            context.diagnostics.ordered(),
            context.phases.trace(),
            context.phases.next_phase,
        )


def frontend_control_plane_ready_for_type(
    result: FrontendControlPlaneResult,
) -> bool:
    return (
        result.success
        and result.next_phase is PhaseKind.TYPE
        and all(
            trace.endswith(
                (
                    PhaseStatus.COMMITTED.value.upper(),
                    PhaseStatus.SKIPPED.value.upper(),
                )
            )
            for trace in result.phase_trace
        )
    )


__all__ = [
    "FrontendControlPlaneResult",
    "frontend_control_plane_ready_for_type",
    "ingest_source_frontend",
]