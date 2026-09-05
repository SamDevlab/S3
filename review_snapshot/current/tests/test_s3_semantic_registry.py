"""Focused contracts for the derived semantic registry."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.s3_lang import canonical_registry_bytes, load_registry, registry_sha256, semantic_diff


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "reports" / "language" / "S3_SEMANTIC_REGISTRY.json"


def test_registry_is_deterministic_and_derived() -> None:
    data = load_registry(REGISTRY)
    rule_ids = [rule["rule_id"] for rule in data["rules"]]
    assert rule_ids == sorted(rule_ids)
    assert all(rule["provenance_class"] == "DERIVED" for rule in data["rules"])
    assert registry_sha256(data) == registry_sha256(load_registry(REGISTRY))
    assert canonical_registry_bytes(data).endswith(b"\n")


def test_registry_semantics_do_not_depend_on_json_object_key_order(tmp_path: Path) -> None:
    source = json.loads(REGISTRY.read_text(encoding="utf-8"))
    reordered = {
        "rules": [
            {key: rule[key] for key in reversed(tuple(rule))}
            for rule in reversed(source["rules"])
        ],
        "provenance": source["provenance"],
        "version": source["version"],
        "format": source["format"],
    }
    path = tmp_path / "reordered.json"
    path.write_text(json.dumps(reordered), encoding="utf-8")

    assert load_registry(path) == load_registry(REGISTRY)


def test_registry_rejects_duplicate_rule_ids(tmp_path: Path) -> None:
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    data["rules"].append(dict(data["rules"][0]))
    path = tmp_path / "duplicate.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="unique"):
        load_registry(path)


def test_semantic_diff_is_explicit_about_rule_changes(tmp_path: Path) -> None:
    original = load_registry(REGISTRY)
    changed = json.loads(json.dumps(original))
    changed["rules"][0]["notes"] = ["test change"]
    changed_path = tmp_path / "changed.json"
    changed_path.write_text(json.dumps(changed), encoding="utf-8")

    diff = semantic_diff(original, load_registry(changed_path))

    assert diff["RULES_ADDED"] == []
    assert diff["RULES_REMOVED"] == []
    assert diff["RULES_CHANGED"] == [changed["rules"][0]["rule_id"]]
    assert diff["AUTHORITATIVE_SOURCE_CHANGED"] == []
