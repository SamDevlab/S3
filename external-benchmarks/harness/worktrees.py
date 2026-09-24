"""Safe git-worktree orchestration for isolated external benchmark scenarios."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .core import ExternalBenchmarkError

_STATE_FILE = ".s3-external-worktrees.json"


def _object(value: object, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ExternalBenchmarkError(f"{name} must be a JSON object")
    return value


def _safe_relative(value: object, name: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ExternalBenchmarkError(f"{name} must be a non-empty string")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ExternalBenchmarkError(f"{name} must be repository-relative")
    return path


def _run(argv: Sequence[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            list(argv),
            cwd=cwd,
            capture_output=True,
            text=True,
            shell=False,
            check=False,
        )
    except OSError as error:
        raise ExternalBenchmarkError(f"could not execute {argv[0]}") from error


def _git(repository_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return _run(("git", "-C", str(repository_root), *args))


def _canonical_repository_root(repository_root: Path) -> Path:
    repository_root = repository_root.resolve()
    result = _git(repository_root, "rev-parse", "--show-toplevel")
    if result.returncode != 0:
        raise ExternalBenchmarkError("repository_root is not a git worktree")
    resolved = Path(result.stdout.strip()).resolve()
    if resolved != repository_root:
        raise ExternalBenchmarkError("repository_root must be the git worktree root")
    return resolved


def _resolve_commit(repository_root: Path, revision: str) -> str:
    result = _git(repository_root, "rev-parse", "--verify", f"{revision}^{{commit}}")
    if result.returncode != 0:
        raise ExternalBenchmarkError("run-plan S3 commit does not exist locally")
    commit = result.stdout.strip()
    if len(commit) != 40:
        raise ExternalBenchmarkError("git did not resolve a full commit id")
    return commit


@dataclass(frozen=True, slots=True)
class WorktreeSpec:
    scenario_id: str
    path: Path
    commit: str

    def as_document(self) -> dict[str, str]:
        return {
            "scenario_id": self.scenario_id,
            "path": str(self.path),
            "commit": self.commit,
        }


def build_worktree_specs(
    plan: Mapping[str, Any],
    *,
    repository_root: Path,
    worktree_root: Path,
) -> list[WorktreeSpec]:
    """Resolve isolated worktree paths for every scenario in one run plan."""

    repository_root = _canonical_repository_root(repository_root)
    execution = _object(plan.get("execution"), "run plan execution")
    revision = execution.get("s3_commit")
    if not isinstance(revision, str) or not revision:
        raise ExternalBenchmarkError("run plan execution.s3_commit is invalid")
    commit = _resolve_commit(repository_root, revision)

    rows = plan.get("scenarios")
    if not isinstance(rows, list) or not rows:
        raise ExternalBenchmarkError("run plan scenarios must be a non-empty list")

    root = worktree_root.resolve()
    if root == repository_root or repository_root in root.parents:
        raise ExternalBenchmarkError("worktree_root must be outside the controller repository")

    specs: list[WorktreeSpec] = []
    seen: set[Path] = set()
    for raw in rows:
        row = _object(raw, "run plan scenario")
        scenario_id = row.get("scenario_id")
        if not isinstance(scenario_id, str) or not scenario_id:
            raise ExternalBenchmarkError("run plan scenario_id is invalid")
        key = _safe_relative(row.get("worktree_key"), "run plan worktree_key")
        target = (root / key).resolve()
        try:
            target.relative_to(root)
        except ValueError as error:
            raise ExternalBenchmarkError("worktree path escapes worktree_root") from error
        if target in seen:
            raise ExternalBenchmarkError("duplicate worktree path in run plan")
        seen.add(target)
        specs.append(WorktreeSpec(scenario_id=scenario_id, path=target, commit=commit))
    return specs


def worktree_plan_document(
    plan: Mapping[str, Any],
    *,
    repository_root: Path,
    worktree_root: Path,
) -> dict[str, object]:
    specs = build_worktree_specs(
        plan,
        repository_root=repository_root,
        worktree_root=worktree_root,
    )
    return {
        "schema_version": "1.0.0",
        "operation": "prepare",
        "worktrees": [
            {
                **spec.as_document(),
                "argv": [
                    "git",
                    "-C",
                    str(repository_root.resolve()),
                    "worktree",
                    "add",
                    "--detach",
                    str(spec.path),
                    spec.commit,
                ],
            }
            for spec in specs
        ],
    }


def _state_path(worktree_root: Path) -> Path:
    return worktree_root.resolve() / _STATE_FILE


def prepare_worktrees(
    plan: Mapping[str, Any],
    *,
    repository_root: Path,
    worktree_root: Path,
) -> list[WorktreeSpec]:
    """Create all scenario worktrees atomically enough to avoid silent partial setup."""

    repository_root = _canonical_repository_root(repository_root)
    specs = build_worktree_specs(
        plan,
        repository_root=repository_root,
        worktree_root=worktree_root,
    )
    root = worktree_root.resolve()
    state_path = _state_path(root)
    if state_path.exists():
        raise ExternalBenchmarkError("worktree_root already contains external benchmark state")
    for spec in specs:
        if spec.path.exists():
            raise ExternalBenchmarkError(f"worktree destination already exists: {spec.path}")

    root.mkdir(parents=True, exist_ok=True)
    created: list[WorktreeSpec] = []
    try:
        for spec in specs:
            spec.path.parent.mkdir(parents=True, exist_ok=True)
            result = _git(
                repository_root,
                "worktree",
                "add",
                "--detach",
                str(spec.path),
                spec.commit,
            )
            if result.returncode != 0:
                raise ExternalBenchmarkError(
                    f"git worktree add failed for {spec.scenario_id}: {result.stderr.strip()}"
                )
            head = _git(spec.path, "rev-parse", "HEAD")
            if head.returncode != 0 or head.stdout.strip() != spec.commit:
                raise ExternalBenchmarkError(
                    f"prepared worktree commit mismatch for {spec.scenario_id}"
                )
            created.append(spec)

        state = {
            "schema_version": "1.0.0",
            "repository_root": str(repository_root),
            "worktrees": [spec.as_document() for spec in specs],
        }
        state_path.write_text(
            json.dumps(state, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        return specs
    except Exception:
        for spec in reversed(created):
            _git(repository_root, "worktree", "remove", "--force", str(spec.path))
        _git(repository_root, "worktree", "prune")
        if state_path.exists():
            state_path.unlink()
        raise


def _load_state(worktree_root: Path) -> dict[str, Any]:
    path = _state_path(worktree_root)
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ExternalBenchmarkError("external worktree state is unavailable") from error
    except json.JSONDecodeError as error:
        raise ExternalBenchmarkError("external worktree state is invalid JSON") from error
    return _object(document, "external worktree state")


def cleanup_worktrees(
    *,
    repository_root: Path,
    worktree_root: Path,
    discard_changes: bool = False,
) -> None:
    """Remove only worktrees recorded under the dedicated external-benchmark root."""

    repository_root = _canonical_repository_root(repository_root)
    root = worktree_root.resolve()
    state = _load_state(root)
    if Path(str(state.get("repository_root", ""))).resolve() != repository_root:
        raise ExternalBenchmarkError("worktree state belongs to another repository")
    rows = state.get("worktrees")
    if not isinstance(rows, list):
        raise ExternalBenchmarkError("external worktree state has invalid worktrees")

    for raw in rows:
        row = _object(raw, "external worktree state row")
        path = Path(str(row.get("path", ""))).resolve()
        try:
            path.relative_to(root)
        except ValueError as error:
            raise ExternalBenchmarkError("recorded worktree escapes worktree_root") from error
        if not path.exists():
            continue
        status = _git(path, "status", "--porcelain")
        if status.returncode != 0:
            raise ExternalBenchmarkError(f"cannot inspect worktree before cleanup: {path}")
        dirty = bool(status.stdout.strip())
        if dirty and not discard_changes:
            raise ExternalBenchmarkError(
                "worktree has uncommitted experiment changes; pass --discard-changes to remove it"
            )
        args = ["worktree", "remove"]
        if dirty:
            args.append("--force")
        args.append(str(path))
        result = _git(repository_root, *args)
        if result.returncode != 0:
            raise ExternalBenchmarkError(
                f"git worktree remove failed: {result.stderr.strip()}"
            )
    _git(repository_root, "worktree", "prune")
    _state_path(root).unlink(missing_ok=True)
