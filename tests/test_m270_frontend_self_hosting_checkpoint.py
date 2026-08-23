"""M2.70 frontend self-hosting Level-C checkpoint contracts."""

from __future__ import annotations

from pathlib import Path

from bootstrap.s3.assembly_frontend_canary import (
    FrontendExecutionMode,
    run_assembly_frontend,
)
from tools.s3test import ImpactMap, _profile_selection


ROOT = Path(__file__).parents[1]
IMPACT = ImpactMap.load(ROOT / "tests" / "test-impact.json")

EXPECTED = (
    "tests/test_m261_lexer_candidate.py",
    "tests/test_m262_parser_candidate.py",
    "tests/test_m263_canonical_ast_candidate.py",
    "tests/test_m264_module_candidate.py",
    "tests/test_m265_diagnostic_candidate.py",
    "tests/test_m266_workspace_candidate.py",
    "tests/test_m267_incremental_invalidation.py",
    "tests/test_m268_assembly_frontend_closure.py",
    "tests/test_m269_frontend_canary.py",
)


def test_frontend_level_c_profile_covers_m261_through_m269_in_order() -> None:
    selections, tests = _profile_selection(
        ROOT, IMPACT, "level-c-frontend", None, None
    )
    assert tests == EXPECTED
    assert tuple(selection.test for selection in selections) == EXPECTED
    assert all(selection.tiers == ("LEVEL-C",) for selection in selections)


def test_frontend_level_c_profile_is_not_t4() -> None:
    selections, _ = _profile_selection(ROOT, IMPACT, "level-c-frontend", None, None)
    assert all("T4" not in selection.tiers for selection in selections)


def test_python_reference_remains_the_default_frontend_path() -> None:
    result = run_assembly_frontend(".s3asm 0.8.0\n")
    assert result.requested_mode is FrontendExecutionMode.PYTHON_REFERENCE
    assert result.selected_mode is FrontendExecutionMode.PYTHON_REFERENCE
    assert result.used_fallback is False
