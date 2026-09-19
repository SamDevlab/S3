from __future__ import annotations

from bootstrap.s3.compiler_substrate import SourceBundle
from bootstrap.s3.frontend_control_plane import (
    frontend_control_plane_ready_for_semantic,
    ingest_source_frontend,
)
from bootstrap.s3.whole_program import PhaseKind, WholeProgramContext


def test_source_frontend_advances_control_plane_through_type_resolution() -> None:
    context = WholeProgramContext(
        SourceBundle(
            (
                (
                    "main.s3",
                    "module main\nfn main() -> i64:\n    return 0\n",
                ),
            )
        )
    )

    result = ingest_source_frontend(context)

    assert result.success
    assert result.next_phase is PhaseKind.TYPE
    assert result.phase_trace == (
        "INPUT:COMMITTED",
        "SYNTAX:COMMITTED",
        "REGISTRATION:COMMITTED",
    )
    assert frontend_control_plane_ready_for_type(result)
    assert len(result.modules) == 1
    assert context.syntax is result.frontend
    assert context.ir is None
    assert context.sink.to_bytes() == b""


def test_source_frontend_control_plane_fails_in_syntax_without_fake_later_work() -> None:
    context = WholeProgramContext(
        SourceBundle(
            (
                (
                    "broken.s3",
                    "fn main() -> i64:\n    return @\n",
                ),
            )
        )
    )

    result = ingest_source_frontend(context)

    assert not result.success
    assert result.frontend is None
    assert result.registration_plan is None
    assert result.type_resolution is None
    assert result.modules == ()
    assert result.phase_trace[0] == "INPUT:COMMITTED"
    assert result.phase_trace[1] == "SYNTAX:FAILED"
    assert "REGISTRATION:SKIPPED" in result.phase_trace
    assert "TYPE:SKIPPED" in result.phase_trace
    assert "SEMANTIC:SKIPPED" in result.phase_trace
    assert context.ir is None
    assert context.sink.to_bytes() == b""
    assert result.diagnostics


def test_source_frontend_registration_failure_rolls_registry_back() -> None:
    context = WholeProgramContext(
        SourceBundle(
            (
                (
                    "a.s3",
                    "module same\nfn main() -> i64:\n    return 0\n",
                ),
                (
                    "b.s3",
                    "module same\nfn main() -> i64:\n    return 1\n",
                ),
            )
        )
    )

    result = ingest_source_frontend(context)

    assert not result.success
    assert "REGISTRATION:FAILED" in result.phase_trace
    assert len(tuple(context.registry.modules.items())) == 0
    assert len(tuple(context.registry.functions.items())) == 0
    assert result.diagnostics


def test_source_frontend_type_failure_preserves_registered_program_and_rolls_type_state_back() -> None:
    context = WholeProgramContext(
        SourceBundle(
            (
                (
                    "bad_type.s3",
                    "module bad_type\nfn bad(value: Missing) -> i64:\n    return 0\nfn main() -> i64:\n    return 0\n",
                ),
            )
        )
    )
    primitive_count = len(tuple(context.types.types.items()))

    result = ingest_source_frontend(context)

    assert not result.success
    assert "REGISTRATION:COMMITTED" in result.phase_trace
    assert "TYPE:FAILED" in result.phase_trace
    assert len(tuple(context.registry.modules.items())) == 1
    assert len(tuple(context.registry.functions.items())) == 2
    assert len(tuple(context.types.types.items())) == primitive_count
    assert len(tuple(context.semantic.signatures.items())) == 0
    assert context.semantic.node_types == {}
