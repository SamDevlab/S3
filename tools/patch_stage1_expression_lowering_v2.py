"""Generate the Stage04 candidate from accepted source/protocol components."""

from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = "# STAGE1_SEMANTIC_LOWERING_V2_STAGE04\nfn stage04_word(start: i64, end: i64, expected_hash: i64, expected_length: i64) -> trit:\n    match end - start == expected_length:\n        -1:\n            return 0\n        0:\n            match identifier_hash(start, end) == expected_hash:\n                -1:\n                    return -1\n                0:\n                    return 0\n                1:\n                    return 0\n        1:\n            return 0\n\nfn stage04_same_span(left_start: i64, left_length: i64, right_start: i64, right_length: i64) -> trit:\n    match left_length == right_length:\n        -1:\n            return 0\n        0:\n            mut cursor: i64 = 0\n            mut equal: trit = -1\n            while cursor < left_length:\n                match read_at(left_start + cursor) == read_at(right_start + cursor):\n                    -1:\n                        cursor += 1\n                    0:\n                        equal = 0\n                        cursor = left_length\n                    1:\n                        equal = 0\n                        cursor = left_length\n            return equal\n        1:\n            return 0\n\nfn stage04_indent(start: i64) -> i64:\n    mut cursor: i64 = start\n    mut line_start: i64 = 0\n    while cursor > 0:\n        match read_at(cursor - 1) == 10:\n            -1:\n                line_start = cursor\n                cursor = 0\n            0:\n                cursor = cursor - 1\n            1:\n                line_start = cursor\n                cursor = 0\n    return start - line_start\n\nfn stage04_type_code(start: i64, end: i64) -> i64:\n    match stage04_word(start, end, 76, 4):\n        -1:\n            return 1\n        0:\n            match stage04_word(start, end, 313, 5):\n                -1:\n                    return 2\n                0:\n                    match stage04_word(start, end, 66, 3):\n                        -1:\n                            return 3\n                        0:\n                            match stage04_word(start, end, 103, 3):\n                                -1:\n                                    return 4\n                                0:\n                                    return 0\n                                1:\n                                    return 0\n                        1:\n                            return 0\n                1:\n                    return 0\n        1:\n            return 0\n\nfn stage04_precedence(op: i64) -> i64:\n    match op == 20:\n        -1:\n            return 6\n        0:\n            match op == 22:\n                -1:\n                    return 6\n                0:\n                    match op == 5:\n                        -1:\n                            return 5\n                        0:\n                            match op == 7:\n                                -1:\n                                    return 5\n                                0:\n                                    match op == 18:\n                                        -1:\n                                            return 4\n                                        0:\n                                            match op == 19:\n                                                -1:\n                                                    return 3\n                                                0:\n                                                    match op == 15:\n                                                        -1:\n                                                            return 2\n                                                        0:\n                                                            match op == 13:\n                                                                -1:\n                                                                    return 1\n                                                                0:\n                                                                    match op == 21:\n                                                                        -1:\n                                                                            return 1\n                                                                        0:\n                                                                            match op == 16:\n                                                                                -1:\n                                                                                    return 1\n                                                                                0:\n                                                                                    match op == 23:\n                                                                                        -1:\n                                                                                            return 1\n                                                                                        0:\n                                                                                            match op == 17:\n                                                                                                -1:\n                                                                                                    return 1\n                                                                                                0:\n                                                                                                    match op == 24:\n                                                                                                        -1:\n                                                                                                            return 1\n                                                                                                        0:\n                                                                                                            return 0\n                                                                                                        1:\n                                                                                                            return 0\n                                                                                                1:\n                                                                                                    return 1\n                                                                                        1:\n                                                                                            return 1\n                                                                                1:\n                                                                                    return 1\n                                                                        1:\n                                                                            return 1\n                                                                1:\n                                                                    return 1\n                                                        1:\n                                                            return 2\n                                                1:\n                                                    return 3\n                                        1:\n                                            return 4\n                                1:\n                                    return 5\n                        1:\n                            return 5\n                1:\n                    return 6\n        1:\n            return 6\n\nfn stage04_number(start: i64, end: i64) -> i64:\n    mut cursor: i64 = start\n    mut negative: trit = 0\n    match cursor < end:\n        -1:\n            match read_at(cursor) == 45:\n                -1:\n                    negative = -1\n                    cursor += 1\n                0:\n                    discard 0\n                1:\n                    discard 0\n        0:\n            discard 0\n        1:\n            discard 0\n    mut number: i64 = 0\n    while cursor < end:\n        number = number * 10 + to_i64(read_at(cursor)) - 48\n        cursor += 1\n    match negative == -1:\n        -1:\n            return 0 - number\n        0:\n            return number\n        1:\n            return number\n\nfn main() -> i64:\n    mut length: i64 = s3_stage1_source_length()\n    mut parse_ok: trit = -1\n    mut token_kind: tryte[128] = [__Z128__]\n    mut token_start: i64[128] = [__Z128__]\n    mut token_end: i64[128] = [__Z128__]\n    mut token_value: i64[128] = [__Z128__]\n    mut token_count: i64 = 0\n    mut scan_cursor: i64 = 0\n    while scan_cursor < length:\n        mut packed: i64 = scan_token(scan_cursor, length)\n        mut next_cursor: i64 = packed / 1000000\n        mut remainder: i64 = packed - next_cursor * 1000000\n        mut kind: i64 = remainder / 1000\n        mut value: i64 = remainder - kind * 1000 - 500\n        match kind == 9:\n            -1:\n                match value == 35:\n                    -1:\n                        mut comment_cursor: i64 = next_cursor\n                        mut comment_done: trit = 0\n                        while comment_done == 0:\n                            match comment_cursor < length:\n                                -1:\n                                    match read_at(comment_cursor) == 10:\n                                        -1:\n                                            comment_done = -1\n                                        0:\n                                            comment_cursor += 1\n                                        1:\n                                            comment_done = -1\n                                0:\n                                    comment_done = -1\n                                1:\n                                    comment_done = -1\n                        packed = scan_token(comment_cursor, length)\n                        next_cursor = packed / 1000000\n                        remainder = packed - next_cursor * 1000000\n                        kind = remainder / 1000\n                        value = remainder - kind * 1000 - 500\n                    0:\n                        match value == 38:\n                            -1:\n                                kind = 4\n                                value = 18\n                            0:\n                                match value == 124:\n                                    -1:\n                                        kind = 4\n                                        value = 19\n                                    0:\n                                        match value == 126:\n                                            -1:\n                                                kind = 4\n                                                value = 20\n                                            0:\n                                                match value == 33:\n                                                    -1:\n                                                        match next_cursor < length:\n                                                            -1:\n                                                                match read_at(next_cursor) == 61:\n                                                                    -1:\n                                                                        next_cursor += 1\n                                                                        kind = 4\n                                                                        value = 21\n                                                                    0:\n                                                                        discard 0\n                                                                    1:\n                                                                        discard 0\n                                                            0:\n                                                                discard 0\n                                                            1:\n                                                                discard 0\n                                                    0:\n                                                        discard 0\n                                                    1:\n                                                        discard 0\n                                            1:\n                                                discard 0\n                                    1:\n                                        discard 0\n                            1:\n                                discard 0\n                0:\n                    discard 0\n                1:\n                    discard 0\n        0:\n            discard 0\n        1:\n            discard 0\n        match next_cursor > scan_cursor:\n            -1:\n                match kind == 0:\n                    -1:\n                        scan_cursor = next_cursor\n                    0:\n                        match token_count < 128:\n                            -1:\n                                mut actual_start: i64 = scan_cursor\n                                while actual_start < next_cursor:\n                                    match is_space_unit(read_at(actual_start)):\n                                        -1:\n                                            actual_start += 1\n                                        0:\n                                            actual_start = next_cursor\n                                        1:\n                                            actual_start = next_cursor\n                                token_kind[token_count] = to_tryte(kind)\n                                token_start[token_count] = actual_start\n                                token_end[token_count] = next_cursor\n                                token_value[token_count] = value\n                                token_count += 1\n                                scan_cursor = next_cursor\n                            0:\n                                parse_ok = 0\n                                scan_cursor = length\n                            1:\n                                parse_ok = 0\n                                scan_cursor = length\n                    1:\n                        parse_ok = 0\n                        scan_cursor = length\n            0:\n                parse_ok = 0\n                scan_cursor = length\n            1:\n                parse_ok = 0\n                scan_cursor = length\n\n    mut function_count: i64 = 0\n    mut function_name_start: i64[32] = [__Z32__]\n    mut function_name_length: i64[32] = [__Z32__]\n    mut function_kind: tryte[32] = [__Z32__]\n    mut function_param_start: i64[32] = [__Z32__]\n    mut function_param_count: i64[32] = [__Z32__]\n    mut function_return_type: tryte[32] = [__Z32__]\n    mut function_body_start: i64[32] = [__Z32__]\n    mut function_body_end: i64[32] = [__Z32__]\n    mut parameter_count: i64 = 0\n    mut parameter_owner: i64[64] = [__Z64__]\n    mut parameter_name_start: i64[64] = [__Z64__]\n    mut parameter_name_length: i64[64] = [__Z64__]\n    mut parameter_type: tryte[64] = [__Z64__]\n    mut parameter_value_id: i64[64] = [__Z64__]\n    mut local_count: i64 = 0\n    mut local_owner: i64[64] = [__Z64__]\n    mut local_name_start: i64[64] = [__Z64__]\n    mut local_name_length: i64[64] = [__Z64__]\n    mut local_type: tryte[64] = [__Z64__]\n    mut local_mutable: trit[64] = [__Z64__]\n    mut local_storage: i64[64] = [__Z64__]\n    mut local_declaration_token: i64[64] = [__Z64__]\n    mut local_init_start: i64[64] = [__Z64__]\n    mut local_init_end: i64[64] = [__Z64__]\n    mut local_value_id: i64[64] = [__Z64__]\n    mut value_count: i64 = 0\n    mut value_kind: tryte[128] = [__Z128__]\n    mut value_owner: i64[128] = [__Z128__]\n    mut value_type: tryte[128] = [__Z128__]\n    mut value_anchor_start: i64[128] = [__Z128__]\n    mut value_anchor_length: i64[128] = [__Z128__]\n    mut value_mutable: trit[128] = [__Z128__]\n    mut value_storage: i64[128] = [__Z128__]\n    mut instruction_count: i64 = 0\n    mut instruction_owner: i64[128] = [__Z128__]\n    mut instruction_block: i64[128] = [__Z128__]\n    mut instruction_ordinal: i64[128] = [__Z128__]\n    mut instruction_opcode: tryte[128] = [__Z128__]\n    mut instruction_results: i64[128] = [__Z128__]\n    mut instruction_operands: i64[128] = [__Z128__]\n    mut instruction_aux_a: i64[128] = [__Z128__]\n    mut instruction_aux_b: i64[128] = [__Z128__]\n    mut instruction_result_value: i64[128] = [__Z128__]\n    mut instruction_operand_a: i64[128] = [__Z128__]\n    mut instruction_operand_b: i64[128] = [__Z128__]\n    mut terminator_instruction: i64[32] = [__Z32__]\n    mut terminator_return_value: i64[32] = [__Z32__]\n    mut function_instruction_start: i64[32] = [__Z32__]\n    mut function_instruction_count: i64[32] = [__Z32__]\n    mut local_current: i64[64] = [__ZN64__]\n    mut expression_values: i64[64] = [__Z64__]\n    mut expression_types: tryte[64] = [__Z64__]\n    mut expression_rpn_kind: tryte[64] = [__Z64__]\n    mut expression_rpn_value: i64[64] = [__Z64__]\n    mut expression_rpn_token: i64[64] = [__Z64__]\n    mut expression_operators: i64[64] = [__Z64__]\n\n    mut token_index: i64 = 0\n    while token_index < token_count:\n        mut fn_index: i64 = token_index\n        mut foreign_flag: i64 = 0\n        match token_kind[token_index] == 1:\n            -1:\n                match stage04_word(token_start[token_index], token_end[token_index], 311, 7):\n                    -1:\n                        foreign_flag = 1\n                        fn_index += 1\n                    0:\n                        discard 0\n                    1:\n                        discard 0\n            0:\n                discard 0\n            1:\n                discard 0\n        mut is_function: trit = 0\n        match fn_index < token_count:\n            -1:\n                match token_kind[fn_index] == 1:\n                    -1:\n                        match stage04_word(token_start[fn_index], token_end[fn_index], 352, 2):\n                            -1:\n                                is_function = -1\n                            0:\n                                discard 0\n                            1:\n                                discard 0\n                    0:\n                        discard 0\n                    1:\n                        discard 0\n            0:\n                discard 0\n            1:\n                discard 0\n        match is_function:\n            -1:\n                match function_count < 32:\n                    -1:\n                        mut name_index: i64 = fn_index + 1\n                        mut cursor: i64 = name_index + 1\n                        mut header_ok: trit = -1\n                        match name_index < token_count:\n                            -1:\n                                match token_kind[name_index] == 1:\n                                    -1:\n                                        discard 0\n                                    0:\n                                        header_ok = 0\n                                    1:\n                                        header_ok = 0\n                                0:\n                                    header_ok = 0\n                                1:\n                                    header_ok = 0\n                        0:\n                            header_ok = 0\n                        1:\n                            header_ok = 0\n                        match header_ok:\n                            -1:\n                                match cursor < token_count:\n                                    -1:\n                                        match token_kind[cursor] == 4:\n                                            -1:\n                                                match token_value[cursor] == 1:\n                                                    -1:\n                                                        cursor += 1\n                                                    0:\n                                                        header_ok = 0\n                                                    1:\n                                                        header_ok = 0\n                                            0:\n                                                header_ok = 0\n                                            1:\n                                                header_ok = 0\n                                    0:\n                                        header_ok = 0\n                                    1:\n                                        header_ok = 0\n                        match header_ok:\n                            -1:\n                                function_name_start[function_count] = token_start[name_index]\n                                function_name_length[function_count] = token_end[name_index] - token_start[name_index]\n                                function_kind[function_count] = to_tryte(1)\n                                match foreign_flag == 1:\n                                    -1:\n                                        function_kind[function_count] = to_tryte(2)\n                                    0:\n                                        discard 0\n                                    1:\n                                        function_kind[function_count] = to_tryte(2)\n                                function_param_start[function_count] = parameter_count\n                                mut parameter_done: trit = 0\n                                while parameter_done == 0:\n                                    match cursor < token_count:\n                                        -1:\n                                            match token_kind[cursor] == 4:\n                                                -1:\n                                                    match token_value[cursor] == 2:\n                                                        -1:\n                                                            parameter_done = -1\n                                                            cursor += 1\n                                                        0:\n                                                            discard 0\n                                                        1:\n                                                            discard 0\n                                                0:\n                                                    match parameter_count < 64:\n                                                        -1:\n                                                            match cursor + 2 < token_count:\n                                                                -1:\n                                                                    parameter_name_start[parameter_count] = token_start[cursor]\n                                                                    parameter_name_length[parameter_count] = token_end[cursor] - token_start[cursor]\n                                                                    parameter_owner[parameter_count] = function_count\n                                                                    parameter_type[parameter_count] = to_tryte(stage04_type_code(token_start[cursor + 2], token_end[cursor + 2]))\n                                                                    parameter_count += 1\n                                                                    cursor = cursor + 3\n                                                                    match cursor < token_count:\n                                                                        -1:\n                                                                            match token_value[cursor] == 4:\n                                                                                -1:\n                                                                                    cursor += 1\n                                                                                0:\n                                                                                    discard 0\n                                                                                1:\n                                                                                    discard 0\n                                                                        0:\n                                                                            discard 0\n                                                                        1:\n                                                                            discard 0\n                                                                0:\n                                                                    parse_ok = 0\n                                                                    parameter_done = -1\n                                                                1:\n                                                                    parse_ok = 0\n                                                                    parameter_done = -1\n                                                        0:\n                                                            parse_ok = 0\n                                                            parameter_done = -1\n                                                        1:\n                                                            parse_ok = 0\n                                                            parameter_done = -1\n                                                0:\n                                                    parse_ok = 0\n                                                    parameter_done = -1\n                                                1:\n                                                    parse_ok = 0\n                                                    parameter_done = -1\n                                        0:\n                                            parse_ok = 0\n                                            parameter_done = -1\n                                        1:\n                                            parse_ok = 0\n                                            parameter_done = -1\n                                match cursor < token_count:\n                                    -1:\n                                        match token_value[cursor] == 12:\n                                            -1:\n                                                cursor += 1\n                                            0:\n                                                header_ok = 0\n                                            1:\n                                                header_ok = 0\n                                    0:\n                                        header_ok = 0\n                                    1:\n                                        header_ok = 0\n                                match header_ok:\n                                    -1:\n                                        match cursor < token_count:\n                                            -1:\n                                                function_return_type[function_count] = to_tryte(stage04_type_code(token_start[cursor], token_end[cursor]))\n                                                cursor += 1\n                                            0:\n                                                header_ok = 0\n                                            1:\n                                                header_ok = 0\n                                    0:\n                                        header_ok = 0\n                                    1:\n                                        header_ok = 0\n                                match header_ok:\n                                    -1:\n                                        match cursor < token_count:\n                                            -1:\n                                                match token_value[cursor] == 3:\n                                                    -1:\n                                                        cursor += 1\n                                                    0:\n                                                        header_ok = 0\n                                                    1:\n                                                        header_ok = 0\n                                            0:\n                                                header_ok = 0\n                                            1:\n                                                header_ok = 0\n                                    0:\n                                        discard 0\n                                    1:\n                                        discard 0\n                                function_param_count[function_count] = parameter_count - function_param_start[function_count]\n                                function_body_start[function_count] = cursor\n                                function_body_end[function_count] = token_count\n                                match foreign_flag == 1:\n                                    -1:\n                                        function_body_end[function_count] = cursor\n                                    0:\n                                        discard 0\n                                    1:\n                                        function_body_end[function_count] = cursor\n                                function_count += 1\n                                token_index = cursor\n                            0:\n                                parse_ok = 0\n                                token_index += 1\n                            1:\n                                parse_ok = 0\n                                token_index += 1\n                    0:\n                        parse_ok = 0\n                        token_index += 1\n                    1:\n                        parse_ok = 0\n                        token_index += 1\n            0:\n                token_index += 1\n            1:\n                token_index += 1\n\n    mut function_end_scan: i64 = 0\n    while function_end_scan < function_count:\n        match function_kind[function_end_scan] == 1:\n            -1:\n                mut boundary: i64 = function_body_start[function_end_scan]\n                while boundary < token_count:\n                    mut at_top: trit = 0\n                    match token_kind[boundary] == 1:\n                        -1:\n                            match stage04_word(token_start[boundary], token_end[boundary], 352, 2):\n                                -1:\n                                    match stage04_indent(token_start[boundary]) == 0:\n                                        -1:\n                                            at_top = -1\n                                        0:\n                                            discard 0\n                                        1:\n                                            at_top = -1\n                                0:\n                                    discard 0\n                                1:\n                                    discard 0\n                        0:\n                            discard 0\n                        1:\n                            discard 0\n                    match at_top:\n                        -1:\n                            function_body_end[function_end_scan] = boundary\n                            boundary = token_count\n                        0:\n                            boundary += 1\n                        1:\n                            boundary += 1\n                mut local_probe: i64 = function_body_start[function_end_scan]\n                while local_probe < function_body_end[function_end_scan]:\n                    mut line_end: i64 = local_probe\n                    while line_end < function_body_end[function_end_scan]:\n                        match token_kind[line_end] == 3:\n                            -1:\n                                line_end = function_body_end[function_end_scan]\n                            0:\n                                line_end += 1\n                            1:\n                                line_end += 1\n                    mut declaration_name: i64 = local_probe\n                    mut mutable_flag: trit = 0\n                    match token_kind[local_probe] == 1:\n                        -1:\n                            match stage04_word(token_start[local_probe], token_end[local_probe], 87, 3):\n                                -1:\n                                    mutable_flag = -1\n                                    declaration_name += 1\n                                0:\n                                    discard 0\n                                1:\n                                    discard 0\n                        0:\n                            declaration_name = line_end\n                        1:\n                            declaration_name = line_end\n                    match declaration_name < line_end:\n                        -1:\n                            match token_kind[declaration_name] == 1:\n                                -1:\n                                    match token_kind[declaration_name + 1] == 4:\n                                        -1:\n                                            match token_value[declaration_name + 1] == 3:\n                                                -1:\n                                                    match token_kind[declaration_name + 2] == 1:\n                                                        -1:\n                                                            match token_value[declaration_name + 3] == 5:\n                                                                -1:\n                                                                    match local_count < 64:\n                                                                        -1:\n                                                                            local_owner[local_count] = function_end_scan\n                                                                            local_name_start[local_count] = token_start[declaration_name]\n                                                                            local_name_length[local_count] = token_end[declaration_name] - token_start[declaration_name]\n                                                                            local_type[local_count] = to_tryte(stage04_type_code(token_start[declaration_name + 2], token_end[declaration_name + 2]))\n                                                                            local_mutable[local_count] = mutable_flag\n                                                                            local_storage[local_count] = local_count\n                                                                            local_declaration_token[local_count] = declaration_name\n                                                                            local_init_start[local_count] = declaration_name + 4\n                                                                            local_init_end[local_count] = line_end\n                                                                            local_count += 1\n                                                                        0:\n                                                                            parse_ok = 0\n                                                                        1:\n                                                                            parse_ok = 0\n                                                                0:\n                                                                    parse_ok = 0\n                                                                1:\n                                                                    parse_ok = 0\n                                                        0:\n                                                            parse_ok = 0\n                                                        1:\n                                                            parse_ok = 0\n                                        0:\n                                            discard 0\n                                        1:\n                                            discard 0\n                                0:\n                                    discard 0\n                                1:\n                                    discard 0\n                        0:\n                            discard 0\n                        1:\n                            discard 0\n                    match line_end < function_body_end[function_end_scan]:\n                        -1:\n                            local_probe = line_end + 1\n                        0:\n                            local_probe = function_body_end[function_end_scan]\n                        1:\n                            local_probe = function_body_end[function_end_scan]\n                0:\n                    discard 0\n                1:\n                    discard 0\n        0:\n            discard 0\n        1:\n            discard 0\n        function_end_scan += 1\n\n    mut value_function: i64 = 0\n    while value_function < function_count:\n        mut parameter_scan: i64 = 0\n        while parameter_scan < parameter_count:\n            match parameter_owner[parameter_scan] == value_function:\n                -1:\n                    parameter_value_id[parameter_scan] = value_count\n                    value_kind[value_count] = to_tryte(1)\n                    value_owner[value_count] = value_function\n                    value_type[value_count] = parameter_type[parameter_scan]\n                    value_anchor_start[value_count] = parameter_name_start[parameter_scan]\n                    value_anchor_length[value_count] = parameter_name_length[parameter_scan]\n                    value_mutable[value_count] = 0\n                    value_storage[value_count] = -1\n                    value_count += 1\n                0:\n                    discard 0\n                1:\n                    discard 0\n            parameter_scan += 1\n        mut local_scan: i64 = 0\n        while local_scan < local_count:\n            match local_owner[local_scan] == value_function:\n                -1:\n                    local_value_id[local_scan] = value_count\n                    value_kind[value_count] = to_tryte(2)\n                    value_owner[value_count] = value_function\n                    value_type[value_count] = local_type[local_scan]\n                    value_anchor_start[value_count] = local_name_start[local_scan]\n                    value_anchor_length[value_count] = local_name_length[local_scan]\n                    value_mutable[value_count] = local_mutable[local_scan]\n                    value_storage[value_count] = -1\n                    value_count += 1\n                0:\n                    discard 0\n                1:\n                    discard 0\n            local_scan += 1\n        value_function += 1\n\n    mut lower_function: i64 = 0\n    while lower_function < function_count:\n        match function_kind[lower_function] == 1:\n            -1:\n                function_instruction_start[lower_function] = instruction_count\n                mut reset_local: i64 = 0\n                while reset_local < local_count:\n                    match local_owner[reset_local] == lower_function:\n                        -1:\n                            local_current[reset_local] = -1\n                        0:\n                            discard 0\n                        1:\n                            discard 0\n                    reset_local += 1\n                mut statement: i64 = function_body_start[lower_function]\n                mut last_instruction: i64 = -1\n                while statement < function_body_end[lower_function]:\n                    match token_kind[statement] == 3:\n                        -1:\n                            statement += 1\n                        0:\n                            mut line_end: i64 = statement\n                            while line_end < function_body_end[lower_function]:\n                                match token_kind[line_end] == 3:\n                                    -1:\n                                        line_end = function_body_end[lower_function]\n                                    0:\n                                        line_end += 1\n                                    1:\n                                        line_end += 1\n                            mut mode: i64 = 0\n                            mut expression_start: i64 = -1\n                            mut target_local: i64 = -1\n                            match stage04_word(token_start[statement], token_end[statement], 342, 6):\n                                -1:\n                                    mode = 1\n                                    expression_start = statement + 1\n                                0:\n                                    match stage04_word(token_start[statement], token_end[statement], 87, 3):\n                                        -1:\n                                            mut name_token: i64 = statement + 1\n                                            match name_token + 3 < line_end:\n                                                -1:\n                                                    mode = 2\n                                                    expression_start = name_token + 4\n                                                    mut local_find: i64 = 0\n                                                    while local_find < local_count:\n                                                        match local_owner[local_find] == lower_function:\n                                                            -1:\n                                                                match local_declaration_token[local_find] == name_token:\n                                                                    -1:\n                                                                        target_local = local_find\n                                                                        local_find = local_count\n                                                                    0:\n                                                                        local_find += 1\n                                                                    1:\n                                                                        local_find += 1\n                                                            0:\n                                                                local_find += 1\n                                                            1:\n                                                                local_find += 1\n                                                0:\n                                                    discard 0\n                                                1:\n                                                    discard 0\n                                        0:\n                                            mut name_token: i64 = statement\n                                            match name_token + 1 < line_end:\n                                                -1:\n                                                    match token_value[name_token + 1] == 5:\n                                                        -1:\n                                                            mode = 3\n                                                            expression_start = name_token + 2\n                                                            mut local_find: i64 = local_count - 1\n                                                            while local_find >= 0:\n                                                                match local_owner[local_find] == lower_function:\n                                                                    -1:\n                                                                        match stage04_same_span(token_start[name_token], token_end[name_token] - token_start[name_token], local_name_start[local_find], local_name_length[local_find]):\n                                                                            -1:\n                                                                                target_local = local_find\n                                                                                local_find = -1\n                                                                            0:\n                                                                                local_find = local_find - 1\n                                                                            1:\n                                                                                local_find = local_find - 1\n                                                                    0:\n                                                                        local_find = local_find - 1\n                                                                    1:\n                                                                        local_find = local_find - 1\n                                                        0:\n                                                            discard 0\n                                                        1:\n                                                            discard 0\n                                                0:\n                                                    discard 0\n                                                1:\n                                                    discard 0\n                                1:\n                                    discard 0\n                            match mode > 0:\n                                -1:\n                                    mut rpn_count: i64 = 0\n                                    mut op_count: i64 = 0\n                                    mut expect_operand: trit = -1\n                                    mut expression_token: i64 = expression_start\n                                    while expression_token < line_end:\n                                        mut current_kind: i64 = to_i64(token_kind[expression_token])\n                                        mut current_code: i64 = token_value[expression_token]\n                                        match current_kind == 1:\n                                            -1:\n                                                match rpn_count < 64:\n                                                    -1:\n                                                        expression_rpn_kind[rpn_count] = to_tryte(1)\n                                                        expression_rpn_token[rpn_count] = expression_token\n                                                        rpn_count += 1\n                                                        expect_operand = 0\n                                                    0:\n                                                        parse_ok = 0\n                                                    1:\n                                                        parse_ok = 0\n                                            0:\n                                                match current_kind == 2:\n                                                    -1:\n                                                        match rpn_count < 64:\n                                                            -1:\n                                                                expression_rpn_kind[rpn_count] = to_tryte(1)\n                                                                expression_rpn_token[rpn_count] = expression_token\n                                                                rpn_count += 1\n                                                                expect_operand = 0\n                                                            0:\n                                                                parse_ok = 0\n                                                            1:\n                                                                parse_ok = 0\n                                                0:\n                                                    match current_kind == 4:\n                                                        -1:\n                                                            match current_code == 1:\n                                                                -1:\n                                                                    op_count += 1\n                                                                    expression_operators[op_count - 1] = 1\n                                                                    expect_operand = -1\n                                                                0:\n                                                                    match current_code == 2:\n                                                                        -1:\n                                                                            while op_count > 0:\n                                                                                match expression_operators[op_count - 1] == 1:\n                                                                                    -1:\n                                                                                        op_count = 0\n                                                                                    0:\n                                                                                        expression_rpn_kind[rpn_count] = to_tryte(2)\n                                                                                        expression_rpn_value[rpn_count] = expression_operators[op_count - 1]\n                                                                                        rpn_count += 1\n                                                                                        op_count = op_count - 1\n                                                                                    1:\n                                                                                        op_count = 0\n                                                                            expect_operand = 0\n                                                                        0:\n                                                                            mut op: i64 = current_code\n                                                                            match expect_operand:\n                                                                                -1:\n                                                                                    match op == 7:\n                                                                                        -1:\n                                                                                            op = 20\n                                                                                        0:\n                                                                                            match op == 20:\n                                                                                                -1:\n                                                                                                    op = 22\n                                                                                                0:\n                                                                                                    parse_ok = 0\n                                                                                                1:\n                                                                                                    parse_ok = 0\n                                                                                        1:\n                                                                                            parse_ok = 0\n                                                                                    0:\n                                                                                        parse_ok = 0\n                                                                                    1:\n                                                                                        parse_ok = 0\n                                                                                0:\n                                                                                    discard 0\n                                                                                1:\n                                                                                    discard 0\n                                                                            match stage04_precedence(op) > 0:\n                                                                                -1:\n                                                                                    mut reduce: trit = -1\n                                                                                    while reduce == -1:\n                                                                                        match op_count > 0:\n                                                                                            -1:\n                                                                                                match expression_operators[op_count - 1] == 1:\n                                                                                                    -1:\n                                                                                                        reduce = 0\n                                                                                                    0:\n                                                                                                        match stage04_precedence(expression_operators[op_count - 1]) >= stage04_precedence(op):\n                                                                                                            -1:\n                                                                                                                reduce = 0\n                                                                                                            0:\n                                                                                                                expression_rpn_kind[rpn_count] = to_tryte(2)\n                                                                                                                expression_rpn_value[rpn_count] = expression_operators[op_count - 1]\n                                                                                                                rpn_count += 1\n                                                                                                                op_count = op_count - 1\n                                                                                                            1:\n                                                                                                                expression_rpn_kind[rpn_count] = to_tryte(2)\n                                                                                                                expression_rpn_value[rpn_count] = expression_operators[op_count - 1]\n                                                                                                                rpn_count += 1\n                                                                                                                op_count = op_count - 1\n                                                                                            0:\n                                                                                                reduce = 0\n                                                                                            1:\n                                                                                                reduce = 0\n                                                                                    match op_count < 64:\n                                                                                        -1:\n                                                                                            expression_operators[op_count] = op\n                                                                                            op_count += 1\n                                                                                        0:\n                                                                                            parse_ok = 0\n                                                                                        1:\n                                                                                            parse_ok = 0\n                                                                                0:\n                                                                                    parse_ok = 0\n                                                                                1:\n                                                                                    parse_ok = 0\n                                                        0:\n                                                            parse_ok = 0\n                                                        1:\n                                                            parse_ok = 0\n                                            1:\n                                                parse_ok = 0\n                                        expression_token += 1\n                                    mut pop: i64 = op_count\n                                    while pop > 0:\n                                        match expression_operators[pop - 1] == 1:\n                                            -1:\n                                                parse_ok = 0\n                                            0:\n                                                expression_rpn_kind[rpn_count] = to_tryte(2)\n                                                expression_rpn_value[rpn_count] = expression_operators[pop - 1]\n                                                rpn_count += 1\n                                            1:\n                                                parse_ok = 0\n                                        pop = pop - 1\n                                    mut stack_count: i64 = 0\n                                    mut rpn_index: i64 = 0\n                                    while rpn_index < rpn_count:\n                                        match to_i64(expression_rpn_kind[rpn_index]) == 1:\n                                            -1:\n                                                mut source_token: i64 = expression_rpn_token[rpn_index]\n                                                mut resolved_value: i64 = -1\n                                                mut resolved_type: i64 = to_i64(function_return_type[lower_function])\n                                                match to_i64(token_kind[source_token]) == 2:\n                                                    -1:\n                                                        resolved_value = value_count\n                                                        value_kind[value_count] = to_tryte(3)\n                                                        value_owner[value_count] = lower_function\n                                                        value_type[value_count] = to_tryte(resolved_type)\n                                                        value_anchor_start[value_count] = token_start[source_token]\n                                                        value_anchor_length[value_count] = token_end[source_token] - token_start[source_token]\n                                                        value_mutable[value_count] = 0\n                                                        value_storage[value_count] = -1\n                                                        value_count += 1\n                                                        instruction_owner[instruction_count] = lower_function\n                                                        instruction_block[instruction_count] = 0\n                                                        instruction_ordinal[instruction_count] = instruction_count - function_instruction_start[lower_function]\n                                                        instruction_opcode[instruction_count] = to_tryte(1)\n                                                        instruction_results[instruction_count] = 1\n                                                        instruction_operands[instruction_count] = 0\n                                                        instruction_aux_a[instruction_count] = -1\n                                                        instruction_aux_b[instruction_count] = stage04_number(token_start[source_token], token_end[source_token])\n                                                        instruction_result_value[instruction_count] = resolved_value\n                                                        instruction_operand_a[instruction_count] = -1\n                                                        instruction_operand_b[instruction_count] = -1\n                                                        instruction_count += 1\n                                                    0:\n                                                        mut parameter_find: i64 = parameter_count - 1\n                                                        while parameter_find >= 0:\n                                                            match parameter_owner[parameter_find] == lower_function:\n                                                                -1:\n                                                                    match stage04_same_span(token_start[source_token], token_end[source_token] - token_start[source_token], parameter_name_start[parameter_find], parameter_name_length[parameter_find]):\n                                                                        -1:\n                                                                            resolved_value = parameter_value_id[parameter_find]\n                                                                            resolved_type = to_i64(parameter_type[parameter_find])\n                                                                            parameter_find = -1\n                                                                        0:\n                                                                            parameter_find = parameter_find - 1\n                                                                        1:\n                                                                            parameter_find = parameter_find - 1\n                                                                0:\n                                                                    parameter_find = parameter_find - 1\n                                                                1:\n                                                                    parameter_find = parameter_find - 1\n                                                        mut local_find: i64 = local_count - 1\n                                                        while local_find >= 0:\n                                                            match local_owner[local_find] == lower_function:\n                                                                -1:\n                                                                    match local_declaration_token[local_find] < source_token:\n                                                                        -1:\n                                                                            match stage04_same_span(token_start[source_token], token_end[source_token] - token_start[source_token], local_name_start[local_find], local_name_length[local_find]):\n                                                                                -1:\n                                                                                    match local_mutable[local_find] == -1:\n                                                                                        -1:\n                                                                                            mut zero_value: i64 = value_count\n                                                                                            value_kind[value_count] = to_tryte(3)\n                                                                                            value_owner[value_count] = lower_function\n                                                                                            value_type[value_count] = to_tryte(2)\n                                                                                            value_anchor_start[value_count] = token_start[source_token]\n                                                                                            value_anchor_length[value_count] = 0\n                                                                                            value_mutable[value_count] = 0\n                                                                                            value_storage[value_count] = -1\n                                                                                            value_count += 1\n                                                                                            instruction_owner[instruction_count] = lower_function\n                                                                                            instruction_block[instruction_count] = 0\n                                                                                            instruction_ordinal[instruction_count] = instruction_count - function_instruction_start[lower_function]\n                                                                                            instruction_opcode[instruction_count] = to_tryte(1)\n                                                                                            instruction_results[instruction_count] = 1\n                                                                                            instruction_operands[instruction_count] = 0\n                                                                                            instruction_aux_a[instruction_count] = -1\n                                                                                            instruction_aux_b[instruction_count] = 0\n                                                                                            instruction_result_value[instruction_count] = zero_value\n                                                                                            instruction_operand_a[instruction_count] = -1\n                                                                                            instruction_operand_b[instruction_count] = -1\n                                                                                            instruction_count += 1\n                                                                                            mut load_value: i64 = value_count\n                                                                                            value_kind[value_count] = to_tryte(4)\n                                                                                            value_owner[value_count] = lower_function\n                                                                                            value_type[value_count] = local_type[local_find]\n                                                                                            value_anchor_start[value_count] = token_start[source_token]\n                                                                                            value_anchor_length[value_count] = 0\n                                                                                            value_mutable[value_count] = 0\n                                                                                            value_storage[value_count] = -1\n                                                                                            value_count += 1\n                                                                                            instruction_owner[instruction_count] = lower_function\n                                                                                            instruction_block[instruction_count] = 0\n                                                                                            instruction_ordinal[instruction_count] = instruction_count - function_instruction_start[lower_function]\n                                                                                            instruction_opcode[instruction_count] = to_tryte(15)\n                                                                                            instruction_results[instruction_count] = 1\n                                                                                            instruction_operands[instruction_count] = 1\n                                                                                            instruction_aux_a[instruction_count] = local_storage[local_find]\n                                                                                            instruction_aux_b[instruction_count] = -1\n                                                                                            instruction_result_value[instruction_count] = load_value\n                                                                                            instruction_operand_a[instruction_count] = zero_value\n                                                                                            instruction_operand_b[instruction_count] = -1\n                                                                                            instruction_count += 1\n                                                                                            resolved_value = load_value\n                                                                                            resolved_type = to_i64(local_type[local_find])\n                                                                                        0:\n                                                                                            match local_current[local_find] >= 0:\n                                                                                                -1:\n                                                                                                    resolved_value = local_current[local_find]\n                                                                                                    resolved_type = to_i64(local_type[local_find])\n                                                                                                0:\n                                                                                                    parse_ok = 0\n                                                                                                1:\n                                                                                                    parse_ok = 0\n                                                                                        1:\n                                                                                            discard 0\n                                                                                    local_find = -1\n                                                                                0:\n                                                                                    local_find = local_find - 1\n                                                                                1:\n                                                                                    local_find = local_find - 1\n                                                                    0:\n                                                                        local_find = local_find - 1\n                                                                    1:\n                                                                        local_find = local_find - 1\n                                                        match resolved_value >= 0:\n                                                            -1:\n                                                                expression_values[stack_count] = resolved_value\n                                                                expression_types[stack_count] = to_tryte(resolved_type)\n                                                                stack_count += 1\n                                                            0:\n                                                                parse_ok = 0\n                                                            1:\n                                                                parse_ok = 0\n                                            0:\n                                                mut op: i64 = expression_rpn_value[rpn_index]\n                                                match op == 20:\n                                                    -1:\n                                                        match stack_count > 0:\n                                                            -1:\n                                                                mut operand: i64 = expression_values[stack_count - 1]\n                                                                mut result_value: i64 = value_count\n                                                                value_kind[result_value] = to_tryte(4)\n                                                                value_owner[result_value] = lower_function\n                                                                value_type[result_value] = expression_types[stack_count - 1]\n                                                                value_anchor_start[result_value] = token_start[expression_start]\n                                                                value_anchor_length[result_value] = 0\n                                                                value_mutable[result_value] = 0\n                                                                value_storage[result_value] = -1\n                                                                value_count += 1\n                                                                instruction_owner[instruction_count] = lower_function\n                                                                instruction_block[instruction_count] = 0\n                                                                instruction_ordinal[instruction_count] = instruction_count - function_instruction_start[lower_function]\n                                                                instruction_opcode[instruction_count] = to_tryte(4)\n                                                                instruction_results[instruction_count] = 1\n                                                                instruction_operands[instruction_count] = 1\n                                                                instruction_aux_a[instruction_count] = -1\n                                                                instruction_aux_b[instruction_count] = -1\n                                                                instruction_result_value[instruction_count] = result_value\n                                                                instruction_operand_a[instruction_count] = operand\n                                                                instruction_operand_b[instruction_count] = -1\n                                                                instruction_count += 1\n                                                                expression_values[stack_count - 1] = result_value\n                                                            0:\n                                                                parse_ok = 0\n                                                            1:\n                                                                parse_ok = 0\n                                                    0:\n                                                        match op == 22:\n                                                            -1:\n                                                                match stack_count > 0:\n                                                                    -1:\n                                                                        mut operand: i64 = expression_values[stack_count - 1]\n                                                                        mut result_value: i64 = value_count\n                                                                        value_kind[result_value] = to_tryte(4)\n                                                                        value_owner[result_value] = lower_function\n                                                                        value_type[result_value] = expression_types[stack_count - 1]\n                                                                        value_anchor_start[result_value] = token_start[expression_start]\n                                                                        value_anchor_length[result_value] = 0\n                                                                        value_mutable[result_value] = 0\n                                                                        value_storage[result_value] = -1\n                                                                        value_count += 1\n                                                                        instruction_owner[instruction_count] = lower_function\n                                                                        instruction_block[instruction_count] = 0\n                                                                        instruction_ordinal[instruction_count] = instruction_count - function_instruction_start[lower_function]\n                                                                        instruction_opcode[instruction_count] = to_tryte(4)\n                                                                        instruction_results[instruction_count] = 1\n                                                                        instruction_operands[instruction_count] = 1\n                                                                        instruction_aux_a[instruction_count] = -1\n                                                                        instruction_aux_b[instruction_count] = -1\n                                                                        instruction_result_value[instruction_count] = result_value\n                                                                        instruction_operand_a[instruction_count] = operand\n                                                                        instruction_operand_b[instruction_count] = -1\n                                                                        instruction_count += 1\n                                                                        expression_values[stack_count - 1] = result_value\n                                                                    0:\n                                                                        parse_ok = 0\n                                                                    1:\n                                                                        parse_ok = 0\n                                                            0:\n                                                                match stack_count >= 2:\n                                                                    -1:\n                                                                        mut right_value: i64 = expression_values[stack_count - 1]\n                                                                        mut left_value: i64 = expression_values[stack_count - 2]\n                                                                        mut relation_aux: i64 = -1\n                                                                        mut opcode: i64 = 0\n                                                                        match op == 5:\n                                                                            -1:\n                                                                                opcode = 5\n                                                                            0:\n                                                                                match op == 7:\n                                                                                    -1:\n                                                                                        opcode = 6\n                                                                                    0:\n                                                                                        match op == 18:\n                                                                                            -1:\n                                                                                                opcode = 11\n                                                                                            0:\n                                                                                                match op == 19:\n                                                                                                    -1:\n                                                                                                        opcode = 12\n                                                                                                    0:\n                                                                                                        match op == 15:\n                                                                                                            -1:\n                                                                                                                opcode = 13\n                                                                                                            0:\n                                                                                                                match op == 13:\n                                                                                                                    -1:\n                                                                                                                        opcode = 9\n                                                                                                                        relation_aux = 0\n                                                                                                                    0:\n                                                                                                                        match op == 21:\n                                                                                                                            -1:\n                                                                                                                                opcode = 9\n                                                                                                                                relation_aux = 1\n                                                                                                                            0:\n                                                                                                                                match op == 16:\n                                                                                                                                    -1:\n                                                                                                                                        opcode = 9\n                                                                                                                                        relation_aux = 2\n                                                                                                                                    0:\n                                                                                                                                        match op == 23:\n                                                                                                                                            -1:\n                                                                                                                                                opcode = 9\n                                                                                                                                                relation_aux = 3\n                                                                                                                                            0:\n                                                                                                                                                match op == 17:\n                                                                                                                                                    -1:\n                                                                                                                                                        opcode = 9\n                                                                                                                                                        relation_aux = 4\n                                                                                                                                                    0:\n                                                                                                                                                        match op == 24:\n                                                                                                                                                            -1:\n                                                                                                                                                                opcode = 9\n                                                                                                                                                                relation_aux = 5\n                                                                                                                                                            0:\n                                                                                                                                                                parse_ok = 0\n                                                                                                                                                            1:\n                                                                                                                                                                parse_ok = 0\n                                                                                                                                                    1:\n                                                                                                                                                        opcode = 9\n                                                                                                                                                        relation_aux = 4\n                                                                                                                                            1:\n                                                                                                                                                opcode = 9\n                                                                                                                                1:\n                                                                                                                                    opcode = 9\n                                                                                                                            1:\n                                                                                                                                opcode = 13\n                                                                                                                1:\n                                                                                                                    opcode = 13\n                                                                                                        1:\n                                                                                                            opcode = 12\n                                                                                            1:\n                                                                                                opcode = 11\n                                                                                1:\n                                                                                    opcode = 6\n                                                                        match opcode > 0:\n                                                                            -1:\n                                                                                expression_values[stack_count - 2] = value_count\n                                                                                stack_count = stack_count - 1\n                                                                                value_kind[value_count] = to_tryte(4)\n                                                                                value_owner[value_count] = lower_function\n                                                                                match relation_aux >= 0:\n                                                                                    -1:\n                                                                                        value_type[value_count] = to_tryte(1)\n                                                                                    0:\n                                                                                        value_type[value_count] = function_return_type[lower_function]\n                                                                                    1:\n                                                                                        value_type[value_count] = function_return_type[lower_function]\n                                                                                value_anchor_start[value_count] = token_start[expression_start]\n                                                                                value_anchor_length[value_count] = 0\n                                                                                value_mutable[value_count] = 0\n                                                                                value_storage[value_count] = -1\n                                                                                value_count += 1\n                                                                                instruction_owner[instruction_count] = lower_function\n                                                                                instruction_block[instruction_count] = 0\n                                                                                instruction_ordinal[instruction_count] = instruction_count - function_instruction_start[lower_function]\n                                                                                instruction_opcode[instruction_count] = to_tryte(opcode)\n                                                                                instruction_results[instruction_count] = 1\n                                                                                instruction_operands[instruction_count] = 2\n                                                                                instruction_aux_a[instruction_count] = -1\n                                                                                instruction_aux_b[instruction_count] = relation_aux\n                                                                                instruction_result_value[instruction_count] = expression_values[stack_count - 1]\n                                                                                instruction_operand_a[instruction_count] = left_value\n                                                                                instruction_operand_b[instruction_count] = right_value\n                                                                                instruction_count += 1\n                                                                            0:\n                                                                                parse_ok = 0\n                                                                            1:\n                                                                                parse_ok = 0\n                                                                    0:\n                                                                        parse_ok = 0\n                                                                    1:\n                                                                        parse_ok = 0\n                                                    1:\n                                                        parse_ok = 0\n                                                rpn_index += 1\n                                    match stack_count == 1:\n                                        -1:\n                                            mut expression_result: i64 = expression_values[0]\n                                            match mode == 1:\n                                                -1:\n                                                    instruction_owner[instruction_count] = lower_function\n                                                    instruction_block[instruction_count] = 0\n                                                    instruction_ordinal[instruction_count] = instruction_count - function_instruction_start[lower_function]\n                                                    instruction_opcode[instruction_count] = to_tryte(23)\n                                                    instruction_results[instruction_count] = 0\n                                                    instruction_operands[instruction_count] = 1\n                                                    instruction_aux_a[instruction_count] = -1\n                                                    instruction_aux_b[instruction_count] = -1\n                                                    instruction_result_value[instruction_count] = -1\n                                                    instruction_operand_a[instruction_count] = expression_result\n                                                    instruction_operand_b[instruction_count] = -1\n                                                    terminator_instruction[lower_function] = instruction_count\n                                                    terminator_return_value[lower_function] = expression_result\n                                                    last_instruction = instruction_count\n                                                    instruction_count += 1\n                                                0:\n                                                    match mode == 2:\n                                                        -1:\n                                                            match target_local >= 0:\n                                                                -1:\n                                                                    match local_mutable[target_local] == 0:\n                                                                        -1:\n                                                                            local_current[target_local] = value_count\n                                                                            value_kind[value_count] = to_tryte(4)\n                                                                            value_owner[value_count] = lower_function\n                                                                            value_type[value_count] = local_type[target_local]\n                                                                            value_anchor_start[value_count] = local_name_start[target_local]\n                                                                            value_anchor_length[value_count] = 0\n                                                                            value_mutable[value_count] = 0\n                                                                            value_storage[value_count] = -1\n                                                                            value_count += 1\n                                                                            instruction_owner[instruction_count] = lower_function\n                                                                            instruction_block[instruction_count] = 0\n                                                                            instruction_ordinal[instruction_count] = instruction_count - function_instruction_start[lower_function]\n                                                                            instruction_opcode[instruction_count] = to_tryte(3)\n                                                                            instruction_results[instruction_count] = 1\n                                                                            instruction_operands[instruction_count] = 1\n                                                                            instruction_aux_a[instruction_count] = -1\n                                                                            instruction_aux_b[instruction_count] = -1\n                                                                            instruction_result_value[instruction_count] = local_current[target_local]\n                                                                            instruction_operand_a[instruction_count] = expression_result\n                                                                            instruction_operand_b[instruction_count] = -1\n                                                                            instruction_count += 1\n                                                                        0:\n                                                                            parse_ok = 0\n                                                                        1:\n                                                                            parse_ok = 0\n                                                                    0:\n                                                                        match local_mutable[target_local] == -1:\n                                                                            -1:\n                                                                                discard 0\n                                                                            0:\n                                                                                parse_ok = 0\n                                                                            1:\n                                                                                parse_ok = 0\n                                                                0:\n                                                                    parse_ok = 0\n                                                                1:\n                                                                    parse_ok = 0\n                                                        0:\n                                                            parse_ok = 0\n                                                        1:\n                                                            parse_ok = 0\n                                                0:\n                                                    match mode == 3:\n                                                        -1:\n                                                            match target_local >= 0:\n                                                                -1:\n                                                                    match local_mutable[target_local] == -1:\n                                                                        -1:\n                                                                            mut zero_value: i64 = value_count\n                                                                            value_kind[value_count] = to_tryte(3)\n                                                                            value_owner[value_count] = lower_function\n                                                                            value_type[value_count] = to_tryte(2)\n                                                                            value_anchor_start[value_count] = local_name_start[target_local]\n                                                                            value_anchor_length[value_count] = 0\n                                                                            value_mutable[value_count] = 0\n                                                                            value_storage[value_count] = -1\n                                                                            value_count += 1\n                                                                            instruction_owner[instruction_count] = lower_function\n                                                                            instruction_block[instruction_count] = 0\n                                                                            instruction_ordinal[instruction_count] = instruction_count - function_instruction_start[lower_function]\n                                                                            instruction_opcode[instruction_count] = to_tryte(1)\n                                                                            instruction_results[instruction_count] = 1\n                                                                            instruction_operands[instruction_count] = 0\n                                                                            instruction_aux_a[instruction_count] = -1\n                                                                            instruction_aux_b[instruction_count] = 0\n                                                                            instruction_result_value[instruction_count] = zero_value\n                                                                            instruction_operand_a[instruction_count] = -1\n                                                                            instruction_operand_b[instruction_count] = -1\n                                                                            instruction_count += 1\n                                                                            instruction_owner[instruction_count] = lower_function\n                                                                            instruction_block[instruction_count] = 0\n                                                                            instruction_ordinal[instruction_count] = instruction_count - function_instruction_start[lower_function]\n                                                                            instruction_opcode[instruction_count] = to_tryte(16)\n                                                                            instruction_results[instruction_count] = 0\n                                                                            instruction_operands[instruction_count] = 2\n                                                                            instruction_aux_a[instruction_count] = local_storage[target_local]\n                                                                            instruction_aux_b[instruction_count] = -1\n                                                                            instruction_result_value[instruction_count] = -1\n                                                                            instruction_operand_a[instruction_count] = zero_value\n                                                                            instruction_operand_b[instruction_count] = expression_result\n                                                                            instruction_count += 1\n                                                                        0:\n                                                                            parse_ok = 0\n                                                                        1:\n                                                                            parse_ok = 0\n                                                                0:\n                                                                    parse_ok = 0\n                                                                1:\n                                                                    parse_ok = 0\n                                                        0:\n                                                            parse_ok = 0\n                                                        1:\n                                                            parse_ok = 0\n                                                0:\n                                                    parse_ok = 0\n                                                1:\n                                                    parse_ok = 0\n                                        0:\n                                            parse_ok = 0\n                                        1:\n                                            parse_ok = 0\n                                    match line_end < function_body_end[lower_function]:\n                                        -1:\n                                            statement = line_end + 1\n                                        0:\n                                            statement = function_body_end[lower_function]\n                                        1:\n                                            statement = function_body_end[lower_function]\n                        0:\n                            parse_ok = 0\n                            statement = line_end\n                        1:\n                            parse_ok = 0\n                            statement = line_end\n                function_instruction_count[lower_function] = instruction_count - function_instruction_start[lower_function]\n                match last_instruction >= 0:\n                    -1:\n                        discard 0\n                    0:\n                        parse_ok = 0\n                    1:\n                        parse_ok = 0\n            0:\n                discard 0\n            1:\n                discard 0\n        lower_function += 1\n\n    discard semantic_v2_header()\n    mut output_function: i64 = 0\n    while output_function < function_count:\n        discard semantic_v2_function(output_function, to_i64(function_kind[output_function]), function_name_start[output_function], function_name_length[output_function], function_param_count[output_function], 1)\n        output_function += 1\n    mut output_block: i64 = 0\n    while output_block < function_count:\n        match function_kind[output_block] == 1:\n            -1:\n                discard semantic_v2_block(output_block, 0, 0, function_instruction_count[output_block], terminator_instruction[output_block])\n            0:\n                discard 0\n            1:\n                discard 0\n        output_block += 1\n    mut output_value: i64 = 0\n    while output_value < value_count:\n        discard semantic_v2_value(output_value, value_owner[output_value], to_i64(value_kind[output_value]), to_i64(value_type[output_value]), value_anchor_start[output_value], value_anchor_length[output_value], to_i64(value_mutable[output_value]), value_storage[output_value])\n        output_value += 1\n    mut output_memory: i64 = 0\n    while output_memory < local_count:\n        match local_mutable[output_memory] == -1:\n            -1:\n                discard semantic_v2_memory(local_owner[output_memory], local_storage[output_memory], to_i64(local_type[output_memory]), 1, 1)\n            0:\n                discard 0\n            1:\n                discard 0\n        output_memory += 1\n    mut output_instruction: i64 = 0\n    while output_instruction < instruction_count:\n        discard semantic_v2_instruction(output_instruction, instruction_owner[output_instruction], instruction_block[output_instruction], instruction_ordinal[output_instruction], to_i64(instruction_opcode[output_instruction]), instruction_results[output_instruction], instruction_operands[output_instruction], instruction_aux_a[output_instruction], instruction_aux_b[output_instruction])\n        match instruction_operands[output_instruction] > 0:\n            -1:\n                discard semantic_v2_operand(output_instruction, 0, instruction_operand_a[output_instruction])\n            0:\n                discard 0\n            1:\n                discard 0\n        match instruction_operands[output_instruction] > 1:\n            -1:\n                discard semantic_v2_operand(output_instruction, 1, instruction_operand_b[output_instruction])\n            0:\n                discard 0\n            1:\n                discard 0\n        match instruction_results[output_instruction] > 0:\n            -1:\n                discard semantic_v2_result(output_instruction, 0, instruction_result_value[output_instruction])\n            0:\n                discard 0\n            1:\n                discard 0\n        output_instruction += 1\n    mut output_terminator: i64 = 0\n    while output_terminator < function_count:\n        match function_kind[output_terminator] == 1:\n            -1:\n                discard semantic_v2_terminator(terminator_instruction[output_terminator], 1, -1, -1, -1, -1, terminator_return_value[output_terminator])\n            0:\n                discard 0\n            1:\n                discard 0\n        output_terminator += 1\n    discard semantic_v2_complete(3)\n    return 0\n"

STAGE04_OPERATOR_HELPERS = """
fn stage04_binary_opcode(op: i64) -> i64:
    mut opcode: i64 = 0
    match op == 5:
        -1:
            opcode = 5
        0:
            discard 0
        1:
            discard 0
    match op == 7:
        -1:
            opcode = 6
        0:
            discard 0
        1:
            discard 0
    match op == 18:
        -1:
            opcode = 11
        0:
            discard 0
        1:
            discard 0
    match op == 19:
        -1:
            opcode = 12
        0:
            discard 0
        1:
            discard 0
    match op == 15:
        -1:
            opcode = 13
        0:
            discard 0
        1:
            discard 0
    match op == 13:
        -1:
            opcode = 9
        0:
            discard 0
        1:
            discard 0
    match op == 21:
        -1:
            opcode = 9
        0:
            discard 0
        1:
            discard 0
    match op == 16:
        -1:
            opcode = 9
        0:
            discard 0
        1:
            discard 0
    match op == 23:
        -1:
            opcode = 9
        0:
            discard 0
        1:
            discard 0
    match op == 17:
        -1:
            opcode = 9
        0:
            discard 0
        1:
            discard 0
    match op == 24:
        -1:
            opcode = 9
        0:
            discard 0
        1:
            discard 0
    return opcode

fn stage04_relation_aux(op: i64) -> i64:
    mut relation: i64 = -1
    match op == 13:
        -1:
            relation = 0
        0:
            discard 0
        1:
            discard 0
    match op == 21:
        -1:
            relation = 1
        0:
            discard 0
        1:
            discard 0
    match op == 16:
        -1:
            relation = 2
        0:
            discard 0
        1:
            discard 0
    match op == 23:
        -1:
            relation = 3
        0:
            discard 0
        1:
            discard 0
    match op == 17:
        -1:
            relation = 4
        0:
            discard 0
        1:
            discard 0
    match op == 24:
        -1:
            relation = 5
        0:
            discard 0
        1:
            discard 0
    return relation
""".strip()


def _zeros(size: int, value: str = "0") -> str:
    return ", ".join([value] * size)


def _cast_stage04_array_indices(source: str) -> str:
    array_names = (
        "token_kind", "token_start", "token_end", "token_value",
        "function_name_start", "function_name_length", "function_kind",
        "function_param_start", "function_param_count", "function_return_type",
        "function_body_start", "function_body_end", "parameter_owner",
        "parameter_name_start", "parameter_name_length", "parameter_type",
        "parameter_value_id", "local_owner", "local_name_start",
        "local_name_length", "local_type", "local_mutable", "local_storage",
        "local_declaration_token", "local_init_start", "local_init_end",
        "local_indent",
        "local_value_id", "value_kind", "value_owner", "value_type",
        "value_anchor_start", "value_anchor_length", "value_mutable",
        "value_storage", "instruction_owner", "instruction_block",
        "instruction_ordinal", "instruction_opcode", "instruction_results",
        "instruction_operands", "instruction_aux_a", "instruction_aux_b",
        "instruction_result_value", "instruction_operand_a", "instruction_operand_b",
        "terminator_instruction", "terminator_return_value",
        "function_instruction_start", "function_instruction_count", "local_current",
        "expression_values", "expression_types", "expression_rpn_kind",
        "expression_rpn_value", "expression_rpn_token", "expression_operators",
    )
    changed = True
    while changed:
        changed = False
        for name in array_names:
            marker = name + "["
            cursor = 0
            while True:
                start = source.find(marker, cursor)
                if start < 0:
                    break
                index_start = start + len(marker)
                depth = 1
                end = index_start
                while end < len(source) and depth:
                    if source[end] == "[":
                        depth += 1
                    elif source[end] == "]":
                        depth -= 1
                    end += 1
                if depth:
                    break
                index_expression = source[index_start : end - 1]
                stripped_index = index_expression.strip()
                is_integer_literal = stripped_index.lstrip("-").isdigit()
                if not index_expression.startswith("to_tryte(") and not is_integer_literal:
                    source = source[:index_start] + "to_tryte(" + index_expression + ")" + source[end - 1 :]
                    changed = True
                    cursor = index_start + len("to_tryte(") + len(index_expression) + 1
                else:
                    cursor = end
    return source


def _repair_stage04_indentation(source: str) -> str:
    lines = source.splitlines()
    value_thirty_five = next(
        index
        for index, line in enumerate(lines)
        if line.strip() == "match value == 35:"
    )
    value_base = len(lines[value_thirty_five]) - len(lines[value_thirty_five].lstrip())
    value_block_start = next(
        index
        for index in range(value_thirty_five + 1, len(lines))
        if lines[index].strip() == "0:"
        and len(lines[index]) - len(lines[index].lstrip()) == value_base
    )
    value_block_end = next(
        index
        for index in range(value_block_start + 1, len(lines))
        if lines[index].strip() == "0:"
        and len(lines[index]) - len(lines[index].lstrip()) == value_base - 8
    )
    for index in range(value_block_start, value_block_end):
        lines[index] = "    " + lines[index]
    value_one_twenty_four = next(
        index
        for index, line in enumerate(lines)
        if line.strip() == "match value == 124:"
    )
    value_one_twenty_four_base = len(lines[value_one_twenty_four]) - len(lines[value_one_twenty_four].lstrip())
    value_one_twenty_four_branch = next(
        index
        for index in range(value_one_twenty_four + 1, len(lines))
        if lines[index].strip() == "1:"
        and len(lines[index]) - len(lines[index].lstrip()) == value_one_twenty_four_base
    )
    for index in range(value_one_twenty_four_branch, value_one_twenty_four_branch + 2):
        lines[index] = "    " + lines[index]
    lines[value_block_start] = " " * (value_base + 4) + "1:"
    del lines[value_block_start + 2 : value_block_start + 4]

    kind_nine = next(
        index
        for index, line in enumerate(lines)
        if line.strip() == "match kind == 9:"
    )
    kind_base = len(lines[kind_nine]) - len(lines[kind_nine].lstrip())
    kind_block_start = next(
        index
        for index in range(kind_nine + 1, len(lines))
        if lines[index].strip() == "0:"
        and len(lines[index]) - len(lines[index].lstrip()) == kind_base
    )
    kind_block_end = next(
        index
        for index in range(kind_block_start + 1, len(lines))
        if lines[index].strip() == "match next_cursor > scan_cursor:"
        and len(lines[index]) - len(lines[index].lstrip()) == kind_base
    )
    for index in range(kind_block_start, kind_block_end):
        lines[index] = "    " + lines[index]

    name_token_kind = next(
        index
        for index, line in enumerate(lines)
        if line.strip() == "match token_kind[name_index] == 1:"
    )
    name_base = len(lines[name_token_kind]) - len(lines[name_token_kind].lstrip())
    name_block_start = next(
        index
        for index in range(name_token_kind + 1, len(lines))
        if lines[index].strip() == "0:"
        and len(lines[index]) - len(lines[index].lstrip()) == name_base
    )
    name_block_end = next(
        index
        for index in range(name_block_start + 1, len(lines))
        if lines[index].strip() == "0:"
        and len(lines[index]) - len(lines[index].lstrip()) == name_base - 8
    )
    del lines[name_block_start : name_block_start + 4]
    name_block_end -= 4
    name_tail_end = next(
        index
        for index in range(name_block_end, len(lines))
        if lines[index].strip() == "match header_ok:"
        and len(lines[index]) - len(lines[index].lstrip()) == name_base - 8
    )
    for index in range(name_block_end, name_tail_end):
        lines[index] = "    " + lines[index]

    function_end_match = next(
        index
        for index, line in enumerate(lines)
        if line.strip() == "match function_kind[function_end_scan] == 1:"
    )
    function_end_base = len(lines[function_end_match]) - len(lines[function_end_match].lstrip())
    function_end_increment = next(
        index
        for index in range(function_end_match + 1, len(lines))
        if lines[index].strip() == "function_end_scan += 1"
    )
    duplicate_branch = next(
        index
        for index in range(function_end_match + 1, function_end_increment)
        if lines[index].strip() == "0:"
        and len(lines[index]) - len(lines[index].lstrip()) == function_end_base + 8
    )
    del lines[duplicate_branch : duplicate_branch + 4]
    function_end_increment -= 4
    outer_branch = next(
        index
        for index in range(function_end_match + 1, function_end_increment)
        if lines[index].strip() == "0:"
        and len(lines[index]) - len(lines[index].lstrip()) == function_end_base
    )
    for index in range(outer_branch, outer_branch + 4):
        lines[index] = "    " + lines[index]

    unary_operator_match = next(
        index
        for index, line in enumerate(lines)
        if line.strip() == "match op == 7:"
        and any("match expect_operand:" in lines[probe] for probe in range(max(0, index - 8), index))
    )
    unary_base = len(lines[unary_operator_match]) - len(lines[unary_operator_match].lstrip())
    unary_block_start = next(
        index
        for index in range(unary_operator_match + 1, len(lines))
        if lines[index].strip() == "0:"
        and len(lines[index]) - len(lines[index].lstrip()) == unary_base
    )
    unary_block_end = next(
        index
        for index in range(unary_block_start + 1, len(lines))
        if lines[index].strip() == "0:"
        and len(lines[index]) - len(lines[index].lstrip()) == unary_base - 4
    )
    for index in range(unary_block_start, unary_block_end):
        lines[index] = "    " + lines[index]
    unary_direct_one = next(
        index
        for index in range(unary_operator_match + 1, unary_block_end)
        if lines[index].strip() == "1:"
        and len(lines[index]) - len(lines[index].lstrip()) == unary_base + 4
    )
    duplicate_unary_branch = next(
        index
        for index in range(unary_direct_one + 1, unary_block_end)
        if lines[index].strip() == "0:"
        and len(lines[index]) - len(lines[index].lstrip()) == unary_base + 4
    )
    del lines[duplicate_unary_branch : duplicate_unary_branch + 4]

    local_declaration_match = next(
        index
        for index, line in enumerate(lines)
        if line.strip() == "match local_declaration_token[local_find] < source_token:"
    )
    local_declaration_base = len(lines[local_declaration_match]) - len(lines[local_declaration_match].lstrip())
    local_declaration_tail = next(
        index
        for index in range(local_declaration_match + 1, len(lines))
        if lines[index].strip() == "match resolved_value >= 0:"
    )
    local_declaration_branch = next(
        index
        for index in range(local_declaration_match + 1, local_declaration_tail)
        if lines[index].strip() == "0:"
        and len(lines[index]) - len(lines[index].lstrip()) == local_declaration_base
    )
    for index in range(local_declaration_branch, local_declaration_branch + 4):
        lines[index] = "    " + lines[index]
    local_owner_base = local_declaration_base - 8
    local_owner_branch = local_declaration_tail
    local_owner_body = local_owner_branch + 1
    lines[local_owner_branch:local_owner_branch] = [
        "    " * ((local_owner_base + 4) // 4) + "0:",
        "    " * ((local_owner_base + 8) // 4) + "local_find = local_find - 1",
        "    " * ((local_owner_base + 4) // 4) + "1:",
        "    " * ((local_owner_base + 8) // 4) + "local_find = local_find - 1",
    ]

    parameter_token_kind = [
        index
        for index, line in enumerate(lines)
        if line.strip() == "match token_kind[cursor] == 4:"
        and any("match parameter_count < 64:" in lines[probe] for probe in range(index, min(len(lines), index + 80)))
    ][-1]
    parameter_token_base = len(lines[parameter_token_kind]) - len(lines[parameter_token_kind].lstrip())
    parameter_return_match = next(
        index
        for index in range(parameter_token_kind + 1, len(lines))
        if lines[index].strip() == "match cursor < token_count:"
        and len(lines[index]) - len(lines[index].lstrip()) == parameter_token_base - 12
    )
    parameter_token_branch = [
        index
        for index in range(parameter_token_kind + 1, parameter_return_match)
        if lines[index].strip() == "0:"
        and len(lines[index]) - len(lines[index].lstrip()) == parameter_token_base + 4
    ][-1]
    lines[parameter_token_branch] = " " * (parameter_token_base + 4) + "1:"
    del lines[parameter_token_branch + 2 : parameter_token_branch + 4]

    assignment_mutable_match = next(
        index
        for index, line in enumerate(lines)
        if line.strip() == "match local_mutable[target_local] == 0:"
    )
    assignment_mutable_base = len(lines[assignment_mutable_match]) - len(lines[assignment_mutable_match].lstrip())
    assignment_mutable_start = next(
        index
        for index in range(assignment_mutable_match + 1, len(lines))
        if lines[index].strip() == "0:"
        and len(lines[index]) - len(lines[index].lstrip()) == assignment_mutable_base
    )
    assignment_mutable_end = next(
        index
        for index in range(assignment_mutable_start + 1, len(lines))
        if lines[index].strip() == "0:"
        and len(lines[index]) - len(lines[index].lstrip()) == assignment_mutable_base - 4
    )
    for index in range(assignment_mutable_start, assignment_mutable_end):
        lines[index] = lines[index][4:]

    target_local_match = next(
        index
        for index, line in enumerate(lines)
        if line.strip() == "match target_local >= 0:"
    )
    target_local_base = len(lines[target_local_match]) - len(lines[target_local_match].lstrip())
    target_local_zero_branches = [
        index
        for index in range(target_local_match + 1, len(lines))
        if lines[index].strip() == "0:"
        and len(lines[index]) - len(lines[index].lstrip()) == target_local_base + 4
    ]
    if len(target_local_zero_branches) > 1:
        duplicate_target_local_zero = target_local_zero_branches[1]
        duplicate_target_local_end = next(
            index
            for index in range(duplicate_target_local_zero + 1, len(lines))
            if lines[index].strip() in {"-1:", "0:", "1:"}
            and len(lines[index]) - len(lines[index].lstrip()) == target_local_base + 4
        )
        del lines[duplicate_target_local_zero:duplicate_target_local_end]

    declaration_value_match = next(
        index
        for index, line in enumerate(lines)
        if line.strip() == "match token_value[declaration_name + 1] == 3:"
    )
    declaration_value_base = len(lines[declaration_value_match]) - len(lines[declaration_value_match].lstrip())
    declaration_value_branch = next(
        index
        for index in range(declaration_value_match + 1, len(lines))
        if lines[index].strip() == "0:"
        and len(lines[index]) - len(lines[index].lstrip()) == declaration_value_base - 4
    )
    declaration_value_tail = next(
        index
        for index in range(declaration_value_branch + 1, len(lines))
        if lines[index].strip() == "match line_end < function_body_end[function_end_scan]:"
    )
    for index in range(declaration_value_branch, declaration_value_tail):
        lines[index] = "        " + lines[index]
    declaration_tail_end = next(
        index
        for index in range(declaration_value_tail + 1, len(lines))
        if lines[index].strip() == "0:"
        and len(lines[index]) - len(lines[index].lstrip()) == declaration_value_base - 32
    )
    for index in range(declaration_value_tail, declaration_tail_end):
        lines[index] = "        " + lines[index]
    declaration_name_base = declaration_value_base - 24
    lines[declaration_tail_end:declaration_tail_end] = [
        " " * (declaration_name_base + 4) + "0:",
        " " * (declaration_name_base + 8) + "discard 0",
        " " * (declaration_name_base + 4) + "1:",
        " " * (declaration_name_base + 8) + "discard 0",
    ]

    header_checks = [
        index
        for index, line in enumerate(lines)
        if line.strip() == "match header_ok:"
    ]
    first_header_check = header_checks[0]
    second_header_check = header_checks[1]
    header_base = len(lines[first_header_check]) - len(lines[first_header_check].lstrip())
    lines[second_header_check:second_header_check] = [
        " " * (header_base + 4) + "0:",
        " " * (header_base + 8) + "header_ok = 0",
        " " * (header_base + 4) + "1:",
        " " * (header_base + 8) + "header_ok = 0",
    ]

    mode_one_match = next(
        index
        for index, line in enumerate(lines)
        if line.strip() == "match mode == 1:"
    )
    mode_one_base = len(lines[mode_one_match]) - len(lines[mode_one_match].lstrip())
    mode_three_match = next(
        index
        for index in range(mode_one_match + 1, len(lines))
        if lines[index].strip() == "match mode == 3:"
    )
    mode_three_parent_branch = next(
        index
        for index in range(mode_three_match - 1, mode_one_match, -1)
        if lines[index].strip() == "0:"
        and len(lines[index]) - len(lines[index].lstrip()) == mode_one_base + 4
    )
    lines[mode_three_parent_branch] = " " * (mode_one_base + 4) + "1:"
    duplicate_mode_one_branch = next(
        index
        for index in range(mode_three_match + 1, len(lines))
        if lines[index].strip() == "0:"
        and len(lines[index]) - len(lines[index].lstrip()) == mode_one_base + 4
    )
    del lines[duplicate_mode_one_branch : duplicate_mode_one_branch + 4]

    mut_word_match = next(
        index
        for index, line in enumerate(lines)
        if line.strip() == "match stage04_word(token_start[statement], token_end[statement], 87, 3):"
    )
    mut_word_base = len(lines[mut_word_match]) - len(lines[mut_word_match].lstrip())
    mut_word_outer_branch = next(
        index
        for index in range(mut_word_match + 1, len(lines))
        if lines[index].strip() == "1:"
        and len(lines[index]) - len(lines[index].lstrip()) == mut_word_base - 4
    )
    lines[mut_word_outer_branch:mut_word_outer_branch] = [
        " " * (mut_word_base + 4) + "1:",
        " " * (mut_word_base + 8) + "discard 0",
    ]

    current_kind_two = next(
        index
        for index, line in enumerate(lines)
        if line.strip() == "match current_kind == 2:"
        and any("expression_token" in lines[probe] for probe in range(max(0, index - 12), index))
    )
    base = len(lines[current_kind_two]) - len(lines[current_kind_two].lstrip())
    block_start = next(
        index
        for index in range(current_kind_two + 1, len(lines))
        if lines[index].strip() == "0:"
        and len(lines[index]) - len(lines[index].lstrip()) == base
    )
    block_end = next(
        index
        for index in range(block_start + 1, len(lines))
        if lines[index].strip() == "1:"
        and len(lines[index]) - len(lines[index].lstrip()) == base - 4
    )
    for index in range(block_start, block_end):
        lines[index] = "    " + lines[index]

    current_kind_one = next(
        index
        for index, line in enumerate(lines)
        if line.strip() == "match current_kind == 1:"
    )
    current_kind_one_branch = next(
        index
        for index in range(current_kind_two + 1, len(lines))
        if lines[index].strip() == "1:"
        and len(lines[index]) - len(lines[index].lstrip())
        == len(lines[current_kind_one]) - len(lines[current_kind_one].lstrip()) + 4
    )
    current_kind_two_base = len(lines[current_kind_two]) - len(lines[current_kind_two].lstrip())
    lines[current_kind_one_branch:current_kind_one_branch] = [
        " " * (current_kind_two_base + 4) + "1:",
        " " * (current_kind_two_base + 8) + "parse_ok = 0",
    ]

    def add_missing_case(match_text: str, body: str, occurrence: int = 1) -> None:
        match_indices = [
            index
            for index, line in enumerate(lines)
            if line.strip() == match_text
        ]
        match_index = match_indices[occurrence - 1]
        match_base = len(lines[match_index]) - len(lines[match_index].lstrip())
        insertion = next(
            index
            for index in range(match_index + 1, len(lines))
            if len(lines[index]) - len(lines[index].lstrip()) <= match_base
        )
        lines[insertion:insertion] = [
            " " * (match_base + 4) + "1:",
            " " * (match_base + 8) + body,
        ]

    add_missing_case("match current_code == 2:", "parse_ok = 0")
    add_missing_case("match current_code == 1:", "parse_ok = 0")
    add_missing_case(
        "match expression_operators[op_count - 1] == 1:",
        "reduce = 0",
        occurrence=2,
    )
    add_missing_case(
        "match to_i64(expression_rpn_kind[rpn_index]) == 1:",
        "parse_ok = 0",
    )
    add_missing_case(
        "match to_i64(token_kind[source_token]) == 2:",
        "parse_ok = 0",
    )
    add_missing_case("match op == 22:", "parse_ok = 0", occurrence=2)

    line_kind_match = next(
        index
        for index, line in enumerate(lines)
        if line.strip() == "match token_kind[statement] == 3:"
    )
    line_kind_base = len(lines[line_kind_match]) - len(lines[line_kind_match].lstrip())
    line_kind_tail = next(
        index
        for index in range(line_kind_match + 1, len(lines))
        if lines[index].strip() == "function_instruction_count[lower_function] = instruction_count - function_instruction_start[lower_function]"
    )
    trailing_line_kind_branch = next(
        index
        for index in range(line_kind_tail - 1, line_kind_match, -1)
        if lines[index].strip() == "0:"
        and len(lines[index]) - len(lines[index].lstrip()) == line_kind_base + 4
    )
    mode_match = next(
        index
        for index, line in enumerate(lines)
        if line.strip() == "match mode > 0:"
    )
    mode_base = len(lines[mode_match]) - len(lines[mode_match].lstrip())
    lines[trailing_line_kind_branch:trailing_line_kind_branch] = [
        " " * (mode_base + 4) + "0:",
        " " * (mode_base + 8) + "discard 0",
        " " * (mode_base + 4) + "1:",
        " " * (mode_base + 8) + "discard 0",
    ]
    trailing_line_kind_branch += 4
    line_kind_tail += 4
    lines[trailing_line_kind_branch] = " " * (line_kind_base + 4) + "1:"
    lines[trailing_line_kind_branch + 2] = " " * (line_kind_base + 8) + "statement += 1"
    duplicate_line_kind_branch = next(
        index
        for index in range(trailing_line_kind_branch + 1, line_kind_tail)
        if lines[index].strip() == "1:"
        and len(lines[index]) - len(lines[index].lstrip()) == line_kind_base + 4
    )
    del lines[duplicate_line_kind_branch : duplicate_line_kind_branch + 3]
    return "\n".join(lines) + "\n"


def _replace_operator_lowering(source: str) -> str:
    lines = source.splitlines()
    start = next(
        index
        for index, line in enumerate(lines)
        if line.strip() == "mut relation_aux: i64 = -1"
    )
    end = next(
        index
        for index in range(start + 1, len(lines))
        if lines[index].strip() == "match opcode > 0:"
    )
    indent = len(lines[start]) - len(lines[start].lstrip())
    pad = " " * indent
    child = " " * (indent + 4)
    grandchild = " " * (indent + 8)
    replacement = [
        pad + "mut relation_aux: i64 = -1",
        pad + "mut opcode: i64 = stage04_binary_opcode(op)",
        pad + "match opcode == 9:",
        child + "-1:",
        grandchild + "relation_aux = stage04_relation_aux(op)",
        child + "0:",
        grandchild + "discard 0",
        child + "1:",
        grandchild + "discard 0",
    ]
    lines[start:end] = replacement
    return "\n".join(lines) + "\n"


def _repair_stage04_add_operator_code(source: str) -> str:
    return source.replace("match op == 5:\n", "match op == 6:\n", 1)


def _repair_stage04_target_local_predicate(source: str) -> str:
    marker = "fn stage04_word(start: i64, end: i64, expected_hash: i64, expected_length: i64) -> trit:\n"
    helper = """fn stage04_nonnegative(value: i64) -> trit:
    match value < 0:
        -1:
            return 0
        0:
            return -1
        1:
            return -1

"""
    if marker not in source:
        raise ValueError("Stage04 predicate insertion marker not found")
    source = source.replace(marker, helper + marker, 1)
    matches = source.count("match target_local >= 0:")
    if matches != 2:
        raise ValueError(f"expected two Stage04 target-local predicates, found {matches}")
    return source.replace(
        "match target_local >= 0:",
        "match stage04_nonnegative(target_local):",
    )


def _repair_stage04_comparison_tokens(source: str) -> str:
    marker = "        match next_cursor > scan_cursor:\n"
    replacement = """        match kind == 4:
            -1:
                match value == 16:
                    -1:
                        match next_cursor < length:
                            -1:
                                match read_at(next_cursor) == 61:
                                    -1:
                                        next_cursor += 1
                                        value = 23
                                    0:
                                        discard 0
                                    1:
                                        discard 0
                            0:
                                discard 0
                            1:
                                discard 0
                    0:
                        match value == 17:
                            -1:
                                match next_cursor < length:
                                    -1:
                                        match read_at(next_cursor) == 61:
                                            -1:
                                                next_cursor += 1
                                                value = 24
                                            0:
                                                discard 0
                                            1:
                                                discard 0
                                    0:
                                        discard 0
                                    1:
                                        discard 0
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
        match next_cursor > scan_cursor:
"""
    if marker not in source:
        raise ValueError("Stage04 token scan marker not found")
    return source.replace(marker, replacement, 1)


def _repair_stage04_casts(source: str) -> str:
    helper = """fn stage04_cast_code(start: i64, end: i64) -> i64:
    match stage04_word(start, end, 33, 6):
        -1:
            return 25
        0:
            match stage04_word(start, end, 70, 6):
                -1:
                    return 26
                0:
                    match stage04_word(start, end, 355, 8):
                        -1:
                            return 27
                        0:
                            return 0
                        1:
                            return 0
                1:
                    return 0
        1:
            return 0

fn stage04_cast_type(op: i64) -> i64:
    match op == 25:
        -1:
            return 3
        0:
            match op == 26:
                -1:
                    return 4
                0:
                    match op == 27:
                        -1:
                            return 2
                        0:
                            return 0
                        1:
                            return 0
                1:
                    return 0
        1:
            return 0

fn stage04_cast_allowed(target_type: i64, source_type: i64) -> trit:
    match target_type == 3:
        -1:
            match source_type == 1:
                -1:
                    return -1
                0:
                    match source_type == 2:
                        -1:
                            return -1
                        0:
                            return 0
                        1:
                            return 0
                1:
                    return 0
        0:
            match target_type == 4:
                -1:
                    match source_type == 1:
                        -1:
                            return -1
                        0:
                            match source_type == 2:
                                -1:
                                    return -1
                                0:
                                    match source_type == 3:
                                        -1:
                                            return -1
                                        0:
                                            return 0
                                        1:
                                            return 0
                                1:
                                    return 0
                        1:
                            return 0
                0:
                    match target_type == 2:
                        -1:
                            match source_type == 3:
                                -1:
                                    return -1
                                0:
                                    return 0
                                1:
                                    return 0
                        0:
                            return 0
                        1:
                            return 0
                1:
                    return 0
        1:
            return 0

"""
    marker = "fn stage04_word(start: i64, end: i64, expected_hash: i64, expected_length: i64) -> trit:\n"
    if marker not in source:
        raise ValueError("Stage04 cast helper insertion marker not found")
    source = source.replace(marker, helper + marker, 1)
    lines = source.splitlines()

    expect_index = next(
        index
        for index, line in enumerate(lines)
        if line.strip() == "mut expect_operand: trit = -1"
    )
    declaration_indent = " " * (len(lines[expect_index]) - len(lines[expect_index].lstrip()))
    lines[expect_index + 1:expect_index + 1] = [
        declaration_indent + "mut cast_code_pending: i64 = 0",
        declaration_indent + "mut cast_open: trit = 0",
        declaration_indent + "mut cast_paren_depth: i64 = 0",
    ]

    current_match = next(
        index
        for index, line in enumerate(lines)
        if line.strip() == "match current_kind == 1:"
    )
    branch_indent = len(lines[current_match]) - len(lines[current_match].lstrip()) + 4
    branch_true = next(
        index
        for index in range(current_match + 1, len(lines))
        if len(lines[index]) - len(lines[index].lstrip()) == branch_indent
        and lines[index].strip() == "-1:"
    )
    branch_zero = next(
        index
        for index in range(branch_true + 1, len(lines))
        if len(lines[index]) - len(lines[index].lstrip()) == branch_indent
        and lines[index].strip() == "0:"
    )
    body_indent = " " * (branch_indent + 4)
    case_indent = " " * (branch_indent + 8)
    case_body_indent = " " * (branch_indent + 12)
    cast_process_indent = case_body_indent + "        "
    normal_operand = [
        ("        " + line) if line else line
        for line in lines[branch_true + 1:branch_zero]
    ]
    cast_process = [
        cast_process_indent + "match expression_token + 1 < line_end:",
        cast_process_indent + "    -1:",
        cast_process_indent + "        match to_i64(token_kind[expression_token + 1]) == 4:",
        cast_process_indent + "            -1:",
        cast_process_indent + "                match token_value[expression_token + 1] == 1:",
        cast_process_indent + "                    -1:",
        cast_process_indent + "                        cast_code_pending = cast_code",
        cast_process_indent + "                        cast_open = -1",
        cast_process_indent + "                        cast_paren_depth = 0",
        cast_process_indent + "                        expect_operand = -1",
        cast_process_indent + "                    0:",
        cast_process_indent + "                        parse_ok = 0",
        cast_process_indent + "                    1:",
        cast_process_indent + "                        parse_ok = 0",
        cast_process_indent + "            0:",
        cast_process_indent + "                parse_ok = 0",
        cast_process_indent + "            1:",
        cast_process_indent + "                parse_ok = 0",
        cast_process_indent + "    0:",
        cast_process_indent + "        parse_ok = 0",
        cast_process_indent + "    1:",
        cast_process_indent + "        parse_ok = 0",
    ]
    nested_normal_operand = [
        ("                " + line) if line else line
        for line in lines[branch_true + 1:branch_zero]
    ]
    cast_body = [
        case_body_indent + "match cast_code_pending > 0:",
        case_body_indent + "    -1:",
        case_body_indent + "        parse_ok = 0",
        case_body_indent + "    0:",
        *cast_process,
        case_body_indent + "    1:",
        case_body_indent + "        parse_ok = 0",
    ]
    replacement = [
        body_indent + "mut cast_code: i64 = stage04_cast_code(token_start[expression_token], token_end[expression_token])",
        body_indent + "match cast_code == 0:",
        case_indent + "-1:",
        *normal_operand,
        case_indent + "0:",
        *cast_body,
        case_indent + "1:",
        *cast_body,
    ]
    lines[branch_true + 1:branch_zero] = replacement

    open_match = next(
        index
        for index in range(current_match + 1, len(lines))
        if lines[index].strip() == "match current_code == 1:"
    )
    open_branch_indent = len(lines[open_match]) - len(lines[open_match].lstrip()) + 4
    open_true = next(
        index
        for index in range(open_match + 1, len(lines))
        if len(lines[index]) - len(lines[index].lstrip()) == open_branch_indent
        and lines[index].strip() == "-1:"
    )
    open_zero = next(
        index
        for index in range(open_true + 1, len(lines))
        if len(lines[index]) - len(lines[index].lstrip()) == open_branch_indent
        and lines[index].strip() == "0:"
    )
    open_body = " " * (open_branch_indent + 4)
    open_case = " " * (open_branch_indent + 8)
    open_case_body = " " * (open_branch_indent + 12)
    normal_open = [
        ("        " + line) if line else line
        for line in lines[open_true + 1:open_zero]
    ]
    nested_normal_open = [
        ("                " + line) if line else line
        for line in lines[open_true + 1:open_zero]
    ]
    normal_open_prefix = [
        open_case_body + "match cast_code_pending > 0:",
        open_case_body + "    -1:",
        open_case_body + "        cast_paren_depth += 1",
        open_case_body + "    0:",
        *nested_normal_open,
        open_case_body + "    1:",
        open_case_body + "        discard 0",
    ]
    lines[open_true + 1:open_zero] = [
        open_body + "match cast_open:",
        open_case + "-1:",
        open_case_body + "cast_open = 0",
        open_case_body + "cast_paren_depth = 1",
        open_case + "0:",
        *normal_open_prefix,
        open_case + "1:",
        *normal_open_prefix,
    ]

    close_match = next(
        index
        for index in range(open_match + 1, len(lines))
        if lines[index].strip() == "match current_code == 2:"
    )
    close_branch_indent = len(lines[close_match]) - len(lines[close_match].lstrip()) + 4
    close_true = next(
        index
        for index in range(close_match + 1, len(lines))
        if len(lines[index]) - len(lines[index].lstrip()) == close_branch_indent
        and lines[index].strip() == "-1:"
    )
    close_body_indent = " " * (close_branch_indent + 4)
    close_insert = [
        close_body_indent + "match cast_code_pending > 0:",
        close_body_indent + "    -1:",
        close_body_indent + "        match cast_paren_depth == 1:",
        close_body_indent + "            -1:",
        close_body_indent + "                match rpn_count < 64:",
        close_body_indent + "                    -1:",
        close_body_indent + "                        expression_rpn_kind[rpn_count] = 2",
        close_body_indent + "                        expression_rpn_value[rpn_count] = cast_code_pending",
        close_body_indent + "                        rpn_count += 1",
        close_body_indent + "                        cast_code_pending = 0",
        close_body_indent + "                        cast_paren_depth = 0",
        close_body_indent + "                    0:",
        close_body_indent + "                        parse_ok = 0",
        close_body_indent + "                    1:",
        close_body_indent + "                        parse_ok = 0",
        close_body_indent + "            0:",
        close_body_indent + "                cast_paren_depth = cast_paren_depth - 1",
        close_body_indent + "            1:",
        close_body_indent + "                cast_paren_depth = cast_paren_depth - 1",
        close_body_indent + "    0:",
        close_body_indent + "        discard 0",
        close_body_indent + "    1:",
        close_body_indent + "        discard 0",
    ]
    expect_close = next(
        index
        for index in range(close_true + 1, len(lines))
        if lines[index].strip() == "expect_operand = 0"
    )
    lines[expect_close:expect_close] = close_insert

    rpn_value = next(
        index
        for index, line in enumerate(lines)
        if line.strip() == "mut op: i64 = expression_rpn_value[rpn_index]"
    )
    evaluator_indent = " " * (len(lines[rpn_value]) - len(lines[rpn_value].lstrip()))
    lines[rpn_value + 1:rpn_value + 1] = [
        evaluator_indent + "mut cast_target_type: i64 = stage04_cast_type(op)",
        evaluator_indent + "match cast_target_type > 0:",
        evaluator_indent + "    -1:",
        evaluator_indent + "        op = 20",
        evaluator_indent + "    0:",
        evaluator_indent + "        discard 0",
        evaluator_indent + "    1:",
        evaluator_indent + "        discard 0",
    ]
    unary_match = next(
        index
        for index in range(rpn_value + 1, len(lines))
        if lines[index].strip() == "match op == 20:"
    )
    unary_true = next(
        index
        for index in range(unary_match + 1, len(lines))
        if lines[index].strip() == "-1:"
    )
    unary_stack = next(
        index
        for index in range(unary_true + 1, len(lines))
        if lines[index].strip() == "match stack_count > 0:"
    )
    type_line = next(
        index
        for index in range(unary_stack + 1, len(lines))
        if lines[index].strip() == "value_type[result_value] = expression_types[stack_count - 1]"
    )
    opcode_line = next(
        index
        for index in range(type_line, len(lines))
        if lines[index].strip()
        in {
            "instruction_opcode[instruction_count] = 4",
            "instruction_opcode[instruction_count] = to_tryte(4)",
        }
    )
    type_indent = " " * (len(lines[type_line]) - len(lines[type_line].lstrip()))
    lines[type_line:type_line + 1] = [
        type_indent + "mut result_type: i64 = to_i64(expression_types[stack_count - 1])",
        type_indent + "match cast_target_type > 0:",
        type_indent + "    -1:",
        type_indent + "        match stage04_cast_allowed(cast_target_type, result_type):",
        type_indent + "            -1:",
        type_indent + "                result_type = cast_target_type",
        type_indent + "            0:",
        type_indent + "                parse_ok = 0",
        type_indent + "            1:",
        type_indent + "                parse_ok = 0",
        type_indent + "    0:",
        type_indent + "        discard 0",
        type_indent + "    1:",
        type_indent + "        discard 0",
        type_indent + "value_type[result_value] = to_tryte(result_type)",
    ]
    opcode_line += 14
    opcode_indent = " " * (len(lines[opcode_line]) - len(lines[opcode_line].lstrip()))
    lines[opcode_line:opcode_line + 1] = [
        opcode_indent + "mut emitted_opcode: i64 = 4",
        opcode_indent + "match cast_target_type > 0:",
        opcode_indent + "    -1:",
        opcode_indent + "        emitted_opcode = 10",
        opcode_indent + "    0:",
        opcode_indent + "        discard 0",
        opcode_indent + "    1:",
        opcode_indent + "        discard 0",
        opcode_indent + "instruction_opcode[instruction_count] = to_tryte(emitted_opcode)",
    ]
    return "\n".join(lines) + "\n"


def _repair_stage04_token_span(source: str) -> str:
    old = """                                mut actual_start: i64 = scan_cursor
                                while actual_start < next_cursor:
                                    match is_space_unit(read_at(actual_start)):
                                        -1:
                                            actual_start += 1
                                        0:
                                            actual_start = next_cursor
                                        1:
                                            actual_start = next_cursor
"""
    new = """                                mut actual_start: i64 = scan_cursor
                                mut trim_cursor: i64 = scan_cursor
                                while trim_cursor < next_cursor:
                                    match is_space_unit(read_at(trim_cursor)):
                                        -1:
                                            actual_start += 1
                                            trim_cursor += 1
                                        0:
                                            trim_cursor = next_cursor
                                        1:
                                            trim_cursor = next_cursor
"""
    if old not in source:
        raise ValueError("Stage04 token span block not found")
    return source.replace(old, new, 1)


def _repair_stage04_predicates(source: str) -> str:
    old_word = """fn stage04_word(start: i64, end: i64, expected_hash: i64, expected_length: i64) -> trit:
    match end - start == expected_length:
        -1:
            return 0
        0:
            match identifier_hash(start, end) == expected_hash:
                -1:
                    return -1
                0:
                    return 0
                1:
                    return 0
        1:
            return 0
"""
    new_word = """fn stage04_word(start: i64, end: i64, expected_hash: i64, expected_length: i64) -> trit:
    match end - start == expected_length:
        -1:
            match identifier_hash(start, end) == expected_hash:
                -1:
                    return -1
                0:
                    return 0
                1:
                    return 0
        0:
            return 0
        1:
            return 0
"""
    old_span = """fn stage04_same_span(left_start: i64, left_length: i64, right_start: i64, right_length: i64) -> trit:
    match left_length == right_length:
        -1:
            return 0
        0:
            mut cursor: i64 = 0
            mut equal: trit = -1
            while cursor < left_length:
                match read_at(left_start + cursor) == read_at(right_start + cursor):
                    -1:
                        cursor += 1
                    0:
                        equal = 0
                        cursor = left_length
                    1:
                        equal = 0
                        cursor = left_length
            return equal
        1:
            return 0
"""
    new_span = """fn stage04_same_span(left_start: i64, left_length: i64, right_start: i64, right_length: i64) -> trit:
    match left_length == right_length:
        -1:
            mut cursor: i64 = 0
            mut equal: trit = -1
            while cursor < left_length:
                match read_at(left_start + cursor) == read_at(right_start + cursor):
                    -1:
                        cursor += 1
                    0:
                        equal = 0
                        cursor = left_length
                    1:
                        equal = 0
                        cursor = left_length
            return equal
        0:
            return 0
        1:
            return 0
"""
    if old_word not in source or old_span not in source:
        raise ValueError("Stage04 predicate block not found")
    source = source.replace(old_word, new_word, 1)
    return source.replace(old_span, new_span, 1)


def _repair_stage04_function_header(source: str) -> str:
    lines = source.splitlines()
    index = next(
        index
        for index, line in enumerate(lines)
        if line.strip() == "match token_value[cursor] == 12:"
    )
    base = len(lines[index]) - len(lines[index].lstrip())
    replacement = [
        " " * base + "match token_value[cursor] == 2:",
        " " * (base + 4) + "-1:",
        " " * (base + 8) + "cursor += 1",
        " " * (base + 8) + "match cursor < token_count:",
        " " * (base + 12) + "-1:",
        " " * (base + 16) + "match token_value[cursor] == 12:",
        " " * (base + 20) + "-1:",
        " " * (base + 24) + "cursor += 1",
        " " * (base + 20) + "0:",
        " " * (base + 24) + "header_ok = 0",
        " " * (base + 20) + "1:",
        " " * (base + 24) + "header_ok = 0",
        " " * (base + 12) + "0:",
        " " * (base + 16) + "header_ok = 0",
        " " * (base + 12) + "1:",
        " " * (base + 16) + "header_ok = 0",
        " " * (base + 4) + "0:",
        " " * (base + 8) + "header_ok = 0",
        " " * (base + 4) + "1:",
        " " * (base + 8) + "header_ok = 0",
    ]
    lines[index : index + 7] = replacement
    return "\n".join(lines) + "\n"


def _repair_stage04_local_probe_progress(source: str) -> str:
    lines = source.splitlines()
    declaration = next(
        index
        for index, line in enumerate(lines)
        if line.strip() == "match declaration_name < line_end:"
    )
    declaration_indent = len(lines[declaration]) - len(lines[declaration].lstrip())
    progress = next(
        index
        for index in range(declaration + 1, len(lines))
        if lines[index].strip() == "match line_end < function_body_end[function_end_scan]:"
    )
    progress_indent = len(lines[progress]) - len(lines[progress].lstrip())
    if progress_indent != declaration_indent + 8:
        raise ValueError("Stage04 local probe progress has unexpected indentation")
    progress_block = [line[8:] for line in lines[progress : progress + 7]]
    del lines[progress : progress + 7]
    branch_one = next(
        index
        for index in range(declaration + 1, len(lines))
        if lines[index].strip() == "1:"
        and len(lines[index]) - len(lines[index].lstrip()) == declaration_indent + 4
    )
    insertion = branch_one + 1
    while insertion < len(lines):
        indent = len(lines[insertion]) - len(lines[insertion].lstrip())
        if indent <= declaration_indent:
            break
        insertion += 1
    lines[insertion:insertion] = progress_block
    return "\n".join(lines) + "\n"


def _repair_stage04_line_scans(source: str) -> str:
    lines = source.splitlines()
    starts = [
        index
        for index, line in enumerate(lines)
        if line.strip() == "while line_end < function_body_end[function_end_scan]:"
        or line.strip() == "while line_end < function_body_end[lower_function]:"
    ]
    if len(starts) != 2:
        raise ValueError("Stage04 line scanners not found")
    for start in reversed(starts):
        while_indent = len(lines[start]) - len(lines[start].lstrip())
        child = " " * (while_indent + 4)
        grandchild = " " * (while_indent + 8)
        great_grandchild = " " * (while_indent + 12)
        replacement = [
            " " * while_indent + "mut line_scan_cursor: i64 = line_end",
            " " * while_indent + "mut line_done: trit = 0",
            " " * while_indent + lines[start].lstrip().replace("line_end", "line_scan_cursor"),
            child + "match line_done == 0:",
            grandchild + "-1:",
            great_grandchild + "match token_kind[line_scan_cursor] == 3:",
            " " * (while_indent + 16) + "-1:",
            " " * (while_indent + 20) + "line_end = line_scan_cursor",
            " " * (while_indent + 20) + "line_done = -1",
            " " * (while_indent + 16) + "0:",
            " " * (while_indent + 20) + "line_scan_cursor += 1",
            " " * (while_indent + 16) + "1:",
            " " * (while_indent + 20) + "line_scan_cursor += 1",
            grandchild + "0:",
            great_grandchild + "line_scan_cursor = function_body_end[" + (
                "function_end_scan" if "function_end_scan" in lines[start] else "lower_function"
            ) + "]",
            grandchild + "1:",
            great_grandchild + "line_scan_cursor = function_body_end[" + (
                "function_end_scan" if "function_end_scan" in lines[start] else "lower_function"
            ) + "]",
            " " * while_indent + "match line_done == 0:",
            child + "-1:",
            grandchild + "line_end = function_body_end[" + (
                "function_end_scan" if "function_end_scan" in lines[start] else "lower_function"
            ) + "]",
            child + "0:",
            grandchild + "discard 0",
            child + "1:",
            grandchild + "discard 0",
        ]
        end = start + 8
        if end > len(lines) or lines[start + 1].strip() != "match token_kind[line_end] == 3:":
            raise ValueError("Stage04 line scanner shape changed")
        del lines[start:end]
        lines[start:start] = replacement
    return "\n".join(lines) + "\n"


def _repair_stage04_statement_progress(source: str) -> str:
    lines = source.splitlines()
    mode = next(
        index
        for index, line in enumerate(lines)
        if line.strip() == "match mode > 0:"
    )
    mode_indent = len(lines[mode]) - len(lines[mode].lstrip())
    progress = next(
        index
        for index in range(mode + 1, len(lines))
        if lines[index].strip() == "match line_end < function_body_end[lower_function]:"
    )
    progress_indent = len(lines[progress]) - len(lines[progress].lstrip())
    if progress_indent != mode_indent + 8:
        raise ValueError("Stage04 statement progress has unexpected indentation")
    progress_block = [line[8:] for line in lines[progress : progress + 7]]
    del lines[progress : progress + 7]
    branch_one = next(
        index
        for index in range(mode + 1, len(lines))
        if lines[index].strip() == "1:"
        and len(lines[index]) - len(lines[index].lstrip()) == mode_indent + 4
    )
    insertion = branch_one + 1
    while insertion < len(lines):
        indent = len(lines[insertion]) - len(lines[insertion].lstrip())
        if indent <= mode_indent:
            break
        insertion += 1
    lines[insertion:insertion] = progress_block
    return "\n".join(lines) + "\n"


def _repair_stage04_rpn_progress(source: str) -> str:
    lines = source.splitlines()
    rpn_loop = next(
        index
        for index, line in enumerate(lines)
        if line.strip() == "while rpn_index < rpn_count:"
    )
    loop_indent = len(lines[rpn_loop]) - len(lines[rpn_loop].lstrip())
    increment = next(
        index
        for index in range(rpn_loop + 1, len(lines))
        if lines[index].strip() == "rpn_index += 1"
    )
    del lines[increment]
    stack_check = next(
        index
        for index in range(rpn_loop + 1, len(lines))
        if lines[index].strip() == "match stack_count == 1:"
    )
    lines[stack_check:stack_check] = [" " * (loop_indent + 4) + "rpn_index += 1"]
    return "\n".join(lines) + "\n"


def _repair_stage04_resolved_value_scope(source: str) -> str:
    lines = source.splitlines()
    rpn_loop = next(
        index
        for index, line in enumerate(lines)
        if line.strip() == "while rpn_index < rpn_count:"
    )
    rpn_indent = len(lines[rpn_loop]) - len(lines[rpn_loop].lstrip())
    resolved = next(
        index
        for index in range(rpn_loop + 1, len(lines))
        if lines[index].strip() == "match resolved_value >= 0:"
    )
    resolved_indent = len(lines[resolved]) - len(lines[resolved].lstrip())
    block_end = next(
        index
        for index in range(resolved + 1, len(lines))
        if lines[index].strip() == "1:"
        and len(lines[index]) - len(lines[index].lstrip()) == resolved_indent + 4
    )
    block_end += 2
    rpn_operator_branch = next(
        index
        for index in range(resolved + 1, len(lines))
        if lines[index].strip() == "0:"
        and len(lines[index]) - len(lines[index].lstrip()) == rpn_indent + 8
    )
    block = lines[resolved:block_end]
    dedent = resolved_indent - (rpn_indent + 12)
    if dedent < 0 or dedent % 4:
        raise ValueError("unexpected Stage04 resolved-value indentation")
    if dedent:
        block = [line[dedent:] if line.strip() else line for line in block]
    del lines[resolved:block_end]
    lines[rpn_operator_branch - (block_end - resolved):rpn_operator_branch - (block_end - resolved)] = block
    return "\n".join(lines) + "\n"


def _repair_stage04_mutable_initializer(source: str) -> str:
    lines = source.splitlines()
    mode_two = next(
        index
        for index, line in enumerate(lines)
        if line.strip() == "match mode == 2:"
    )
    mode_three = next(
        index
        for index in range(mode_two + 1, len(lines))
        if lines[index].strip() == "match mode == 3:"
    )
    mode_one = next(
        index
        for index, line in enumerate(lines)
        if line.strip() == "match mode == 1:"
    )
    mode_one_base = len(lines[mode_one]) - len(lines[mode_one].lstrip())
    mode_three_base = len(lines[mode_three]) - len(lines[mode_three].lstrip())
    mode_three_end = next(
        index
        for index in range(mode_three + 1, len(lines))
        if len(lines[index]) - len(lines[index].lstrip())
        <= mode_three_base - 4
    )
    mode_three_block = lines[mode_three:mode_three_end]
    outer_mode_one_branch = mode_three - 1
    if (
        lines[outer_mode_one_branch].strip() != "1:"
        or len(lines[outer_mode_one_branch]) - len(lines[outer_mode_one_branch].lstrip())
        != mode_one_base + 4
    ):
        raise ValueError("Stage04 mode dispatcher has unexpected outer branch")
    del lines[mode_three:mode_three_end]
    lines[outer_mode_one_branch + 1 : outer_mode_one_branch + 1] = [
        " " * (mode_three_base + 4) + "parse_ok = 0"
    ]
    mode_two = next(
        index
        for index, line in enumerate(lines)
        if line.strip() == "match mode == 2:"
    )
    mode_two_base = len(lines[mode_two]) - len(lines[mode_two].lstrip())
    mode_two_false = next(
        index
        for index in range(mode_two + 1, len(lines))
        if lines[index].strip() == "0:"
        and len(lines[index]) - len(lines[index].lstrip()) == mode_two_base + 4
    )
    mode_two_true = next(
        index
        for index in range(mode_two_false + 1, len(lines))
        if lines[index].strip() == "1:"
        and len(lines[index]) - len(lines[index].lstrip()) == mode_two_base + 4
    )
    shifted_mode_three_block = [
        " " * (mode_two_base + 8)
        + line[mode_three_base:]
        for line in mode_three_block
    ]
    lines[mode_two_false + 1 : mode_two_true] = shifted_mode_three_block
    mode_three = next(
        index
        for index in range(mode_two + 1, len(lines))
        if lines[index].strip() == "match mode == 3:"
    )
    declaration_token_match = next(
        index
        for index, line in enumerate(lines)
        if line.strip() == "match local_declaration_token[to_tryte(local_find)] == name_token:"
    )
    declaration_indent = len(lines[declaration_token_match]) - len(lines[declaration_token_match].lstrip())
    lines[declaration_token_match] = (
        " " * declaration_indent
        + "match stage04_same_span(token_start[to_tryte(name_token)], token_end[to_tryte(name_token)] - token_start[to_tryte(name_token)], local_name_start[to_tryte(local_find)], local_name_length[to_tryte(local_find)]):"
    )
    target_match = next(
        index
        for index in range(mode_two + 1, mode_three)
        if lines[index].strip() == "match stage04_nonnegative(target_local):"
    )
    target_base = len(lines[target_match]) - len(lines[target_match].lstrip())
    target_zero = next(
        index
        for index in range(target_match + 1, len(lines))
        if lines[index].strip() == "0:"
        and len(lines[index]) - len(lines[index].lstrip()) == target_base + 4
    )
    target_one = next(
        index
        for index in range(target_zero + 1, len(lines))
        if lines[index].strip() == "1:"
        and len(lines[index]) - len(lines[index].lstrip()) == target_base + 4
    )
    lines[target_zero + 1 : target_one] = [
        " " * (target_base + 8) + "parse_ok = 0"
    ]

    mode_three = next(
        index
        for index in range(mode_two + 1, len(lines))
        if lines[index].strip() == "match mode == 3:"
    )

    outer_match = next(
        index
        for index in range(target_match + 1, target_zero)
        if lines[index].strip() == "match local_mutable[to_tryte(target_local)] == 0:"
    )
    outer_base = len(lines[outer_match]) - len(lines[outer_match].lstrip())
    outer_zero = next(
        index
        for index in range(outer_match + 1, len(lines))
        if lines[index].strip() == "0:"
        and len(lines[index]) - len(lines[index].lstrip()) == outer_base + 4
    )
    outer_one = next(
        index
        for index in range(outer_zero + 1, len(lines))
        if lines[index].strip() == "1:"
        and len(lines[index]) - len(lines[index].lstrip()) == outer_base + 4
    )

    source_match = next(
        index
        for index in range(mode_three + 1, len(lines))
        if lines[index].strip() == "match local_mutable[to_tryte(target_local)] == -1:"
    )
    source_base = len(lines[source_match]) - len(lines[source_match].lstrip())
    source_branch = next(
        index
        for index in range(source_match + 1, len(lines))
        if lines[index].strip() == "-1:"
        and len(lines[index]) - len(lines[index].lstrip()) == source_base + 4
    )
    source_end = next(
        index
        for index in range(source_branch + 1, len(lines))
        if lines[index].strip() == "0:"
        and len(lines[index]) - len(lines[index].lstrip()) == source_base + 4
    )
    source_body = lines[source_branch + 1 : source_end]
    if not source_body or any(
        len(line) - len(line.lstrip()) < source_base + 8
        for line in source_body
        if line.strip()
    ):
        raise ValueError("Stage04 mutable store body has unexpected indentation")
    target_indent = outer_base + 8
    body = [
        " " * target_indent + line[source_base + 8 :]
        for line in source_body
    ]
    lines[outer_zero + 1 : outer_one] = body
    return "\n".join(lines) + "\n"


def _repair_stage04_completion_mask(source: str) -> str:
    old = "    discard semantic_v2_complete(3)\n    return 0\n"
    new = """    mut completion_mask: i64 = 3
    match parse_ok == -1:
        -1:
            discard 0
        0:
            completion_mask = 0
        1:
            completion_mask = 0
    discard semantic_v2_complete(completion_mask)
    return 0
"""
    if old not in source:
        raise ValueError("Stage04 completion marker not found")
    return source.replace(old, new, 1)


def _repair_stage04_literal_types(source: str) -> str:
    """Keep numeric operands in the semantic tryte domain until context resolves them."""
    literal_type = "mut resolved_type: i64 = to_i64(function_return_type[lower_function])"
    if source.count(literal_type) != 1:
        raise ValueError("Stage04 numeric literal type marker is not unique")
    source = source.replace(literal_type, "mut resolved_type: i64 = 2", 1)

    marker = """                                    match stack_count == 1:
                                        -1:
                                            mut expression_result: i64 = expression_values[0]
                                            match mode == 1:
"""
    replacement = """                                    match stack_count == 1:
                                        -1:
                                            mut expression_result: i64 = expression_values[0]
                                            match rpn_count == 1:
                                                -1:
                                                    match to_i64(expression_rpn_kind[0]) == 1:
                                                        -1:
                                                            match to_i64(token_kind[expression_rpn_token[0]]) == 2:
                                                                -1:
                                                                    value_type[expression_result] = function_return_type[lower_function]
                                                                0:
                                                                    discard 0
                                                                1:
                                                                    discard 0
                                                        0:
                                                            discard 0
                                                        1:
                                                            discard 0
                                                0:
                                                    discard 0
                                                1:
                                                    discard 0
                                            match mode == 1:
"""
    if marker not in source:
        raise ValueError("Stage04 expression result marker not found")
    return source.replace(marker, replacement, 1)


def _repair_stage04_contextual_literal_types(source: str) -> str:
    marker = "fn stage04_word(start: i64, end: i64, expected_hash: i64, expected_length: i64) -> trit:\n"
    helper = """fn stage04_is_relational(op: i64) -> trit:
    mut relational: trit = 0
    match op == 15:
        -1:
            relational = -1
        0:
            discard 0
        1:
            discard 0
    match op == 13:
        -1:
            relational = -1
        0:
            discard 0
        1:
            discard 0
    match op == 21:
        -1:
            relational = -1
        0:
            discard 0
        1:
            discard 0
    match op == 16:
        -1:
            relational = -1
        0:
            discard 0
        1:
            discard 0
    match op == 23:
        -1:
            relational = -1
        0:
            discard 0
        1:
            discard 0
    match op == 17:
        -1:
            relational = -1
        0:
            discard 0
        1:
            discard 0
    match op == 24:
        -1:
            relational = -1
        0:
            discard 0
        1:
            discard 0
    return relational

fn stage04_contextual_literal_type(op: i64, peer_type: i64, return_type: i64, both_literals: trit) -> i64:
    mut selected: i64 = 0
    match both_literals == -1:
        -1:
            match stage04_is_relational(op):
                -1:
                    discard 0
                0:
                    selected = return_type
                1:
                    selected = return_type
        0:
            match peer_type == 1:
                -1:
                    selected = 1
                0:
                    match peer_type == 3:
                        -1:
                            selected = 3
                        0:
                            match peer_type == 4:
                                -1:
                                    selected = 4
                                0:
                                    discard 0
                                1:
                                    discard 0
                        1:
                            discard 0
                1:
                    discard 0
        1:
            discard 0
    return selected

"""
    if marker not in source:
        raise ValueError("Stage04 contextual literal helper marker not found")
    source = source.replace(marker, helper + marker, 1)

    lines = source.splitlines()
    relation_index = next(
        index
        for index, line in enumerate(lines)
        if line.strip() == "mut relation_aux: i64 = -1"
    )
    base = len(lines[relation_index]) - len(lines[relation_index].lstrip())
    pad = " " * base
    child = " " * (base + 4)
    grandchild = " " * (base + 8)
    great_grandchild = " " * (base + 12)
    great_great_grandchild = " " * (base + 16)
    adjustment = [
        pad + "mut left_type: i64 = to_i64(expression_types[stack_count - 2])",
        pad + "mut right_type: i64 = to_i64(expression_types[stack_count - 1])",
        pad + "mut left_literal: trit = 0",
        pad + "mut right_literal: trit = 0",
        pad + "match value_kind[left_value] == 3:",
        child + "-1:",
        grandchild + "left_literal = -1",
        child + "0:",
        grandchild + "discard 0",
        child + "1:",
        grandchild + "discard 0",
        pad + "match value_kind[right_value] == 3:",
        child + "-1:",
        grandchild + "right_literal = -1",
        child + "0:",
        grandchild + "discard 0",
        child + "1:",
        grandchild + "discard 0",
        pad + "mut left_context_type: i64 = 0",
        pad + "mut right_context_type: i64 = 0",
        pad + "match left_literal == -1:",
        child + "-1:",
        grandchild + "match right_literal == -1:",
        great_grandchild + "-1:",
        great_great_grandchild + "left_context_type = stage04_contextual_literal_type(op, 0, to_i64(function_return_type[lower_function]), -1)",
        great_great_grandchild + "right_context_type = stage04_contextual_literal_type(op, 0, to_i64(function_return_type[lower_function]), -1)",
        great_grandchild + "0:",
        great_great_grandchild + "left_context_type = stage04_contextual_literal_type(op, right_type, to_i64(function_return_type[lower_function]), 0)",
        great_grandchild + "1:",
        great_great_grandchild + "discard 0",
        child + "0:",
        grandchild + "match right_literal == -1:",
        great_grandchild + "-1:",
        great_great_grandchild + "right_context_type = stage04_contextual_literal_type(op, left_type, to_i64(function_return_type[lower_function]), 0)",
        great_grandchild + "0:",
        great_great_grandchild + "discard 0",
        great_grandchild + "1:",
        great_great_grandchild + "discard 0",
        child + "1:",
        grandchild + "discard 0",
        pad + "match left_context_type > 0:",
        child + "-1:",
        grandchild + "value_type[left_value] = to_tryte(left_context_type)",
        grandchild + "expression_types[stack_count - 2] = to_tryte(left_context_type)",
        child + "0:",
        grandchild + "discard 0",
        child + "1:",
        grandchild + "discard 0",
        pad + "match right_context_type > 0:",
        child + "-1:",
        grandchild + "value_type[right_value] = to_tryte(right_context_type)",
        grandchild + "expression_types[stack_count - 1] = to_tryte(right_context_type)",
        child + "0:",
        grandchild + "discard 0",
        child + "1:",
        grandchild + "discard 0",
    ]
    lines[relation_index:relation_index] = adjustment
    return "\n".join(lines) + "\n"


def _repair_stage04_unary_type_validation(source: str) -> str:
    marker = "fn stage04_word(start: i64, end: i64, expected_hash: i64, expected_length: i64) -> trit:\n"
    helper = """fn stage04_unary_type_valid(op: i64, value_type: i64) -> trit:
    match op == 22:
        -1:
            match value_type == 1:
                -1:
                    return -1
                0:
                    match value_type == 2:
                        -1:
                            return -1
                        0:
                            return 0
                        1:
                            return 0
                1:
                    return 0
        0:
            return -1
        1:
            return -1

"""
    if marker not in source:
        raise ValueError("Stage04 unary helper marker not found")
    source = source.replace(marker, helper + marker, 1)
    lines = source.splitlines()
    cast_index = next(
        index
        for index, line in enumerate(lines)
        if line.strip() == "mut cast_target_type: i64 = stage04_cast_type(op)"
    )
    evaluator_index = next(
        index
        for index in range(cast_index + 1, len(lines))
        if lines[index].strip() == "match op == 20:"
    )
    base = len(lines[evaluator_index]) - len(lines[evaluator_index].lstrip())
    pad = " " * base
    child = " " * (base + 4)
    grandchild = " " * (base + 8)
    great_grandchild = " " * (base + 12)
    validation = [
        pad + "match op == 22:",
        child + "-1:",
        grandchild + "match stack_count > 0:",
        great_grandchild + "-1:",
        " " * (base + 16) + "match value_kind[expression_values[stack_count - 1]] == 3:",
        " " * (base + 20) + "-1:",
        " " * (base + 24) + "value_type[expression_values[stack_count - 1]] = function_return_type[lower_function]",
        " " * (base + 24) + "expression_types[stack_count - 1] = function_return_type[lower_function]",
        " " * (base + 20) + "0:",
        " " * (base + 24) + "discard 0",
        " " * (base + 20) + "1:",
        " " * (base + 24) + "discard 0",
        " " * (base + 16) + "match stage04_unary_type_valid(op, to_i64(expression_types[stack_count - 1])):",
        " " * (base + 20) + "-1:",
        " " * (base + 24) + "discard 0",
        " " * (base + 20) + "0:",
        " " * (base + 24) + "parse_ok = 0",
        " " * (base + 20) + "1:",
        " " * (base + 24) + "parse_ok = 0",
        great_grandchild + "0:",
        " " * (base + 16) + "parse_ok = 0",
        great_grandchild + "1:",
        " " * (base + 16) + "parse_ok = 0",
        child + "0:",
        grandchild + "discard 0",
        child + "1:",
        grandchild + "discard 0",
        pad + "match op == 20:",
    ]
    lines[evaluator_index : evaluator_index + 1] = validation
    op20_index = evaluator_index + len(validation) - 1
    op20_stack_index = next(
        index
        for index in range(op20_index + 1, len(lines))
        if lines[index].strip() == "match stack_count > 0:"
    )
    op20_context = [
        " " * (base + 16) + "match value_kind[expression_values[stack_count - 1]] == 3:",
        " " * (base + 20) + "-1:",
        " " * (base + 24) + "value_type[expression_values[stack_count - 1]] = function_return_type[lower_function]",
        " " * (base + 24) + "expression_types[stack_count - 1] = function_return_type[lower_function]",
        " " * (base + 20) + "0:",
        " " * (base + 24) + "discard 0",
        " " * (base + 20) + "1:",
        " " * (base + 24) + "discard 0",
    ]
    lines[op20_stack_index + 2 : op20_stack_index + 2] = op20_context
    return "\n".join(lines) + "\n"


def _repair_stage04_binary_type_validation(source: str) -> str:
    marker = "fn stage04_word(start: i64, end: i64, expected_hash: i64, expected_length: i64) -> trit:\n"
    helper = """fn stage04_binary_type_valid(op: i64, left_type: i64, right_type: i64) -> trit:
    match op == 18:
        -1:
            match left_type == 1:
                -1:
                    match right_type == 1:
                        -1:
                            return -1
                        0:
                            match right_type == 2:
                                -1:
                                    return -1
                                0:
                                    return 0
                                1:
                                    return 0
                        1:
                            return 0
                0:
                    match left_type == 2:
                        -1:
                            match right_type == 1:
                                -1:
                                    return -1
                                0:
                                    match right_type == 2:
                                        -1:
                                            return -1
                                        0:
                                            return 0
                                        1:
                                            return 0
                                1:
                                    return 0
                        0:
                            return 0
                        1:
                            return 0
                1:
                    return 0
        0:
            match op == 19:
                -1:
                    match left_type == 1:
                        -1:
                            match right_type == 1:
                                -1:
                                    return -1
                                0:
                                    match right_type == 2:
                                        -1:
                                            return -1
                                        0:
                                            return 0
                                        1:
                                            return 0
                                1:
                                    return 0
                        0:
                            match left_type == 2:
                                -1:
                                    match right_type == 1:
                                        -1:
                                            return -1
                                        0:
                                            match right_type == 2:
                                                -1:
                                                    return -1
                                                0:
                                                    return 0
                                                1:
                                                    return 0
                                        1:
                                            return 0
                                0:
                                    return 0
                                1:
                                    return 0
                        1:
                            return 0
                0:
                    return -1
                1:
                    return -1
        1:
            return -1

"""
    if marker not in source:
        raise ValueError("Stage04 binary helper marker not found")
    source = source.replace(marker, helper + marker, 1)
    lines = source.splitlines()
    relation_index = next(
        index
        for index, line in enumerate(lines)
        if line.strip() == "mut relation_aux: i64 = -1"
    )
    base = len(lines[relation_index]) - len(lines[relation_index].lstrip())
    validation = [
        " " * base + "match stage04_binary_type_valid(op, left_type, right_type):",
        " " * (base + 4) + "-1:",
        " " * (base + 8) + "discard 0",
        " " * (base + 4) + "0:",
        " " * (base + 8) + "parse_ok = 0",
        " " * (base + 4) + "1:",
        " " * (base + 8) + "parse_ok = 0",
    ]
    lines[relation_index:relation_index] = validation
    return "\n".join(lines) + "\n"


def _repair_stage04_local_mutability_encoding(source: str) -> str:
    marker = "fn stage04_word(start: i64, end: i64, expected_hash: i64, expected_length: i64) -> trit:\n"
    helper = """fn stage04_mutable_flag(value: trit) -> trit:
    match value == -1:
        -1:
            return 1
        0:
            return 0
        1:
            return 0

"""
    if marker not in source:
        raise ValueError("Stage04 mutability helper marker not found")
    source = source.replace(marker, helper + marker, 1)
    old = "value_mutable[value_count] = local_mutable[local_scan]"
    if source.count(old) != 1:
        raise ValueError("Stage04 local mutability assignment is not unique")
    return source.replace(
        old,
        "value_mutable[value_count] = stage04_mutable_flag(local_mutable[local_scan])",
        1,
    )


def _repair_stage04_lexical_scope(source: str) -> str:
    lines = source.splitlines()
    declaration_index = next(
        (
            index
            for index, line in enumerate(lines)
            if line.strip().startswith("mut local_declaration_token: i64[64] = [")
        ),
        None,
    )
    if declaration_index is None:
        raise ValueError("Stage04 local declaration table marker not found")
    declaration_indent = lines[declaration_index][: len(lines[declaration_index]) - len(lines[declaration_index].lstrip())]
    lines.insert(
        declaration_index + 1,
        declaration_indent + "mut local_indent: i64[64] = [" + _zeros(64) + "]",
    )
    source = "\n".join(lines) + "\n"
    assignment = "local_declaration_token[local_count] = declaration_name\n"
    if source.count(assignment) != 1:
        raise ValueError("Stage04 local declaration anchor is not unique")
    source = source.replace(
        assignment,
        assignment + "                                                                            local_indent[local_count] = stage04_indent(token_start[local_probe])\n",
        1,
    )

    lines = source.splitlines()
    declaration_match = next(
        index
        for index, line in enumerate(lines)
        if line.strip() == "match local_declaration_token[local_find] < source_token:"
    )
    base = len(lines[declaration_match]) - len(lines[declaration_match].lstrip())
    true_branch = next(
        index
        for index in range(declaration_match + 1, len(lines))
        if lines[index].strip() == "-1:"
        and len(lines[index]) - len(lines[index].lstrip()) == base + 4
    )
    false_branch = next(
        index
        for index in range(true_branch + 1, len(lines))
        if lines[index].strip() == "0:"
        and len(lines[index]) - len(lines[index].lstrip()) == base + 4
    )
    body = lines[true_branch + 1 : false_branch]
    scoped_body = ["        " + line for line in body]
    lines[true_branch + 1 : false_branch] = [
        " " * (base + 8)
        + "match stage04_indent(token_start[source_token]) >= local_indent[local_find]:",
        " " * (base + 12) + "-1:",
        *scoped_body,
        " " * (base + 12) + "0:",
        " " * (base + 16) + "local_find = local_find - 1",
        " " * (base + 12) + "1:",
        " " * (base + 16) + "local_find = local_find - 1",
    ]
    return "\n".join(lines) + "\n"


def _repair_stage04_immutable_declaration(source: str) -> str:
    marker = "fn stage04_word(start: i64, end: i64, expected_hash: i64, expected_length: i64) -> trit:\n"
    helper = """fn stage04_immutable_declaration(colon: i64, type_kind: i64, equal: i64) -> trit:
    match colon == 3:
        -1:
            match type_kind == 1:
                -1:
                    match equal == 5:
                        -1:
                            return -1
                        0:
                            return 0
                        1:
                            return 0
                0:
                    return 0
                1:
                    return 0
        0:
            return 0
        1:
            return 0

"""
    if marker not in source:
        raise ValueError("Stage04 immutable declaration marker not found")
    source = source.replace(marker, helper + marker, 1)
    lines = source.splitlines()
    match_index = next(
        index
        for index, line in enumerate(lines)
        if line.strip() == "match token_value[to_tryte(name_token + 1)] == 5:"
    )
    match_base = len(lines[match_index]) - len(lines[match_index].lstrip())
    false_branch = next(
        index
        for index in range(match_index + 1, len(lines))
        if lines[index].strip() == "0:"
        and len(lines[index]) - len(lines[index].lstrip()) == match_base + 4
    )
    true_branch = next(
        index
        for index in range(false_branch + 1, len(lines))
        if lines[index].strip() == "1:"
        and len(lines[index]) - len(lines[index].lstrip()) == match_base + 4
    )
    body = [
        " " * (match_base + 8) + "match stage04_immutable_declaration(token_value[to_tryte(name_token + 1)], to_i64(token_kind[to_tryte(name_token + 2)]), token_value[to_tryte(name_token + 3)]):",
        " " * (match_base + 12) + "-1:",
        " " * (match_base + 16) + "mode = 2",
        " " * (match_base + 16) + "expression_start = name_token + 4",
        " " * (match_base + 16) + "mut local_find: i64 = 0",
        " " * (match_base + 16) + "while local_find < local_count:",
        " " * (match_base + 20) + "match local_owner[to_tryte(local_find)] == lower_function:",
        " " * (match_base + 24) + "-1:",
        " " * (match_base + 28) + "match local_declaration_token[to_tryte(local_find)] == name_token:",
        " " * (match_base + 32) + "-1:",
        " " * (match_base + 36) + "target_local = local_find",
        " " * (match_base + 36) + "local_find = local_count",
        " " * (match_base + 32) + "0:",
        " " * (match_base + 36) + "local_find += 1",
        " " * (match_base + 32) + "1:",
        " " * (match_base + 36) + "local_find += 1",
        " " * (match_base + 24) + "0:",
        " " * (match_base + 28) + "local_find += 1",
        " " * (match_base + 24) + "1:",
        " " * (match_base + 28) + "local_find += 1",
        " " * (match_base + 12) + "0:",
        " " * (match_base + 16) + "discard 0",
        " " * (match_base + 12) + "1:",
        " " * (match_base + 16) + "discard 0",
    ]
    lines[false_branch + 1 : true_branch] = body
    return "\n".join(lines) + "\n"


def build_candidate(canonical: str, stream_helpers: str) -> str:
    prefix, marker, _ = canonical.partition("fn main() -> tryte:")
    if not marker:
        raise ValueError("canonical Stage1 main marker not found")
    helper_prefix = stream_helpers.split("fn main() -> i64:", 1)[0]
    helper_prefix = helper_prefix.replace("foreign fn s3_stage1_write_byte(value: tryte) -> tryte\n\n", "")
    main = MAIN
    for literal in range(32):
        main = main.replace(f"to_tryte({literal})", str(literal))
    main = main.replace("__Z32__", _zeros(32)).replace("__Z64__", _zeros(64)).replace("__ZN64__", _zeros(64, "-1")).replace("__Z128__", _zeros(128))
    main = _replace_operator_lowering(main)
    main = _repair_stage04_predicates(main)
    main = _repair_stage04_add_operator_code(main)
    main = _repair_stage04_token_span(main)
    main = _repair_stage04_indentation(main)
    main = _repair_stage04_target_local_predicate(main)
    main = _repair_stage04_comparison_tokens(main)
    main = _repair_stage04_local_probe_progress(main)
    main = _repair_stage04_line_scans(main)
    main = _repair_stage04_statement_progress(main)
    main = _repair_stage04_rpn_progress(main)
    main = _repair_stage04_casts(main)
    main = _repair_stage04_resolved_value_scope(main)
    main = _repair_stage04_literal_types(main)
    main = _repair_stage04_contextual_literal_types(main)
    main = _repair_stage04_unary_type_validation(main)
    main = _repair_stage04_binary_type_validation(main)
    main = _repair_stage04_local_mutability_encoding(main)
    main = _repair_stage04_lexical_scope(main)
    main = _repair_stage04_completion_mask(main)
    main = _cast_stage04_array_indices(main)
    main = _repair_stage04_immutable_declaration(main)
    main = _repair_stage04_mutable_initializer(main)
    operator_helpers = STAGE04_OPERATOR_HELPERS.replace("match op == 5:\n", "match op == 6:\n", 1)
    return prefix.rstrip() + "\n\n" + helper_prefix.rstrip() + "\n\n" + operator_helpers + "\n\n" + main

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=ROOT / "selfhost" / "compiler" / "s3c_stage1.s3")
    args = parser.parse_args()
    canonical = args.source.resolve().read_text(encoding="utf-8")
    stream = (ROOT / "selfhost" / "compiler" / "stage1_semantic_stream_v2.s3").read_text(encoding="utf-8")
    candidate = build_candidate(canonical, stream)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(candidate, encoding="utf-8", newline="\n")
    print(f"OUTPUT={args.output.resolve()}")
    print(f"CANDIDATE_BYTES={len(candidate.encode('utf-8'))}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
