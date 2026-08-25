"""Static audit for the Stage1 codegen-complete IR contract.

This tool is deliberately not a compiler gate by itself.  It checks that the
S3-authored Stage1 source exposes the structural lanes required by the IR-v2
contract and reports storage-bank pressure.  Native Linux execution remains the
authoritative qualification for counts and self-emission.
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


REQUIRED_MARKERS = {
    "parameter_name_identity": "ir_param_name",
    "parameter_type": "ir_param_type",
    "parameter_owner": "ir_param_function",
    "parameter_value_id": "ir_param_value_id",
    "parameter_abi_index": "ir_param_abi_index",
    "local_name_identity": "ir_local_name",
    "local_type": "ir_local_type",
    "local_owner": "ir_local_function",
    "local_mutability": "ir_local_mutability",
    "local_value_id": "ir_local_value_id",
    "local_frame_slot": "ir_local_frame_slot",
    "instruction_operand_a": "ir_instruction_operand_a",
    "instruction_operand_b": "ir_instruction_operand_b",
    "instruction_result": "ir_instruction_result",
    "instruction_block": "ir_instruction_block",
    "call_instruction": "ir_call_instruction",
    "call_result": "ir_call_result",
    "terminator_condition": "ir_block_condition_value",
    "terminator_return": "ir_block_return_value",
}


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


def audit(source_path: Path, contract_path: Path) -> dict[str, object]:
    source_bytes = source_path.read_bytes()
    source = source_bytes.decode("utf-8")
    contract = json.loads(contract_path.read_text(encoding="utf-8"))

    required = {
        name: marker in source for name, marker in REQUIRED_MARKERS.items()
    }
    missing = [name for name, present in required.items() if not present]

    storage = {
        "ast_event_records": _bank_summary(source, "ir_ast_event_records"),
        "instruction_records": _bank_summary(source, "ir_instruction_records"),
        "value_records": _bank_summary(source, "ir_value_records"),
        "call_records": {
            "callee": _bank_summary(source, "ir_call_callee"),
            "argument_count": _bank_summary(source, "ir_call_arg_count"),
        },
        "call_argument_records": _bank_summary(source, "ir_call_args"),
    }

    observed = contract["observed_self_source"]
    event_capacity = int(storage["ast_event_records"]["total_slots"])
    observed_events = int(observed["instructions_or_events"])
    event_headroom = event_capacity - observed_events

    return {
        "schema": "s3.selfhost.codegen-ir-v2-static-audit.v1",
        "source": str(source_path.relative_to(ROOT)),
        "source_bytes": len(source_bytes),
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "contract": str(contract_path.relative_to(ROOT)),
        "contract_schema": contract["schema"],
        "required_lane_markers": required,
        "missing_required_lane_markers": missing,
        "storage": storage,
        "capacity_observation": {
            "native_baseline_events": observed_events,
            "static_event_slots": event_capacity,
            "static_event_headroom_against_native_baseline": event_headroom,
            "preflight_required": event_headroom <= 0,
            "note": (
                "This comparison uses the last native count only. Any source change "
                "requires a new native Linux measurement before a capacity gate can pass."
            ),
        },
        "static_status": (
            "IR_V2_MARKERS_PRESENT_NATIVE_QUALIFICATION_REQUIRED"
            if not missing
            else "BLOCKED_MISSING_CODEGEN_IR_V2_LANES"
        ),
        "native_linux_qualification_required": True,
        "self_emit_claimed": False,
        "stage2_claimed": False,
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
