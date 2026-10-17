from __future__ import annotations

import sys
from pathlib import Path

import pytest

EXTERNAL_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = EXTERNAL_ROOT.parent
sys.path.insert(0, str(EXTERNAL_ROOT))

from harness.core import ExternalBenchmarkError  # noqa: E402
from harness.provider_profile import (  # noqa: E402
    build_provider_profile,
    provider_profile_identity,
    sanitize_provider_profile,
)


def test_gated_profile_uses_current_registry_hash() -> None:
    profile = build_provider_profile(
        "ai-memory+s3-integrity-gate",
        repository_root=REPOSITORY_ROOT,
    )

    clean = sanitize_provider_profile(
        profile,
        provider_id="ai-memory+s3-integrity-gate",
    )
    assert clean == profile
    assert clean["integrity_gate"]["enabled"] is True
    assert len(clean["integrity_gate"]["registry_sha256"]) == 64


def test_plain_ai_memory_profile_has_gate_disabled() -> None:
    profile = build_provider_profile("ai-memory", repository_root=REPOSITORY_ROOT)

    assert profile == {
        "schema_version": "1.0.0",
        "memory_mode": "ai-memory",
        "integrity_gate": {"enabled": False},
    }


def test_profile_sanitizer_rejects_gate_state_that_does_not_match_arm() -> None:
    with pytest.raises(ExternalBenchmarkError, match="gate state"):
        sanitize_provider_profile(
            {
                "schema_version": "1.0.0",
                "memory_mode": "ai-memory",
                "integrity_gate": {
                    "enabled": True,
                    "registry_schema_version": "1.0.0",
                    "registry_sha256": "a" * 64,
                },
            },
            provider_id="ai-memory",
        )


def test_profile_identity_is_order_independent() -> None:
    left = {
        "schema_version": "1.0.0",
        "memory_mode": "ai-memory",
        "integrity_gate": {"enabled": False},
    }
    right = {
        "integrity_gate": {"enabled": False},
        "memory_mode": "ai-memory",
        "schema_version": "1.0.0",
    }

    assert provider_profile_identity(left) == provider_profile_identity(right)
