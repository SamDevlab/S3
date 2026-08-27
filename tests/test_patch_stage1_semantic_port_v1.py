from __future__ import annotations

from pathlib import Path

from tools.patch_stage1_semantic_port_v1 import PATCH_MARKER, apply_patch


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "selfhost" / "compiler" / "s3c_stage1.s3"
STREAM = ROOT / "selfhost" / "compiler" / "stage1_semantic_stream_v1.s3"


def _patched() -> tuple[str, str]:
    source = SOURCE.read_text(encoding="utf-8")
    stream = STREAM.read_text(encoding="utf-8")
    return source, apply_patch(source, stream)


def test_patch_is_deterministic_and_idempotent() -> None:
    source, patched = _patched()
    stream = STREAM.read_text(encoding="utf-8")

    assert patched != source
    assert apply_patch(patched, stream) == patched
    assert patched.count(PATCH_MARKER) == 1


def test_s1_parameter_identity_uses_logical_ids_and_exact_source_spans() -> None:
    _source, patched = _patched()
    for marker in (
        "ir_parameter_value_id: i64[68]",
        "ir_parameter_value_valid: trit[68]",
        "ir_parameter_name_start: i64[68]",
        "ir_parameter_name_length: i64[68]",
        "ir_parameter_mutable: trit[68]",
        "ir_parameter_value_id[parameter_count] = semantic_next_value_id",
        "semantic_next_value_id += 1",
        "semantic_emit_value(ir_parameter_value_id[parameter_type_slot]",
    ):
        assert marker in patched


def test_s1_local_identity_uses_reusable_physical_scratch_not_value_ids() -> None:
    _source, patched = _patched()
    for marker in (
        "semantic_local_name_start: i64[365]",
        "semantic_local_name_length: i64[365]",
        "semantic_local_value_id: i64[365]",
        "semantic_local_storage_id: i64[365]",
        "semantic_local_scratch_count = 0",
        "semantic_local_value_id[semantic_local_scratch_count] = semantic_next_value_id",
        "semantic_local_storage_id[semantic_local_pending_slot] = semantic_next_storage_id",
    ):
        assert marker in patched
    assert "semantic_local_value_id[semantic_local_scratch_count] = semantic_local_scratch_count" not in patched


def test_candidate_stream_is_disabled_by_default() -> None:
    _source, patched = _patched()
    assert "mut semantic_stream_enabled: trit = 0" in patched
    assert "semantic_stream_enabled: trit = -1" not in patched


def test_local_declaration_recognizer_requires_line_head_or_mut_prefix() -> None:
    _source, patched = _patched()
    assert "token_kind[semantic_prev2_slot]) == 3" in patched
    assert "token_value[semantic_prev2_slot] == 87" in patched
    assert "current_indent > 0" in patched
    assert "signature_paren_depth == 0" in patched


def test_constants_and_instruction_results_are_not_falsely_marked_closed() -> None:
    source = Path(ROOT / "tools" / "patch_stage1_semantic_port_v1.py").read_text(encoding="utf-8")
    assert 'print("S1_CONSTANTS=BLOCKED_EXPRESSION_LOWERER")' in source
    assert 'print("S1_RESULTS=BLOCKED_EXPRESSION_LOWERER")' in source
