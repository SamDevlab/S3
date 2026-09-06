from __future__ import annotations

import hashlib
from pathlib import Path

EXPECTED_SHA256 = "34352f505c4e1452594f9e1c5d1db64efa77a94e30870f9887ca5c85dd0eb8d7"

FUNCTION_START = "fn scan_while_relation_match_body_v3("
FUNCTION_END = "\nfn scan_while_line("

HELPER_INSERT_BEFORE = "\nfn scan_while_relation_match_body_v3("

HELPERS = r'''
fn function_mutable_storage_count(header_end: i64) -> i64:
    mut length: i64 = s3_stage1_source_length()
    mut cursor: i64 = header_end + 1
    while cursor < length:
        mut stop: i64 = line_end(cursor, length)
        mut first: i64 = first_non_space(cursor, stop)
        match first == cursor:
            -1:
                match parse_header(first, stop, 1) > 0:
                    -1:
                        return mutable_storage_count_before(header_end + 1, cursor)
                    0:
                        match parse_foreign_header(first, stop) > 0:
                            -1:
                                return mutable_storage_count_before(header_end + 1, cursor)
                            0:
                                discard 0
                            1:
                                discard 0
                    1:
                        discard 0
            0:
                discard 0
            1:
                discard 0
        cursor = stop + 1
    return mutable_storage_count_before(header_end + 1, length)

fn scan_linear_statement_segment(mode: i64, function_id: i64, return_type: i64, header_start: i64, header_end: i64, start: i64, end: i64, value_id: i64, block_start: i64) -> i64:
    mut cursor: i64 = start
    mut next_id: i64 = value_id
    while cursor < end:
        mut stop: i64 = line_end(cursor, end)
        match stop > end:
            -1:
                stop = end
            0:
                discard 0
            1:
                discard 0
        mut first: i64 = first_non_space(cursor, stop)
        match first == stop:
            -1:
                discard 0
            0:
                mut word_stop: i64 = word_end(first, stop)
                match is_return_line(first, stop):
                    -1:
                        return -1
                    0:
                        discard 0
                    1:
                        return -1
                match parse_break_statement(first, stop) > 0:
                    -1:
                        return -1
                    0:
                        discard 0
                    1:
                        return -1
                match word_is(first, word_stop, 103668165, 5):
                    -1:
                        return -1
                    0:
                        discard 0
                    1:
                        return -1
                match word_is(first, word_stop, 113101617, 5):
                    -1:
                        return -1
                    0:
                        discard 0
                    1:
                        return -1
                mut line_next_id: i64 = scan_body_line(mode, function_id, return_type, header_start, header_end, first, stop, next_id, block_start)
                match lowering_result_kind(line_next_id) == 0:
                    -1:
                        match line_next_id >= 0:
                            -1:
                                next_id = line_next_id
                            0:
                                return -1
                            1:
                                return -1
                    0:
                        return -1
                    1:
                        return -1
            1:
                return -1
        cursor = stop + 1
    return next_id
'''

OLD_SETUP = r'''    mut body_start: i64 = line_end(source_line_start(first), length) + 1
    mut body_stop: i64 = line_end(body_start, length)
    mut nested_match_start: i64 = first_non_space(body_start, body_stop)
    mut nested_match_stop: i64 = body_stop
    mut nested_match_info: i64 = parse_match_comparison(nested_match_start, nested_match_stop)
    match nested_match_info > 0:
        -1:
            discard 0
        0:
            nested_match_info = parse_match_parameter_rhs_comparison(nested_match_start, nested_match_stop)
        1:
            discard 0
    mut nested_match_end: i64 = while_body_end(nested_match_start, length)
'''

NEW_SETUP = r'''    mut body_start: i64 = line_end(source_line_start(first), length) + 1
    mut after_loop_start: i64 = while_body_end(first, length)
    mut nested_match_start: i64 = body_start
    mut nested_match_stop: i64 = body_start
    mut nested_match_info: i64 = 0
    mut body_cursor: i64 = body_start
    mut body_indent: i64 = first - source_line_start(first) + 4
    mut nested_found: trit = 0
    while body_cursor < after_loop_start:
        mut body_line_stop: i64 = line_end(body_cursor, length)
        mut body_line_first: i64 = first_non_space(body_cursor, body_line_stop)
        match body_line_first < body_line_stop:
            -1:
                match body_line_first - body_cursor == body_indent:
                    -1:
                        mut candidate_match_info: i64 = parse_match_comparison(body_line_first, body_line_stop)
                        match candidate_match_info > 0:
                            -1:
                                nested_match_start = body_line_first
                                nested_match_stop = body_line_stop
                                nested_match_info = candidate_match_info
                                nested_found = -1
                                body_cursor = after_loop_start
                            0:
                                candidate_match_info = parse_match_parameter_rhs_comparison(body_line_first, body_line_stop)
                                match candidate_match_info > 0:
                                    -1:
                                        nested_match_start = body_line_first
                                        nested_match_stop = body_line_stop
                                        nested_match_info = candidate_match_info
                                        nested_found = -1
                                        body_cursor = after_loop_start
                                    0:
                                        body_cursor = body_line_stop + 1
                                    1:
                                        body_cursor = body_line_stop + 1
                            1:
                                body_cursor = body_line_stop + 1
                    0:
                        return -1
                    1:
                        return -1
            0:
                body_cursor = body_line_stop + 1
            1:
                return -1
    mut nested_match_end: i64 = nested_match_stop
    match nested_found == -1:
        -1:
            nested_match_end = while_body_end(nested_match_start, length)
        0:
            discard 0
        1:
            discard 0
    mut prelude_stop: i64 = source_line_start(nested_match_start)
    mut postlude_start: i64 = nested_match_end
'''

OLD_AFTER_LOOP = r'''    mut increment_start: i64 = nested_match_end
    mut increment_stop: i64 = line_end(increment_start, length)
    mut after_loop_start: i64 = while_body_end(first, length)
    mut after_loop_stop: i64 = line_end(after_loop_start, length)
'''

NEW_AFTER_LOOP = r'''    mut after_loop_stop: i64 = line_end(after_loop_start, length)
'''

OLD_INCREMENT_DECL = r'''    mut increment_info: trit = parse_increment_statement(increment_start, increment_stop)
'''

OLD_BLOCK_DECLS = r'''    mut final_block: i64 = current_block + 20
    mut lane_first_block: i64 = current_block + 6
    mut lane_dispatch_block: i64 = current_block + 9
    mut nested_match_block: i64 = current_block + 10
    mut nested_successor_block: i64 = current_block + 14
    mut valid: trit = -1
'''

NEW_BLOCK_DECLS = r'''    mut final_block: i64 = current_block + 20
    mut lane_first_block: i64 = current_block + 6
    mut lane_dispatch_block: i64 = current_block + 9
    mut nested_match_block: i64 = current_block + 10
    mut valid: trit = -1
    match nested_found == -1:
        -1:
            discard 0
        0:
            valid = 0
        1:
            valid = 0
    mut prelude_validation_id: i64 = value_id
    match prelude_stop > body_start:
        -1:
            prelude_validation_id = scan_linear_statement_segment(0, function_id, return_type, header_start, header_end, body_start, prelude_stop, value_id, body_start)
            match prelude_validation_id >= 0:
                -1:
                    discard 0
                0:
                    valid = 0
                1:
                    valid = 0
        0:
            discard 0
        1:
            valid = 0
    mut postlude_validation_id: i64 = value_id
    match after_loop_start > postlude_start:
        -1:
            postlude_validation_id = scan_linear_statement_segment(0, function_id, return_type, header_start, header_end, postlude_start, after_loop_start, value_id, postlude_start)
            match postlude_validation_id >= 0:
                -1:
                    discard 0
                0:
                    valid = 0
                1:
                    valid = 0
        0:
            discard 0
        1:
            valid = 0
'''

OLD_INCREMENT_VALIDATION_START = r'''    match increment_info:
'''
OLD_RETURN_VALIDATION = r'''    match return_info < 0:
'''

OLD_TEMP_STORAGE = "            mut temporary_storage_id: i64 = mutable_storage_count_before(header_end + 1, first)\n"
NEW_TEMP_STORAGE = "            mut temporary_storage_id: i64 = function_mutable_storage_count(header_end)\n"

OLD_EMISSION_START = r'''            discard emit_v3_i_block(body_jump_id, function_id, body_block, ordinal + 5, 24, 0, 0, -1, -1)
'''
OUTER_TAIL = r'''        0:
            return -1
        1:
            return -1
'''

NEW_EMISSION = r'''            mut body_context_function_id: i64 = v3_context_function_id(v3_logical_function_id(function_id), body_block)
            mut prelude_next_id: i64 = nested_value_id
            match prelude_stop > body_start:
                -1:
                    prelude_next_id = scan_linear_statement_segment(2, body_context_function_id, return_type, header_start, header_end, body_start, prelude_stop, nested_value_id, body_start)
                    match prelude_next_id >= 0:
                        -1:
                            discard 0
                        0:
                            return -1
                        1:
                            return -1
                0:
                    discard 0
                1:
                    return -1
            mut body_jump_ordinal: i64 = count_core_instructions_between(header_end + 1, nested_match_start)
            mut actual_body_jump_id: i64 = body_context_function_id * 1000000 + body_jump_ordinal
            discard emit_v3_i_block(actual_body_jump_id, body_context_function_id, body_block, body_jump_ordinal, 24, 0, 0, -1, -1)
            discard emit_v3_t_jump(actual_body_jump_id, nested_match_block)
            mut nested_next_id: i64 = scan_match_relation_fallthrough_v3(function_id, return_type, header_start, header_end, nested_match_start, nested_match_stop, nested_match_info, prelude_next_id, nested_match_block, nested_match_start, 0)
            match lowering_result_kind(nested_next_id) == 3:
                -1:
                    mut decoded_block_id: i64 = lowering_result_next_block(nested_next_id)
                    mut decoded_value_id: i64 = lowering_result_next_id(nested_next_id)
                    mut decoded_cursor: i64 = lowering_result_next_cursor(nested_next_id)
                    match decoded_block_id >= 0:
                        -1:
                            match decoded_cursor == postlude_start:
                                -1:
                                    mut postlude_function_id: i64 = v3_context_function_id(v3_logical_function_id(function_id), decoded_block_id)
                                    mut postlude_next_id: i64 = decoded_value_id
                                    match after_loop_start > postlude_start:
                                        -1:
                                            postlude_next_id = scan_linear_statement_segment(2, postlude_function_id, return_type, header_start, header_end, postlude_start, after_loop_start, decoded_value_id, postlude_start)
                                            match postlude_next_id >= 0:
                                                -1:
                                                    discard 0
                                                0:
                                                    return -1
                                                1:
                                                    return -1
                                        0:
                                            discard 0
                                        1:
                                            return -1
                                    final_block = decoded_block_id + 1
                                    mut postlude_jump_ordinal: i64 = count_core_instructions_between(header_end + 1, after_loop_start)
                                    mut postlude_jump_id: i64 = postlude_function_id * 1000000 + postlude_jump_ordinal
                                    discard emit_v3_i_block(postlude_jump_id, postlude_function_id, decoded_block_id, postlude_jump_ordinal, 24, 0, 0, -1, -1)
                                    discard emit_v3_t_jump(postlude_jump_id, current_block + 1)
                                    discard emit_v3_i_block(exit_zero_jump_id, function_id, exit_zero_block, ordinal + 6, 24, 0, 0, -1, -1)
                                    discard emit_v3_t_jump(exit_zero_jump_id, final_block)
                                    discard emit_v3_i_block(exit_positive_jump_id, function_id, exit_positive_block, ordinal + 7, 24, 0, 0, -1, -1)
                                    discard emit_v3_t_jump(exit_positive_jump_id, final_block)
                                    discard emit_v3_b_block(function_id, current_block, current_block, ordinal + 1, entry_jump_id)
                                    discard emit_v3_b_block(function_id, current_block + 1, current_block + 1, condition_instruction_count, condition_branch_id)
                                    discard emit_v3_b_block(function_id, body_block, body_block, count_core_instructions_between(body_start, prelude_stop) + 1, v3_context_instruction_id(actual_body_jump_id))
                                    discard emit_v3_b_block(function_id, exit_zero_block, exit_zero_block, 1, exit_zero_jump_id)
                                    discard emit_v3_b_block(function_id, exit_positive_block, exit_positive_block, 1, exit_positive_jump_id)
                                    discard emit_v3_b_block(function_id, lane_first_block, lane_first_block, 4, lane_first_id + 3)
                                    discard emit_v3_b_block(function_id, lane_first_block + 1, lane_first_block + 1, 4, lane_first_id + 7)
                                    discard emit_v3_b_block(function_id, lane_first_block + 2, lane_first_block + 2, 4, lane_first_id + 11)
                                    discard emit_v3_b_block(function_id, lane_dispatch_block, lane_dispatch_block, 3, dispatch_branch_id)
                                    discard emit_v3_b_block(function_id, decoded_block_id, decoded_block_id, count_core_instructions_between(postlude_start, after_loop_start) + 1, v3_context_instruction_id(postlude_jump_id))
                                    mut encoded_next_id: i64 = 3000000000000 + final_block * 100000000000
                                    encoded_next_id = encoded_next_id + postlude_next_id * 1000000 + after_loop_start
                                    return encoded_next_id
                                0:
                                    return -1
                                1:
                                    return -1
                        0:
                            return -1
                        1:
                            return -1
                0:
                    return -1
                1:
                    return -1
'''


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise ValueError(f"{label}: expected exactly 1 match, found {count}")
    return text.replace(old, new, 1)


def patch_source(source: str, *, enforce_hash: bool = True) -> str:
    if enforce_hash:
        digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
        if digest != EXPECTED_SHA256:
            raise ValueError(f"unexpected candidate SHA256: {digest}")

    start = source.index(FUNCTION_START)
    end = source.index(FUNCTION_END, start)
    function = source[start:end]

    function = _replace_once(function, OLD_SETUP, NEW_SETUP, "body/nested setup")
    function = _replace_once(function, OLD_AFTER_LOOP, NEW_AFTER_LOOP, "after-loop setup")
    function = _replace_once(function, OLD_INCREMENT_DECL, "", "increment declaration")
    function = _replace_once(function, OLD_BLOCK_DECLS, NEW_BLOCK_DECLS, "block declarations")

    inc_start = function.index(OLD_INCREMENT_VALIDATION_START)
    ret_start = function.index(OLD_RETURN_VALIDATION, inc_start)
    function = function[:inc_start] + function[ret_start:]

    function = _replace_once(function, OLD_TEMP_STORAGE, NEW_TEMP_STORAGE, "temporary storage id")

    emission_start = function.index(OLD_EMISSION_START)
    tail_start = function.rfind(OUTER_TAIL)
    if tail_start <= emission_start:
        raise ValueError("could not locate outer match-valid tail")
    function = function[:emission_start] + NEW_EMISSION + function[tail_start:]

    patched = source[:start] + function + source[end:]
    if HELPERS.strip() not in patched:
        patched = _replace_once(
            patched,
            HELPER_INSERT_BEFORE,
            "\n" + HELPERS + "\nfn scan_while_relation_match_body_v3(",
            "helper insertion",
        )
    return patched


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    source = args.path.read_text(encoding="utf-8")
    patched = patch_source(source)
    digest = hashlib.sha256(patched.encode("utf-8")).hexdigest()
    print(f"PATCHED_SHA256={digest}")
    print(f"PATCHED_BYTES={len(patched.encode('utf-8'))}")
    if args.write:
        args.path.write_text(patched, encoding="utf-8")
    if args.check and patched == source:
        raise SystemExit("patch produced no change")


if __name__ == "__main__":
    main()
