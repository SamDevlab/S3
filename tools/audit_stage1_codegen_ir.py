"""Static audit for the Stage1 codegen-complete IR contract.

This tool is deliberately not a compiler gate by itself. Contract-owned source
markers keep the audit synchronized with representation decisions while native
Linux execution remains authoritative for implementation counts and behavior.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "selfhost" / "compiler" / "s3c_stage1.s3"
DEFAULT_CONTRACT = ROOT / "reports" / "selfhost" / "stage1" / "codegen-ir-v2-contract.json"

ARRAY_DECLARATION = re.compile(
    r"\bmut\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*):\s*"
    r"(?P<type>[A-Za-z0-9_]+)\[(?P<size>\d+)\]"
)


def _bank_summary(source: str, prefix: str) -> dict[str, object]:
    banks: list[dict[str, object]] = []
    for match in ARRAY_DECLARATION.finditer(source):
        name = match.group("name")
        if name == prefix or name.startswith(prefix + "_"):
            banks.append(
                {
                    "name": name,
                    "element_type": match.group("type"),
                    "size": int(match.group("size")),
                }
            )
    return {
        "bank_count": len(banks),
        "total_slots": sum(int(bank["size"]) for bank in banks),
        "banks": banks,
    }


def _contract_markers(contract: dict[str, object]) -> dict[str, str]:
    raw = contract.get("required_source_markers")
    if not isinstance(raw, dict) or not raw:
        raise ValueError("IR-v2 contract must define non-empty required_source_markers")
    markers: dict[str, str] = {}
    for name, marker in raw.items():
        if not isinstance(name, str) or not name:
            raise ValueError("IR-v2 marker names must be non-empty strings")
        if not isinstance(marker, str) or not marker:
            raise ValueError(f"IR-v2 marker {name} must be a non-empty string")
        markers[name] = marker
    return markers


def audit(source_path: Path, contract_path: Path) -> dict[str, object]:
    source_bytes = source_path.read_bytes()
    source = source_bytes.decode("utf-8")
    contract_value = json.loads(contract_path.read_text(encoding="utf-8"))
    if not isinstance(contract_value, dict):
        raise ValueError("IR-v2 contract must be a JSON object")
    contract = contract_value

    markers = _contract_markers(contract)
    required = {name: marker in source for name, marker in markers.items()}
    missing = [name for name, present in required.items() if not present]

    storage = {
        "ast_event_records": _bank_summary(source, "ir_ast_event_records"),
        "instruction_records": _bank_summary(source, "ir_instruction_records"),
        "value_records": _bank_summary(source, "ir_value_records"),
        "parameter_records": _bank_summary(source, "ir_parameter_records"),
        "local_records": _bank_summary(source, "ir_local_records"),
        "call_records": {
            "callee": _bank_summary(source, "ir_call_callee"),
            "argument_count": _bank_summary(source, "ir_call_arg_count"),
        },
        "call_argument_records": _bank_summary(source, "ir_call_args"),
    }

    observed = contract.get("observed_self_source")
    if not isinstance(observed, dict):
        raise ValueError("IR-v2 contract observed_self_source is missing")
    event_capacity = int(storage["ast_event_records"]["total_slots"])
    observed_events = int(observed["instructions_or_events"])
    observed_discards = int(observed["discards"])
    event_headroom = event_capacity - observed_events
    projected_events_without_discard_keyword = observed_events - observed_discards
    projected_headroom_without_discard_keyword = event_capacity - projected_events_without_discard_keyword

    return {
        "schema": "s3.selfhost.codegen-ir-v2-static-audit.v3",
        "source": str(source_path.relative_to(ROOT)),
        "source_bytes": len(source_bytes),
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "contract": str(contract_path.relative_to(ROOT)),
        "contract_schema": contract.get("schema"),
        "contract_owned_markers": markers,
        "required_lane_markers": required,
        "missing_required_lane_markers": missing,
        "storage": storage,
        "capacity_observation": {
            "native_baseline_events": observed_events,
            "native_baseline_discard_events": observed_discards,
            "static_event_slots": event_capacity,
            "static_event_headroom_against_native_baseline": event_headroom,
            "preflight_required": event_headroom <= 0,
            "compaction_projection": {
                "strategy": "DO_NOT_SERIALIZE_AGGREGATE_DISCARD_KEYWORD_EVENT",
                "projected_events": projected_events_without_discard_keyword,
                "projected_headroom": projected_headroom_without_discard_keyword,
                "side_effect_rule": (
                    "Calls/stores remain explicit instructions; only the redundant "
                    "aggregate discard-keyword event is a compaction candidate."
                ),
                "status": "PROJECTION_ONLY_NATIVE_REMEASUREMENT_REQUIRED"
            },
            "note": (
                "Baseline counts are historical native evidence. Any source change "
                "requires a new native Linux measurement before implementation PASS."
            )
        },
        "static_status": (
            "IR_V2_CONTRACT_MARKERS_PRESENT_NATIVE_QUALIFICATION_REQUIRED"
            if not missing
            else "BLOCKED_MISSING_CODEGEN_IR_V2_LANES"
        ),
        "native_linux_qualification_required": true if False else True,
        "self_emit_claimed": False,
        "stage2_claimed": False
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    result = audit(args.source.resolve(), args.contract.resolve())
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        output = args.output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8", newline="\n")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
