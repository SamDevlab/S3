"""Create a Stage1 semantic-lowering candidate without mutating the canonical source.

The first vertical slice ports S1 source-binding identity for parameters and local
bindings into the current PR #268 Stage1 source. Logical value/storage IDs are
module-monotonic and independent from reusable physical scratch slots.

The semantic stream is compiled into the candidate but disabled by default. This
lets Stage0 parse/typecheck the port before any canonical output behavior changes.
Constants and instruction results intentionally remain outside the S1 completion
gate until the expression lowerer is ported.
"""

from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "selfhost" / "compiler" / "s3c_stage1.s3"
DEFAULT_STREAM = ROOT / "selfhost" / "compiler" / "stage1_semantic_stream_v1.s3"

PATCH_MARKER = "# STAGE1_SEMANTIC_PORT_V1_S1"


def _zeros(count: int) -> str:
    return ", ".join("0" for _ in range(count))


def _array(name: str, type_name: str, count: int) -> str:
    return f"    mut {name}: {type_name}[{count}] = [{_zeros(count)}]\n"


def _extract_helper_block(stream_source: str) -> str:
    start = stream_source.index("fn semantic_read_byte(")
    end = stream_source.index("fn main() -> i64:")
    block = stream_source[start:end].rstrip() + "\n\n"
    if "fn semantic_emit_value(" not in block or "fn semantic_span_equal(" not in block:
        raise ValueError("semantic stream helper block is incomplete")
    return block


def _insert_after_line(source: str, prefix: str, payload: str) -> str:
    start = source.index(prefix)
    newline = source.index("\n", start)
    return source[: newline + 1] + payload + source[newline + 1 :]


def _replace_once(source: str, old: str, new: str) -> str:
    count = source.count(old)
    if count != 1:
        raise ValueError(f"expected one patch anchor, found {count}: {old[:80]!r}")
    return source.replace(old, new, 1)


def apply_patch(source: str, stream_source: str) -> str:
    if PATCH_MARKER in source:
        return source

    helper_block = _extract_helper_block(stream_source)
    main_anchor = "fn main() -> tryte:\n"
    if main_anchor not in source:
        raise ValueError("Stage1 main anchor not found")
    source = source.replace(
        main_anchor,
        f"{PATCH_MARKER}\n{helper_block}{main_anchor}",
        1,
    )

    declaration_anchor = "    mut ir_parameter_type: i64[68] = ["
    declarations = ""
    declarations += _array("ir_parameter_value_id", "i64", 68)
    declarations += _array("ir_parameter_value_valid", "trit", 68)
    declarations += _array("ir_parameter_name_start", "i64", 68)
    declarations += _array("ir_parameter_name_length", "i64", 68)
    declarations += _array("ir_parameter_mutable", "trit", 68)
    declarations += _array("semantic_local_name_start", "i64", 365)
    declarations += _array("semantic_local_name_length", "i64", 365)
    declarations += _array("semantic_local_type", "i64", 365)
    declarations += _array("semantic_local_mutable", "trit", 365)
    declarations += _array("semantic_local_value_id", "i64", 365)
    declarations += _array("semantic_local_value_valid", "trit", 365)
    declarations += _array("semantic_local_indent", "i64", 365)
    declarations += _array("semantic_local_array_length", "i64", 365)
    declarations += _array("semantic_local_storage_id", "i64", 365)
    declarations += _array("semantic_local_storage_valid", "trit", 365)
    source = _insert_after_line(source, declaration_anchor, declarations)

    state_anchor = "    mut parameter_type_pending: trit = 0\n"
    states = (
        "    mut semantic_stream_enabled: trit = 0\n"
        "    mut semantic_next_value_id: i64 = 0\n"
        "    mut semantic_next_storage_id: i64 = 0\n"
        "    mut semantic_local_scratch_count: i64 = 0\n"
        "    mut semantic_local_type_pending: trit = 0\n"
        "    mut semantic_local_type_slot: i64 = -1\n"
        "    mut semantic_local_declaration_pending: trit = 0\n"
        "    mut semantic_local_array_pending: trit = 0\n"
        "    mut semantic_local_pending_slot: i64 = -1\n"
    )
    source = _replace_once(source, state_anchor, state_anchor + states)

    parameter_type_anchor = (
        "                    -1:\n"
        "                        ir_parameter_type[parameter_type_slot] = value\n"
        "                        parameter_type_pending = 0\n"
    )
    parameter_type_hook = (
        "                    -1:\n"
        "                        ir_parameter_type[parameter_type_slot] = value\n"
        "                        match ir_parameter_value_valid[parameter_type_slot] == -1:\n"
        "                            -1:\n"
        "                                match semantic_stream_enabled == -1:\n"
        "                                    -1:\n"
        "                                        discard semantic_emit_value(ir_parameter_value_id[parameter_type_slot], ir_parameter_owner[parameter_type_slot], 1, value, ir_parameter_name_start[parameter_type_slot], ir_parameter_name_length[parameter_type_slot], 0, -1)\n"
        "                                    0:\n"
        "                                        discard 0\n"
        "                                    1:\n"
        "                                        discard 0\n"
        "                            0:\n"
        "                                ir_capacity_ok = 0\n"
        "                            1:\n"
        "                                ir_capacity_ok = 0\n"
        "                        parameter_type_pending = 0\n"
    )
    source = _replace_once(source, parameter_type_anchor, parameter_type_hook)

    parameter_name_anchor = "                                                        ir_parameter_name[parameter_count] = previous_value\n"
    parameter_name_hook = (
        parameter_name_anchor
        + "                                                        mut semantic_parameter_previous_slot: i64 = slot - 1\n"
        + "                                                        match semantic_parameter_previous_slot < 0:\n"
        + "                                                            -1:\n"
        + "                                                                semantic_parameter_previous_slot = 15\n"
        + "                                                            0:\n"
        + "                                                                discard 0\n"
        + "                                                            1:\n"
        + "                                                                discard 0\n"
        + "                                                        ir_parameter_name_start[parameter_count] = token_start[semantic_parameter_previous_slot]\n"
        + "                                                        ir_parameter_name_length[parameter_count] = token_end[semantic_parameter_previous_slot] - token_start[semantic_parameter_previous_slot]\n"
        + "                                                        ir_parameter_mutable[parameter_count] = 0\n"
        + "                                                        ir_parameter_value_id[parameter_count] = semantic_next_value_id\n"
        + "                                                        ir_parameter_value_valid[parameter_count] = -1\n"
        + "                                                        semantic_next_value_id += 1\n"
    )
    source = _replace_once(source, parameter_name_anchor, parameter_name_hook)

    # Capture the base type for a pending local declaration. Array length is
    # finalized later when the declaration reaches '='.
    local_type_anchor = "                match value == 311:\n"
    local_type_hook = (
        "                match semantic_local_type_pending == -1:\n"
        "                    -1:\n"
        "                        match semantic_local_type_slot >= 0:\n"
        "                            -1:\n"
        "                                semantic_local_type[semantic_local_type_slot] = value\n"
        "                                semantic_local_type_pending = 0\n"
        "                                semantic_local_declaration_pending = -1\n"
        "                                semantic_local_pending_slot = semantic_local_type_slot\n"
        "                            0:\n"
        "                                ir_capacity_ok = 0\n"
        "                            1:\n"
        "                                ir_capacity_ok = 0\n"
        "                    0:\n"
        "                        discard 0\n"
        "                    1:\n"
        "                        discard 0\n"
        + local_type_anchor
    )
    source = _replace_once(source, local_type_anchor, local_type_hook)

    # Independent declaration recognizer. A local declaration colon is preceded
    # by either NEWLINE,identifier,':' or NEWLINE,'mut',identifier,':'. This avoids
    # treating match/while selectors as bindings.
    local_decl_anchor = "        argument_possible = 0\n"
    local_decl_hook = (
        "        match kind == 4:\n"
        "            -1:\n"
        "                match value == 3:\n"
        "                    -1:\n"
        "                        match signature_paren_depth == 0:\n"
        "                            -1:\n"
        "                                match current_function >= 0:\n"
        "                                    -1:\n"
        "                                        match current_indent > 0:\n"
        "                                            -1:\n"
        "                                                match previous_kind == 1:\n"
        "                                                    -1:\n"
        "                                                        mut semantic_prev_slot: i64 = slot - 1\n"
        "                                                        match semantic_prev_slot < 0:\n"
        "                                                            -1:\n"
        "                                                                semantic_prev_slot = 15\n"
        "                                                            0:\n"
        "                                                                discard 0\n"
        "                                                            1:\n"
        "                                                                discard 0\n"
        "                                                        mut semantic_prev2_slot: i64 = semantic_prev_slot - 1\n"
        "                                                        match semantic_prev2_slot < 0:\n"
        "                                                            -1:\n"
        "                                                                semantic_prev2_slot = semantic_prev2_slot + 16\n"
        "                                                            0:\n"
        "                                                                discard 0\n"
        "                                                            1:\n"
        "                                                                discard 0\n"
        "                                                        mut semantic_decl_candidate: trit = 0\n"
        "                                                        mut semantic_decl_mutable: trit = 0\n"
        "                                                        match to_i64(token_kind[semantic_prev2_slot]) == 3:\n"
        "                                                            -1:\n"
        "                                                                semantic_decl_candidate = -1\n"
        "                                                            0:\n"
        "                                                                match to_i64(token_kind[semantic_prev2_slot]) == 1:\n"
        "                                                                    -1:\n"
        "                                                                        match token_value[semantic_prev2_slot] == 87:\n"
        "                                                                            -1:\n"
        "                                                                                semantic_decl_candidate = -1\n"
        "                                                                                semantic_decl_mutable = -1\n"
        "                                                                            0:\n"
        "                                                                                discard 0\n"
        "                                                                            1:\n"
        "                                                                                discard 0\n"
        "                                                                    0:\n"
        "                                                                        discard 0\n"
        "                                                                    1:\n"
        "                                                                        discard 0\n"
        "                                                            1:\n"
        "                                                                discard 0\n"
        "                                                        match semantic_decl_candidate == -1:\n"
        "                                                            -1:\n"
        "                                                                match semantic_local_scratch_count < 365:\n"
        "                                                                    -1:\n"
        "                                                                        semantic_local_name_start[semantic_local_scratch_count] = token_start[semantic_prev_slot]\n"
        "                                                                        semantic_local_name_length[semantic_local_scratch_count] = token_end[semantic_prev_slot] - token_start[semantic_prev_slot]\n"
        "                                                                        semantic_local_mutable[semantic_local_scratch_count] = semantic_decl_mutable\n"
        "                                                                        semantic_local_value_id[semantic_local_scratch_count] = semantic_next_value_id\n"
        "                                                                        semantic_local_value_valid[semantic_local_scratch_count] = -1\n"
        "                                                                        semantic_local_indent[semantic_local_scratch_count] = current_indent\n"
        "                                                                        semantic_local_array_length[semantic_local_scratch_count] = 0\n"
        "                                                                        semantic_local_storage_valid[semantic_local_scratch_count] = 0\n"
        "                                                                        semantic_local_type_pending = -1\n"
        "                                                                        semantic_local_type_slot = semantic_local_scratch_count\n"
        "                                                                        semantic_next_value_id += 1\n"
        "                                                                        semantic_local_scratch_count += 1\n"
        "                                                                    0:\n"
        "                                                                        ir_capacity_ok = 0\n"
        "                                                                    1:\n"
        "                                                                        ir_capacity_ok = 0\n"
        "                                                            0:\n"
        "                                                                discard 0\n"
        "                                                            1:\n"
        "                                                                discard 0\n"
        "                                                    0:\n"
        "                                                        discard 0\n"
        "                                                    1:\n"
        "                                                        discard 0\n"
        "                                            0:\n"
        "                                                discard 0\n"
        "                                            1:\n"
        "                                                discard 0\n"
        "                                    0:\n"
        "                                        discard 0\n"
        "                                    1:\n"
        "                                        discard 0\n"
        "                            0:\n"
        "                                discard 0\n"
        "                            1:\n"
        "                                discard 0\n"
        "                    0:\n"
        "                        discard 0\n"
        "                    1:\n"
        "                        discard 0\n"
        "            0:\n"
        "                discard 0\n"
        "            1:\n"
        "                discard 0\n"
        + local_decl_anchor
    )
    source = _replace_once(source, local_decl_anchor, local_decl_hook)

    # Array length capture for a pending local declaration.
    numeric_anchor = "        match kind == 2:\n            -1:\n                match array_initializer_depth >= 0:\n"
    numeric_hook = (
        "        match kind == 2:\n"
        "            -1:\n"
        "                match semantic_local_array_pending == -1:\n"
        "                    -1:\n"
        "                        match semantic_local_pending_slot >= 0:\n"
        "                            -1:\n"
        "                                semantic_local_array_length[semantic_local_pending_slot] = value\n"
        "                                semantic_local_array_pending = 0\n"
        "                            0:\n"
        "                                ir_capacity_ok = 0\n"
        "                            1:\n"
        "                                ir_capacity_ok = 0\n"
        "                    0:\n"
        "                        discard 0\n"
        "                    1:\n"
        "                        discard 0\n"
        "                match array_initializer_depth >= 0:\n"
    )
    source = _replace_once(source, numeric_anchor, numeric_hook)

    punctuation_anchor = "        match kind == 4:\n            -1:\n                match value == 4:\n"
    punctuation_hook = (
        "        match kind == 4:\n"
        "            -1:\n"
        "                match semantic_local_declaration_pending == -1:\n"
        "                    -1:\n"
        "                        match value == 10:\n"
        "                            -1:\n"
        "                                semantic_local_array_pending = -1\n"
        "                            0:\n"
        "                                match value == 5:\n"
        "                                    -1:\n"
        "                                        match semantic_local_pending_slot >= 0:\n"
        "                                            -1:\n"
        "                                                match semantic_local_mutable[semantic_local_pending_slot] == -1:\n"
        "                                                    -1:\n"
        "                                                        semantic_local_storage_id[semantic_local_pending_slot] = semantic_next_storage_id\n"
        "                                                        semantic_local_storage_valid[semantic_local_pending_slot] = -1\n"
        "                                                        semantic_next_storage_id += 1\n"
        "                                                    0:\n"
        "                                                        match semantic_local_array_length[semantic_local_pending_slot] > 0:\n"
        "                                                            -1:\n"
        "                                                                semantic_local_storage_id[semantic_local_pending_slot] = semantic_next_storage_id\n"
        "                                                                semantic_local_storage_valid[semantic_local_pending_slot] = -1\n"
        "                                                                semantic_next_storage_id += 1\n"
        "                                                            0:\n"
        "                                                                discard 0\n"
        "                                                            1:\n"
        "                                                                discard 0\n"
        "                                                    1:\n"
        "                                                        discard 0\n"
        "                                                match semantic_stream_enabled == -1:\n"
        "                                                    -1:\n"
        "                                                        mut semantic_emit_storage_id: i64 = -1\n"
        "                                                        match semantic_local_storage_valid[semantic_local_pending_slot] == -1:\n"
        "                                                            -1:\n"
        "                                                                semantic_emit_storage_id = semantic_local_storage_id[semantic_local_pending_slot]\n"
        "                                                                discard semantic_emit_memory(current_function, semantic_emit_storage_id, semantic_local_type[semantic_local_pending_slot], semantic_local_array_length[semantic_local_pending_slot], to_i64(semantic_local_mutable[semantic_local_pending_slot]))\n"
        "                                                            0:\n"
        "                                                                discard 0\n"
        "                                                            1:\n"
        "                                                                discard 0\n"
        "                                                        discard semantic_emit_value(semantic_local_value_id[semantic_local_pending_slot], current_function, 2, semantic_local_type[semantic_local_pending_slot], semantic_local_name_start[semantic_local_pending_slot], semantic_local_name_length[semantic_local_pending_slot], to_i64(semantic_local_mutable[semantic_local_pending_slot]), semantic_emit_storage_id)\n"
        "                                                    0:\n"
        "                                                        discard 0\n"
        "                                                    1:\n"
        "                                                        discard 0\n"
        "                                                semantic_local_declaration_pending = 0\n"
        "                                                semantic_local_array_pending = 0\n"
        "                                                semantic_local_pending_slot = -1\n"
        "                                            0:\n"
        "                                                ir_capacity_ok = 0\n"
        "                                            1:\n"
        "                                                ir_capacity_ok = 0\n"
        "                                    0:\n"
        "                                        discard 0\n"
        "                                    1:\n"
        "                                        discard 0\n"
        "                            1:\n"
        "                                discard 0\n"
        "                    0:\n"
        "                        discard 0\n"
        "                    1:\n"
        "                        discard 0\n"
        "                match value == 4:\n"
    )
    source = _replace_once(source, punctuation_anchor, punctuation_hook)

    # Reuse local scratch per source function while logical IDs remain global.
    function_reset_anchor = (
        "                                function_count += 1\n"
        "                                current_function = function_count - 1\n"
        "                                pending_function_name = 0\n"
    )
    function_reset_hook = (
        "                                function_count += 1\n"
        "                                current_function = function_count - 1\n"
        "                                semantic_local_scratch_count = 0\n"
        "                                semantic_local_type_pending = 0\n"
        "                                semantic_local_declaration_pending = 0\n"
        "                                semantic_local_array_pending = 0\n"
        "                                semantic_local_pending_slot = -1\n"
        "                                pending_function_name = 0\n"
    )
    source = _replace_once(source, function_reset_anchor, function_reset_hook)

    return source


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--stream-source", type=Path, default=DEFAULT_STREAM)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    source = args.source.read_text(encoding="utf-8")
    stream = args.stream_source.read_text(encoding="utf-8")
    patched = apply_patch(source, stream)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(patched, encoding="utf-8", newline="\n")
    print(f"OUTPUT={args.output}")
    print(f"SOURCE_MUTATED={args.output.resolve() == args.source.resolve()}")
    print("S1_PARAMETERS=IMPLEMENTED_CANDIDATE")
    print("S1_LOCALS=IMPLEMENTED_CANDIDATE")
    print("S1_CONSTANTS=BLOCKED_EXPRESSION_LOWERER")
    print("S1_RESULTS=BLOCKED_EXPRESSION_LOWERER")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
