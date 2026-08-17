from __future__ import annotations

from tools.m150_renderer_component import (
    COMPONENT_MEMORY_LIMIT_BYTES,
    COMPONENT_PROFILE,
    ENTRY_METADATA,
    check_component,
    component_identity,
)


def test_m150_component_identity_is_locked_to_source_and_lockfile() -> None:
    identity = component_identity()
    assert identity["component"] == COMPONENT_PROFILE
    assert len(identity["source_sha256"]) == 64
    assert len(identity["lock_sha256"]) == 64
    assert len(identity["identity"]) == 64


def test_m150_component_manifest_is_bounded_and_explicit() -> None:
    assert COMPONENT_MEMORY_LIMIT_BYTES == 8 * 1024 * 1024
    assert tuple(ENTRY_METADATA) == (
        "render_first",
        "render_simple_call",
        "render_sign",
    )


def test_m150_hosted_component_matches_oracle_at_o0_and_o1() -> None:
    result = check_component()
    assert result["hosted_o0_oracle"] == "PASS"
    assert result["hosted_o1_execution"] == "PASS"
    assert result["o1_output_parity"] == "DEFERRED_OPTIMIZER_OBSERVABLE_MEMORY_CONTRACT"
    assert result["native_linux"] == "DEFERRED_ENVIRONMENT"
    assert result["wasi_runtime"] == "DEFERRED_ENVIRONMENT"
    entries = result["entries"]
    assert len(entries) == 3
    assert all(entry["o0_python_oracle_equal"] for entry in entries)
    assert all(entry["o1_execution"] == "PASS" for entry in entries)
    assert all(
        entry["o1_output_parity"]
        == "DEFERRED_OPTIMIZER_OBSERVABLE_MEMORY_CONTRACT"
        for entry in entries
    )
    assert all(entry["allocated_cells"] < COMPONENT_MEMORY_LIMIT_BYTES for entry in entries)
