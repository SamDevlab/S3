"""Static audit of fixed-array initializers in the canonical Stage1 source.

The current structural value counter is not a final semantic SSA namespace.
This audit quantifies fixed-array initializer payloads, especially repeated zero
initializers, so a later IR-v2 transform can decide whether aggregate zero-init
metadata can replace per-token semantic values. Static counts are not native IR
evidence and do not authorize source mutation.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "selfhost" / "compiler" / "s3c_stage1.s3"
DEFAULT_REPORT = (
    ROOT / "reports" / "selfhost" / "stage1" /
    "codegen-ir-v2-array-initializer-audit.json"
)

_ARRAY = re.compile(
    r"(?m)^\s*mut\s+(?P<name>[A-Za-z0-9_]+):\s*"
    r"(?P<type>i64|tryte|trit)\[(?P<size>\d+)\]\s*=\s*"
    r"\[(?P<body>[^\]]*)\]"
)
_NUMERIC = re.compile(r"^-?\d+$")


def _items(body: str) -> list[str]:
    stripped = body.strip()
    if not stripped:
        return []
    return [part.strip() for part in stripped.split(",")]


def audit(source: str) -> dict[str, object]:
    arrays: list[dict[str, object]] = []
    malformed: list[str] = []
    total_declared_slots = 0
    total_initializer_items = 0
    zero_initializer_items = 0
    numeric_initializer_items = 0
    all_zero_arrays = 0
    non_zero_numeric_arrays = 0

    for match in _ARRAY.finditer(source):
        name = match.group("name")
        array_type = match.group("type")
        size = int(match.group("size"))
        items = _items(match.group("body"))
        numeric = all(_NUMERIC.fullmatch(item) is not None for item in items)
        zero_count = sum(item in {"0", "+0", "-0"} for item in items) if numeric else 0
        all_zero = bool(items) and numeric and zero_count == len(items)
        item_count_matches_size = len(items) == size
        if not item_count_matches_size:
            malformed.append(name)
        if all_zero:
            all_zero_arrays += 1
        elif numeric:
            non_zero_numeric_arrays += 1

        total_declared_slots += size
        total_initializer_items += len(items)
        zero_initializer_items += zero_count
        numeric_initializer_items += len(items) if numeric else 0
        arrays.append(
            {
                "name": name,
                "type": array_type,
                "declared_size": size,
                "initializer_items": len(items),
                "item_count_matches_size": item_count_matches_size,
                "numeric_only": numeric,
                "zero_items": zero_count,
                "all_zero": all_zero,
            }
        )

    guards = {
        "found_fixed_arrays": len(arrays) > 0,
        "all_matched_array_initializers_have_declared_item_count": not malformed,
        "zero_initializer_payload_exists": zero_initializer_items > 0,
    }

    return {
        "schema": "s3.selfhost.codegen-ir-v2-array-initializer-audit.v1",
        "status": "STATIC_ARRAY_INITIALIZER_AUDIT_PASS" if all(guards.values()) else "STATIC_ARRAY_INITIALIZER_AUDIT_FAIL",
        "native_evidence": False,
        "canonical_source_mutated": False,
        "summary": {
            "matched_fixed_arrays": len(arrays),
            "total_declared_slots": total_declared_slots,
            "total_initializer_items": total_initializer_items,
            "numeric_initializer_items": numeric_initializer_items,
            "zero_initializer_items": zero_initializer_items,
            "all_zero_arrays": all_zero_arrays,
            "non_zero_numeric_arrays": non_zero_numeric_arrays,
            "malformed_array_names": malformed,
        },
        "arrays": arrays,
        "guards": guards,
        "ir_v2_implication": {
            "aggregate_zero_init_candidate": zero_initializer_items > 0,
            "rule": "A future transform may replace repeated all-zero initializer semantic values with aggregate zero-init metadata only after a native candidate proves identical Stage1 behavior and reduced semantic value usage.",
            "non_zero_rule": "Non-zero initializer elements remain explicit unless a separate aggregate representation is verified.",
            "static_zero_count_is_not_ir_value_headroom": True,
        },
        "stage2": "NOT_STARTED",
        "stage3": "NOT_STARTED",
        "full_self_hosting": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)
    result = audit(args.source.resolve().read_text(encoding="utf-8"))
    destination = args.report.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"REPORT={destination}")
    print(f"STATUS={result['status']}")
    summary = result["summary"]
    print(f"MATCHED_FIXED_ARRAYS={summary['matched_fixed_arrays']}")
    print(f"ZERO_INITIALIZER_ITEMS={summary['zero_initializer_items']}")
    print(f"ALL_ZERO_ARRAYS={summary['all_zero_arrays']}")
    print("NATIVE_EVIDENCE=False")
    return 0 if result["status"] == "STATIC_ARRAY_INITIALIZER_AUDIT_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
