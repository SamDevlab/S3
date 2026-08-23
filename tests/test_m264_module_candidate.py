"""M2.64 bounded module/import candidate differential contracts."""

from __future__ import annotations

from pathlib import Path

import pytest

from bootstrap.s3.module_candidate import (
    ModuleCandidateError,
    candidate_module_fingerprint,
    reference_module_fingerprint,
    run_module_differential,
)


ROOT = Path(__file__).parents[1]
SELFHOST_SOURCE = (ROOT / "selfhost/frontend/module_candidate.s3").read_text(
    encoding="utf-8"
)


def test_candidate_source_is_s3_authored_and_bounded() -> None:
    assert "fn module_import_fingerprint" in SELFHOST_SOURCE
    assert "tryte[16]" in SELFHOST_SOURCE
    assert "fn main" not in SELFHOST_SOURCE


@pytest.mark.parametrize(
    "source",
    [
        "module app\n",
        "from math import inc\n",
    ],
)
def test_candidate_matches_module_reference(source: str) -> None:
    evidence = run_module_differential(source)
    assert evidence.reference_fingerprint == reference_module_fingerprint(source)
    assert evidence.candidate_fingerprint == candidate_module_fingerprint(source)
    assert evidence.match is True


def test_module_and_import_names_are_semantically_visible() -> None:
    assert reference_module_fingerprint("module app\n") != reference_module_fingerprint(
        "module core\n"
    )
    assert reference_module_fingerprint("from math import inc\n") != reference_module_fingerprint(
        "from math import dec\n"
    )


def test_candidate_rejects_other_top_level_declarations() -> None:
    with pytest.raises(ModuleCandidateError, match="unsupported"):
        candidate_module_fingerprint("from math as alias\n")
