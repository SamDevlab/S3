"""Query the derived S3 semantic registry without replacing its authorities."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "reports" / "language" / "S3_SEMANTIC_REGISTRY.json"
REQUIRED_FIELDS = {
    "rule_id", "category", "status", "title", "description",
    "authoritative_source", "source_location", "provenance_class",
    "accepted_forms", "rejected_forms", "type_rules", "control_flow_effect",
    "ir_effect", "resource_effect", "fail_closed_behavior",
    "related_signatures", "related_diagnostics", "test_references", "notes",
}


def load_registry(path: Path = DEFAULT_REGISTRY) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("format") != "s3-derived-semantic-registry":
        raise ValueError("unexpected semantic registry format")
    rules = data.get("rules")
    if not isinstance(rules, list):
        raise ValueError("semantic registry rules must be a list")
    rule_ids = [rule.get("rule_id") for rule in rules]
    if any(not isinstance(rule_id, str) for rule_id in rule_ids):
        raise ValueError("semantic rule IDs must be strings")
    if len(set(rule_ids)) != len(rule_ids):
        raise ValueError("semantic rule IDs must be unique")
    for rule in rules:
        missing = REQUIRED_FIELDS - set(rule)
        if missing:
            raise ValueError(f"semantic rule {rule.get('rule_id')} missing {sorted(missing)}")
        if rule["provenance_class"] != "DERIVED":
            raise ValueError(f"semantic rule {rule['rule_id']} must remain DERIVED")
    normalized = dict(data)
    normalized["rules"] = sorted(rules, key=lambda rule: rule["rule_id"])
    return normalized


def canonical_registry_bytes(data: dict[str, Any]) -> bytes:
    return (json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def registry_sha256(data: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_registry_bytes(data)).hexdigest()


def _rule_map(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {rule["rule_id"]: rule for rule in data["rules"]}


def semantic_diff(old: dict[str, Any], new: dict[str, Any]) -> dict[str, list[str]]:
    before = _rule_map(old)
    after = _rule_map(new)
    return {
        "RULES_ADDED": sorted(set(after) - set(before)),
        "RULES_REMOVED": sorted(set(before) - set(after)),
        "RULES_CHANGED": sorted(rule_id for rule_id in set(before) & set(after) if before[rule_id] != after[rule_id]),
        "AUTHORITATIVE_SOURCE_CHANGED": sorted(
            rule_id for rule_id in set(before) & set(after)
            if before[rule_id].get("authoritative_source") != after[rule_id].get("authoritative_source")
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("check")
    subparsers.add_parser("rules")
    subparsers.add_parser("ruleset-sha")
    query = subparsers.add_parser("query")
    query.add_argument("rule_id")
    signature = subparsers.add_parser("signature")
    signature.add_argument("name")
    diff = subparsers.add_parser("semantic-diff")
    diff.add_argument("old", type=Path)
    diff.add_argument("new", type=Path)
    args = parser.parse_args(argv)

    data = load_registry(args.registry)
    if args.command == "check":
        print("SEMANTIC_REGISTRY=PASS")
    elif args.command == "rules":
        print(json.dumps(data["rules"], ensure_ascii=False, sort_keys=True))
    elif args.command == "ruleset-sha":
        print(f"SEMANTIC_RULESET_SHA256={registry_sha256(data)}")
    elif args.command == "query":
        rule = _rule_map(data).get(args.rule_id)
        if rule is None:
            raise SystemExit(f"unknown semantic rule: {args.rule_id}")
        print(json.dumps(rule, ensure_ascii=False, sort_keys=True))
    elif args.command == "signature":
        matches = [
            rule for rule in data["rules"]
            if args.name in rule.get("related_signatures", [])
        ]
        print(json.dumps({"name": args.name, "rules": matches}, ensure_ascii=False, sort_keys=True))
    elif args.command == "semantic-diff":
        print(json.dumps(semantic_diff(load_registry(args.old), load_registry(args.new)), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
