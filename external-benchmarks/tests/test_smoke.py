from __future__ import annotations

import sys
from pathlib import Path

EXTERNAL_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = EXTERNAL_ROOT.parent
sys.path.insert(0, str(EXTERNAL_ROOT))

from harness.smoke import run_protocol_smoke  # noqa: E402


def test_agent_memory_v1_offline_smoke_covers_all_28_bundles(tmp_path: Path) -> None:
    result = run_protocol_smoke(
        repository_root=REPOSITORY_ROOT,
        workspace_root=tmp_path,
        with_oracles=False,
    )

    assert result == {
        "schema_version": "1.0.0",
        "kind": "protocol-smoke",
        "status": "PASS",
        "scientific_claims_allowed": False,
        "subject_commit": "db5f4bf10e2066f52bf144d23e6f7db56154e298",
        "providers": 4,
        "scenarios": 7,
        "bundles": 28,
        "phase_steps": 52,
        "synthetic_observations": 28,
        "semantic_oracles_validated": 0,
        "semantic_oracle_failures": [],
    }

    for provider in (
        "no-memory",
        "context-only",
        "ai-memory",
        "ai-memory+s3-integrity-gate",
    ):
        run_dir = tmp_path / provider / "run-1"
        assert (run_dir / "plan.json").is_file()
        assert (run_dir / "runbook.json").is_file()
        assert (run_dir / "prompts").is_dir()
