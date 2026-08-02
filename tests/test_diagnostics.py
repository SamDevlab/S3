from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from bootstrap.s3.assembly import (
    AssemblyError,
    AssemblyParseError,
    parse_assembly,
)
from bootstrap.s3.backends.x86_64 import (
    NativeBackendError,
    NativePlatformError,
    NativeToolchainError,
)
from bootstrap.s3.codegen import CodegenError
from bootstrap.s3.diagnostics import (
    DIAGNOSTIC_SCHEMA,
    DIAGNOSTIC_SCHEMA_VERSION,
    Diagnostic,
    DiagnosticCategory,
    DiagnosticCode,
    DiagnosticPhase,
    DiagnosticSeverity,
    DiagnosticSource,
    LexError,
    LoweringError,
    ParseError,
    S3Error,
    SemanticError,
    diagnostic_from_exception,
)
from bootstrap.s3.emulator import EmulatorError, execute_assembly
from bootstrap.s3.initialization import InitializationAnalysisError
from bootstrap.s3.ir_serialization import IRSerializationError
from bootstrap.s3.ternary import TernaryRangeError
from bootstrap.s3.verifier import IRVerificationError


def _diagnostic_for_failure(
    assembly: str,
    **limits: int,
) -> dict[str, object]:
    with pytest.raises(EmulatorError) as captured:
        execute_assembly(assembly, **limits)
    return diagnostic_from_exception(captured.value).to_dict()


def test_diagnostic_serialization_is_deterministic_utf8_and_one_line() -> None:
    diagnostic = Diagnostic(
        DiagnosticSeverity.ERROR,
        DiagnosticCategory.SEMANTIC,
        DiagnosticPhase.SEMANTIC,
        DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
        "nome não declarado: ação",
        file="diretório com espaços/fonte.s3",
        source=DiagnosticSource(offset=4, line=2, column=3),
        notes=("informação adicional",),
    )
    first = diagnostic.to_json()
    second = diagnostic.to_json()
    assert first == second
    assert first.count("\n") == 1
    assert "\\u" not in first
    payload = json.loads(first)
    assert payload["schema"] == DIAGNOSTIC_SCHEMA
    assert payload["schema_version"] == DIAGNOSTIC_SCHEMA_VERSION
    assert payload["message"] == "nome não declarado: ação"
    assert payload["source"] == {"offset": 4, "line": 2, "column": 3}
    assert "function" not in payload
    assert "value" not in payload


@pytest.mark.parametrize(
    "source",
    (
        {"offset": -1},
        {"line": 0},
    ),
)
def test_invalid_source_positions_are_rejected_at_construction(
    source: dict[str, int],
) -> None:
    with pytest.raises(ValueError):
        DiagnosticSource(**source)


@pytest.mark.parametrize(
    ("field", "arguments"),
    (
        (
            "severity",
            (
                "",
                DiagnosticCategory.SYNTAX,
                DiagnosticPhase.CLI,
                DiagnosticCode.CLI_USAGE,
            ),
        ),
        (
            "category",
            (
                DiagnosticSeverity.ERROR,
                "",
                DiagnosticPhase.CLI,
                DiagnosticCode.CLI_USAGE,
            ),
        ),
        (
            "phase",
            (
                DiagnosticSeverity.ERROR,
                DiagnosticCategory.SYNTAX,
                "",
                DiagnosticCode.CLI_USAGE,
            ),
        ),
        (
            "code",
            (
                DiagnosticSeverity.ERROR,
                DiagnosticCategory.SYNTAX,
                DiagnosticPhase.CLI,
                "",
            ),
        ),
    ),
)
def test_empty_or_untyped_required_enums_are_rejected(
    field: str,
    arguments: tuple[object, object, object, object],
) -> None:
    with pytest.raises(TypeError, match=field):
        Diagnostic(
            *arguments,  # type: ignore[arg-type]
            "invalid",
        )


def test_diagnostic_rejects_nonserializable_or_mutable_field_values() -> None:
    with pytest.raises(TypeError, match="message"):
        Diagnostic(
            DiagnosticSeverity.ERROR,
            DiagnosticCategory.SYNTAX,
            DiagnosticPhase.CLI,
            DiagnosticCode.CLI_USAGE,
            1,  # type: ignore[arg-type]
        )
    with pytest.raises(TypeError, match="file"):
        Diagnostic(
            DiagnosticSeverity.ERROR,
            DiagnosticCategory.SYNTAX,
            DiagnosticPhase.CLI,
            DiagnosticCode.CLI_USAGE,
            "invalid",
            file=Path("source.s3"),  # type: ignore[arg-type]
        )
    with pytest.raises(TypeError, match="notes"):
        Diagnostic(
            DiagnosticSeverity.ERROR,
            DiagnosticCategory.SYNTAX,
            DiagnosticPhase.CLI,
            DiagnosticCode.CLI_USAGE,
            "invalid",
            notes=["mutable"],  # type: ignore[arg-type]
        )


def test_diagnostic_and_source_are_immutable_after_construction() -> None:
    source = DiagnosticSource(offset=0, line=1, column=1)
    diagnostic = Diagnostic(
        DiagnosticSeverity.ERROR,
        DiagnosticCategory.SYNTAX,
        DiagnosticPhase.CLI,
        DiagnosticCode.CLI_USAGE,
        "invalid",
        source=source,
    )
    with pytest.raises(FrozenInstanceError):
        diagnostic.message = "changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        source.line = 2  # type: ignore[misc]


def test_normative_spec_lists_every_public_category_and_code() -> None:
    specification = Path("spec/diagnostics.md").read_text(encoding="utf-8")
    for category in DiagnosticCategory:
        assert f"\n{category.value}\n" in specification
    for code in DiagnosticCode:
        assert f"\n{code.value}\n" in specification


def test_public_error_classes_have_centralized_category_code_and_phase() -> None:
    error_classes = (
        S3Error,
        LexError,
        ParseError,
        SemanticError,
        LoweringError,
        InitializationAnalysisError,
        IRSerializationError,
        IRVerificationError,
        AssemblyError,
        AssemblyParseError,
        EmulatorError,
        CodegenError,
        TernaryRangeError,
        NativeBackendError,
        NativePlatformError,
        NativeToolchainError,
    )
    for error_class in error_classes:
        assert isinstance(error_class.diagnostic_category, DiagnosticCategory)
        assert isinstance(error_class.diagnostic_code, DiagnosticCode)
        assert isinstance(error_class.diagnostic_phase, DiagnosticPhase)


def test_bounds_diagnostic_exposes_context_without_message_parsing() -> None:
    payload = _diagnostic_for_failure(
        """\
.function main -> tryte
    .register r0, tryte
    .register r1, tryte
    .memory m0, tryte, 2, mutable
.label entry
    TCONST r0, -1
    TLOAD r1, m0, r0 ; source=7:9:31
    TRET r1
.end
"""
    )
    assert payload["category"] == "bounds"
    assert payload["code"] == "S3E_RUNTIME_BOUNDS"
    assert payload["phase"] == "emulation"
    assert payload["function"] == "main"
    assert payload["block"] == "entry"
    assert payload["opcode"] == "TLOAD"
    assert payload["memory"] == "m0"
    assert payload["index"] == -1
    assert payload["lower_bound"] == 0
    assert payload["upper_bound"] == 2
    assert payload["source"] == {"offset": 31, "line": 7, "column": 9}


def test_overflow_diagnostic_exposes_value_and_range() -> None:
    payload = _diagnostic_for_failure(
        """\
.function main -> tryte
    .register r0, tryte
    .register r1, tryte
    .register r2, tryte
.label entry
    TCONST r0, 364
    TCONST r1, 1
    TADD r2, r0, r1
    TRET r2
.end
"""
    )
    assert payload["category"] == "overflow"
    assert payload["code"] == "S3E_RUNTIME_OVERFLOW"
    assert payload["opcode"] == "TADD"
    assert payload["value"] == 365
    assert payload["lower_bound"] == -364
    assert payload["upper_bound"] == 364


def test_uninitialized_and_immutable_diagnostics_are_distinct() -> None:
    uninitialized = _diagnostic_for_failure(
        """\
.function main -> tryte
    .register r0, tryte
    .register r1, tryte
    .memory m0, tryte, 1, mutable
.label entry
    TCONST r0, 0
    TLOAD r1, m0, r0
    TRET r1
.end
"""
    )
    assert uninitialized["category"] == "uninitialized"
    assert uninitialized["code"] == "S3E_RUNTIME_UNINITIALIZED_MEMORY"
    assert uninitialized["memory"] == "m0"
    assert uninitialized["index"] == 0

    immutable = _diagnostic_for_failure(
        """\
.function main -> tryte
    .register r0, tryte
    .register r1, tryte
    .register r2, tryte
    .memory m0, tryte, 1, immutable
.label entry
    TCONST r0, 0
    TCONST r1, 1
    TCONST r2, 2
    TSTORE m0, r0, r1
    TSTORE m0, r0, r2
    TRET r2
.end
"""
    )
    assert immutable["category"] == "immutable-write"
    assert immutable["code"] == "S3E_RUNTIME_IMMUTABLE_WRITE"
    assert immutable["memory"] == "m0"
    assert immutable["index"] == 0


def test_frame_and_instruction_limits_have_separate_codes() -> None:
    recursive = """\
.function recurse -> tryte
    .register r0, tryte
.label entry
    TCALL r0, recurse
    TRET r0
.end

.function main -> tryte
    .register r0, tryte
.label entry
    TCALL r0, recurse
    TRET r0
.end
"""
    frame = _diagnostic_for_failure(recursive, max_frames=2)
    assert frame["category"] == "frame-limit"
    assert frame["code"] == "S3E_RUNTIME_FRAME_LIMIT"
    assert frame["limit"] == 2
    assert frame["function"] == "recurse"

    instruction = _diagnostic_for_failure(recursive, max_instructions=1)
    assert instruction["category"] == "instruction-limit"
    assert instruction["code"] == "S3E_RUNTIME_INSTRUCTION_LIMIT"
    assert instruction["limit"] == 1
    assert instruction["function"] == "recurse"


def test_assembly_version_is_a_versioned_artifact_diagnostic() -> None:
    with pytest.raises(AssemblyParseError) as captured:
        parse_assembly(".s3asm 9.9.9\n")
    payload = diagnostic_from_exception(captured.value).to_dict()
    assert payload["category"] == "version"
    assert payload["code"] == "S3E_ARTIFACT_UNSUPPORTED_VERSION"
    assert payload["phase"] == "artifact-read"
    assert payload["source"] == {"line": 1}
