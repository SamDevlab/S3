"""Fail-closed audit for historical fixed-64 local-namespace assumptions."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "selfhost" / "compiler" / "s3c_stage1.s3"
LOCAL_TRANSFORM = ROOT / "tools" / "patch_stage1_codegen_ir_v2_locals.py"
VALUE_CONTRACT = (
    ROOT / "reports" / "selfhost" / "stage1" / "codegen-ir-v2-value-namespace-contract.json"
)
DEFAULT_REPORT = (
    ROOT / "reports" / "selfhost" / "stage1" / "local-namespace-rebase-gate.json"
)

PARAMETER_LANES = (
    "ir_parameter_owner",
    "ir_parameter_name",
    "ir_parameter_ordinal",
    "ir_parameter_type",
)


def _capacity(source: str, name: str) -> int | None:
    match = re.search(
        rf"(?m)^\s*mut\s+{re.escape(name)}:\s*i64\[(\d+)\]\s*=",
        source,
    )
    return int(match.group(1)) if match else None


def audit(
    *,
    source: str,
    local_transform: str,
    value_contract: dict[str, Any],
) -> dict[str, Any]:
    parameter_capacities = {name: _capacity(source, name) for name in PARAMETER_LANES}
    layout = value_contract.get("semantic_id_layout", {})
    if not isinstance(layout, dict):
        raise ValueError("value namespace contract is missing semantic_id_layout")

    stale_assumptions = {
        "requires_packed_parameter_records_64": (
            'mut ir_parameter_records: i64[64]' in local_transform
        ),
        "packs_local_value_id_from_fixed_64": (
            "64 + local_capture_index + 1" in local_transform
            or "64 + local_capture_index" in local_transform
        ),
        "documents_fixed_64_parameter_domain": (
            "[0,64)" in local_transform
            or "local IDs start at 64" in local_transform
        ),
    }
    current_guards = {
        "direct_parameter_lanes_present": all(
            parameter_capacities[name] is not None for name in PARAMETER_LANES
        ),
        "direct_parameter_lanes_are_68": all(
            parameter_capacities[name] == 68 for name in PARAMETER_LANES
        ),
        "value_contract_parameter_domain_is_dynamic": (
            layout.get("parameter_domain") == "[0,parameter_count)"
        ),
        "value_contract_local_start_is_dynamic": (
            layout.get("local_domain_start") == "parameter_count"
        ),
        "value_contract_fixed_64_disabled": (
            layout.get("fixed_64_parameter_reservation") is False
        ),
    }

    rebase_required = any(stale_assumptions.values()) and all(current_guards.values())
    status = (
        "LOCAL_TRANSFORM_REBASE_REQUIRED"
        if rebase_required
        else "LOCAL_TRANSFORM_NAMESPACE_CONSISTENT"
        if all(current_guards.values()) and not any(stale_assumptions.values())
        else "LOCAL_NAMESPACE_PROVENANCE_RECONCILIATION_REQUIRED"
    )
    return {
        "schema": "s3.selfhost.stage1-local-namespace-rebase-gate.v1",
        "status": status,
        "native_evidence": False,
        "canonical_source_mutated": False,
        "current_parameter_capacities": parameter_capacities,
        "current_value_namespace": {
            "parameter_domain": layout.get("parameter_domain"),
            "local_domain_start": layout.get("local_domain_start"),
            "dynamic_start": layout.get("dynamic_start"),
        },
        "historical_local_transform_assumptions": stale_assumptions,
        "guards": current_guards,
        "local_transform_execution_allowed": status == "LOCAL_TRANSFORM_NAMESPACE_CONSISTENT",
        "required_rebase": [
            "consume current direct parameter metadata instead of ir_parameter_records[64]",
            "derive local semantic value IDs from parameter_count + local_record_index",
            "keep exact native parameter_count/local_record_count as qualification inputs",
            "do not promote until a Linux x86-64 candidate proves the rebased transform",
        ]
        if status == "LOCAL_TRANSFORM_REBASE_REQUIRED"
        else [],
        "next": (
            "REBUILD_LOCAL_TRANSFORM_ON_DIRECT_68_SLOT_PARAMETER_METADATA_AND_DYNAMIC_NAMESPACE"
            if status == "LOCAL_TRANSFORM_REBASE_REQUIRED"
            else "CONTINUE_NATIVE_LOCAL_QUALIFICATION"
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--local-transform", type=Path, default=LOCAL_TRANSFORM)
    parser.add_argument("--value-contract", type=Path, default=VALUE_CONTRACT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)

    result = audit(
        source=args.source.resolve().read_text(encoding="utf-8"),
        local_transform=args.local_transform.resolve().read_text(encoding="utf-8"),
        value_contract=json.loads(
            args.value_contract.resolve().read_text(encoding="utf-8")
        ),
    )
    destination = args.report.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"REPORT={destination}")
    print(f"STATUS={result['status']}")
    print(f"LOCAL_TRANSFORM_EXECUTION_ALLOWED={result['local_transform_execution_allowed']}")
    print("NATIVE_EVIDENCE=False")
    return 0 if result["status"] != "LOCAL_NAMESPACE_PROVENANCE_RECONCILIATION_REQUIRED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
