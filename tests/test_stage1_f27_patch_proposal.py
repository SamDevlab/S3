from __future__ import annotations

import importlib.util
from pathlib import Path

from bootstrap.s3 import ir_emulator
from bootstrap.s3.host_services import SourceResourceRuntime
from bootstrap.s3.pipeline import compile_source


ROOT = Path(__file__).resolve().parents[1]
FROZEN_CANDIDATE = (
    ROOT
    / "review_snapshot_post_f23_nested_terminal_fix"
    / "current"
    / "selfhost"
    / "compiler"
    / "stage1_semantic_event_spine.s3"
)
PATCHER_PATH = (
    ROOT
    / "review_snapshot_post_f27_fix"
    / "proposed"
    / "apply_f27_while_compound_fix.py"
)


def _program(*postlude: bytes, after_loop_match: bool = True) -> bytes:
    lines = [
        b"fn sweep(value: i64) -> trit:\n",
        b"    mut number: i64 = value\n",
        b"    mut divisor: i64 = 100\n",
        b"    mut started: trit = 0\n",
        b"    while divisor > 0:\n",
        b"        mut digit: i64 = number / divisor\n",
        b"        match digit > 0:\n",
        b"            -1:\n",
        b"                started = -1\n",
        b"            0:\n",
        b"                discard 0\n",
        b"            1:\n",
        b"                discard 0\n",
    ]
    lines.extend(postlude)
    if after_loop_match:
        lines.extend(
            [
                b"    match started == -1:\n",
                b"        -1:\n",
                b"            return -1\n",
                b"        0:\n",
                b"            return 0\n",
                b"        1:\n",
                b"            return 1\n",
            ]
        )
    else:
        lines.append(b"    return -1\n")
    lines.extend(
        [
            b"fn after() -> trit:\n",
            b"    return 0\n",
        ]
    )
    return b"".join(lines)


PRELUDE_MATCH_ONLY = _program(after_loop_match=False)
POSTLUDE_DIVISION = _program(b"        divisor = divisor / 10\n", after_loop_match=False)
POSTLUDE_COMPOUND = _program(
    b"        number = number - digit * divisor\n",
    b"        divisor = divisor / 10\n",
    after_loop_match=False,
)
FULL_F27_SHAPE = _program(
    b"        number = number - digit * divisor\n",
    b"        divisor = divisor / 10\n",
    after_loop_match=True,
)

IMMEDIATE_MATCH_WHILE_SOURCE = (
    b"fn sweep(limit: i64) -> i64:\n"
    b"    mut position: i64 = 0\n"
    b"    while position < limit:\n"
    b"        match position > 0:\n"
    b"            -1:\n"
    b"                position += 1\n"
    b"            0:\n"
    b"                position += 1\n"
    b"            1:\n"
    b"                position += 1\n"
    b"    return position\n"
    b"fn after() -> i64:\n"
    b"    return 0\n"
)


def _load_patcher():
    spec = importlib.util.spec_from_file_location("stage1_f27_patch", PATCHER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_scan(candidate_source: str, program_source: bytes):
    candidate = compile_source(candidate_source, "O0")
    ir_emulator.functions_module = candidate.ir
    ir_emulator.resource_runtime = SourceResourceRuntime()
    functions = {function.name: function for function in candidate.ir.functions}
    output = bytearray()
    original_execute = ir_emulator._execute_function

    def execute(functions_module, function, arguments, caller):
        name = function.name
        if name == "s3_stage1_source_length":
            return len(program_source)
        if name == "s3_stage1_read_byte":
            index = arguments[0]
            return program_source[index] if 0 <= index < len(program_source) else 0
        if name == "s3_stage1_write_byte":
            output.append(arguments[0] & 0xFF)
            return 0
        if name == "s3_stage1_write_error_byte":
            return 0
        if name == "s3_stage1_exit":
            return 0
        return original_execute(functions_module, function, arguments, caller)

    ir_emulator._execute_function = execute
    try:
        result = original_execute(functions, functions["scan_program"], (2, 0), ())
    finally:
        ir_emulator._execute_function = original_execute

    records: dict[str, list[tuple[int, ...]]] = {}
    for line in bytes(output).decode("ascii").splitlines():
        fields = line.split()
        if not fields:
            continue
        records.setdefault(fields[0], []).append(tuple(int(item) for item in fields[1:]))
    return result, records


def _function_names(source: bytes, records: dict[str, list[tuple[int, ...]]]) -> list[str]:
    return [
        source[row[2] : row[2] + row[3]].decode("ascii")
        for row in records.get("F", [])
    ]


def _assert_ir_integrity(records: dict[str, list[tuple[int, ...]]]) -> None:
    instruction_ids = {row[0] for row in records.get("I", [])}
    value_ids = [row[0] for row in records.get("V", [])]
    value_id_set = set(value_ids)
    assert len(value_ids) == len(value_id_set)

    result_values = [row[2] for row in records.get("R", [])]
    assert len(result_values) == len(set(result_values))
    assert all(
        row[0] in instruction_ids and row[2] in value_id_set
        for row in records.get("O", [])
    )
    assert all(
        row[0] in instruction_ids and row[2] in value_id_set
        for row in records.get("R", [])
    )

    terminators = {row[0] for row in records.get("T", [])}
    assert len(terminators) == len(records.get("T", []))
    assert all(
        row[4] in instruction_ids and row[4] in terminators
        for row in records.get("B", [])
    )

    storage_keys = [(row[0], row[1]) for row in records.get("M", [])]
    assert len(storage_keys) == len(set(storage_keys))


def _assert_crosses(candidate_source: str, source: bytes) -> None:
    result, records = _run_scan(candidate_source, source)
    names = _function_names(source, records)
    assert result >= 0, f"scan_program={result}; F={names}"
    assert names == ["sweep", "after"]
    _assert_ir_integrity(records)


def test_original_candidate_still_reproduces_full_f27_failure() -> None:
    frozen = FROZEN_CANDIDATE.read_text(encoding="utf-8")
    result, records = _run_scan(frozen, FULL_F27_SHAPE)
    assert result < 0
    assert "after" not in _function_names(FULL_F27_SHAPE, records)


def test_proposal_stage_a_prelude_then_match_then_return() -> None:
    patcher = _load_patcher()
    patched = patcher.patch_source(FROZEN_CANDIDATE.read_text(encoding="utf-8"))
    _assert_crosses(patched, PRELUDE_MATCH_ONLY)


def test_proposal_stage_b_division_postlude() -> None:
    patcher = _load_patcher()
    patched = patcher.patch_source(FROZEN_CANDIDATE.read_text(encoding="utf-8"))
    _assert_crosses(patched, POSTLUDE_DIVISION)


def test_proposal_stage_c_compound_product_postlude() -> None:
    patcher = _load_patcher()
    patched = patcher.patch_source(FROZEN_CANDIDATE.read_text(encoding="utf-8"))
    _assert_crosses(patched, POSTLUDE_COMPOUND)


def test_proposal_stage_d_full_f27_composition_and_following_boundary() -> None:
    patcher = _load_patcher()
    patched = patcher.patch_source(FROZEN_CANDIDATE.read_text(encoding="utf-8"))
    _assert_crosses(patched, FULL_F27_SHAPE)


def test_proposal_preserves_immediate_nested_match_while_boundary() -> None:
    patcher = _load_patcher()
    patched = patcher.patch_source(FROZEN_CANDIDATE.read_text(encoding="utf-8"))
    _assert_crosses(patched, IMMEDIATE_MATCH_WHILE_SOURCE)


def test_proposal_has_no_canonical_identity_special_case() -> None:
    patcher = _load_patcher()
    frozen = FROZEN_CANDIDATE.read_text(encoding="utf-8")
    patched = patcher.patch_source(frozen)

    assert patched != frozen
    assert "emit_audit_decimal" not in patched
    assert "scan_f27_" not in patched
    assert "F27" not in patched
