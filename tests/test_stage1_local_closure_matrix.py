from __future__ import annotations

import hashlib
import importlib.util
import os
from dataclasses import dataclass
from pathlib import Path

import pytest

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
EXPECTED_CANDIDATE_SHA256 = "34352f505c4e1452594f9e1c5d1db64efa77a94e30870f9887ca5c85dd0eb8d7"
EXPECTED_CANONICAL_SHA256 = "44f022820a9191e3a6d402c188eb4b242e0ffeefd7a149b15e2b46039031b9cb"
EXPECTED_CANONICAL_BYTES = 225699


@dataclass(frozen=True)
class FunctionSpan:
    name: str
    header: bytes
    body: bytes


def _load_patcher():
    spec = importlib.util.spec_from_file_location("stage1_f27_patch", PATCHER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _protected_canonical() -> bytes:
    if os.environ.get("S3_STAGE1_LOCAL_CLOSURE") != "1":
        pytest.skip("review-only local closure matrix")
    path_value = os.environ.get("S3_STAGE1_CANONICAL_PATH")
    assert path_value, "S3_STAGE1_CANONICAL_PATH is required"
    data = Path(path_value).read_bytes()
    assert len(data) == EXPECTED_CANONICAL_BYTES
    assert hashlib.sha256(data).hexdigest() == EXPECTED_CANONICAL_SHA256
    return data


def _top_level_functions(source: bytes) -> list[FunctionSpan]:
    lines = source.splitlines(keepends=True)
    starts = [index for index, line in enumerate(lines) if line.startswith(b"fn ")]
    spans: list[FunctionSpan] = []
    for position, line_index in enumerate(starts):
        next_line_index = starts[position + 1] if position + 1 < len(starts) else len(lines)
        header = lines[line_index]
        body = b"".join(lines[line_index:next_line_index])
        name = header[3 : header.index(b"(")].decode("ascii")
        spans.append(FunctionSpan(name=name, header=header, body=body))
    return spans


def _foreign_headers(source: bytes) -> bytes:
    return b"".join(
        line for line in source.splitlines(keepends=True) if line.startswith(b"foreign fn ")
    )


def _scalar_stub(span: FunctionSpan) -> bytes:
    header = span.header
    marker = b" -> "
    assert marker in header, span.name
    return_type = header.split(marker, 1)[1].rsplit(b":", 1)[0].strip()
    if return_type in {b"i64", b"tryte", b"trit"}:
        return header + b"    return 0\n\n"
    # Do not invent a fake value for an uncommon non-scalar signature. Keep
    # that body exact; the protected canonical currently only needs scalar
    # stubs here, but this keeps the window harness fail-safe if that changes.
    return span.body


def _window_source(canonical: bytes, spans: list[FunctionSpan], target_index: int) -> bytes:
    pieces = [_foreign_headers(canonical), b"\n"]
    # Keep every original function in original order so the target retains its
    # canonical F ordinal/function id. Only the target keeps its exact body;
    # unrelated scalar bodies collapse to a one-return stub. Insert `after`
    # immediately after the target, then keep later signatures/stubs available
    # for whole-source resolution. This preserves the target's identity without
    # replaying the expensive canonical prefix semantics.
    for index, span in enumerate(spans):
        if index == target_index:
            pieces.append(span.body)
            pieces.append(b"fn after() -> trit:\n    return 0\n\n")
        else:
            pieces.append(_scalar_stub(span))
    return b"".join(pieces)


def _compile_patched_candidate():
    frozen = FROZEN_CANDIDATE.read_text(encoding="utf-8")
    assert hashlib.sha256(frozen.encode("utf-8")).hexdigest() == EXPECTED_CANDIDATE_SHA256
    patcher = _load_patcher()
    patched = patcher.patch_source(frozen)
    compiled = compile_source(patched, "O0")
    assert compiled.ir is not None
    return compiled


def _run_scan(compiled, program_source: bytes):
    ir_emulator.functions_module = compiled.ir
    ir_emulator.resource_runtime = SourceResourceRuntime()
    functions = {function.name: function for function in compiled.ir.functions}
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
    return [source[row[2] : row[2] + row[3]].decode("ascii") for row in records.get("F", [])]


def _assert_integrity(records: dict[str, list[tuple[int, ...]]]) -> None:
    instruction_ids = {row[0] for row in records.get("I", [])}
    values = [row[0] for row in records.get("V", [])]
    value_ids = set(values)
    assert len(values) == len(value_ids), "duplicate V ids"

    result_values = [row[2] for row in records.get("R", [])]
    assert len(result_values) == len(set(result_values)), "duplicate result producers"
    assert all(row[0] in instruction_ids and row[2] in value_ids for row in records.get("O", []))
    assert all(row[0] in instruction_ids and row[2] in value_ids for row in records.get("R", []))

    terminators = [row[0] for row in records.get("T", [])]
    assert len(terminators) == len(set(terminators)), "duplicate terminators"
    terminator_ids = set(terminators)
    assert all(row[4] in instruction_ids and row[4] in terminator_ids for row in records.get("B", []))

    storage_keys = [(row[0], row[1]) for row in records.get("M", [])]
    assert len(storage_keys) == len(set(storage_keys)), "storage collision"


def test_remaining_canonical_function_windows_close_locally() -> None:
    canonical = _protected_canonical()
    spans = _top_level_functions(canonical)
    names = [span.name for span in spans]

    # Truthful ordinal calibration against the already-proven frontier.
    assert names[24:28] == [
        "emit_error",
        "emit_blocked",
        "emit_audit_header",
        "emit_audit_decimal",
    ]

    compiled = _compile_patched_candidate()
    failures: list[str] = []
    passes: list[str] = []

    for target_index in range(27, len(spans)):
        target = spans[target_index]
        source = _window_source(canonical, spans, target_index)
        result, records = _run_scan(compiled, source)
        emitted = _function_names(source, records)

        target_position_ok = len(emitted) > target_index and emitted[target_index] == target.name
        after_position_ok = len(emitted) > target_index + 1 and emitted[target_index + 1] == "after"
        if result < 0 or not target_position_ok or not after_position_ok:
            lower = max(0, target_index - 2)
            upper = min(len(emitted), target_index + 5)
            failures.append(
                f"F{target_index} {target.name}: scan_program={result}; "
                f"windowF={emitted[lower:upper]}"
            )
            break

        try:
            _assert_integrity(records)
        except AssertionError as exc:
            failures.append(f"F{target_index} {target.name}: IR integrity: {exc}")
            break

        passes.append(f"F{target_index}:{target.name}")
        print(f"LOCAL_WINDOW_PASS F{target_index} {target.name}")

    print("LOCAL_WINDOW_PASSES=" + ",".join(passes))
    assert not failures, failures[0]
    assert passes, "no remaining windows executed"
