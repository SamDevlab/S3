from __future__ import annotations

import pytest

from tools.patch_stage1_codegen_ir_v2_parameters_after_token_lane import (
    build_candidate,
)
from tools.patch_stage1_token_lane_wide_literals import SOURCE


def test_rebased_parameter_candidate_rejects_advanced_source() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="packed parameter candidate is stale"):
        build_candidate(source)


def test_rebased_parameter_candidate_is_deterministic() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="packed parameter candidate is stale"):
        build_candidate(source)
