from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

EXTERNAL_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = EXTERNAL_ROOT.parent
sys.path.insert(0, str(EXTERNAL_ROOT))

from harness.core import ExternalBenchmarkError  # noqa: E402
from harness.worktrees import (  # noqa: E402
    cleanup_worktrees,
    prepare_worktrees,
    worktree_plan_document,
)


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _plan(commit: str) -> dict[str, object]:
    return {
        "execution": {"s3_commit": commit},
        "scenarios": [
            {
                "scenario_id": "one",
                "worktree_key": "provider/run-1/one",
            }
        ],
    }


def test_worktree_plan_is_detached_and_outside_controller(tmp_path: Path) -> None:
    commit = _git(REPOSITORY_ROOT, "rev-parse", "HEAD")
    document = worktree_plan_document(
        _plan(commit),
        repository_root=REPOSITORY_ROOT,
        worktree_root=tmp_path / "worktrees",
    )
    argv = document["worktrees"][0]["argv"]
    assert "worktree" in argv
    assert "--detach" in argv
    assert argv[-1] == commit


def test_worktree_root_inside_controller_is_rejected() -> None:
    commit = _git(REPOSITORY_ROOT, "rev-parse", "HEAD")
    with pytest.raises(ExternalBenchmarkError, match="outside the controller"):
        worktree_plan_document(
            _plan(commit),
            repository_root=REPOSITORY_ROOT,
            worktree_root=REPOSITORY_ROOT / ".tmp-external-worktrees",
        )


def test_prepare_and_cleanup_clean_worktree(tmp_path: Path) -> None:
    commit = _git(REPOSITORY_ROOT, "rev-parse", "HEAD")
    root = tmp_path / "worktrees"
    specs = prepare_worktrees(
        _plan(commit),
        repository_root=REPOSITORY_ROOT,
        worktree_root=root,
    )
    try:
        assert len(specs) == 1
        assert specs[0].path.is_dir()
        assert _git(specs[0].path, "rev-parse", "HEAD") == commit
        state = json.loads((root / ".s3-external-worktrees.json").read_text(encoding="utf-8"))
        assert state["worktrees"][0]["scenario_id"] == "one"
    finally:
        cleanup_worktrees(
            repository_root=REPOSITORY_ROOT,
            worktree_root=root,
        )
    assert not specs[0].path.exists()


def test_cleanup_refuses_dirty_worktree_without_explicit_discard(tmp_path: Path) -> None:
    commit = _git(REPOSITORY_ROOT, "rev-parse", "HEAD")
    root = tmp_path / "worktrees"
    specs = prepare_worktrees(
        _plan(commit),
        repository_root=REPOSITORY_ROOT,
        worktree_root=root,
    )
    (specs[0].path / "experiment.tmp").write_text("dirty\n", encoding="utf-8")
    with pytest.raises(ExternalBenchmarkError, match="--discard-changes"):
        cleanup_worktrees(
            repository_root=REPOSITORY_ROOT,
            worktree_root=root,
        )
    cleanup_worktrees(
        repository_root=REPOSITORY_ROOT,
        worktree_root=root,
        discard_changes=True,
    )
    assert not specs[0].path.exists()
