from __future__ import annotations

import json
from pathlib import Path

from bootstrap.s3.pipeline import compile_source


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "selfhost" / "compiler" / "s3c_stage1.s3"
FIXTURE_PATH = ROOT / "tests" / "stage1_ir_fixtures.json"


def test_structural_fixture_corpus_is_parseable_by_stage0() -> None:
    fixtures = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert len(fixtures) == 9
    names = {fixture["name"] for fixture in fixtures}
    assert len(names) == len(fixtures)

    for fixture in fixtures:
        source = fixture["source"]
        for marker in fixture["markers"]:
            assert marker in source
        result = compile_source(source)
        assert result.assembly


def test_stage1_ir_ledger_is_bounded_explicit_and_verifiable() -> None:
    source = SOURCE_PATH.read_text(encoding="utf-8")
    for marker in (
        "ir_ast_event_records_0",
        "ir_ast_event_records_1",
        "ir_ast_event_records_2",
        "ir_ast_event_records_3",
        "ir_ast_event_count < 1460",
        "pack_ir_record(ir_ast_event_opcode",
        "event_verify_opcode < 17",
        "event_verify_owner <= function_count",
    ):
        assert marker in source


def test_stage1_ir_retains_identity_calls_operands_and_control_markers() -> None:
    source = SOURCE_PATH.read_text(encoding="utf-8")
    for marker in (
        "function_name_starts",
        "function_name_lengths",
        "function_flags",
        "ir_call_callee",
        "ir_call_arg_start",
        "ir_call_args_0",
        "ir_call_args_1",
        "ir_block_function",
        "ir_block_terminator",
        "ir_block_target_a",
        "ir_block_target_b",
        "ir_value_records_0",
        "ir_ast_event_operand",
        "ir_ast_event_offset",
        "ir_ast_event_opcode = 16",
    ):
        assert marker in source
    assert "ir_ast_event_opcode = 16" in source
    assert "S3_STAGE1_EMITTER_BLOCKED" not in source


def test_fixture_categories_cover_required_lossless_ir_shapes() -> None:
    fixtures = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    categories = {category for fixture in fixtures for category in fixture["categories"]}
    assert {
        "functions",
        "foreign",
        "parameters",
        "locals",
        "assignments",
        "calls",
        "binops",
        "comparisons",
        "matches",
        "loops",
        "breaks",
        "returns",
        "discards",
        "control_flow",
        "values",
    } <= categories
