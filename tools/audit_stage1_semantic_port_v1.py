"""Audit Stage1 semantic-port closure without promoting protocol scaffolding to PASS."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def audit(source: str) -> dict[str, Any]:
    parameter_ids = all(
        marker in source
        for marker in (
            "ir_parameter_value_id: i64[68]",
            "ir_parameter_name_start: i64[68]",
            "ir_parameter_name_length: i64[68]",
            "ir_parameter_value_id[parameter_count] = semantic_next_value_id",
        )
    )
    local_ids = all(
        marker in source
        for marker in (
            "semantic_local_name_start: i64[365]",
            "semantic_local_value_id: i64[365]",
            "semantic_local_value_id[semantic_local_scratch_count] = semantic_next_value_id",
        )
    )
    constants = "SEMANTIC_CONSTANT_LOWERING_V1" in source
    instruction_results = "SEMANTIC_RESULT_LOWERING_V1" in source

    instruction_def_use = all(
        marker in source
        for marker in (
            "SEMANTIC_INSTRUCTION_LOWERING_V1",
            "semantic_emit_operand(",
            "semantic_emit_result(",
        )
    )
    call_dataflow = all(
        marker in source
        for marker in (
            "SEMANTIC_CALL_LOWERING_V1",
            "semantic_emit_call(",
            "semantic_emit_call_argument(",
        )
    )
    terminators = all(
        marker in source
        for marker in (
            "SEMANTIC_TERMINATOR_LOWERING_V1",
            "semantic_emit_terminator(",
        )
    )
    serializer_protocol = all(
        marker in source
        for marker in (
            "fn semantic_emit_header(",
            "fn semantic_emit_complete(",
        )
    )
    authoritative_serializer = "SEMANTIC_SERIALIZER_AUTHORITATIVE_V1" in source

    s1_complete = parameter_ids and local_ids and constants and instruction_results
    s2_complete = s1_complete and instruction_def_use
    s3_complete = s2_complete and call_dataflow
    s4_complete = s3_complete and terminators
    s5_complete = s4_complete and serializer_protocol and authoritative_serializer

    return {
        "schema": "s3.selfhost.semantic-port-audit.v1",
        "S1_typed_values": {
            "status": "PASS" if s1_complete else "PARTIAL" if parameter_ids or local_ids else "BLOCKED",
            "parameters": "PASS" if parameter_ids else "BLOCKED",
            "locals": "PASS" if local_ids else "BLOCKED",
            "constants": "PASS" if constants else "BLOCKED",
            "instruction_results": "PASS" if instruction_results else "BLOCKED",
        },
        "S2_instruction_def_use": "PASS" if s2_complete else "BLOCKED",
        "S3_call_dataflow": "PASS" if s3_complete else "BLOCKED",
        "S4_complete_terminators": "PASS" if s4_complete else "BLOCKED",
        "S5_canonical_serialization": "PASS" if s5_complete else "BLOCKED",
        "protocol": {
            "instruction_edges": "AVAILABLE" if "semantic_emit_operand(" in source and "semantic_emit_result(" in source else "MISSING",
            "calls": "AVAILABLE" if "semantic_emit_call(" in source else "MISSING",
            "terminators": "AVAILABLE" if "semantic_emit_terminator(" in source else "MISSING",
            "serializer": "AVAILABLE" if serializer_protocol else "MISSING",
            "protocol_is_lowering_evidence": False,
        },
        "general_emitter_authorized": s5_complete,
        "self_emit_authorized": False,
        "stage2_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    report = audit(args.source.read_text(encoding="utf-8"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"OUTPUT={args.output}")
    print(f"S1={report['S1_typed_values']['status']}")
    print(f"S2={report['S2_instruction_def_use']}")
    print(f"S3={report['S3_call_dataflow']}")
    print(f"S4={report['S4_complete_terminators']}")
    print(f"S5={report['S5_canonical_serialization']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
