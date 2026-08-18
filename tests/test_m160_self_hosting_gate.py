from __future__ import annotations

import pytest

from bootstrap.s3.self_hosting_gate import (
    M160_MAX_FRAMES,
    M160_MAX_INSTRUCTIONS,
    M160_MAX_MEMORY_CELLS,
    M160_MAX_SOURCE_BYTES,
    SelfHostingGateError,
    run_manifest_self_hosting_gate,
)


def _manifest(path, *, mode: str = "hosted"):
    path.mkdir(parents=True, exist_ok=True)
    (path / "case.s3").write_text("fn main() -> tryte:\n    return 1\n", encoding="utf-8")
    manifest = path / "s3-test.toml"
    manifest.write_text(
        f"""\
[runner]
seed = 17
timeout_ms = 5000
max_frames = 64
max_instructions = 1000
optimization = "O1"
mode = "{mode}"

[[test]]
name = "alpha"
source = "case.s3"
expected = 1
""",
        encoding="utf-8",
    )
    return manifest


def test_m160_bounded_manifest_projection_matches_python_oracle(tmp_path) -> None:
    result = run_manifest_self_hosting_gate(_manifest(tmp_path))

    assert result.equal is True
    assert result.deterministic is True
    assert result.used_fallback is False
    assert result.candidate_value == result.oracle_value
    assert result.source_bytes <= M160_MAX_SOURCE_BYTES
    assert result.memory_cells <= M160_MAX_MEMORY_CELLS
    assert result.max_frames == M160_MAX_FRAMES
    assert result.max_instructions == M160_MAX_INSTRUCTIONS


def test_m160_projection_is_deterministic_across_manifest_modes(tmp_path) -> None:
    hosted = run_manifest_self_hosting_gate(_manifest(tmp_path / "hosted"))
    native = run_manifest_self_hosting_gate(_manifest(tmp_path / "native", mode="native"))

    assert hosted.as_dict() == run_manifest_self_hosting_gate(_manifest(tmp_path / "hosted")).as_dict()
    assert hosted.oracle_value != native.oracle_value
    assert native.equal is True


def test_m160_candidate_failure_uses_authoritative_python_fallback(tmp_path) -> None:
    result = run_manifest_self_hosting_gate(
        _manifest(tmp_path),
        candidate_source="fn main(\n",
    )

    assert result.equal is True
    assert result.used_fallback is True
    assert result.candidate_value is None
    assert result.fallback_reason


def test_m160_candidate_disagreement_is_not_hidden_by_fallback(tmp_path) -> None:
    with pytest.raises(SelfHostingGateError, match="candidate disagrees"):
        run_manifest_self_hosting_gate(
            _manifest(tmp_path),
            candidate_source="fn main() -> i64:\n    return 0\n",
        )


def test_m160_fallback_can_be_disabled(tmp_path) -> None:
    with pytest.raises(SelfHostingGateError, match="failed without fallback"):
        run_manifest_self_hosting_gate(
            _manifest(tmp_path),
            allow_fallback=False,
            candidate_source="fn main(\n",
        )
