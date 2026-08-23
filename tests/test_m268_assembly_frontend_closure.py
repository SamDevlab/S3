"""M2.68 composed self-hosted Assembly frontend contracts."""

from __future__ import annotations

from pathlib import Path

import pytest

from bootstrap.s3.assembly_frontend_closure_candidate import (
    AssemblyFrontendClosureError,
    candidate_assembly_frontend_fingerprint,
    reference_assembly_frontend_fingerprint,
    run_assembly_frontend_closure,
)


ROOT = Path(__file__).parents[1]
CLOSURE_SOURCE = (ROOT / "selfhost/frontend/assembly_frontend_closure.s3").read_text(
    encoding="utf-8"
)
FRONTEND_SOURCE = (ROOT / "selfhost/assembly/assembly_frontend.s3").read_text(
    encoding="utf-8"
)

VALID_ASSEMBLY = ".s3asm 0.6.0\n\n.function main -> [tryte, trit]\n    .register r0, tryte\n    .register r1, trit\n.label entry\n    TCALL  [r0, r1], pair\n    TRET   [r0, r1]\n.end\n"


def test_closure_source_composes_the_self_hosted_frontend() -> None:
    assert "export fn assembly_frontend_fingerprint" in CLOSURE_SOURCE
    assert "analyze_bounded_assembly" in CLOSURE_SOURCE
    assert "AssemblyFrontendResult.Summary" in CLOSURE_SOURCE
    assert "export fn analyze_bounded_assembly" in FRONTEND_SOURCE


def test_valid_assembly_matches_python_reference() -> None:
    evidence = run_assembly_frontend_closure(VALID_ASSEMBLY)
    assert evidence.reference_fingerprint == reference_assembly_frontend_fingerprint(
        VALID_ASSEMBLY
    )
    assert evidence.candidate_fingerprint == candidate_assembly_frontend_fingerprint(
        VALID_ASSEMBLY
    )
    assert evidence.match is True


def test_frontend_error_contract_matches_python_reference() -> None:
    source = ".s3asm 0.8.0\n"
    assert candidate_assembly_frontend_fingerprint(source) == reference_assembly_frontend_fingerprint(
        source
    )
    assert candidate_assembly_frontend_fingerprint(source) == -1


def test_composed_frontend_is_deterministic() -> None:
    first = candidate_assembly_frontend_fingerprint(VALID_ASSEMBLY)
    second = candidate_assembly_frontend_fingerprint(VALID_ASSEMBLY)
    assert first == second


def test_frontend_source_is_bounded() -> None:
    with pytest.raises(AssemblyFrontendClosureError, match="capacity"):
        candidate_assembly_frontend_fingerprint("x" * 365)
