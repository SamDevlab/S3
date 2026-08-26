from __future__ import annotations

import json
from pathlib import Path

import pytest

import tools.selfhost_contract_authority as authority
from tools.selfhost_contract_authority import (
    ContractAuthorityError,
    require_authoritative_contract,
)


pytestmark = pytest.mark.s3_fast


def _write(path: Path, document: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def test_exact_authoritative_contract_passes(tmp_path: Path) -> None:
    authoritative = tmp_path / "authority.json"
    document = {
        "schema": "example.contract.v1",
        "required": {"gate_a": True, "gate_b": True},
    }
    _write(authoritative, document)
    loaded, binding = require_authoritative_contract(
        authoritative,
        authoritative=authoritative,
        expected_schema="example.contract.v1",
        label="example contract",
    )
    assert loaded == document
    assert binding["status"] == "PASS_CANONICAL_CONTRACT_AUTHORITY"
    assert binding["exact_bytes_equal"] is True
    assert binding["candidate_path"] == binding["authoritative_path"]
    assert len(binding["sha256"]) == 64
    assert "git_head_binding" not in binding


def test_byte_identical_relocated_contract_passes(tmp_path: Path) -> None:
    authoritative = tmp_path / "authority.json"
    relocated = tmp_path / "relocated.json"
    document = {
        "schema": "example.contract.v1",
        "required": {"gate_a": True, "gate_b": True},
    }
    _write(authoritative, document)
    relocated.write_bytes(authoritative.read_bytes())
    _, binding = require_authoritative_contract(
        relocated,
        authoritative=authoritative,
        expected_schema="example.contract.v1",
        label="example contract",
    )
    assert binding["candidate_path"] != binding["authoritative_path"]
    assert binding["exact_bytes_equal"] is True


def test_same_schema_but_weakened_policy_is_rejected(tmp_path: Path) -> None:
    authoritative = tmp_path / "authority.json"
    weakened = tmp_path / "weakened.json"
    _write(
        authoritative,
        {
            "schema": "example.contract.v1",
            "required": {"gate_a": True, "gate_b": True},
        },
    )
    _write(
        weakened,
        {
            "schema": "example.contract.v1",
            "required": {"gate_a": True},
        },
    )
    with pytest.raises(ContractAuthorityError, match="not the canonical authoritative policy"):
        require_authoritative_contract(
            weakened,
            authoritative=authoritative,
            expected_schema="example.contract.v1",
            label="example contract",
        )


def test_schema_alias_cannot_bypass_authority(tmp_path: Path) -> None:
    authoritative = tmp_path / "authority.json"
    candidate = tmp_path / "candidate.json"
    _write(authoritative, {"schema": "example.contract.v1", "required": {"gate": True}})
    _write(candidate, {"schema": "example.contract.v2", "required": {"gate": True}})
    with pytest.raises(ContractAuthorityError, match="schema mismatch"):
        require_authoritative_contract(
            candidate,
            authoritative=authoritative,
            expected_schema="example.contract.v1",
            label="example contract",
        )


def test_invalid_json_contract_is_rejected_before_policy_use(tmp_path: Path) -> None:
    authoritative = tmp_path / "authority.json"
    candidate = tmp_path / "candidate.json"
    _write(authoritative, {"schema": "example.contract.v1", "required": {"gate": True}})
    candidate.write_text("{broken", encoding="utf-8")
    with pytest.raises(ContractAuthorityError, match="not valid UTF-8 JSON"):
        require_authoritative_contract(
            candidate,
            authoritative=authoritative,
            expected_schema="example.contract.v1",
            label="example contract",
        )


def test_git_checkout_policy_is_automatically_bound_to_head(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    authoritative = repo / "policy.json"
    _write(authoritative, {"schema": "example.contract.v1", "required": {"gate": True}})
    payload = authoritative.read_bytes()
    head = "a" * 40
    calls: list[list[str]] = []

    def fake_run_git(root: Path, args: list[str]) -> bytes:
        assert root.resolve() == repo.resolve()
        calls.append(args)
        if args == ["rev-parse", "HEAD"]:
            return (head + "\n").encode("ascii")
        if args == ["cat-file", "-t", head]:
            return b"commit\n"
        if args == ["show", f"{head}:policy.json"]:
            return payload
        raise AssertionError(args)

    monkeypatch.setattr(authority, "_run_git", fake_run_git)
    _, binding = require_authoritative_contract(
        authoritative,
        authoritative=authoritative,
        expected_schema="example.contract.v1",
        label="example contract",
    )
    git_binding = binding["git_head_binding"]
    assert git_binding["status"] == "PASS_REPOSITORY_FILE_GIT_HEAD_BINDING"
    assert git_binding["commit"] == head
    assert git_binding["working_tree_equals_head_blob"] is True
    assert calls == [
        ["rev-parse", "HEAD"],
        ["cat-file", "-t", head],
        ["show", f"{head}:policy.json"],
    ]


def test_uncommitted_authoritative_policy_edit_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    authoritative = repo / "policy.json"
    _write(authoritative, {"schema": "example.contract.v1", "required": {"gate": False}})
    head = "b" * 40

    def fake_run_git(root: Path, args: list[str]) -> bytes:
        del root
        if args == ["rev-parse", "HEAD"]:
            return (head + "\n").encode("ascii")
        if args == ["cat-file", "-t", head]:
            return b"commit\n"
        if args == ["show", f"{head}:policy.json"]:
            return b'{"schema":"example.contract.v1","required":{"gate":true}}\n'
        raise AssertionError(args)

    monkeypatch.setattr(authority, "_run_git", fake_run_git)
    with pytest.raises(ContractAuthorityError, match="differs from its Git HEAD blob"):
        require_authoritative_contract(
            authoritative,
            authoritative=authoritative,
            expected_schema="example.contract.v1",
            label="example contract",
        )
