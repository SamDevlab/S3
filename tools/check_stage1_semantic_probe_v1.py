"""Verify a partial native Stage1 semantic-probe stream fail-closed."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.stage1_semantic_stream_protocol import parse_stream, verify_stream


def check(text: str) -> dict[str, Any]:
    parsed = parse_stream(text)
    verification = verify_stream(parsed)
    values = [record for record in parsed["records"] if record["tag"] == "V"]
    memories = [record for record in parsed["records"] if record["tag"] == "M"]
    value_kinds: dict[int, int] = {}
    for record in values:
        kind = record["fields"][2]
        value_kinds[kind] = value_kinds.get(kind, 0) + 1

    errors: list[str] = []
    if parsed["completeness_mask"] != 0:
        errors.append("S1 probe must remain incomplete with mask 0")
    if verification["status"] != "BLOCKED":
        errors.append("partial probe must not verify as complete PASS")
    if value_kinds.get(1, 0) < 1:
        errors.append("probe emitted no parameter value definitions")
    if value_kinds.get(2, 0) < 1:
        errors.append("probe emitted no local value definitions")

    return {
        "schema": "s3.selfhost.semantic-native-probe-check.v1",
        "status": "PASS_PARTIAL_EVIDENCE" if not errors else "FAIL",
        "completeness_mask": parsed["completeness_mask"],
        "stream_verification": verification["status"],
        "value_records": len(values),
        "memory_records": len(memories),
        "value_kind_counts": {str(key): value for key, value in sorted(value_kinds.items())},
        "errors": errors,
        "S1_typed_values": "PARTIAL",
        "general_emitter_authorized": False,
        "self_emit_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stream", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    report = check(args.stream.read_text(encoding="utf-8"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"STATUS={report['status']}")
    print(f"VALUE_RECORDS={report['value_records']}")
    print(f"PARAMETER_VALUES={report['value_kind_counts'].get('1', 0)}")
    print(f"LOCAL_VALUES={report['value_kind_counts'].get('2', 0)}")
    return 0 if report["status"] == "PASS_PARTIAL_EVIDENCE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
