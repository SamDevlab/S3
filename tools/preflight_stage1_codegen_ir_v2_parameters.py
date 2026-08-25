"""Static source-delta preflight for the packed-parameter IR-v2 candidate.

This tool is deliberately not a substitute for native Stage1 measurement. It
compares the compaction-only candidate with the compaction+parameter candidate
and computes bounded source-level deltas that are useful for rejecting an
obviously impossible bootstrap candidate before Linux build/execute work.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from tools.patch_stage1_codegen_ir_v2_capacity import (
    BASELINE_SOURCE_SHA256,
    transform as compact_discard_events,
)
from tools.patch_stage1_codegen_ir_v2_parameters import transform_parameters
from tools.qualify_stage1_codegen_ir_v2_capacity import EXPECTED_COMPACTED_VALUES


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "selfhost" / "compiler" / "s3c_stage1.s3"
DEFAULT_REPORT = (
    ROOT
    / "reports"
    / "selfhost"
    / "stage1"
    / "codegen-ir-v2-parameter-preflight.json"
)

VALUE_CAPACITY = 1460
BLOCK_CAPACITY = 365
LAST_NATIVE_BLOCKS = 305
LAST_NATIVE_LOCALS = 23

_NUMERIC_TOKEN = re.compile(r"(?<![A-Za-z0-9_])-?\d+(?![A-Za-z0-9_])")
_MATCH_LINE = re.compile(r"(?m)^\s*match\s+")
_WHILE_LINE = re.compile(r"(?m)^\s*while\s+")
_MUT_TOKEN = re.compile(r"(?m)^\s*mut\s+")
_FUNCTION_LINE = re.compile(r"(?m)^\s*(?:foreign\s+)?fn\s+")


def _count(pattern: re.Pattern[str], source: str) -> int:
    return len(pattern.findall(source))


def build_preflight(baseline: str) -> dict[str, object]:
    compacted = compact_discard_events(baseline)
    candidate = transform_parameters(compacted)

    numeric_delta = _count(_NUMERIC_TOKEN, candidate) - _count(_NUMERIC_TOKEN, compacted)
    match_delta = _count(_MATCH_LINE, candidate) - _count(_MATCH_LINE, compacted)
    while_delta = _count(_WHILE_LINE, candidate) - _count(_WHILE_LINE, compacted)
    mut_delta = _count(_MUT_TOKEN, candidate) - _count(_MUT_TOKEN, compacted)
    function_delta = _count(_FUNCTION_LINE, candidate) - _count(_FUNCTION_LINE, compacted)

    projected_values_upper_bound = EXPECTED_COMPACTED_VALUES + numeric_delta
    # Current Stage1 structural lowering allocates up to three synthetic blocks
    # per match/while control event. Treat that as an upper-bound projection,
    # not as an asserted post-change native block count.
    projected_blocks_upper_bound = LAST_NATIVE_BLOCKS + 3 * (match_delta + while_delta)
    projected_locals = LAST_NATIVE_LOCALS + mut_delta

    guards = {
        "no_new_function_signatures": function_delta == 0,
        "value_upper_bound_below_capacity": projected_values_upper_bound < VALUE_CAPACITY,
        "block_upper_bound_below_capacity": projected_blocks_upper_bound < BLOCK_CAPACITY,
        "single_packed_parameter_lane": candidate.count("mut ir_parameter_records: i64[64]") == 1,
        "discard_compaction_retained": "ir_ast_event_opcode = 5" not in candidate,
    }

    return {
        "schema": "s3.selfhost.codegen-ir-v2-parameter-preflight.v1",
        "status": "STATIC_PREFLIGHT_ONLY",
        "native_evidence": False,
        "baseline_source_sha256": BASELINE_SOURCE_SHA256,
        "storage_strategy": {
            "parameter_capacity": 64,
            "physical_lanes": 1,
            "lane_type": "i64[64]",
            "packed_fields": [
                "owner_function_id",
                "name_identity",
                "type_id",
                "abi_index",
                "value_id",
            ],
            "reason": "five independent i64[64] arrays would add at least 320 initializer literals and exceed the current value headroom before native remeasurement",
        },
        "source_delta": {
            "numeric_tokens": numeric_delta,
            "match_lines": match_delta,
            "while_lines": while_delta,
            "mut_declarations": mut_delta,
            "function_signatures": function_delta,
        },
        "capacity_projection": {
            "compaction_expected_values": EXPECTED_COMPACTED_VALUES,
            "projected_values_upper_bound": projected_values_upper_bound,
            "value_capacity": VALUE_CAPACITY,
            "last_native_blocks": LAST_NATIVE_BLOCKS,
            "projected_blocks_upper_bound": projected_blocks_upper_bound,
            "block_capacity": BLOCK_CAPACITY,
            "last_native_locals": LAST_NATIVE_LOCALS,
            "projected_local_count": projected_locals,
        },
        "guards": guards,
        "preflight_pass": all(guards.values()),
        "qualification_rule": "Native Linux x86-64 Stage1 build/self-source verification is mandatory before any parameter IR-v2 PASS or canonical promotion.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)

    source = args.source.resolve().read_text(encoding="utf-8")
    report = build_preflight(source)
    destination = args.report.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    print(f"REPORT={destination}")
    print(f"PREFLIGHT_PASS={report['preflight_pass']}")
    projection = report["capacity_projection"]
    print(f"PROJECTED_VALUES_UPPER_BOUND={projection['projected_values_upper_bound']}")
    print(f"PROJECTED_BLOCKS_UPPER_BOUND={projection['projected_blocks_upper_bound']}")
    print(f"PROJECTED_LOCAL_COUNT={projection['projected_local_count']}")
    print("NATIVE_EVIDENCE=False")
    return 0 if report["preflight_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
