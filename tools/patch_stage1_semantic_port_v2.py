"""Build the candidate-only Stage1 semantic v2 Pass 1.

This transform adds a bounded source-binding pass to the current Stage1 source.
It deliberately leaves normal emission disabled and never overwrites the
canonical compiler. Logical value IDs are monotonic; binding and scope tables
are reusable physical scratch with capacities derived from the current source
audit (229 locals, 32 lexical levels).
"""

from __future__ import annotations

import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "selfhost" / "compiler" / "s3c_stage1.s3"
DEFAULT_OUTPUT = ROOT / ".artifacts" / "s3c_stage1_semantic_v2.s3"

PATCH_MARKER = "# STAGE1_SEMANTIC_PORT_V2_PASS1"
FUNCTION_CAPACITY = 64
PARAMETER_CAPACITY = 70
BINDING_CAPACITY = 256
SCOPE_CAPACITY = 32


def _zeros(count: int) -> str:
    return ", ".join("0" for _ in range(count))


def _array(name: str, type_name: str, count: int) -> str:
    return f"    mut {name}: {type_name}[{count}] = [{_zeros(count)}]\n"


def _insert_after_prefix(source: str, prefix: str, payload: str) -> str:
    lines = source.splitlines(keepends=True)
    matches = [index for index, line in enumerate(lines) if line.startswith(prefix)]
    if len(matches) != 1:
        raise ValueError(f"expected one line beginning {prefix!r}, found {len(matches)}")
    index = matches[0]
    lines.insert(index + 1, payload)
    return "".join(lines)


def _replace_once(source: str, old: str, new: str) -> str:
    count = source.count(old)
    if count != 1:
        raise ValueError(f"expected one patch anchor, found {count}: {old[:100]!r}")
    return source.replace(old, new, 1)


def _declarations() -> str:
    declarations = ""
    for name, type_name, count in (
        ("semantic_v2_function_kind", "tryte", FUNCTION_CAPACITY),
        ("semantic_v2_function_name_start", "i64", FUNCTION_CAPACITY),
        ("semantic_v2_function_name_length", "i64", FUNCTION_CAPACITY),
        ("semantic_v2_function_param_start", "i64", FUNCTION_CAPACITY),
        ("semantic_v2_function_param_count", "i64", FUNCTION_CAPACITY),
        ("semantic_v2_function_return_type", "i64", FUNCTION_CAPACITY),
        ("semantic_v2_function_result_count", "i64", FUNCTION_CAPACITY),
        ("semantic_v2_function_valid", "trit", FUNCTION_CAPACITY),
        ("semantic_v2_parameter_function", "i64", PARAMETER_CAPACITY),
        ("semantic_v2_parameter_name_start", "i64", PARAMETER_CAPACITY),
        ("semantic_v2_parameter_name_length", "i64", PARAMETER_CAPACITY),
        ("semantic_v2_parameter_ordinal", "i64", PARAMETER_CAPACITY),
        ("semantic_v2_parameter_type", "i64", PARAMETER_CAPACITY),
        ("semantic_v2_parameter_value_id", "i64", PARAMETER_CAPACITY),
        ("semantic_v2_parameter_valid", "trit", PARAMETER_CAPACITY),
        ("semantic_v2_binding_function", "i64", BINDING_CAPACITY),
        ("semantic_v2_binding_kind", "tryte", BINDING_CAPACITY),
        ("semantic_v2_binding_name_start", "i64", BINDING_CAPACITY),
        ("semantic_v2_binding_name_length", "i64", BINDING_CAPACITY),
        ("semantic_v2_binding_type", "i64", BINDING_CAPACITY),
        ("semantic_v2_binding_mutable", "trit", BINDING_CAPACITY),
        ("semantic_v2_binding_scope", "i64", BINDING_CAPACITY),
        ("semantic_v2_binding_storage", "i64", BINDING_CAPACITY),
        ("semantic_v2_binding_ordinal", "i64", BINDING_CAPACITY),
        ("semantic_v2_binding_value_id", "i64", BINDING_CAPACITY),
        ("semantic_v2_binding_valid", "trit", BINDING_CAPACITY),
        ("semantic_v2_token_start", "i64", 16),
    ):
        declarations += _array(name, type_name, count)
    return declarations


def _state_declarations() -> str:
    return (
        "    mut semantic_v2_current_function: i64 = -1\n"
        "    mut semantic_v2_next_value_id: i64 = 0\n"
        "    mut semantic_v2_next_storage_id: i64 = 0\n"
        "    mut semantic_v2_binding_count: i64 = 0\n"
        "    mut semantic_v2_scope_depth: i64 = 0\n"
        "    mut semantic_v2_scope_id: i64 = 0\n"
        "    mut semantic_v2_next_scope_id: i64 = 0\n"
        "    mut semantic_v2_scope_indent: i64[32] = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]\n"
        "    mut semantic_v2_scope_ids: i64[32] = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]\n"
        "    mut semantic_v2_scope_scan: i64 = 0\n"
        "    mut semantic_v2_scope_top: i64 = 0\n"
        "    mut semantic_v2_pass1_ok: trit = -1\n"
        "    mut semantic_v2_loop_capture_state: i64 = 0\n"
        "    mut semantic_v2_loop_name: i64 = 0\n"
        "    mut semantic_v2_loop_name_start: i64 = 0\n"
        "    mut semantic_v2_loop_name_length: i64 = 0\n"
        "    mut semantic_v2_loop_type: i64 = 0\n"
        "    mut semantic_v2_loop_scope: i64 = 0\n"
        "    mut semantic_v2_loop_ordinal: i64 = 0\n"
        "    mut local_capture_name_start: i64 = 0\n"
        "    mut local_capture_name_length: i64 = 0\n"
        "    mut local_capture_scope: i64 = 0\n"
        "    mut semantic_v2_parameter_name_slot: i64 = 0\n"
        "    mut semantic_v2_parameter_previous_slot: i64 = 0\n"
    )


def _scope_hook() -> str:
    return (
        "                semantic_v2_scope_scan = semantic_v2_scope_depth\n"
        "                while semantic_v2_scope_scan > 0:\n"
        "                    semantic_v2_scope_top = semantic_v2_scope_scan - 1\n"
        "                    match current_indent < semantic_v2_scope_indent[semantic_v2_scope_top]:\n"
        "                        -1:\n"
        "                            semantic_v2_scope_depth = semantic_v2_scope_depth - 1\n"
        "                            semantic_v2_scope_scan = semantic_v2_scope_scan - 1\n"
        "                        0:\n"
        "                            semantic_v2_scope_scan = 0\n"
        "                        1:\n"
        "                            semantic_v2_scope_scan = 0\n"
        "                match semantic_v2_scope_depth > 0:\n"
        "                    -1:\n"
        "                        semantic_v2_scope_top = semantic_v2_scope_depth - 1\n"
        "                        semantic_v2_scope_id = semantic_v2_scope_ids[semantic_v2_scope_top]\n"
        "                        match current_indent > semantic_v2_scope_indent[semantic_v2_scope_top]:\n"
        "                            -1:\n"
        "                                match semantic_v2_scope_depth < 32:\n"
        "                                    -1:\n"
        "                                        semantic_v2_scope_indent[semantic_v2_scope_depth] = current_indent\n"
        "                                        semantic_v2_scope_ids[semantic_v2_scope_depth] = semantic_v2_next_scope_id\n"
        "                                        semantic_v2_scope_id = semantic_v2_next_scope_id\n"
        "                                        semantic_v2_next_scope_id += 1\n"
        "                                        semantic_v2_scope_depth += 1\n"
        "                                    0:\n"
        "                                        semantic_v2_pass1_ok = 0\n"
        "                                    1:\n"
        "                                        semantic_v2_pass1_ok = 0\n"
        "                            0:\n"
        "                                discard 0\n"
        "                            1:\n"
        "                                discard 0\n"
        "                    0:\n"
        "                        match current_indent > 0:\n"
        "                            -1:\n"
        "                                match semantic_v2_scope_depth < 32:\n"
        "                                    -1:\n"
        "                                        semantic_v2_scope_indent[0] = current_indent\n"
        "                                        semantic_v2_scope_ids[0] = semantic_v2_next_scope_id\n"
        "                                        semantic_v2_scope_id = semantic_v2_next_scope_id\n"
        "                                        semantic_v2_next_scope_id += 1\n"
        "                                        semantic_v2_scope_depth = 1\n"
        "                                    0:\n"
        "                                        semantic_v2_pass1_ok = 0\n"
        "                                    1:\n"
        "                                        semantic_v2_pass1_ok = 0\n"
        "                            0:\n"
        "                                semantic_v2_scope_id = 0\n"
        "                            1:\n"
        "                                semantic_v2_scope_id = 0\n"
        "                    1:\n"
        "                        semantic_v2_scope_id = 0\n"
    )


def _loop_hook() -> str:
    return (
        "                match semantic_v2_loop_capture_state == 1:\n"
        "                    -1:\n"
        "                        match kind == 1:\n"
        "                            -1:\n"
        "                                semantic_v2_loop_name = value\n"
        "                                semantic_v2_loop_name_start = semantic_v2_token_start[slot]\n"
        "                                semantic_v2_loop_name_length = token_end[slot] - semantic_v2_token_start[slot]\n"
        "                                semantic_v2_loop_scope = semantic_v2_scope_id\n"
        "                                semantic_v2_loop_capture_state = 2\n"
        "                            0:\n"
        "                                semantic_v2_pass1_ok = 0\n"
        "                                semantic_v2_loop_capture_state = 0\n"
        "                            1:\n"
        "                                semantic_v2_pass1_ok = 0\n"
        "                                semantic_v2_loop_capture_state = 0\n"
        "                    0:\n"
        "                        discard 0\n"
        "                    1:\n"
        "                        discard 0\n"
        "                match semantic_v2_loop_capture_state == 2:\n"
        "                    -1:\n"
        "                        match kind == 4:\n"
        "                            -1:\n"
        "                                match value == 3:\n"
        "                                    -1:\n"
        "                                        semantic_v2_loop_capture_state = 3\n"
        "                                    0:\n"
        "                                        semantic_v2_pass1_ok = 0\n"
        "                                        semantic_v2_loop_capture_state = 0\n"
        "                                    1:\n"
        "                                        semantic_v2_pass1_ok = 0\n"
        "                                        semantic_v2_loop_capture_state = 0\n"
        "                            0:\n"
        "                                semantic_v2_pass1_ok = 0\n"
        "                                semantic_v2_loop_capture_state = 0\n"
        "                            1:\n"
        "                                semantic_v2_pass1_ok = 0\n"
        "                                semantic_v2_loop_capture_state = 0\n"
        "                    0:\n"
        "                        discard 0\n"
        "                    1:\n"
        "                        discard 0\n"
        "                match semantic_v2_loop_capture_state == 3:\n"
        "                    -1:\n"
        "                        match kind == 1:\n"
        "                            -1:\n"
        "                                semantic_v2_loop_type = value\n"
        "                                semantic_v2_loop_capture_state = 4\n"
        "                            0:\n"
        "                                semantic_v2_pass1_ok = 0\n"
        "                                semantic_v2_loop_capture_state = 0\n"
        "                            1:\n"
        "                                semantic_v2_pass1_ok = 0\n"
        "                                semantic_v2_loop_capture_state = 0\n"
        "                    0:\n"
        "                        discard 0\n"
        "                    1:\n"
        "                        discard 0\n"
        "                match semantic_v2_loop_capture_state == 4:\n"
        "                    -1:\n"
        "                        match kind == 1:\n"
        "                            -1:\n"
        "                                match value == 80:\n"
        "                                    -1:\n"
        "                                        match semantic_v2_binding_count < 256:\n"
        "                                            -1:\n"
        "                                                semantic_v2_binding_function[semantic_v2_binding_count] = semantic_v2_current_function\n"
        "                                                semantic_v2_binding_kind[semantic_v2_binding_count] = 2\n"
        "                                                semantic_v2_binding_name_start[semantic_v2_binding_count] = semantic_v2_loop_name_start\n"
        "                                                semantic_v2_binding_name_length[semantic_v2_binding_count] = semantic_v2_loop_name_length\n"
        "                                                semantic_v2_binding_type[semantic_v2_binding_count] = semantic_v2_loop_type\n"
        "                                                semantic_v2_binding_mutable[semantic_v2_binding_count] = 0\n"
        "                                                semantic_v2_binding_scope[semantic_v2_binding_count] = semantic_v2_loop_scope\n"
        "                                                semantic_v2_binding_storage[semantic_v2_binding_count] = semantic_v2_next_storage_id\n"
        "                                                semantic_v2_next_storage_id += 1\n"
        "                                                semantic_v2_binding_ordinal[semantic_v2_binding_count] = semantic_v2_loop_ordinal\n"
        "                                                semantic_v2_loop_ordinal += 1\n"
        "                                                semantic_v2_binding_value_id[semantic_v2_binding_count] = semantic_v2_next_value_id\n"
        "                                                semantic_v2_next_value_id += 1\n"
        "                                                semantic_v2_binding_valid[semantic_v2_binding_count] = -1\n"
        "                                                semantic_v2_binding_count += 1\n"
        "                                            0:\n"
        "                                                semantic_v2_pass1_ok = 0\n"
        "                                            1:\n"
        "                                                semantic_v2_pass1_ok = 0\n"
        "                                        semantic_v2_loop_capture_state = 0\n"
        "                                    0:\n"
        "                                        semantic_v2_pass1_ok = 0\n"
        "                                        semantic_v2_loop_capture_state = 0\n"
        "                                    1:\n"
        "                                        semantic_v2_pass1_ok = 0\n"
        "                                        semantic_v2_loop_capture_state = 0\n"
        "                            0:\n"
        "                                semantic_v2_pass1_ok = 0\n"
        "                                semantic_v2_loop_capture_state = 0\n"
        "                            1:\n"
        "                                semantic_v2_pass1_ok = 0\n"
        "                                semantic_v2_loop_capture_state = 0\n"
        "                    0:\n"
        "                        discard 0\n"
        "                    1:\n"
        "                        discard 0\n"
        "                match value == 107:\n"
        "                    -1:\n"
        "                        semantic_v2_loop_capture_state = 1\n"
        "                    0:\n"
        "                        discard 0\n"
        "                    1:\n"
        "                        discard 0\n"
    )


def _parameter_hook() -> str:
    return (
        "                                                        semantic_v2_parameter_function[parameter_count] = semantic_v2_current_function\n"
        "                                                        semantic_v2_parameter_previous_slot = semantic_v2_parameter_name_slot\n"
        "                                                        semantic_v2_parameter_name_start[parameter_count] = semantic_v2_token_start[semantic_v2_parameter_previous_slot]\n"
        "                                                        semantic_v2_parameter_name_length[parameter_count] = token_end[semantic_v2_parameter_previous_slot] - semantic_v2_token_start[semantic_v2_parameter_previous_slot]\n"
        "                                                        semantic_v2_parameter_ordinal[parameter_count] = ir_function_param_count[semantic_v2_current_function]\n"
        "                                                        semantic_v2_parameter_value_id[parameter_count] = semantic_v2_next_value_id\n"
        "                                                        semantic_v2_next_value_id += 1\n"
        "                                                        semantic_v2_parameter_valid[parameter_count] = -1\n"
        "                                                        semantic_v2_function_param_count[semantic_v2_current_function] += 1\n"
    )


def _local_commit_hook() -> str:
    return (
        "                                match semantic_v2_binding_count < 256:\n"
        "                                    -1:\n"
        "                                        semantic_v2_binding_function[semantic_v2_binding_count] = local_capture_owner\n"
        "                                        semantic_v2_binding_kind[semantic_v2_binding_count] = 1\n"
        "                                        semantic_v2_binding_name_start[semantic_v2_binding_count] = local_capture_name_start\n"
        "                                        semantic_v2_binding_name_length[semantic_v2_binding_count] = local_capture_name_length\n"
        "                                        semantic_v2_binding_type[semantic_v2_binding_count] = local_capture_type\n"
        "                                        semantic_v2_binding_mutable[semantic_v2_binding_count] = 1\n"
        "                                        semantic_v2_binding_scope[semantic_v2_binding_count] = local_capture_scope\n"
        "                                        semantic_v2_binding_storage[semantic_v2_binding_count] = semantic_v2_next_storage_id\n"
        "                                        semantic_v2_next_storage_id += 1\n"
        "                                        semantic_v2_binding_ordinal[semantic_v2_binding_count] = local_capture_ordinal\n"
        "                                        semantic_v2_binding_value_id[semantic_v2_binding_count] = semantic_v2_next_value_id\n"
        "                                        semantic_v2_next_value_id += 1\n"
        "                                        semantic_v2_binding_valid[semantic_v2_binding_count] = -1\n"
        "                                        semantic_v2_binding_count += 1\n"
        "                                    0:\n"
        "                                        semantic_v2_pass1_ok = 0\n"
        "                                    1:\n"
        "                                        semantic_v2_pass1_ok = 0\n"
    )


def apply_patch(source: str) -> str:
    """Return a deterministic Pass 1 candidate derived from *source*."""

    if PATCH_MARKER in source:
        return source

    source = _insert_after_prefix(
        source,
        "    mut function_flags: tryte[64] = [",
        _declarations(),
    )
    source = _insert_after_prefix(
        source,
        "    mut ir_local_record_count: i64 = 0",
        _state_declarations(),
    )
    source = _replace_once(
        source,
        "        token_start[slot] = cursor\n",
        "        token_start[slot] = cursor\n"
        "        semantic_v2_token_start[slot] = actual_start\n",
    )
    source = _replace_once(
        source,
        "                line_indent_value = current_indent\n                line_start_pending = 0\n",
        "                line_indent_value = current_indent\n"
        + _scope_hook()
        + "                line_start_pending = 0\n",
    )
    source = _replace_once(
        source,
        "                                ir_function_param_start[function_count] = parameter_count\n",
        "                                ir_function_param_start[function_count] = parameter_count\n"
        "                                semantic_v2_current_function = function_count\n"
        "                                semantic_v2_function_name_start[function_count] = actual_start\n"
        "                                semantic_v2_function_name_length[function_count] = next_cursor - actual_start\n"
        "                                semantic_v2_function_param_start[function_count] = parameter_count\n"
        "                                semantic_v2_function_param_count[function_count] = 0\n"
        "                                semantic_v2_function_return_type[function_count] = 0\n"
        "                                semantic_v2_function_result_count[function_count] = 0\n"
        "                                semantic_v2_function_kind[function_count] = 1\n"
        "                                match pending_foreign == -1:\n"
        "                                    -1:\n"
        "                                        semantic_v2_function_kind[function_count] = 2\n"
        "                                    0:\n"
        "                                        discard 0\n"
        "                                    1:\n"
        "                                        discard 0\n"
        "                                semantic_v2_function_valid[function_count] = -1\n"
        "                                semantic_v2_scope_depth = 0\n"
        "                                semantic_v2_scope_id = 0\n"
        "                                semantic_v2_next_scope_id = 0\n"
        "                                semantic_v2_loop_capture_state = 0\n"
        "                                semantic_v2_loop_ordinal = 0\n",
    )
    source = _replace_once(
        source,
        "                        ir_parameter_type[parameter_type_slot] = value\n"
        "                        ir_semantic_value_records[parameter_type_slot] = pack_ir_record(1, ir_parameter_owner[parameter_type_slot], value, parameter_type_slot)\n",
        "                        ir_parameter_type[parameter_type_slot] = value\n"
        "                        semantic_v2_parameter_type[parameter_type_slot] = value\n"
        "                        ir_semantic_value_records[parameter_type_slot] = pack_ir_record(1, ir_parameter_owner[parameter_type_slot], value, parameter_type_slot)\n",
    )
    source = _replace_once(
        source,
        "                                                        ir_parameter_owner[parameter_count] = current_function\n",
        "                                                        ir_parameter_owner[parameter_count] = current_function\n"
        "                                                        semantic_v2_parameter_name_slot = slot - 1\n"
        "                                                        match semantic_v2_parameter_name_slot < 0:\n"
        "                                                            -1:\n"
        "                                                                semantic_v2_parameter_name_slot = 15\n"
        "                                                            0:\n"
        "                                                                discard 0\n"
        "                                                            1:\n"
        "                                                                discard 0\n"
        + _parameter_hook(),
    )
    source = _replace_once(
        source,
        "                        local_capture_owner = current_function\n",
        "                        local_capture_owner = semantic_v2_current_function\n"
        "                        local_capture_scope = semantic_v2_scope_id\n",
    )
    source = _replace_once(
        source,
        "                        local_capture_name = value\n                        local_capture_state = 2\n",
        "                        local_capture_name = value\n"
        "                        local_capture_name_start = semantic_v2_token_start[slot]\n"
        "                        local_capture_name_length = token_end[slot] - semantic_v2_token_start[slot]\n"
        "                        local_capture_state = 2\n",
    )
    source = _replace_once(
        source,
        "                                ir_local_record_count += 1\n"
        "                                local_capture_owner = -1\n",
        _local_commit_hook()
        + "                                ir_local_record_count += 1\n"
        "                                local_capture_owner = -1\n",
    )
    source = _replace_once(
        source,
        "                                function_types[current_function] = to_tryte(value)\n                                awaiting_return_type = 0\n",
        "                                function_types[current_function] = to_tryte(value)\n"
        "                                semantic_v2_function_return_type[current_function] = value\n"
        "                                semantic_v2_function_result_count[current_function] = 1\n"
        "                                awaiting_return_type = 0\n",
    )
    source = _replace_once(
        source,
        "        match kind == 1:\n            -1:\n                match parameter_type_pending == -1:\n",
        "        match kind == 1:\n            -1:\n"
        + _loop_hook()
        + "                match parameter_type_pending == -1:\n",
    )
    source = source.replace(
        "# STAGE1_SEMANTIC_PORT_V2_PASS1\n",
        "# STAGE1_SEMANTIC_PORT_V2_PASS1\n",
        1,
    )
    return PATCH_MARKER + "\n" + source


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    source = args.source.read_text(encoding="utf-8")
    candidate = apply_patch(source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(candidate, encoding="utf-8", newline="\n")
    print(f"OUTPUT={args.output}")
    print(f"SOURCE_MUTATED={args.output.resolve() == args.source.resolve()}")
    print("PASS1_FUNCTIONS=IMPLEMENTED_CANDIDATE")
    print("PASS1_PARAMETERS=IMPLEMENTED_CANDIDATE")
    print("PASS1_LOCALS=IMPLEMENTED_CANDIDATE")
    print("PASS1_SCOPE_RESOLUTION=IMPLEMENTED_CANDIDATE")
    print("S1=PARTIAL_EXPECTED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
