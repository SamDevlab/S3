from __future__ import annotations

import hashlib
from pathlib import Path

from tools.s3_111_value_cost_experiments import _artifact_facts, _check_guard


def _facts(*, peak_live: int, stack_resident: int) -> dict[str, object]:
    return {"allocation": {
        "peak_live_virtual_registers": peak_live,
        "stack_resident_virtual_register_count": stack_resident,
    }}


def test_pressure_guard_accepts_nonincreasing_static_pressure() -> None:
    result = _check_guard(
        _facts(peak_live=12, stack_resident=4),
        _facts(peak_live=11, stack_resident=4),
    )
    assert result["pressure_guard_accepts"] is True


def test_pressure_guard_rejects_stack_residency_growth() -> None:
    result = _check_guard(
        _facts(peak_live=11, stack_resident=4),
        _facts(peak_live=11, stack_resident=5),
    )
    assert result["stack_resident_virtual_delta"] == 1
    assert result["pressure_guard_accepts"] is False


def test_pressure_guard_rejects_peak_live_growth() -> None:
    result = _check_guard(
        _facts(peak_live=11, stack_resident=4),
        _facts(peak_live=12, stack_resident=4),
    )
    assert result["peak_live_delta"] == 1
    assert result["pressure_guard_accepts"] is False


def test_pareto_guard_rejects_memory_growth_despite_smaller_code() -> None:
    baseline = {
        **_facts(peak_live=8, stack_resident=2),
    }
    candidate = {
        **_facts(peak_live=8, stack_resident=2),
    }
    baseline_binary = {
        "text_section_bytes": 100,
        "static_machine_instructions": 10,
        "static_memory_references": 5,
        "static_stack_references": 4,
        "static_branches": 2,
        "stack_frame_bytes": 32,
    }
    candidate_binary = {
        **baseline_binary,
        "text_section_bytes": 90,
        "static_machine_instructions": 9,
        "static_memory_references": 6,
    }
    result = _check_guard(baseline, candidate, baseline_binary, candidate_binary)
    assert result["pressure_guard_accepts"] is True
    assert result["native_pareto_dominates"] is False
    assert result["adaptive_candidate_selected"] is False


def test_pareto_guard_selects_strict_native_improvement_without_pressure_growth() -> None:
    baseline = _facts(peak_live=8, stack_resident=2)
    candidate = _facts(peak_live=7, stack_resident=2)
    baseline_binary = {
        "text_section_bytes": 100,
        "static_machine_instructions": 10,
        "static_memory_references": 5,
        "static_stack_references": 4,
        "static_branches": 2,
        "stack_frame_bytes": 32,
    }
    candidate_binary = {
        "text_section_bytes": 90,
        "static_machine_instructions": 9,
        "static_memory_references": 4,
        "static_stack_references": 3,
        "static_branches": 1,
        "stack_frame_bytes": 16,
    }
    result = _check_guard(baseline, candidate, baseline_binary, candidate_binary)
    assert result["pressure_guard_accepts"] is True
    assert result["native_pareto_dominates"] is True
    assert result["adaptive_candidate_selected"] is True


def test_native_artifact_facts_pin_filename_size_and_digest(tmp_path: Path) -> None:
    artifact = tmp_path / "candidate.so"
    artifact.write_bytes(b"native candidate bytes")

    assert _artifact_facts(artifact) == {
        "file_name": "candidate.so",
        "bytes": len(b"native candidate bytes"),
        "sha256": hashlib.sha256(b"native candidate bytes").hexdigest(),
    }
