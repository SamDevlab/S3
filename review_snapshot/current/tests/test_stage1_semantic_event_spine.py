"""Focused contracts for the bounded semantic-event V replay observer."""

from __future__ import annotations

import platform
import subprocess
from pathlib import Path

import pytest

from bootstrap.s3 import ir_emulator
from bootstrap.s3.host_services import SourceResourceRuntime
from bootstrap.s3.pipeline import compile_source
from tools.build_stage1_semantic_event_spine import build_stage1


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "selfhost" / "compiler" / "stage1_semantic_event_spine.s3"
CANONICAL_SOURCE = ROOT / "selfhost" / "compiler" / "s3c_stage1.s3"
LINUX_NATIVE = platform.system() == "Linux" and platform.machine().lower() in {
    "x86_64",
    "amd64",
}

BREAK_SIMPLE_SOURCE = b"fn main() -> tryte:\n    mut running: trit = -1\n    while running:\n        break\n    return 0\n"
BREAK_NESTED_INNER_SOURCE = b"fn main() -> tryte:\n    mut outer: trit = -1\n    while outer:\n        mut inner: trit = -1\n        while inner:\n            break\n        outer = 0\n    return 0\n"
COMPARE_RETURN_SOURCE = (
    b"fn main() -> trit:\n"
    b"    mut value: i64 = 1\n"
    b"    return value <=> 2\n"
)
MATCH_COMPARE_SOURCE = (
    b"fn main() -> trit:\n"
    b"    mut value: i64 = 1\n"
    b"    match value <=> 2:\n"
    b"        -1:\n"
    b"            return -1\n"
    b"        0:\n"
    b"            return 0\n"
    b"        1:\n"
    b"            return 1\n"
)
MATCH_CONDITION_CANARIES = (
    (b"match value <=> 2:", 1, 1),
    (b"match value < limit:", 2, 1),
    (b"match read_at(position) <=> 2:", 6, 4),
    (b"match is_digit(read_at(position)):", 4, 4),
    (b"match position + 1 < limit:", 7, 2),
)
CALL_ONE_ARG_SOURCE = (
    b"foreign fn host(x: i64) -> tryte\n"
    b"fn read(x: i64) -> tryte:\n"
    b"    return host(x)\n"
    b"fn main() -> tryte:\n"
    b"    return 7\n"
)
CALL_THREE_ARG_SOURCE = (
    b"fn pack_token(next_cursor: i64, kind: i64, value: i64) -> i64:\n"
    b"    return next_cursor\n"
    b"fn probe(position: i64) -> i64:\n"
    b"    return pack_token(position, 0, 0)\n"
    b"fn main() -> i64:\n"
    b"    return 0\n"
)
CALL_DISCARD_SOURCE = (
    b"foreign fn host(x: i64) -> tryte\n"
    b"fn main() -> i64:\n"
    b"    discard host(1)\n"
    b"    return 0\n"
)
PARAMETER_64_SOURCE = (
    b"fn main("
    b"a0: i64, a1: i64, a2: i64, a3: i64, a4: i64, a5: i64, a6: i64, a7: i64, "
    b"a8: i64, a9: i64, a10: i64, a11: i64, a12: i64, a13: i64, a14: i64, a15: i64, "
    b"a16: i64, a17: i64, a18: i64, a19: i64, a20: i64, a21: i64, a22: i64, a23: i64, "
    b"a24: i64, a25: i64, a26: i64, a27: i64, a28: i64, a29: i64, a30: i64, a31: i64, "
    b"a32: i64, a33: i64, a34: i64, a35: i64, a36: i64, a37: i64, a38: i64, a39: i64, "
    b"a40: i64, a41: i64, a42: i64, a43: i64, a44: i64, a45: i64, a46: i64, a47: i64, "
    b"a48: i64, a49: i64, a50: i64, a51: i64, a52: i64, a53: i64, a54: i64, a55: i64, "
    b"a56: i64, a57: i64, a58: i64, a59: i64, a60: i64, a61: i64, a62: i64, a63: i64) -> i64:\n"
    b"    return 0\n"
)
PARAMETER_65_SOURCE = PARAMETER_64_SOURCE.replace(
    b"a63: i64) -> i64:", b"a63: i64, a64: i64) -> i64:"
)
MATCH_PARAMETER_SOURCE = (
    b"fn classify(unit: tryte) -> trit:\n"
    b"    match unit <=> 48:\n"
    b"        -1:\n"
    b"            return 0\n"
    b"        0:\n"
    b"            return -1\n"
    b"        1:\n"
    b"            return 0\n"
    b"fn main() -> trit:\n"
    b"    return 0\n"
)
MATCH_NESTED_PARAMETER_SOURCE = (
    b"fn classify(unit: tryte) -> trit:\n"
    b"    match unit <=> 48:\n"
    b"        -1:\n"
    b"            return 0\n"
    b"        0:\n"
    b"            return -1\n"
    b"        1:\n"
    b"            match unit <=> 57:\n"
    b"                -1:\n"
    b"                    return 0\n"
    b"                0:\n"
    b"                    return -1\n"
    b"                1:\n"
    b"                    return 0\n"
    b"fn main() -> trit:\n"
    b"    return 0\n"
)
MATCH_NESTED_PARAMETER_CHAIN_SOURCE = (
    b"fn classify(unit: i64) -> trit:\n"
    b"    match unit == 66:\n"
    b"        -1:\n"
    b"            return -1\n"
    b"        0:\n"
    b"            match unit == 313:\n"
    b"                -1:\n"
    b"                    return -1\n"
    b"                0:\n"
    b"                    match unit == 76:\n"
    b"                        -1:\n"
    b"                            return -1\n"
    b"                        0:\n"
    b"                            return 0\n"
    b"                        1:\n"
    b"                            return -1\n"
    b"                1:\n"
    b"                    return 0\n"
    b"        1:\n"
    b"            return 0\n"
    b"fn main() -> trit:\n"
    b"    return 0\n"
)
MATCH_PARAMETER_RELATION_SOURCES = tuple(
    f"fn classify(unit: tryte) -> trit:\n    match unit {operator} 95:\n        -1:\n            return 0\n        0:\n            return -1\n        1:\n            return 0\nfn main() -> trit:\n    return 0\n".encode(
        "ascii"
    )
    for operator in ("<", "<=", ">", ">=", "==", "!=")
)
MATCH_LOCAL_RELATION_SOURCES = tuple(
    f"fn main() -> trit:\n    mut value: i64 = 1\n    match value {operator} 2:\n        -1:\n            return 0\n        0:\n            return -1\n        1:\n            return 0\n".encode(
        "ascii"
    )
    for operator in ("<", "<=", ">", ">=", "==", "!=")
)
WHILE_CONSTANT_SOURCES = (
    b"fn main() -> i64:\n"
    b"    mut value: i64 = 0\n"
    b"    while 0:\n"
    b"        value = 1\n"
    b"    return value\n",
    b"fn main() -> i64:\n"
    b"    mut value: i64 = 0\n"
    b"    while 1:\n"
    b"        value = 1\n"
    b"    return value\n",
)
WHILE_TRUTHY_BREAK_SOURCE = (
    b"fn main() -> tryte:\n"
    b"    mut running: trit = -1\n"
    b"    while running:\n"
    b"        break\n"
    b"    return 0\n"
)
WHILE_COMPARE_INCREMENT_SOURCE = (
    b"fn main() -> i64:\n"
    b"    mut value: i64 = 0\n"
    b"    while value <=> 1:\n"
    b"        value = value + 1\n"
    b"    return value\n"
)
WHILE_DEPENDENT_SOURCE = (
    b"fn main() -> i64:\n"
    b"    mut position: i64 = 0\n"
    b"    mut end: i64 = position + 1\n"
    b"    while position <=> end:\n"
    b"        position = position + 1\n"
    b"    return position\n"
)
WHILE_ITERATION_SOURCES = (
    b"fn main() -> i64:\n"
    b"    mut value: i64 = 1\n"
    b"    while value <=> 1:\n"
    b"        value = value + 1\n"
    b"    return value\n",
    b"fn main() -> i64:\n"
    b"    mut value: i64 = 0\n"
    b"    while value <=> 1:\n"
    b"        value = value + 1\n"
    b"    return value\n",
    b"fn main() -> i64:\n"
    b"    mut value: i64 = -1\n"
    b"    while value <=> 1:\n"
    b"        value = value + 1\n"
    b"    return value\n",
)
RELATIONAL_RETURN_SOURCES = tuple(
    f"fn main() -> trit:\n    mut value: i64 = 1\n    return value {operator} 2\n".encode(
        "ascii"
    )
    for operator in ("<", "<=", ">", ">=", "==", "!=")
)
RELATIONAL_WHILE_SOURCES = tuple(
    f"fn main() -> i64:\n    mut value: i64 = 0\n    while value {operator} 1:\n        value = value + 1\n    return value\n".encode(
        "ascii"
    )
    for operator in ("<", "<=", ">", ">=", "==", "!=")
)
RELATIONAL_WHILE_DEPENDENT_SOURCES = tuple(
    f"fn main() -> i64:\n    mut position: i64 = 0\n    mut end: i64 = position + 1\n    while position {operator} end:\n        position = position + 1\n    return position\n".encode(
        "ascii"
    )
    for operator in ("<", "<=", ">", ">=", "==", "!=")
)
PARAMETER_RIGHT_INCREMENT_SOURCE = (
    b"fn loop(end: i64) -> i64:\n"
    b"    mut cursor: i64 = 0\n"
    b"    while cursor < end:\n"
    b"        cursor += 1\n"
    b"    return cursor\n"
    b"fn main() -> i64:\n"
    b"    return 0\n"
)
MUTABLE_IDENTIFIER_INITIALIZER_SOURCE = (
    b"fn adopt(start: i64) -> i64:\n"
    b"    mut cursor: i64 = start\n"
    b"    return cursor\n"
    b"fn main() -> i64:\n"
    b"    return 0\n"
)
MUTABLE_COMPOUND_PRODUCT_INITIALIZER_SOURCE = (
    b"fn remainder_digit(number: i64, divisor: i64) -> i64:\n"
    b"    mut quotient: i64 = number / divisor\n"
    b"    mut remainder: i64 = number - quotient * divisor\n"
    b"    return remainder\n"
    b"fn main() -> i64:\n"
    b"    return 0\n"
)
MUTABLE_BINARY_LITERAL_INITIALIZER_SOURCE = (
    b"fn quotient_value(value: i64) -> i64:\n"
    b"    mut number: i64 = value\n"
    b"    mut quotient: i64 = number / 100\n"
    b"    return quotient\n"
    b"fn main() -> i64:\n"
    b"    return 0\n"
)
MUTABLE_COMPOUND_PRODUCT_LITERAL_INITIALIZER_SOURCE = (
    b"fn remainder_value(value: i64) -> i64:\n"
    b"    mut number: i64 = value\n"
    b"    mut hundreds: i64 = number / 100\n"
    b"    mut remainder: i64 = number - hundreds * 100\n"
    b"    return remainder\n"
    b"fn main() -> i64:\n"
    b"    return 0\n"
)
MUTABLE_ARRAY_INITIALIZER_SOURCE = (
    b"fn main() -> i64:\n"
    b"    mut values: i64[4] = [0, 0, 0, 0]\n"
    b"    return 0\n"
)
COMPOUND_NESTED_PARAMETER_SOURCE = (
    b"foreign fn sample(cursor: i64) -> tryte\n"
    b"fn fold(start: i64, end: i64) -> i64:\n"
    b"    mut cursor: i64 = start\n"
    b"    mut result: i64 = 0\n"
    b"    while cursor < end:\n"
    b"        result = result * 31 + to_i64(sample(cursor))\n"
    b"        while result >= 365:\n"
    b"            result = result - 365\n"
    b"        cursor += 1\n"
    b"    return result\n"
    b"fn main() -> i64:\n"
    b"    return 0\n"
)
NESTED_MATCH_CALL_WHILE_SOURCE = (
    b"foreign fn read_unit(index: i64) -> tryte\n"
    b"foreign fn is_blank(unit: tryte) -> trit\n"
    b"fn skip_prefix(cursor: i64, limit: i64) -> i64:\n"
    b"    mut position: i64 = cursor\n"
    b"    mut skipping: trit = -1\n"
    b"    while skipping == -1:\n"
    b"        match position < limit:\n"
    b"            -1:\n"
    b"                mut unit: tryte = read_unit(position)\n"
    b"                match is_blank(unit):\n"
    b"                    -1:\n"
    b"                        position += 1\n"
    b"                    0:\n"
    b"                        skipping = 0\n"
    b"                    1:\n"
    b"                        skipping = 0\n"
    b"            0:\n"
    b"                skipping = 0\n"
    b"            1:\n"
    b"                skipping = 0\n"
    b"    return position\n"
    b"fn main() -> i64:\n"
    b"    return 0\n"
)
POST_LOOP_NESTED_MATCH_SUCCESSOR_SOURCE = (
    b"foreign fn read_unit(index: i64) -> tryte\n"
    b"fn scan_prefix(cursor: i64, limit: i64) -> i64:\n"
    b"    mut position: i64 = cursor\n"
    b"    mut skipping: trit = -1\n"
    b"    while skipping == -1:\n"
    b"        match position < limit:\n"
    b"            -1:\n"
    b"                mut unit: tryte = read_unit(position)\n"
    b"                match unit == 32:\n"
    b"                    -1:\n"
    b"                        position += 1\n"
    b"                    0:\n"
    b"                        skipping = 0\n"
    b"                    1:\n"
    b"                        skipping = 0\n"
    b"            0:\n"
    b"                skipping = 0\n"
    b"            1:\n"
    b"                skipping = 0\n"
    b"    mut unit: tryte = read_unit(position)\n"
    b"    mut negative: i64 = 1\n"
    b"    match unit == 45:\n"
    b"        -1:\n"
    b"            match position + 1 < limit:\n"
    b"                -1:\n"
    b"                    negative = -1\n"
    b"                    position += 1\n"
    b"                0:\n"
    b"                    discard 0\n"
    b"                1:\n"
    b"                    discard 0\n"
    b"        0:\n"
    b"            discard 0\n"
    b"        1:\n"
    b"            discard 0\n"
    b"    return position\n"
    b"fn next_function() -> i64:\n"
    b"    return 0\n"
)
NESTED_MATCH_CALL_WHILE_CONTINUATION_SOURCE = (
    b"foreign fn read_unit(index: i64) -> tryte\n"
    b"foreign fn is_blank(unit: tryte) -> trit\n"
    b"fn scan_prefix(limit: i64) -> i64:\n"
    b"    mut position: i64 = 0\n"
    b"    mut skipping: trit = -1\n"
    b"    while skipping == -1:\n"
    b"        match position < limit:\n"
    b"            -1:\n"
    b"                mut unit: tryte = read_unit(position)\n"
    b"                match is_blank(unit):\n"
    b"                    -1:\n"
    b"                        position += 1\n"
    b"                    0:\n"
    b"                        skipping = 0\n"
    b"                    1:\n"
    b"                        skipping = 0\n"
    b"            0:\n"
    b"                skipping = 0\n"
    b"            1:\n"
    b"                skipping = 0\n"
    b"    match position >= limit:\n"
    b"        -1:\n"
    b"            return 0\n"
    b"        0:\n"
    b"            return 0\n"
    b"        1:\n"
    b"            return 0\n"
    b"fn main() -> i64:\n"
    b"    return 0\n"
)
NESTED_MATCH_CALL_WHILE_CALL_CONTINUATION_SOURCE = (
    b"foreign fn read_unit(index: i64) -> tryte\n"
    b"foreign fn is_blank(unit: tryte) -> trit\n"
    b"foreign fn pack_token(position: i64, kind: i64, value: i64) -> i64\n"
    b"fn scan_prefix(limit: i64) -> i64:\n"
    b"    mut position: i64 = 0\n"
    b"    mut skipping: trit = -1\n"
    b"    while skipping == -1:\n"
    b"        match position < limit:\n"
    b"            -1:\n"
    b"                mut unit: tryte = read_unit(position)\n"
    b"                match is_blank(unit):\n"
    b"                    -1:\n"
    b"                        position += 1\n"
    b"                    0:\n"
    b"                        skipping = 0\n"
    b"                    1:\n"
    b"                        skipping = 0\n"
    b"            0:\n"
    b"                skipping = 0\n"
    b"            1:\n"
    b"                skipping = 0\n"
    b"    match position >= limit:\n"
    b"        -1:\n"
    b"            return pack_token(position, 0, 0)\n"
    b"        0:\n"
    b"            return pack_token(position, 0, 0)\n"
    b"        1:\n"
    b"            return pack_token(position, 0, 0)\n"
    b"fn main() -> i64:\n"
    b"    return 0\n"
)
NESTED_MATCH_CALL_WHILE_MIXED_CONTINUATION_SOURCE = (
    b"foreign fn read_unit(index: i64) -> tryte\n"
    b"foreign fn is_blank(unit: tryte) -> trit\n"
    b"foreign fn pack_token(position: i64, kind: i64, value: i64) -> i64\n"
    b"fn scan_token(cursor: i64, limit: i64) -> i64:\n"
    b"    mut position: i64 = cursor\n"
    b"    mut skipping: trit = -1\n"
    b"    while skipping == -1:\n"
    b"        match position < limit:\n"
    b"            -1:\n"
    b"                mut unit: tryte = read_unit(position)\n"
    b"                match is_blank(unit):\n"
    b"                    -1:\n"
    b"                        position += 1\n"
    b"                    0:\n"
    b"                        skipping = 0\n"
    b"                    1:\n"
    b"                        skipping = 0\n"
    b"            0:\n"
    b"                skipping = 0\n"
    b"            1:\n"
    b"                skipping = 0\n"
    b"    match position >= limit:\n"
    b"        -1:\n"
    b"            return pack_token(position, 0, 0)\n"
    b"        0:\n"
    b"            discard 0\n"
    b"        1:\n"
    b"            return pack_token(position, 0, 0)\n"
    b"    return position\n"
    b"fn main() -> i64:\n"
    b"    return 0\n"
)
LOOP_MATCH_BODY_WITH_NEXT_FUNCTION_SOURCE = (
    b"foreign fn read_unit(index: i64) -> tryte\n"
    b"fn classify(unit: tryte) -> trit:\n"
    b"    return 0\n"
    b"fn scan(limit: i64) -> i64:\n"
    b"    mut position: i64 = 0\n"
    b"    mut running: trit = -1\n"
    b"    while running == -1:\n"
    b"        match position < limit:\n"
    b"            -1:\n"
    b"                mut unit: tryte = read_unit(position)\n"
    b"                match classify(unit):\n"
    b"                    -1:\n"
    b"                        position += 1\n"
    b"                    0:\n"
    b"                        running = 0\n"
    b"                    1:\n"
    b"                        running = 0\n"
    b"            0:\n"
    b"                running = 0\n"
    b"            1:\n"
    b"                running = 0\n"
    b"    match position >= limit:\n"
    b"        -1:\n"
    b"            return position\n"
    b"        0:\n"
    b"            discard 0\n"
    b"        1:\n"
    b"            return position\n"
    b"    return position\n"
    b"fn next(limit: i64) -> i64:\n"
    b"    return 0\n"
)
FUNCTION_BOUNDARY_FINALIZATION_SOURCE = (
    b"fn first() -> i64:\n"
    b"    return 0\n"
    b"fn second() -> i64:\n"
    b"    return 0\n"
)
FUNCTION_BOUNDARY_ALL_TERMINAL_MATCH_SOURCE = (
    b"fn classify(unit: tryte) -> trit:\n"
    b"    match unit == 95:\n"
    b"        -1:\n"
    b"            return 0\n"
    b"        0:\n"
    b"            return -1\n"
    b"        1:\n"
    b"            return 0\n"
    b"fn after() -> trit:\n"
    b"    return 0\n"
)
POST_SUCCESSOR_PARAMETER_MATCH_SOURCE = (
    b"foreign fn read_unit(index: i64) -> tryte\n"
    b"foreign fn is_blank(unit: tryte) -> trit\n"
    b"foreign fn pack_token(position: i64, kind: i64, value: i64) -> i64\n"
    b"fn scan_token(cursor: i64, limit: i64) -> i64:\n"
    b"    mut position: i64 = cursor\n"
    b"    mut skipping: trit = -1\n"
    b"    while skipping == -1:\n"
    b"        match position < limit:\n"
    b"            -1:\n"
    b"                mut unit: tryte = read_unit(position)\n"
    b"                match is_blank(unit):\n"
    b"                    -1:\n"
    b"                        position += 1\n"
    b"                    0:\n"
    b"                        skipping = 0\n"
    b"                    1:\n"
    b"                        skipping = 0\n"
    b"            0:\n"
    b"                skipping = 0\n"
    b"            1:\n"
    b"                skipping = 0\n"
    b"    match position >= limit:\n"
    b"        -1:\n"
    b"            return pack_token(position, 0, 0)\n"
    b"        0:\n"
    b"            discard 0\n"
    b"        1:\n"
    b"            return pack_token(position, 0, 0)\n"
    b"    mut tail: tryte = read_unit(position)\n"
    b"    match position >= limit:\n"
    b"        -1:\n"
    b"            return pack_token(position, 0, 0)\n"
    b"        0:\n"
    b"            discard 0\n"
    b"        1:\n"
    b"            return pack_token(position, 0, 0)\n"
    b"    return position\n"
    b"fn main() -> i64:\n"
    b"    return 0\n"
)
POST_SUCCESSOR_MUTABLE_LITERAL_MATCH_SOURCE = (
    b"foreign fn read_unit(index: i64) -> tryte\n"
    b"foreign fn is_blank(unit: tryte) -> trit\n"
    b"foreign fn pack_token(position: i64, kind: i64, value: i64) -> i64\n"
    b"fn scan_token(cursor: i64, limit: i64) -> i64:\n"
    b"    mut position: i64 = cursor\n"
    b"    mut skipping: trit = -1\n"
    b"    while skipping == -1:\n"
    b"        match position < limit:\n"
    b"            -1:\n"
    b"                mut unit: tryte = read_unit(position)\n"
    b"                match is_blank(unit):\n"
    b"                    -1:\n"
    b"                        position += 1\n"
    b"                    0:\n"
    b"                        skipping = 0\n"
    b"                    1:\n"
    b"                        skipping = 0\n"
    b"            0:\n"
    b"                skipping = 0\n"
    b"            1:\n"
    b"                skipping = 0\n"
    b"    match position >= limit:\n"
    b"        -1:\n"
    b"            return pack_token(position, 0, 0)\n"
    b"        0:\n"
    b"            discard 0\n"
    b"        1:\n"
    b"            return pack_token(position, 0, 0)\n"
    b"    mut unit: tryte = read_unit(position)\n"
    b"    match unit == 10:\n"
    b"        -1:\n"
    b"            return pack_token(position + 1, 3, 0)\n"
    b"        0:\n"
    b"            discard 0\n"
    b"        1:\n"
    b"            return pack_token(position + 1, 3, 0)\n"
    b"    return position\n"
    b"fn main() -> i64:\n"
    b"    return 0\n"
)
POST_SUCCESSOR_COMPLEX_PREDICATE_MATCH_SOURCE = (
    b"foreign fn read_at(index: i64) -> tryte\n"
    b"foreign fn is_identifier_start(unit: tryte) -> trit\n"
    b"foreign fn is_identifier_continue(unit: tryte) -> trit\n"
    b"foreign fn identifier_hash(start: i64, end: i64) -> i64\n"
    b"foreign fn pack_token(next_cursor: i64, kind: i64, value: i64) -> i64\n"
    b"fn scan_token(cursor: i64, length: i64) -> i64:\n"
    b"    mut position: i64 = cursor\n"
    b"    match position >= length:\n"
    b"        -1:\n"
    b"            return pack_token(position, 0, 0)\n"
    b"        0:\n"
    b"            discard 0\n"
    b"        1:\n"
    b"            return pack_token(position, 0, 0)\n"
    b"    mut unit: tryte = read_at(position)\n"
    b"    match unit == 10:\n"
    b"        -1:\n"
    b"            return pack_token(position + 1, 3, 0)\n"
    b"        0:\n"
    b"            discard 0\n"
    b"        1:\n"
    b"            discard 0\n"
    b"    match is_identifier_start(unit):\n"
    b"        -1:\n"
    b"            mut end: i64 = position + 1\n"
    b"            while end < length:\n"
    b"                match is_identifier_continue(read_at(end)):\n"
    b"                    -1:\n"
    b"                        end += 1\n"
    b"                    0:\n"
    b"                        break\n"
    b"                    1:\n"
    b"                        break\n"
    b"            return pack_token(end, 1, identifier_hash(position, end))\n"
    b"        0:\n"
    b"            discard 0\n"
    b"        1:\n"
    b"            discard 0\n"
    b"    return position\n"
    b"fn main() -> i64:\n"
    b"    return 0\n"
)
FUNCTION_BOUNDARY_NESTED_CALL_SOURCE = (
    b"foreign fn read_at(index: i64) -> tryte\n"
    b"foreign fn is_digit(unit: tryte) -> trit\n"
    b"foreign fn pack_token(next_cursor: i64, kind: i64, value: i64) -> i64\n"
    b"fn parse_unit(cursor: i64) -> i64:\n"
    b"    mut position: i64 = cursor\n"
    b"    match is_digit(read_at(position)):\n"
    b"        -1:\n"
    b"            return pack_token(position, 0, 0)\n"
    b"        0:\n"
    b"            discard 0\n"
    b"        1:\n"
    b"            discard 0\n"
    b"    return position\n"
    b"fn next_function() -> i64:\n"
    b"    return 0\n"
)
FUNCTION_BOUNDARY_NESTED_CALL_RELATION_SOURCE = (
    b"foreign fn read_at(index: i64) -> tryte\n"
    b"fn first(position: i64) -> i64:\n"
    b"    match read_at(position + 1) == 61:\n"
    b"        -1:\n"
    b"            match read_at(position + 2) == 62:\n"
    b"                -1:\n"
    b"                    return position\n"
    b"                0:\n"
    b"                    discard 0\n"
    b"                1:\n"
    b"                    discard 0\n"
    b"        0:\n"
    b"            discard 0\n"
    b"        1:\n"
    b"            discard 0\n"
    b"    return position\n"
    b"fn second() -> i64:\n"
    b"    return 0\n"
)
FUNCTION_BOUNDARY_ADDITIVE_BUILTIN_CALL_SOURCE = (
    b"foreign fn read_at(index: i64) -> tryte\n"
    b"foreign fn pack_token(next_cursor: i64, kind: i64, value: i64) -> i64\n"
    b"fn parse_unit(cursor: i64) -> i64:\n"
    b"    mut position: i64 = cursor\n"
    b"    mut unit: tryte = 0\n"
    b"    return pack_token(position + 1, 9, to_i64(unit))\n"
    b"fn next_function() -> i64:\n"
    b"    return 0\n"
)
FUNCTION_BOUNDARY_BUILTIN_RETURN_CALL_SOURCE = (
    b"fn digit_value(number: i64, divisor: i64) -> tryte:\n"
    b"    mut quotient: i64 = number / divisor\n"
    b"    mut ascii: i64 = quotient + 48\n"
    b"    return to_tryte(ascii)\n"
    b"fn following(limit: i64) -> i64:\n"
    b"    return 0\n"
    b"fn main() -> i64:\n"
    b"    return 0\n"
)
FUNCTION_BOUNDARY_DECLARED_DISCARD_CALL_SOURCE = (
    b"foreign fn write_byte(value: tryte) -> tryte\n"
    b"fn decimal_value(number: i64) -> tryte:\n"
    b"    return 0\n"
    b"fn emit_name(name: i64) -> trit:\n"
    b"    discard write_byte(115)\n"
    b"    discard decimal_value(name)\n"
    b"    return -1\n"
    b"fn following(limit: i64) -> i64:\n"
    b"    return 0\n"
)
FUNCTION_BOUNDARY_NESTED_MIXED_THREE_WAY_SOURCE = (
    b"foreign fn output_byte(value: tryte) -> tryte\n"
    b"foreign fn digit_value(number: i64, divisor: i64) -> tryte\n"
    b"foreign fn remainder_value(number: i64, divisor: i64) -> tryte\n"
    b"fn render_value(value: i64) -> trit:\n"
    b"    mut number: i64 = value\n"
    b"    match number <=> 10:\n"
    b"        -1:\n"
    b"            discard output_byte(to_tryte(number + 48))\n"
    b"        0:\n"
    b"            discard output_byte(49)\n"
    b"            discard output_byte(48)\n"
    b"        1:\n"
    b"            match number <=> 100:\n"
    b"                -1:\n"
    b"                    discard output_byte(digit_value(number, 10))\n"
    b"                    discard output_byte(remainder_value(number, 10))\n"
    b"                0:\n"
    b"                    discard output_byte(49)\n"
    b"                    discard output_byte(48)\n"
    b"                    discard output_byte(48)\n"
    b"                1:\n"
    b"                    mut hundreds: i64 = number / 100\n"
    b"                    mut remainder: i64 = number - hundreds * 100\n"
    b"                    discard output_byte(to_tryte(hundreds + 48))\n"
    b"                    discard output_byte(digit_value(remainder, 10))\n"
    b"                    discard output_byte(remainder_value(remainder, 10))\n"
    b"    return -1\n"
    b"fn following(limit: i64) -> i64:\n"
    b"    return 0\n"
    b"fn main() -> i64:\n"
    b"    return 0\n"
)
FUNCTION_BOUNDARY_DECIMAL_PIPELINE_SOURCE = (
    b"foreign fn write_byte(value: tryte) -> tryte\n"
    b"fn decimal_value(value: i64) -> trit:\n"
    b"    mut number: i64 = value\n"
    b"    match number < 0:\n"
    b"        -1:\n"
    b"            discard write_byte(45)\n"
    b"            number = 0 - number\n"
    b"        0:\n"
    b"            discard 0\n"
    b"        1:\n"
    b"            discard 0\n"
    b"    match number <=> 10:\n"
    b"        -1:\n"
    b"            discard write_byte(to_tryte(number + 48))\n"
    b"        0:\n"
    b"            discard write_byte(49)\n"
    b"            discard write_byte(48)\n"
    b"        1:\n"
    b"            match number <=> 100:\n"
    b"                -1:\n"
    b"                    discard write_byte(to_tryte(number + 48))\n"
    b"                    discard write_byte(to_tryte(number + 48))\n"
    b"                0:\n"
    b"                    discard write_byte(49)\n"
    b"                    discard write_byte(48)\n"
    b"                    discard write_byte(48)\n"
    b"                1:\n"
    b"                    mut hundreds: i64 = number / 100\n"
    b"                    mut remainder: i64 = number - hundreds * 100\n"
    b"                    discard write_byte(to_tryte(hundreds + 48))\n"
    b"                    discard write_byte(to_tryte(remainder + 48))\n"
    b"                    discard write_byte(to_tryte(remainder + 48))\n"
    b"    return -1\n"
    b"fn following(limit: i64) -> i64:\n"
    b"    return 0\n"
)
COMPOUND_NESTED_MATCH_LOOP_BOUNDARY_SOURCE = (
    b"foreign fn read_unit(index: i64) -> tryte\n"
    b"foreign fn is_numeric(unit: tryte) -> trit\n"
    b"foreign fn pack_value(next_cursor: i64, kind: i64, value: i64) -> i64\n"
    b"fn consume(cursor: i64, limit: i64) -> i64:\n"
    b"    mut position: i64 = cursor\n"
    b"    match is_numeric(read_unit(position)):\n"
    b"        -1:\n"
    b"            mut total: i64 = 0\n"
    b"            while position < limit:\n"
    b"                match is_numeric(read_unit(position)):\n"
    b"                    -1:\n"
    b"                        total = total * 10 + (to_i64(read_unit(position)) - 48)\n"
    b"                        position += 1\n"
    b"                    0:\n"
    b"                        break\n"
    b"                    1:\n"
    b"                        break\n"
    b"            return pack_value(0, 2, 0)\n"
    b"        0:\n"
    b"            discard 0\n"
    b"        1:\n"
    b"            discard 0\n"
    b"    return 0\n"
    b"fn next_function() -> i64:\n"
    b"    return 0\n"
)
NESTED_MATCH_TERMINAL_RETURN_BOUNDARY_SOURCE = (
    b"foreign fn read_at(index: i64) -> tryte\n"
    b"foreign fn is_digit(unit: tryte) -> trit\n"
    b"foreign fn pack_token(next_cursor: i64, kind: i64, value: i64) -> i64\n"
    b"fn parse_unit(cursor: i64, limit: i64) -> i64:\n"
    b"    mut position: i64 = cursor\n"
    b"    mut unit: tryte = read_at(position)\n"
    b"    match unit == 45:\n"
    b"        -1:\n"
    b"            match position + 1 < limit:\n"
    b"                -1:\n"
    b"                    match read_at(position + 1) == 62:\n"
    b"                        -1:\n"
    b"                            return pack_token(position + 2, 4, 12)\n"
    b"                        0:\n"
    b"                            discard 0\n"
    b"                        1:\n"
    b"                            discard 0\n"
    b"                0:\n"
    b"                    discard 0\n"
    b"                1:\n"
    b"                    discard 0\n"
    b"            return pack_token(position + 1, 4, 7)\n"
    b"        0:\n"
    b"            discard 0\n"
    b"        1:\n"
    b"            discard 0\n"
    b"    return position\n"
    b"fn next_function() -> i64:\n"
    b"    return 0\n"
)
MATCH_FALLTHROUGH_ASSIGNMENT_SOURCE = (
    b"fn classify(unit: i64) -> i64:\n"
    b"    mut result: i64 = 0\n"
    b"    match unit < 48:\n"
    b"        -1:\n"
    b"            result = 1\n"
    b"        0:\n"
    b"            result = 2\n"
    b"        1:\n"
    b"            result = 3\n"
    b"    result += 1\n"
    b"    return result\n"
    b"fn main() -> i64:\n"
    b"    return 0\n"
)
MATCH_DYNAMIC_CALL_FALLTHROUGH_SOURCE = (
    b"foreign fn pack_token(position: i64, kind: i64, value: i64) -> i64\n"
    b"fn scan(position: i64, limit: i64) -> i64:\n"
    b"    match position >= limit:\n"
    b"        -1:\n"
    b"            return pack_token(position, 0, 0)\n"
    b"        0:\n"
    b"            discard 0\n"
    b"        1:\n"
    b"            return pack_token(position, 0, 0)\n"
    b"    return 0\n"
    b"fn main() -> i64:\n"
    b"    return 0\n"
)
MUTABLE_CALL_MATCH_SOURCE = (
    b"foreign fn read_unit(index: i64) -> tryte\n"
    b"fn scan(position: i64) -> i64:\n"
    b"    mut unit: tryte = read_unit(position)\n"
    b"    match unit == 10:\n"
    b"        -1:\n"
    b"            return 1\n"
    b"        0:\n"
    b"            discard 0\n"
    b"        1:\n"
    b"            discard 0\n"
    b"    return 0\n"
    b"fn main() -> i64:\n"
    b"    return 0\n"
)
MUTABLE_CALL_PREDICATE_MATCH_SOURCE = (
    b"foreign fn read_unit(index: i64) -> tryte\n"
    b"foreign fn is_identifier_start(value: i64) -> trit\n"
    b"fn scan(position: i64) -> i64:\n"
    b"    mut unit: tryte = read_unit(position)\n"
    b"    match is_identifier_start(unit):\n"
    b"        -1:\n"
    b"            return 1\n"
    b"        0:\n"
    b"            discard 0\n"
    b"        1:\n"
    b"            discard 0\n"
    b"    return 0\n"
    b"fn main() -> i64:\n"
    b"    return 0\n"
)
COMPLEX_PREDICATE_MATCH_WHILE_SOURCE = (
    b"foreign fn read_at(index: i64) -> tryte\n"
    b"foreign fn is_identifier_start(value: i64) -> trit\n"
    b"foreign fn is_identifier_continue(value: tryte) -> trit\n"
    b"foreign fn identifier_hash(start: i64, end: i64) -> i64\n"
    b"foreign fn pack_token(next_cursor: i64, kind: i64, value: i64) -> i64\n"
    b"fn scan(cursor: i64, length: i64) -> i64:\n"
    b"    mut unit: tryte = read_at(cursor)\n"
    b"    match is_identifier_start(unit):\n"
    b"        -1:\n"
    b"            mut end: i64 = cursor + 1\n"
    b"            while end < length:\n"
    b"                match is_identifier_continue(read_at(end)):\n"
    b"                    -1:\n"
    b"                        end += 1\n"
    b"                    0:\n"
    b"                        break\n"
    b"                    1:\n"
    b"                        break\n"
    b"            return pack_token(end, 1, identifier_hash(cursor, end))\n"
    b"        0:\n"
    b"            discard 0\n"
    b"        1:\n"
    b"            discard 0\n"
    b"    return 0\n"
    b"fn main() -> i64:\n"
    b"    return 0\n"
)
TOP_LEVEL_PREDICATE_MATCH_WHILE_SOURCE = (
    b"foreign fn read_at(index: i64) -> tryte\n"
    b"foreign fn is_identifier_continue(value: tryte) -> trit\n"
    b"foreign fn identifier_hash(start: i64, end: i64) -> i64\n"
    b"foreign fn pack_token(next_cursor: i64, kind: i64, value: i64) -> i64\n"
    b"fn scan(cursor: i64, length: i64) -> i64:\n"
    b"    mut end: i64 = cursor + 1\n"
    b"    while end < length:\n"
    b"        match is_identifier_continue(read_at(end)):\n"
    b"            -1:\n"
    b"                end += 1\n"
    b"            0:\n"
    b"                break\n"
    b"            1:\n"
    b"                break\n"
    b"    return pack_token(end, 1, identifier_hash(cursor, end))\n"
    b"fn main() -> i64:\n"
    b"    return 0\n"
)
LOCAL_HASH_POSITION_RETURN_SOURCE = (
    b"foreign fn read_at(index: i64) -> tryte\n"
    b"foreign fn is_identifier_continue(value: tryte) -> trit\n"
    b"foreign fn identifier_hash(start: i64, end: i64) -> i64\n"
    b"foreign fn pack_token(next_cursor: i64, kind: i64, value: i64) -> i64\n"
    b"fn scan(cursor: i64, length: i64) -> i64:\n"
    b"    mut position: i64 = cursor\n"
    b"    mut end: i64 = cursor + 1\n"
    b"    while end < length:\n"
    b"        match is_identifier_continue(read_at(end)):\n"
    b"            -1:\n"
    b"                end += 1\n"
    b"            0:\n"
    b"                break\n"
    b"            1:\n"
    b"                break\n"
    b"    return pack_token(end, 1, identifier_hash(position, end))\n"
    b"fn main() -> i64:\n"
    b"    return 0\n"
)
MATCH_FALLTHROUGH_TERMINATING_ARM_SOURCE = (
    b"fn classify(unit: i64) -> i64:\n"
    b"    mut result: i64 = 0\n"
    b"    match unit < 48:\n"
    b"        -1:\n"
    b"            return 0\n"
    b"        0:\n"
    b"            result = 2\n"
    b"        1:\n"
    b"            result = 3\n"
    b"    result += 1\n"
    b"    return result\n"
    b"fn main() -> i64:\n"
    b"    return 0\n"
)
MIXED_MATCH_IN_LOOP_SOURCE = (
    b"foreign fn pack_token(position: i64, kind: i64, value: i64) -> i64\n"
    b"fn scan(limit: i64) -> i64:\n"
    b"    mut position: i64 = 0\n"
    b"    while position < limit:\n"
    b"        match position <=> limit:\n"
    b"            -1:\n"
    b"                return pack_token(position, 0, 0)\n"
    b"            0:\n"
    b"                discard 0\n"
    b"            1:\n"
    b"                return pack_token(position, 0, 0)\n"
    b"        position += 1\n"
    b"    return position\n"
    b"fn main() -> i64:\n"
    b"    return 0\n"
)
MIXED_MATCH_IN_LOOP_LITERAL_SOURCE = (
    b"fn scan(limit: i64) -> i64:\n"
    b"    mut position: i64 = 0\n"
    b"    while position < limit:\n"
    b"        match position < 1:\n"
    b"            -1:\n"
    b"                return -1\n"
    b"            0:\n"
    b"                discard 0\n"
    b"            1:\n"
    b"                return 1\n"
    b"        position += 1\n"
    b"    return position\n"
    b"fn main() -> i64:\n"
    b"    return 0\n"
)
MIXED_MATCH_IN_LOOP_BREAK_SOURCE = (
    b"fn scan(limit: i64) -> i64:\n"
    b"    mut position: i64 = 0\n"
    b"    while position < limit:\n"
    b"        match position < 1:\n"
    b"            -1:\n"
    b"                break\n"
    b"            0:\n"
    b"                discard 0\n"
    b"            1:\n"
    b"                discard 0\n"
    b"        position += 1\n"
    b"    return position\n"
    b"fn main() -> i64:\n"
    b"    return 0\n"
)
NESTED_MATCH_IN_OUTER_MATCH_SOURCE = (
    b"fn choose(value: i64) -> i64:\n"
    b"    mut result: i64 = 0\n"
    b"    match value < 1:\n"
    b"        -1:\n"
    b"            match value < 2:\n"
    b"                -1:\n"
    b"                    result = 1\n"
    b"                0:\n"
    b"                    result = 2\n"
    b"                1:\n"
    b"                    result = 3\n"
    b"            result += 1\n"
    b"        0:\n"
    b"            return -1\n"
    b"        1:\n"
    b"            return 1\n"
    b"    return result\n"
    b"fn main() -> i64:\n"
    b"    return 0\n"
)


def _fixture_cases() -> list[tuple[str, bytes, tuple[tuple[int, ...], ...]]]:
    literal = b"fn main() -> tryte:\n    return 7\n"
    parameter = b"fn main() -> tryte:\n    return 0\nfn identity(x: i64) -> i64:\n    return x\n"
    multi_parameter = b"fn pair(first: i64, second: i64) -> i64:\n    return second\nfn main() -> tryte:\n    return 7\n"
    local = b"fn main() -> tryte:\n    mut value: tryte = 7\n    return value\n"
    local_identifier = b"fn identity(start: i64) -> i64:\n    mut cursor: i64 = start\n    return cursor\nfn main() -> tryte:\n    return 7\n"
    loop = b"fn f(start: i64) -> i64:\n    mut cursor: i64 = start\n    while cursor < 10:\n        cursor += 1\n    return cursor\nfn main() -> tryte:\n    return 7\n"
    multi = b"fn first(x: i64) -> i64:\n    return x\nfn main() -> tryte:\n    mut value: tryte = 7\n    return value\n"
    foreign = b"foreign fn host() -> i64\nfn main() -> tryte:\n    return 7\n"
    call = b"foreign fn host(x: i64) -> tryte\nfn read(x: i64) -> tryte:\n    return host(x)\nfn main() -> tryte:\n    return 7\n"
    call_internal = b"fn is_digit(unit: tryte) -> trit:\n    return 0\nfn wrapper(unit: tryte) -> trit:\n    return is_digit(unit)\nfn main() -> trit:\n    return 0\n"
    call_three_arguments = b"fn pack_token(next_cursor: i64, kind: i64, value: i64) -> i64:\n    return next_cursor\nfn probe(position: i64) -> i64:\n    return pack_token(position, 0, 0)\nfn main() -> i64:\n    return 0\n"
    match = b"fn is_digit(unit: tryte) -> trit:\n    match unit <=> 48:\n        -1:\n            return 0\n        0:\n            return -1\n        1:\n            return 0\nfn main() -> trit:\n    return 0\n"
    match_second_return = match.index(b"return", match.index(b"return") + 1)
    return [
        (
            "literal",
            literal,
            ((0, 0, 3, 2, literal.index(b"7"), 0, 0, -1),),
        ),
        (
            "parameter",
            parameter,
            (
                (0, 0, 3, 2, parameter.index(b"0"), 0, 0, -1),
                (1, 1, 1, 3, parameter.index(b"x"), 1, 0, -1),
            ),
        ),
        (
            "multi_parameter",
            multi_parameter,
            (
                (0, 0, 1, 3, multi_parameter.index(b"first"), 5, 0, -1),
                (1, 0, 1, 3, multi_parameter.index(b"second"), 6, 0, -1),
                (2, 1, 3, 2, multi_parameter.index(b"7"), 0, 0, -1),
            ),
        ),
        (
            "local",
            local,
            (
                (0, 0, 3, 2, local.index(b"7"), 0, 0, -1),
                (1, 0, 3, 2, local.index(b"mut"), 0, 0, -1),
                (2, 0, 3, 2, local.index(b"value", local.index(b"return")), 0, 0, -1),
                (3, 0, 4, 2, local.index(b"value", local.index(b"return")), 0, 0, -1),
                (4, 0, 2, 2, local.index(b"value"), 5, 1, -1),
            ),
        ),
        (
            "local_identifier",
            local_identifier,
            (
                (0, 0, 1, 3, local_identifier.index(b"start"), 5, 0, -1),
                (1, 0, 3, 2, local_identifier.index(b"mut"), 0, 0, -1),
                (2, 0, 3, 2, local_identifier.index(b"cursor", local_identifier.index(b"return")), 0, 0, -1),
                (3, 0, 4, 3, local_identifier.index(b"cursor", local_identifier.index(b"return")), 0, 0, -1),
                (4, 0, 2, 3, local_identifier.index(b"cursor"), 6, 1, -1),
                (5, 1, 3, 2, local_identifier.index(b"7"), 0, 0, -1),
            ),
        ),
        (
            "while_increment",
            loop,
            (
                (0, 0, 1, 3, 5, 5, 0, -1),
                (1, 0, 3, 2, 29, 0, 0, -1),
                (2, 0, 3, 2, 63, 0, 0, -1),
                (3, 0, 4, 3, 63, 0, 0, -1),
                (4, 0, 3, 3, 72, 0, 0, -1),
                (5, 0, 4, 1, 70, 0, 0, -1),
                (6, 0, 3, 2, 70, 0, 0, -1),
                (7, 0, 3, 1, 70, 0, 0, -1),
                (8, 0, 3, 2, 70, 0, 0, -1),
                (9, 0, 3, 1, 70, 0, 0, -1),
                (10, 0, 3, 2, 70, 0, 0, -1),
                (11, 0, 3, 1, 70, 0, 0, -1),
                (12, 0, 3, 2, 70, 0, 0, -1),
                (13, 0, 4, 1, 70, 0, 0, -1),
                (14, 0, 3, 2, 84, 0, 0, -1),
                (15, 0, 4, 3, 84, 0, 0, -1),
                (16, 0, 3, 3, 94, 0, 0, -1),
                (17, 0, 4, 3, 84, 0, 0, -1),
                (18, 0, 3, 2, 84, 0, 0, -1),
                (19, 0, 3, 3, 107, 0, 0, -1),
                (20, 0, 4, 3, 107, 0, 0, -1),
                (21, 1, 3, 2, 145, 0, 0, -1),
                (22, 0, 2, 3, 33, 6, 1, -1),
            ),
        ),
        (
            "multi",
            multi,
            (
                (0, 0, 1, 3, multi.index(b"x"), 1, 0, -1),
                (1, 1, 3, 2, multi.index(b"7"), 0, 0, -1),
                (2, 1, 3, 2, multi.index(b"mut", multi.index(b"fn main")), 0, 0, -1),
                (3, 1, 3, 2, multi.index(b"value", multi.index(b"return")), 0, 0, -1),
                (4, 1, 4, 2, multi.index(b"value", multi.index(b"return")), 0, 0, -1),
                (5, 1, 2, 2, multi.index(b"value", multi.index(b"fn main")), 5, 1, -1),
            ),
        ),
        (
            "foreign_header",
            foreign,
            ((0, 0, 3, 2, foreign.index(b"7"), 0, 0, -1),),
        ),
        (
            "call_return",
            call,
            (
                (0, 0, 1, 3, call.index(b"x", call.index(b"fn read")), 1, 0, -1),
                (1, 0, 4, 2, call.index(b"host", call.index(b"return")), 0, 0, -1),
                (2, 1, 3, 2, call.index(b"7"), 0, 0, -1),
                (3, 2, 1, 3, call.index(b"x"), 1, 0, -1),
            ),
        ),
        (
            "call_internal",
            call_internal,
            (
                (0, 0, 1, 2, call_internal.index(b"unit", call_internal.index(b"fn is_digit")), 4, 0, -1),
                (1, 0, 3, 1, call_internal.index(b"0"), 0, 0, -1),
                (2, 1, 1, 2, call_internal.index(b"unit", call_internal.index(b"fn wrapper")), 4, 0, -1),
                (3, 1, 4, 1, call_internal.index(b"is_digit"), 0, 0, -1),
                (4, 2, 3, 1, call_internal.rindex(b"0"), 0, 0, -1),
            ),
        ),
        (
            "call_three_arguments",
            call_three_arguments,
            (
                (0, 0, 1, 3, call_three_arguments.index(b"next_cursor"), 11, 0, -1),
                (1, 0, 1, 3, call_three_arguments.index(b"kind"), 4, 0, -1),
                (2, 0, 1, 3, call_three_arguments.index(b"value"), 5, 0, -1),
                (3, 1, 1, 3, call_three_arguments.index(b"position"), 8, 0, -1),
                (
                    4,
                    1,
                    3,
                    2,
                    call_three_arguments.index(b"position", call_three_arguments.index(b"return pack_token")),
                    0,
                    0,
                    -1,
                ),
                (
                    5,
                    1,
                    4,
                    3,
                    call_three_arguments.index(b"position", call_three_arguments.index(b"return pack_token")),
                    0,
                    0,
                    -1,
                ),
                (
                    6,
                    1,
                    3,
                    3,
                    call_three_arguments.index(b"0", call_three_arguments.index(b"return pack_token")),
                    0,
                    0,
                    -1,
                ),
                (
                    7,
                    1,
                    3,
                    3,
                    call_three_arguments.index(b"0", call_three_arguments.index(b"return pack_token") + 1),
                    0,
                    0,
                    -1,
                ),
                (
                    8,
                    1,
                    4,
                    3,
                    call_three_arguments.index(b"pack_token", call_three_arguments.index(b"return pack_token")),
                    0,
                    0,
                    -1,
                ),
                (9, 2, 3, 3, call_three_arguments.rindex(b"0"), 0, 0, -1),
            ),
        ),
        (
            "match_comparison",
            match,
            (
                (0, 0, 1, 2, match.index(b"unit"), 4, 0, -1),
                (1, 0, 3, 2, match.index(b"48"), 0, 0, -1),
                (2, 0, 4, 1, match.index(b"<=>"), 0, 0, -1),
                (3, 0, 3, 1, match.index(b"0"), 0, 0, -1),
                (4, 0, 3, 1, match.index(b"-1", match_second_return), 0, 0, -1),
                (5, 0, 3, 1, match.index(b"0", match_second_return + 1), 0, 0, -1),
                (6, 1, 3, 1, match.index(b"0", match.index(b"fn main")), 0, 0, -1),
            ),
        ),
    ]


def _host_register_count(source: bytes) -> int:
    compilation = compile_source(source.decode("ascii"), "O0")
    count = 0
    for function in compilation.ir.functions:
        count += len(function.registers)
    return count


def _parse_rows(stderr: bytes) -> tuple[tuple[int, ...], ...]:
    rows: list[tuple[int, ...]] = []
    for line in stderr.decode("ascii").splitlines():
        if line.strip() == "S3IR2 3":
            break
        fields = line.split()
        if not fields or fields[0] != "V":
            continue
        values: list[int] = []
        for field in fields[1:]:
            values.append(int(field))
        rows.append(tuple(values))
    return tuple(rows)


def _parse_semantic_records(stderr: bytes) -> dict[str, list[tuple[int, ...]]]:
    records: dict[str, list[tuple[int, ...]]] = {}
    for line in stderr.decode("ascii").splitlines():
        if line.strip() == "S3IR2 3":
            break
        fields = line.split()
        if not fields or fields[0] not in {"D", "M", "V"}:
            continue
        records.setdefault(fields[0], []).append(tuple(int(field) for field in fields[1:]))
    return records


def _parse_v3_stream(stdout: bytes) -> dict[str, list[tuple[int, ...]]]:
    lines = stdout.decode("ascii").splitlines()
    assert lines and lines[0] == "S3IR2 3"
    records: dict[str, list[tuple[int, ...]]] = {}
    for line in lines[1:]:
        fields = line.split()
        assert fields
        records.setdefault(fields[0], []).append(
            tuple(int(field) for field in fields[1:])
        )
    return records


def _hosted_candidate_v3_stream(
    source: bytes, *, entry_point: str = "scan_program"
) -> dict[str, list[tuple[int, ...]]]:
    candidate = compile_source(SOURCE_PATH.read_text(encoding="utf-8"), "O0")
    ir_emulator.functions_module = candidate.ir
    ir_emulator.resource_runtime = SourceResourceRuntime()
    functions = {function.name: function for function in candidate.ir.functions}
    output = bytearray()
    original_execute = ir_emulator._execute_function

    def execute(functions_module, function, arguments, caller):
        name = function.name
        if name == "s3_stage1_source_length":
            return len(source)
        if name == "s3_stage1_read_byte":
            index = arguments[0]
            return source[index] if 0 <= index < len(source) else 0
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
        arguments = (2, 0) if entry_point == "scan_program" else ()
        original_execute(functions, functions[entry_point], arguments, ())
    finally:
        ir_emulator._execute_function = original_execute
    if entry_point == "scan_program":
        return _parse_v3_stream(b"S3IR2 3\n" + bytes(output))
    return _parse_v3_stream(bytes(output))


def _hosted_candidate_parameter_count(source: bytes) -> int:
    candidate = compile_source(SOURCE_PATH.read_text(encoding="utf-8"), "O0")
    ir_emulator.functions_module = candidate.ir
    ir_emulator.resource_runtime = SourceResourceRuntime()
    functions = {function.name: function for function in candidate.ir.functions}
    original_execute = ir_emulator._execute_function

    def execute(functions_module, function, arguments, caller):
        name = function.name
        if name == "s3_stage1_source_length":
            return len(source)
        if name == "s3_stage1_read_byte":
            index = arguments[0]
            return source[index] if 0 <= index < len(source) else 0
        return original_execute(functions_module, function, arguments, caller)

    ir_emulator._execute_function = execute
    try:
        return original_execute(functions, functions["count_program_parameters"], (), ())
    finally:
        ir_emulator._execute_function = original_execute


_HOSTED_CANDIDATE_CACHE = None


def _hosted_candidate_functions():
    global _HOSTED_CANDIDATE_CACHE
    if _HOSTED_CANDIDATE_CACHE is None:
        candidate = compile_source(SOURCE_PATH.read_text(encoding="utf-8"), "O0")
        _HOSTED_CANDIDATE_CACHE = (candidate.ir, {function.name: function for function in candidate.ir.functions})
    return _HOSTED_CANDIDATE_CACHE


def _hosted_candidate_function(name: str, source: bytes, arguments: tuple[int, ...]) -> int:
    functions_module, functions = _hosted_candidate_functions()
    ir_emulator.functions_module = functions_module
    ir_emulator.resource_runtime = SourceResourceRuntime()
    original_execute = ir_emulator._execute_function

    def execute(functions_module, function, function_arguments, caller):
        function_name = function.name
        if function_name == "s3_stage1_source_length":
            return len(source)
        if function_name == "s3_stage1_read_byte":
            index = function_arguments[0]
            return source[index] if 0 <= index < len(source) else 0
        return original_execute(functions_module, function, function_arguments, caller)

    ir_emulator._execute_function = execute
    try:
        return original_execute(functions, functions[name], arguments, ())
    finally:
        ir_emulator._execute_function = original_execute


def _hosted_candidate_validation(source: bytes) -> int:
    candidate = compile_source(SOURCE_PATH.read_text(encoding="utf-8"), "O0")
    ir_emulator.functions_module = candidate.ir
    ir_emulator.resource_runtime = SourceResourceRuntime()
    functions = {function.name: function for function in candidate.ir.functions}
    original_execute = ir_emulator._execute_function

    def execute(functions_module, function, arguments, caller):
        name = function.name
        if name == "s3_stage1_source_length":
            return len(source)
        if name == "s3_stage1_read_byte":
            index = arguments[0]
            return source[index] if 0 <= index < len(source) else 0
        return original_execute(functions_module, function, arguments, caller)

    ir_emulator._execute_function = execute
    try:
        return original_execute(functions, functions["scan_program"], (0, 0), ())
    finally:
        ir_emulator._execute_function = original_execute


@pytest.mark.parametrize(
    ("source", "expected_count", "expected_validation"),
    (
        (PARAMETER_64_SOURCE, 64, 0),
        (PARAMETER_65_SOURCE, -1, -1),
    ),
)
def test_candidate_parameter_capacity_is_global_and_fail_closed(
    source: bytes,
    expected_count: int,
    expected_validation: int,
) -> None:
    assert _hosted_candidate_parameter_count(source) == expected_count
    assert _hosted_candidate_validation(source) == expected_validation


def test_event_spine_source_is_streaming_and_bounded() -> None:
    source = SOURCE_PATH.read_text(encoding="utf-8")
    assert "S3_STAGE1_SEMANTIC_EVENT_SPINE" in source
    assert "while cursor < length" in source
    assert "value_id: i64[" not in source
    assert "value_records" not in source
    assert "__Z" not in source


def test_match_condition_descriptor_covers_existing_expression_families() -> None:
    for source, expected_kind, expected_expression_kind in MATCH_CONDITION_CANARIES:
        descriptor = _hosted_candidate_function(
            "match_condition_descriptor", source, (0, len(source))
        )
        assert descriptor > 0
        assert _hosted_candidate_function("match_condition_kind", source, (descriptor,)) == expected_kind
        assert (
            _hosted_candidate_function(
                "match_condition_expression_kind", source, (descriptor,)
            )
            == expected_expression_kind
        )


def test_match_arm_effect_and_successor_protocol_are_shared() -> None:
    assert _hosted_candidate_function("match_arm_effect", b"return 0", (0, 8)) == 1
    assert _hosted_candidate_function("match_arm_effect", b"discard 0", (0, 9)) == 2
    assert _hosted_candidate_function("match_arm_effect", b"value = 1", (0, 9)) == 3

    continuation = _hosted_candidate_function(
        "match_result_continuation", b"", (41, 1234, 7)
    )
    assert _hosted_candidate_function("lowering_result_kind", b"", (continuation,)) == 3
    assert _hosted_candidate_function("lowering_result_next_block", b"", (continuation,)) == 7
    assert _hosted_candidate_function("lowering_result_next_id", b"", (continuation,)) == 41
    assert _hosted_candidate_function("lowering_result_next_cursor", b"", (continuation,)) == 1234


def test_candidate_c_a_residency_is_direct_stream_with_scalar_replay() -> None:
    source = SOURCE_PATH.read_text(encoding="utf-8")
    assert source.count("fn emit_v3_c(") == 1
    assert source.count("fn emit_v3_a(") == 1
    assert source.count("emit_v3_c(") > 1
    assert source.count("emit_v3_a(") > 1
    assert "call_records" not in source
    assert "argument_records" not in source
    assert "call_bank" not in source
    assert "argument_bank" not in source
    assert "ir_capacity_ok" not in source
    assert "730" not in source
    assert "746" not in source
    assert "scan_program(0, 0)" in source
    assert "scan_program(1, 0)" in source
    assert "scan_program(2, 0)" in source


def _assert_streamed_call_edges_are_closed(
    records: dict[str, list[tuple[int, ...]]],
) -> None:
    instruction_ids = {row[0] for row in records["I"]}
    value_ids = {row[0] for row in records["V"]}
    calls = records["C"]
    arguments = records["A"]
    assert calls
    assert arguments
    for instruction_id, _callee, _kind, _start, _length in calls:
        assert instruction_id in instruction_ids
    by_instruction: dict[int, list[int]] = {}
    for instruction_id, ordinal, value_id in arguments:
        assert instruction_id in instruction_ids
        assert value_id in value_ids
        by_instruction.setdefault(instruction_id, []).append(ordinal)
    for ordinals in by_instruction.values():
        assert ordinals == list(range(len(ordinals)))


@pytest.mark.parametrize(
    "source",
    (CALL_ONE_ARG_SOURCE, CALL_THREE_ARG_SOURCE, CALL_DISCARD_SOURCE),
)
def test_candidate_c_a_stream_closes_instruction_and_value_references(
    source: bytes,
) -> None:
    records = _hosted_candidate_v3_stream(source)
    _assert_streamed_call_edges_are_closed(records)


def test_candidate_c_a_replay_is_deterministic_without_resident_records() -> None:
    first = _hosted_candidate_v3_stream(CALL_THREE_ARG_SOURCE)
    second = _hosted_candidate_v3_stream(CALL_THREE_ARG_SOURCE)
    assert first == second
    _assert_streamed_call_edges_are_closed(first)


def test_candidate_v3_emits_joined_cfg_for_dynamic_mixed_match_in_loop() -> None:
    compilation = compile_source(MIXED_MATCH_IN_LOOP_SOURCE.decode("ascii"), "O0")
    function = next(function for function in compilation.ir.functions if function.name == "scan")
    assert any(instruction.opcode.value == "branch3" for block in function.blocks for instruction in block.instructions)

    records = _hosted_candidate_v3_stream(MIXED_MATCH_IN_LOOP_SOURCE)
    assert records["F"]
    function_blocks = [row for row in records["B"] if row[0] == 0]
    function_instructions = [row for row in records["I"] if row[1] == 0]
    function_instruction_ids = {row[0] for row in function_instructions}
    all_instruction_ids = {row[0] for row in records["I"]}
    assert {0, 1, 2, 3, 4, 6, 7, 8, 9, 10, 11, 12, 13, 14} <= {
        row[1] for row in function_blocks
    }
    for row in function_blocks:
        assert row[4] in function_instruction_ids
    jump_targets = {
        row[2]
        for row in records["T"]
        if row[0] in function_instruction_ids and row[1] == 2
    }
    assert {1, 9, 10, 14} <= jump_targets
    assert len(records["C"]) == 2
    assert len(records["A"]) == 6
    assert records.get("Z", []) == []


def test_candidate_v3_emits_dynamic_match_call_fallthrough() -> None:
    records = _hosted_candidate_v3_stream(MATCH_DYNAMIC_CALL_FALLTHROUGH_SOURCE)
    function_blocks = [row for row in records["B"] if row[0] == 0]
    function_instructions = [row for row in records["I"] if row[1] == 0]
    function_instruction_ids = {row[0] for row in function_instructions}
    assert len(function_blocks) == 5
    assert {row[1] for row in function_blocks} == set(range(5))
    assert all(row[4] in function_instruction_ids for row in function_blocks)
    assert len(records["C"]) == 2
    assert len(records["A"]) == 6
    assert any(row[1] == 2 and row[2] == 4 for row in records["T"])


def test_candidate_v3_resolves_storage_for_call_initialized_match_operand() -> None:
    records = _hosted_candidate_v3_stream(MUTABLE_CALL_MATCH_SOURCE)
    function_blocks = [row for row in records["B"] if row[0] == 0]
    function_instructions = [row for row in records["I"] if row[1] == 0]
    function_instruction_ids = {row[0] for row in function_instructions}
    assert len(function_blocks) >= 5
    assert all(row[4] in function_instruction_ids for row in function_blocks)
    assert any(row[1] == 1 for row in records["T"] if row[0] in function_instruction_ids)


def test_candidate_v3_accepts_byte_value_in_predicate_match() -> None:
    records = _hosted_candidate_v3_stream(MUTABLE_CALL_PREDICATE_MATCH_SOURCE)
    function_blocks = [row for row in records["B"] if row[0] == 0]
    function_instructions = [row for row in records["I"] if row[1] == 0]
    function_instruction_ids = {row[0] for row in function_instructions}
    assert len(function_blocks) >= 5
    assert all(row[4] in function_instruction_ids for row in function_blocks)
    assert any(row[1] == 1 for row in records["T"] if row[0] in function_instruction_ids)


def test_candidate_v3_emits_complex_predicate_match_while_return() -> None:
    records = _hosted_candidate_v3_stream(COMPLEX_PREDICATE_MATCH_WHILE_SOURCE)
    function_blocks = [row for row in records["B"] if row[0] == 0]
    function_instructions = [row for row in records["I"] if row[1] == 0]
    function_instruction_ids = {row[0] for row in function_instructions}
    assert len(function_blocks) >= 12
    assert {row[4] for row in function_instructions} >= {1, 5, 14, 15, 16, 23, 24, 25}
    assert all(row[4] in function_instruction_ids for row in function_blocks)
    assert len(records["C"]) == 6
    assert len(records["A"]) >= 5
    assert any(row[1] == 2 and row[2] >= 10 for row in records["T"])


def test_candidate_v3_emits_top_level_predicate_match_while_return() -> None:
    records = _hosted_candidate_v3_stream(TOP_LEVEL_PREDICATE_MATCH_WHILE_SOURCE)
    function_blocks = []
    function_instructions = []
    for row in records["B"]:
        if row[0] == 0:
            function_blocks.append(row)
    for row in records["I"]:
        if row[1] == 0:
            function_instructions.append(row)
    assert records
    assert len(function_blocks) >= 8
    assert {row[4] for row in function_instructions} >= {1, 14, 15, 23, 24, 25}
    assert len(records["C"]) >= 3
    assert len(records["A"]) >= 3


def test_candidate_v3_loads_local_hash_position_before_nested_return() -> None:
    records = _hosted_candidate_v3_stream(LOCAL_HASH_POSITION_RETURN_SOURCE)
    function_instructions = [row for row in records["I"] if row[1] == 0]
    instruction_ids = {row[0] for row in records["I"]}
    assert len([row for row in records["B"] if row[0] == 0]) >= 8
    assert sum(row[4] == 15 for row in function_instructions) >= 2
    assert len(records["C"]) >= 2
    assert all(row[0] in instruction_ids for row in records["O"])
    assert all(row[0] in instruction_ids for row in records["R"])


def test_candidate_v3_emits_joined_cfg_for_literal_mixed_match_in_loop() -> None:
    compilation = compile_source(
        MIXED_MATCH_IN_LOOP_LITERAL_SOURCE.decode("ascii"), "O0"
    )
    function = next(function for function in compilation.ir.functions if function.name == "scan")
    assert len(function.blocks) == 18
    records = _hosted_candidate_v3_stream(MIXED_MATCH_IN_LOOP_LITERAL_SOURCE)
    function_blocks = [row for row in records["B"] if row[0] == 0]
    function_instructions = [row for row in records["I"] if row[1] == 0]
    function_instruction_ids = {row[0] for row in function_instructions}
    function_values = [row for row in records["V"] if row[1] == 0]
    all_instruction_ids = {row[0] for row in records["I"]}
    all_value_ids = {row[0] for row in records["V"]}
    function_terminators = [
        row for row in records["T"] if row[0] in function_instruction_ids
    ]
    block_ids = {row[1] for row in function_blocks}
    assert {0, 1, 2, 3, 4, 6, 7, 8, 9, 10, 11, 12, 13, 14} <= block_ids
    assert len(block_ids) == 15
    assert all(row[4] in function_instruction_ids for row in function_blocks)
    assert len({row[0] for row in function_terminators}) == len(function_terminators)
    jumps = [row for row in function_terminators if row[1] == 2]
    assert any(row[2] == 1 for row in jumps)
    assert any(row[2] >= 10 for row in jumps)


def test_candidate_v3_distinguishes_break_target_from_match_successor() -> None:
    compilation = compile_source(
        MIXED_MATCH_IN_LOOP_BREAK_SOURCE.decode("ascii"), "O0"
    )
    function = next(function for function in compilation.ir.functions if function.name == "scan")
    assert any(
        instruction.opcode.value == "branch3"
        for block in function.blocks
        for instruction in block.instructions
    )
    records = _hosted_candidate_v3_stream(MIXED_MATCH_IN_LOOP_BREAK_SOURCE)
    function_blocks = [row for row in records["B"] if row[0] == 0]
    function_instruction_ids = {row[0] for row in records["I"] if row[1] == 0}
    assert {row[1] for row in function_blocks} >= set(range(16))
    assert all(row[4] in function_instruction_ids for row in function_blocks)
    jumps = [row for row in records["T"] if row[0] in function_instruction_ids and row[1] == 2]
    targets = {row[2] for row in jumps}
    assert 1 in targets
    assert 5 in targets
    assert 6 in targets
    assert 15 in targets


def test_candidate_v3_emits_nested_match_successor_and_outer_continuation() -> None:
    compilation = compile_source(
        NESTED_MATCH_IN_OUTER_MATCH_SOURCE.decode("ascii"), "O0"
    )
    function = next(function for function in compilation.ir.functions if function.name == "choose")
    assert len(function.blocks) == 17
    records = _hosted_candidate_v3_stream(NESTED_MATCH_IN_OUTER_MATCH_SOURCE)
    function_blocks = [row for row in records["B"] if row[0] == 0]
    function_instructions = [row for row in records["I"] if row[1] == 0]
    function_instruction_ids = {row[0] for row in function_instructions}
    assert {row[1] for row in function_blocks} >= set(range(10))
    assert any(row[4] == 24 for row in function_instructions)
    assert all(row[4] in function_instruction_ids for row in function_blocks)
    assert any(row[1] == 2 and row[2] >= 9 for row in records["T"])


@pytest.mark.parametrize("name,source,expected", _fixture_cases())
def test_hosted_event_contract_matches_register_and_binding_counts(
    name: str,
    source: bytes,
    expected: tuple[tuple[int, ...], ...],
) -> None:
    host_rows: list[tuple[int, ...]] = []
    for row in expected:
        if row[2] != 2:
            host_rows.append(row)
    if name == "call_three_arguments":
        # The call-use pair is a semantic observation in addition to IR registers.
        assert _host_register_count(source) == len(host_rows) - 2
    else:
        assert _host_register_count(source) == len(host_rows)
    assert len(expected) >= len(host_rows)
    for row in expected:
        assert row[1] >= 0
        assert row[3] > 0
        assert row[7] == -1


@pytest.mark.skipif(not LINUX_NATIVE, reason="requires Linux x86-64 native execution")
def test_native_event_spine_matches_hosted_fixture_contracts(tmp_path: Path) -> None:
    executable = build_stage1(tmp_path / "s3c-stage1-semantic-event-spine")
    for _name, source, expected in _fixture_cases():
        result = subprocess.run(
            [str(executable)],
            input=source,
            capture_output=True,
            check=False,
            shell=False,
        )
        assert result.returncode == 0
        assert result.stdout == b""
        assert _parse_rows(result.stderr) == expected


@pytest.mark.skipif(not LINUX_NATIVE, reason="requires Linux x86-64 native execution")
@pytest.mark.parametrize("literal", (0, 1, 42))
def test_native_v3_const_return_is_lossless_and_not_literal_specific(
    tmp_path: Path,
    literal: int,
) -> None:
    executable = build_stage1(tmp_path / f"s3c-stage1-v3-const-{literal}")
    source = f"fn main() -> i64:\n    return {literal}\n".encode("ascii")
    result = subprocess.run(
        [str(executable)],
        input=source,
        capture_output=True,
        check=False,
        shell=False,
    )
    assert result.returncode == 0
    records = _parse_v3_stream(result.stdout)
    assert records["F"] == [(0, 1, source.index(b"main"), 4, 0, 1)]
    assert records["B"] == [(0, 0, 0, 2, 1)]
    assert records["V"] == [(0, 0, 2, 3, source.index(str(literal).encode("ascii")), 0, 0, -1)]
    assert records["I"] == [
        (0, 0, 0, 0, 1, 1, 0, -1, literal),
        (1, 0, 0, 1, 23, 0, 1, -1, -1),
    ]
    assert records["O"] == [(1, 0, 0)]
    assert records["R"] == [(0, 0, 0)]
    assert records["T"] == [(1, 1, -1, -1, -1, -1, 0)]
    assert records["Z"] == [(15,)]


@pytest.mark.skipif(not LINUX_NATIVE, reason="requires Linux x86-64 native execution")
def test_native_v3_immutable_initializer_preserves_const_move_and_return_edges(
    tmp_path: Path,
) -> None:
    executable = build_stage1(tmp_path / "s3c-stage1-v3-immutable-local")
    source = b"fn main() -> i64:\n    value: i64 = 1\n    return value\n"
    result = subprocess.run(
        [str(executable)],
        input=source,
        capture_output=True,
        check=False,
        shell=False,
    )
    assert result.returncode == 0
    records = _parse_v3_stream(result.stdout)
    assert records["F"] == [(0, 1, source.index(b"main"), 4, 0, 1)]
    assert records["B"] == [(0, 0, 0, 3, 2)]
    assert records["D"] == [
        (source.index(b"value"), 0, 2, 3, source.index(b"value"), 5, 0, 1, 1)
    ]
    assert records["V"] == [
        (0, 0, 2, 3, source.index(b"1"), 0, 0, -1),
        (1, 0, 3, 3, source.index(b"value"), 0, 0, -1),
    ]
    assert records["I"] == [
        (0, 0, 0, 0, 1, 1, 0, -1, 1),
        (1, 0, 0, 1, 3, 1, 1, -1, -1),
        (2, 0, 0, 2, 23, 0, 1, -1, -1),
    ]
    assert records["O"] == [(1, 0, 0), (2, 0, 1)]
    assert records["R"] == [(0, 0, 0), (1, 0, 1)]
    assert records["T"] == [(2, 1, -1, -1, -1, -1, 1)]
    values = {row[0] for row in records["V"]}
    assert all(row[2] in values for row in records["O"])
    assert all(row[2] in values for row in records["R"])
    assert records["Z"] == [(15,)]


@pytest.mark.skipif(not LINUX_NATIVE, reason="requires Linux x86-64 native execution")
@pytest.mark.parametrize(("left", "right", "total"), ((1, 2, 3), (40, 2, 42)))
def test_native_v3_immutable_additive_initializer_preserves_folded_expression(
    tmp_path: Path,
    left: int,
    right: int,
    total: int,
) -> None:
    executable = build_stage1(tmp_path / f"s3c-stage1-v3-immutable-add-{left}-{right}")
    source = f"fn main() -> i64:\n    value: i64 = {left} + {right}\n    return value\n".encode("ascii")
    result = subprocess.run(
        [str(executable)],
        input=source,
        capture_output=True,
        check=False,
        shell=False,
    )
    assert result.returncode == 0
    records = _parse_v3_stream(result.stdout)
    operator = source.index(b"+")
    assert records["F"] == [(0, 1, source.index(b"main"), 4, 0, 1)]
    assert records["B"] == [(0, 0, 0, 3, 2)]
    assert records["D"] == [
        (source.index(b"value"), 0, 2, 3, source.index(b"value"), 5, 0, 1, 1)
    ]
    assert records["V"] == [
        (0, 0, 2, 3, operator, 0, 0, -1),
        (1, 0, 3, 3, source.index(b"value"), 0, 0, -1),
    ]
    assert records["I"] == [
        (0, 0, 0, 0, 1, 1, 0, -1, total),
        (1, 0, 0, 1, 3, 1, 1, -1, -1),
        (2, 0, 0, 2, 23, 0, 1, -1, -1),
    ]
    assert records["O"] == [(1, 0, 0), (2, 0, 1)]
    assert records["R"] == [(0, 0, 0), (1, 0, 1)]
    assert records["T"] == [(2, 1, -1, -1, -1, -1, 1)]
    assert records["Z"] == [(15,)]


@pytest.mark.skipif(not LINUX_NATIVE, reason="requires Linux x86-64 native execution")
def test_native_v3_immutable_dependent_add_preserves_operand_order_and_binding_target(
    tmp_path: Path,
) -> None:
    executable = build_stage1(tmp_path / "s3c-stage1-v3-immutable-dependent-add")
    source = (
        b"fn main() -> i64:\n"
        b"    a: i64 = 1\n"
        b"    b: i64 = a + 2\n"
        b"    return b\n"
    )
    result = subprocess.run(
        [str(executable)],
        input=source,
        capture_output=True,
        check=False,
        shell=False,
    )
    assert result.returncode == 0
    records = _parse_v3_stream(result.stdout)
    assert records["F"] == [(0, 1, source.index(b"main"), 4, 0, 1)]
    assert records["B"] == [(0, 0, 0, 6, 5)]
    assert records["D"] == [
        (source.index(b"a"), 0, 2, 3, source.index(b"a"), 1, 0, 1, 1),
        (source.index(b"b"), 0, 2, 3, source.index(b"b"), 1, 0, 1, 4),
    ]
    assert records["V"] == [
        (0, 0, 2, 3, source.index(b"1"), 0, 0, -1),
        (1, 0, 3, 3, source.index(b"a"), 0, 0, -1),
        (2, 0, 2, 3, source.index(b"2"), 0, 0, -1),
        (3, 0, 3, 3, source.index(b"+"), 0, 0, -1),
        (4, 0, 3, 3, source.index(b"b"), 0, 0, -1),
    ]
    assert records["I"] == [
        (0, 0, 0, 0, 1, 1, 0, -1, 1),
        (1, 0, 0, 1, 3, 1, 1, -1, -1),
        (2, 0, 0, 2, 1, 1, 0, -1, 2),
        (3, 0, 0, 3, 5, 1, 2, -1, -1),
        (4, 0, 0, 4, 3, 1, 1, -1, -1),
        (5, 0, 0, 5, 23, 0, 1, -1, -1),
    ]
    assert records["O"] == [
        (1, 0, 0),
        (3, 0, 1),
        (3, 1, 2),
        (4, 0, 3),
        (5, 0, 4),
    ]
    assert records["R"] == [(0, 0, 0), (1, 0, 1), (2, 0, 2), (3, 0, 3), (4, 0, 4)]
    assert records["T"] == [(5, 1, -1, -1, -1, -1, 4)]
    assert records["Z"] == [(15,)]
    add_results = [row[2] for row in records["R"] if row[0] == 3]
    assert add_results == [3]
    assert records["O"][1:3] == [(3, 0, 1), (3, 1, 2)]


@pytest.mark.skipif(not LINUX_NATIVE, reason="requires Linux x86-64 native execution")
def test_native_v3_mutable_literal_uses_storage_and_load_provenance(
    tmp_path: Path,
) -> None:
    executable = build_stage1(tmp_path / "s3c-stage1-v3-mutable-literal")
    source = b"fn main() -> i64:\n    mut value: i64 = 1\n    return value\n"
    result = subprocess.run(
        [str(executable)],
        input=source,
        capture_output=True,
        check=False,
        shell=False,
    )
    assert result.returncode == 0
    records = _parse_v3_stream(result.stdout)
    declaration_start = source.index(b"mut")
    name_start = source.index(b"value")
    use_start = source.index(b"value", source.index(b"return"))
    assert records["F"] == [(0, 1, source.index(b"main"), 4, 0, 1)]
    assert records["B"] == [(0, 0, 0, 6, 5)]
    assert records["D"] == [(0, 0, 2, 3, name_start, 5, 1, 2, 0)]
    assert records["V"] == [
        (0, 0, 2, 3, source.index(b"1"), 0, 0, -1),
        (1, 0, 2, 2, declaration_start, 0, 0, -1),
        (2, 0, 2, 2, use_start, 0, 0, -1),
        (3, 0, 3, 3, use_start, 0, 0, -1),
    ]
    assert records["M"] == [(0, 0, 3, 1, 1, declaration_start)]
    assert records["I"] == [
        (0, 0, 0, 0, 1, 1, 0, -1, 1),
        (1, 0, 0, 1, 1, 1, 0, -1, 0),
        (2, 0, 0, 2, 16, 0, 2, 0, -1),
        (3, 0, 0, 3, 1, 1, 0, -1, 0),
        (4, 0, 0, 4, 15, 1, 1, 0, -1),
        (5, 0, 0, 5, 23, 0, 1, -1, -1),
    ]
    assert records["O"] == [
        (2, 0, 1),
        (2, 1, 0),
        (4, 0, 2),
        (5, 0, 3),
    ]
    assert records["R"] == [(0, 0, 0), (1, 0, 1), (3, 0, 2), (4, 0, 3)]
    assert records["T"] == [(5, 1, -1, -1, -1, -1, 3)]
    assert records["Z"] == [(15,)]


def test_hosted_v3_compare_return_is_a_real_trit_result() -> None:
    compilation = compile_source(COMPARE_RETURN_SOURCE.decode("ascii"), "O0")
    function = compilation.ir.functions[0]
    assert len(function.blocks) == 1
    assert [instruction.opcode.value for instruction in function.blocks[0].instructions] == [
        "const",
        "const",
        "store",
        "const",
        "load",
        "const",
        "compare",
        "return",
    ]
    compare = function.blocks[0].instructions[6]
    assert compare.operands == (3, 4)
    assert function.registers[5].type.value == "trit"


def test_hosted_v3_one_argument_call_has_callee_and_argument_edges() -> None:
    compilation = compile_source(CALL_ONE_ARG_SOURCE.decode("ascii"), "O0")
    function = next(function for function in compilation.ir.functions if function.name == "read")
    call = function.blocks[0].instructions[0]
    assert call.opcode.value == "call"
    assert call.callee == "host"
    assert call.operands == (0,)
    assert call.results == (1,)


def test_candidate_v3_one_argument_call_emits_callee_and_argument_edges() -> None:
    records = _hosted_candidate_v3_stream(CALL_ONE_ARG_SOURCE)
    call_start = CALL_ONE_ARG_SOURCE.index(b"host", CALL_ONE_ARG_SOURCE.index(b"return"))
    assert records["C"] == [(0, 0, 2, call_start, 4)]
    assert records["A"] == [(0, 0, 0)]
    assert records["I"][:2] == [
        (0, 0, 0, 0, 14, 1, 1, -1, -1),
        (1, 0, 0, 1, 23, 0, 1, -1, -1),
    ]
    assert records["O"][:2] == [(0, 0, 0), (1, 0, 1)]
    assert records["R"][:1] == [(0, 0, 1)]
    assert records["T"][:1] == [(1, 1, -1, -1, -1, -1, 1)]


def test_candidate_v3_zero_initialized_fixed_array_emits_bounded_storage() -> None:
    records = _hosted_candidate_v3_stream(MUTABLE_ARRAY_INITIALIZER_SOURCE)
    declaration_start = MUTABLE_ARRAY_INITIALIZER_SOURCE.index(b"values")
    first = MUTABLE_ARRAY_INITIALIZER_SOURCE.index(b"mut values")
    bindings = [row for row in records["D"] if row[2] == 2]
    assert bindings == [(0, 0, 2, 10, declaration_start, 6, 1, 2, 0)]
    assert records["M"] == [(0, 0, 3, 4, 1, first)]
    array_initializer_values = []
    for row in records["V"]:
        if row[2] == 2 and row[4] == first:
            array_initializer_values.append(row)
    assert array_initializer_values == []


def test_hosted_v3_three_argument_call_preserves_ordered_operands() -> None:
    compilation = compile_source(CALL_THREE_ARG_SOURCE.decode("ascii"), "O0")
    function = next(function for function in compilation.ir.functions if function.name == "probe")
    instructions = function.blocks[0].instructions
    assert [instruction.opcode.value for instruction in instructions] == [
        "const",
        "const",
        "call",
        "return",
    ]
    call = instructions[2]
    assert call.callee == "pack_token"
    assert call.operands == (0, 1, 2)
    assert call.results == (3,)


def test_candidate_v3_three_argument_call_emits_ordered_callee_and_argument_edges() -> None:
    records = _hosted_candidate_v3_stream(CALL_THREE_ARG_SOURCE)
    call_start = CALL_THREE_ARG_SOURCE.index(
        b"pack_token", CALL_THREE_ARG_SOURCE.index(b"return pack_token")
    )
    assert records["C"] == [(1000002, 0, 1, call_start, 10)]
    assert records["A"] == [
        (1000002, 0, 3),
        (1000002, 1, 4),
        (1000002, 2, 5),
    ]
    assert records["I"][:4] == [
        (0, 0, 0, 0, 23, 0, 1, -1, -1),
        (1000000, 1, 0, 0, 1, 1, 0, -1, 0),
        (1000001, 1, 0, 1, 1, 1, 0, -1, 0),
        (1000002, 1, 0, 2, 14, 1, 3, -1, -1),
    ]
    assert records["O"] == [
        (0, 0, 0),
        (1000002, 0, 3),
        (1000002, 1, 4),
        (1000002, 2, 5),
        (1000003, 0, 6),
        (2000001, 0, 7),
    ]
    assert records["R"] == [
        (1000000, 0, 4),
        (1000001, 0, 5),
        (1000002, 0, 6),
        (2000000, 0, 7),
    ]
    assert records["T"] == [
        (0, 1, -1, -1, -1, -1, 0),
        (1000003, 1, -1, -1, -1, -1, 6),
        (2000001, 1, -1, -1, -1, -1, 7),
    ]


def test_hosted_v3_discard_call_retains_call_result_producer() -> None:
    compilation = compile_source(CALL_DISCARD_SOURCE.decode("ascii"), "O0")
    function = next(function for function in compilation.ir.functions if function.name == "main")
    instructions = function.blocks[0].instructions
    assert [instruction.opcode.value for instruction in instructions] == [
        "const",
        "call",
        "const",
        "return",
    ]
    call = instructions[1]
    assert call.callee == "host"
    assert call.operands == (0,)
    assert call.results == (1,)


def test_candidate_v3_discard_call_emits_callee_argument_and_result_edges() -> None:
    records = _hosted_candidate_v3_stream(CALL_DISCARD_SOURCE)
    call_start = CALL_DISCARD_SOURCE.index(b"host", CALL_DISCARD_SOURCE.index(b"discard"))
    assert records["C"] == [(1, 0, 2, call_start, 4)]
    assert records["A"] == [(1, 0, 0)]
    assert records["I"] == [
        (0, 0, 0, 0, 1, 1, 0, -1, 1),
        (1, 0, 0, 1, 14, 1, 1, -1, -1),
        (2, 0, 0, 2, 1, 1, 0, -1, 0),
        (3, 0, 0, 3, 23, 0, 1, -1, -1),
    ]
    assert records["O"] == [(1, 0, 0), (3, 0, 2)]
    assert records["R"] == [(0, 0, 0), (1, 0, 1), (2, 0, 2)]


@pytest.mark.skipif(not LINUX_NATIVE, reason="requires Linux x86-64 native execution")
def test_native_v3_compare_return_preserves_compare_producer_and_edges(
    tmp_path: Path,
) -> None:
    executable = build_stage1(tmp_path / "s3c-stage1-v3-compare-return")
    result = subprocess.run(
        [str(executable)],
        input=COMPARE_RETURN_SOURCE,
        capture_output=True,
        check=False,
        shell=False,
    )
    assert result.returncode == 0
    records = _parse_v3_stream(result.stdout)
    declaration_start = COMPARE_RETURN_SOURCE.index(b"mut")
    name_start = COMPARE_RETURN_SOURCE.index(b"value")
    use_start = COMPARE_RETURN_SOURCE.index(b"value", COMPARE_RETURN_SOURCE.index(b"return"))
    operator = COMPARE_RETURN_SOURCE.index(b"<=>")
    assert records["F"] == [(0, 1, COMPARE_RETURN_SOURCE.index(b"main"), 4, 0, 1)]
    assert records["B"] == [(0, 0, 0, 8, 7)]
    assert records["D"] == [(0, 0, 2, 3, name_start, 5, 1, 2, 0)]
    assert records["M"] == [(0, 0, 3, 1, 1, declaration_start)]
    assert records["V"] == [
        (0, 0, 2, 3, COMPARE_RETURN_SOURCE.index(b"1"), 0, 0, -1),
        (1, 0, 2, 2, declaration_start, 0, 0, -1),
        (2, 0, 2, 2, use_start, 0, 0, -1),
        (3, 0, 3, 3, use_start, 0, 0, -1),
        (4, 0, 2, 3, COMPARE_RETURN_SOURCE.index(b"2"), 0, 0, -1),
        (5, 0, 3, 1, operator, 0, 0, -1),
    ]
    assert records["I"] == [
        (0, 0, 0, 0, 1, 1, 0, -1, 1),
        (1, 0, 0, 1, 1, 1, 0, -1, 0),
        (2, 0, 0, 2, 16, 0, 2, 0, -1),
        (3, 0, 0, 3, 1, 1, 0, -1, 0),
        (4, 0, 0, 4, 15, 1, 1, 0, -1),
        (5, 0, 0, 5, 1, 1, 0, -1, 2),
        (6, 0, 0, 6, 13, 1, 2, -1, -1),
        (7, 0, 0, 7, 23, 0, 1, -1, -1),
    ]
    assert records["O"] == [
        (2, 0, 1),
        (2, 1, 0),
        (4, 0, 2),
        (6, 0, 3),
        (6, 1, 4),
        (7, 0, 5),
    ]
    assert records["R"] == [
        (0, 0, 0),
        (1, 0, 1),
        (3, 0, 2),
        (4, 0, 3),
        (5, 0, 4),
        (6, 0, 5),
    ]
    assert records["T"] == [(7, 1, -1, -1, -1, -1, 5)]
    assert records["Z"] == [(15,)]


def test_hosted_v3_match_compare_preserves_relation_lanes() -> None:
    compilation = compile_source(MATCH_COMPARE_SOURCE.decode("ascii"), "O0")
    function = compilation.ir.functions[0]
    assert [block.name for block in function.blocks] == [
        "entry",
        "switch_negative_0",
        "switch_neutral_1",
        "switch_positive_2",
    ]
    entry = function.blocks[0].instructions
    assert [instruction.opcode.value for instruction in entry] == [
        "const",
        "const",
        "store",
        "const",
        "load",
        "const",
        "compare",
        "branch3",
    ]
    assert entry[-1].operands == (5,)
    assert entry[-1].targets == (
        "switch_negative_0",
        "switch_neutral_1",
        "switch_positive_2",
    )
    assert [block.instructions[0].immediate for block in function.blocks[1:]] == [
        -1,
        0,
        1,
    ]


def test_hosted_v3_parameter_match_compares_without_storage_load() -> None:
    compilation = compile_source(MATCH_PARAMETER_SOURCE.decode("ascii"), "O0")
    function = compilation.ir.functions[0]
    assert len(function.parameters) == 1
    assert len(function.registers) == 6
    assert [block.name for block in function.blocks] == [
        "entry",
        "switch_negative_0",
        "switch_neutral_1",
        "switch_positive_2",
    ]
    entry = function.blocks[0].instructions
    assert [instruction.opcode.value for instruction in entry] == [
        "const",
        "compare",
        "branch3",
    ]
    assert entry[1].operands == (0, 1)
    assert entry[2].operands == (2,)
    assert [block.instructions[0].immediate for block in function.blocks[1:]] == [
        0,
        -1,
        0,
    ]


def test_hosted_v3_nested_parameter_match_keeps_outer_positive_edge() -> None:
    compilation = compile_source(MATCH_NESTED_PARAMETER_SOURCE.decode("ascii"), "O0")
    function = compilation.ir.functions[0]
    assert len(function.blocks) == 7
    assert len(function.registers) == 10
    assert [block.name for block in function.blocks] == [
        "entry",
        "switch_negative_0",
        "switch_neutral_1",
        "switch_positive_2",
        "switch_negative_3",
        "switch_neutral_4",
        "switch_positive_5",
    ]
    assert function.blocks[0].instructions[-1].targets == (
        "switch_negative_0",
        "switch_neutral_1",
        "switch_positive_2",
    )
    assert function.blocks[3].instructions[-1].targets == (
        "switch_negative_3",
        "switch_neutral_4",
        "switch_positive_5",
    )


def test_candidate_v3_nested_parameter_match_emits_complete_tree() -> None:
    records = _hosted_candidate_v3_stream(MATCH_NESTED_PARAMETER_SOURCE)
    function_blocks = [row for row in records["B"] if row[0] == 0]
    function_values = [row for row in records["V"] if row[1] == 0]
    function_instructions = [row for row in records["I"] if row[1] == 0]
    function_instruction_ids = {row[0] for row in function_instructions}
    function_terminators = [
        row for row in records["T"] if row[0] in function_instruction_ids
    ]
    function_operands = [
        row for row in records["O"] if row[0] in function_instruction_ids
    ]
    function_results = [
        row for row in records["R"] if row[0] in function_instruction_ids
    ]
    assert len(function_blocks) == 7
    assert len(function_values) == 10
    assert len(function_instructions) == 16
    assert len(function_terminators) == 7
    assert len([row for row in function_terminators if row[1] == 3]) == 2
    assert len([row for row in function_terminators if row[1] == 1]) == 5
    value_ids = {row[0] for row in function_values}
    assert all(row[2] in value_ids for row in function_operands)
    assert all(row[2] in value_ids for row in function_results)


def test_candidate_v3_nested_parameter_match_chain_reaches_complete_tree() -> None:
    records = _hosted_candidate_v3_stream(MATCH_NESTED_PARAMETER_CHAIN_SOURCE)
    function_blocks = []
    for row in records["B"]:
        if row[0] == 0:
            function_blocks.append(row)
    function_values = []
    for row in records["V"]:
        if row[1] == 0:
            function_values.append(row)
    function_instructions = []
    for row in records["I"]:
        if row[1] == 0:
            function_instructions.append(row)
    function_instruction_ids = set()
    for row in function_instructions:
        function_instruction_ids.add(row[0])
    function_terminators = []
    for row in records["T"]:
        if row[0] in function_instruction_ids:
            function_terminators.append(row)
    function_operands = []
    for row in records["O"]:
        if row[0] in function_instruction_ids:
            function_operands.append(row)
    function_results = []
    for row in records["R"]:
        if row[0] in function_instruction_ids:
            function_results.append(row)
    assert len(function_blocks) == 10
    assert len(function_values) == 14
    assert len(function_instructions) == 23
    assert len(function_terminators) == 10
    value_ids = set()
    for row in function_values:
        value_ids.add(row[0])
    for row in function_operands:
        assert row[2] in value_ids
    for row in function_results:
        assert row[2] in value_ids


def test_candidate_v3_mutable_identifier_initializer_binds_parameter_storage() -> None:
    records = _hosted_candidate_v3_stream(MUTABLE_IDENTIFIER_INITIALIZER_SOURCE)
    function_values = [row for row in records.get("V", []) if row[1] == 0]
    function_instructions = [row for row in records.get("I", []) if row[1] == 0]
    function_instruction_ids = {row[0] for row in function_instructions}
    function_operands = [
        row for row in records.get("O", []) if row[0] in function_instruction_ids
    ]
    function_results = [
        row for row in records.get("R", []) if row[0] in function_instruction_ids
    ]
    assert records
    assert len(function_values) == 4
    assert len(function_instructions) == 5
    assert [row[4] for row in function_instructions] == [1, 16, 1, 15, 23]
    assert (1, 0, 1) in function_operands
    assert (1, 1, 0) in function_operands
    assert all(row[2] in {row[0] for row in function_values} for row in function_operands)
    assert all(row[2] in {row[0] for row in function_values} for row in function_results)


def test_candidate_v3_mutable_compound_product_initializer_preserves_dataflow() -> None:
    records = _hosted_candidate_v3_stream(MUTABLE_COMPOUND_PRODUCT_INITIALIZER_SOURCE)
    function_instructions = [row for row in records["I"] if row[1] == 0]
    function_values = [row for row in records["V"] if row[1] == 0]
    function_instruction_ids = {row[0] for row in function_instructions}
    function_operands = [
        row for row in records["O"] if row[0] in function_instruction_ids
    ]
    function_results = [
        row for row in records["R"] if row[0] in function_instruction_ids
    ]
    assert [row[4] for row in function_instructions] == [
        8,
        1,
        16,
        1,
        15,
        7,
        6,
        1,
        16,
        1,
        15,
        23,
    ]
    assert len(function_values) == 11
    value_ids = {row[0] for row in function_values}
    assert all(row[2] in value_ids for row in function_operands)
    assert all(row[2] in value_ids for row in function_results)


def test_candidate_v3_mutable_binary_literal_initializer_preserves_dataflow() -> None:
    records = _hosted_candidate_v3_stream(MUTABLE_BINARY_LITERAL_INITIALIZER_SOURCE)
    function_instructions = [row for row in records["I"] if row[1] == 0]
    function_values = [row for row in records["V"] if row[1] == 0]
    function_instruction_ids = {row[0] for row in function_instructions}
    function_operands = [
        row for row in records["O"] if row[0] in function_instruction_ids
    ]
    function_results = [
        row for row in records["R"] if row[0] in function_instruction_ids
    ]
    assert [row[4] for row in function_instructions] == [
        1,
        16,
        1,
        15,
        1,
        8,
        1,
        16,
        1,
        15,
        23,
    ]
    assert len(function_values) >= 5
    value_ids = {row[0] for row in function_values}
    assert all(row[2] in value_ids for row in function_operands)
    assert all(row[2] in value_ids for row in function_results)


def test_candidate_v3_mutable_compound_product_literal_initializer_preserves_dataflow() -> None:
    records = _hosted_candidate_v3_stream(
        MUTABLE_COMPOUND_PRODUCT_LITERAL_INITIALIZER_SOURCE
    )
    function_instructions = [row for row in records["I"] if row[1] == 0]
    function_values = [row for row in records["V"] if row[1] == 0]
    function_instruction_ids = {row[0] for row in function_instructions}
    function_operands = [
        row for row in records["O"] if row[0] in function_instruction_ids
    ]
    function_results = [
        row for row in records["R"] if row[0] in function_instruction_ids
    ]
    assert [row[4] for row in function_instructions] == [
        1,
        16,
        1,
        15,
        1,
        8,
        1,
        16,
        1,
        15,
        1,
        15,
        1,
        7,
        6,
        1,
        16,
        1,
        15,
        23,
    ]
    assert len(function_values) >= 13
    value_ids = {row[0] for row in function_values}
    assert all(row[2] in value_ids for row in function_operands)
    assert all(row[2] in value_ids for row in function_results)


def test_hosted_v3_compound_nested_parameter_loop_has_call_and_inner_loop() -> None:
    compilation = compile_source(COMPOUND_NESTED_PARAMETER_SOURCE.decode("ascii"), "O0")
    function = next(function for function in compilation.ir.functions if function.name == "fold")
    assert len(function.blocks) == 19
    assert len(function.registers) == 50
    assert function.blocks[1].instructions[-1].opcode.value == "branch3"
    assert [instruction.opcode.value for instruction in function.blocks[2].instructions[:-1]] == [
        "const",
        "load",
        "const",
        "multiply",
        "const",
        "load",
        "call",
        "convert",
        "add",
        "const",
        "store",
    ]
    assert function.blocks[2].instructions[-1].opcode.value == "jump"
    calls = [
        instruction
        for block in function.blocks
        for instruction in block.instructions
        if instruction.opcode.value == "call"
    ]
    assert [(call.callee, call.operands, call.results) for call in calls] == [
        ("sample", (21,), (22,)),
    ]
    assert [instruction.opcode.value for instruction in function.blocks[10].instructions][-2:] == [
        "compare",
        "branch3",
    ]
    assert "numeric_difference" in [
        instruction.opcode.value for instruction in function.blocks[11].instructions
    ]


def test_candidate_v3_compound_nested_parameter_loop_emits_complete_graph() -> None:
    records = _hosted_candidate_v3_stream(COMPOUND_NESTED_PARAMETER_SOURCE)
    function_blocks = [row for row in records["B"] if row[0] == 0]
    function_values = [row for row in records["V"] if row[1] == 0]
    function_instructions = [row for row in records["I"] if row[1] == 0]
    function_instruction_ids = {row[0] for row in function_instructions}
    function_terminators = [
        row for row in records["T"] if row[0] in function_instruction_ids
    ]
    function_operands = [
        row for row in records["O"] if row[0] in function_instruction_ids
    ]
    function_results = [
        row for row in records["R"] if row[0] in function_instruction_ids
    ]
    assert records
    assert len(function_blocks) == 19
    assert len(function_instructions) == 78
    assert len(function_terminators) == 19
    assert {row[4] for row in function_instructions} >= {6, 10, 13, 14, 16, 23, 24, 25}
    value_ids = {row[0] for row in function_values}
    assert all(row[2] in value_ids for row in function_operands)
    assert all(row[2] in value_ids for row in function_results)
    call_id = next(row[0] for row in function_instructions if row[4] == 14)
    sample_start = COMPOUND_NESTED_PARAMETER_SOURCE.index(
        b"sample", COMPOUND_NESTED_PARAMETER_SOURCE.index(b"result = result")
    )
    assert records["C"] == [(call_id, 0, 2, sample_start, 6)]
    assert records["A"] == [(call_id, 0, 13)]


def test_hosted_v3_nested_match_call_while_has_bounded_cfg() -> None:
    compilation = compile_source(NESTED_MATCH_CALL_WHILE_SOURCE.decode("ascii"), "O0")
    function = next(
        function for function in compilation.ir.functions if function.name == "skip_prefix"
    )
    assert len(function.blocks) == 22
    assert len(function.registers) == 50
    assert len(function.memory_objects) == 5
    assert [instruction.opcode.value for instruction in function.blocks[14].instructions] == [
        "const",
        "load",
        "call",
        "const",
        "store",
        "const",
        "load",
        "call",
        "branch3",
    ]
    assert function.blocks[1].instructions[-1].targets == (
        "rel_neg_5",
        "rel_zero_6",
        "rel_pos_7",
    )
    assert function.blocks[13].instructions[-1].targets == (
        "switch_negative_13",
        "switch_neutral_14",
        "switch_positive_15",
    )
    calls = [
        instruction
        for block in function.blocks
        for instruction in block.instructions
        if instruction.opcode.value == "call"
    ]
    assert [(call.callee, len(call.operands), len(call.results)) for call in calls] == [
        ("read_unit", 1, 1),
        ("is_blank", 1, 1),
    ]


def test_hosted_v3_nested_match_call_while_can_continue_into_match() -> None:
    compilation = compile_source(
        NESTED_MATCH_CALL_WHILE_CONTINUATION_SOURCE.decode("ascii"), "O0"
    )
    function = next(
        function
        for function in compilation.ir.functions
        if function.name == "scan_prefix"
    )
    assert len(function.blocks) == 29
    assert len(function.registers) == 62
    assert len(function.memory_objects) == 6
    assert [instruction.opcode.value for instruction in function.blocks[5].instructions] == [
        "const",
        "load",
        "compare",
        "branch3",
    ]
    assert function.blocks[5].instructions[-1].targets == (
        "rel_neg_21",
        "rel_zero_22",
        "rel_pos_23",
    )
    assert function.blocks[25].instructions[-1].targets == (
        "switch_negative_25",
        "switch_neutral_26",
        "switch_positive_27",
    )
    assert [function.blocks[index].instructions[-1].opcode.value for index in (26, 27, 28)] == [
        "return",
        "return",
        "return",
    ]


def test_candidate_v3_nested_match_call_while_emits_complete_cfg() -> None:
    records = _hosted_candidate_v3_stream(NESTED_MATCH_CALL_WHILE_SOURCE)
    function_blocks = [row for row in records["B"] if row[0] == 0]
    function_values = [row for row in records["V"] if row[1] == 0]
    function_instructions = [row for row in records["I"] if row[1] == 0]
    function_instruction_ids = {row[0] for row in function_instructions}
    function_terminators = [
        row for row in records["T"] if row[0] in function_instruction_ids
    ]
    function_operands = [
        row for row in records["O"] if row[0] in function_instruction_ids
    ]
    function_results = [
        row for row in records["R"] if row[0] in function_instruction_ids
    ]
    assert records
    assert len(function_blocks) == 22
    assert len(function_values) == 50
    assert len(function_instructions) == 84
    assert len(function_terminators) == 22
    assert {row[4] for row in function_instructions} >= {1, 5, 13, 14, 15, 16, 23, 24, 25}
    value_ids = {row[0] for row in function_values}
    assert all(row[2] in value_ids for row in function_operands)
    assert all(row[2] in value_ids for row in function_results)
    read_start = NESTED_MATCH_CALL_WHILE_SOURCE.index(
        b"read_unit", NESTED_MATCH_CALL_WHILE_SOURCE.index(b"mut unit")
    )
    blank_start = NESTED_MATCH_CALL_WHILE_SOURCE.index(
        b"is_blank", NESTED_MATCH_CALL_WHILE_SOURCE.index(b"match is_blank")
    )
    assert records["C"] == [(52, 0, 2, read_start, 9), (57, 1, 2, blank_start, 8)]
    assert records["A"] == [(52, 0, 29), (57, 0, 33)]


def test_candidate_v3_nested_match_call_while_continuation_emits_joined_cfg() -> None:
    records = _hosted_candidate_v3_stream(NESTED_MATCH_CALL_WHILE_CONTINUATION_SOURCE)
    function_blocks = [row for row in records["B"] if row[0] == 0]
    function_instructions = [row for row in records["I"] if row[1] == 0]
    function_instruction_ids = {row[0] for row in function_instructions}
    function_terminators = [
        row for row in records["T"] if row[0] in function_instruction_ids
    ]
    assert len(function_blocks) == 22
    assert len(function_instructions) == 71
    assert len(function_terminators) == 22
    continuation_branch = next(row for row in function_instructions if row[4] == 25)
    continuation_terminator = next(
        row for row in function_terminators if row[0] == continuation_branch[0]
    )
    assert continuation_terminator[1] == 3
    assert len(set(continuation_terminator[2:5])) == 3
    assert len(records["C"]) == 2
    assert len(records["A"]) == 2


def test_candidate_v3_nested_match_call_three_call_continuation_emits_complete_cfg() -> None:
    records = _hosted_candidate_v3_stream(NESTED_MATCH_CALL_WHILE_CALL_CONTINUATION_SOURCE)
    function_blocks = [row for row in records["B"] if row[0] == 0]
    function_instructions = [row for row in records["I"] if row[1] == 0]
    function_instruction_ids = {row[0] for row in function_instructions}
    function_terminators = [
        row for row in records["T"] if row[0] in function_instruction_ids
    ]
    function_operands = [row for row in records["O"] if row[0] in function_instruction_ids]
    function_results = [row for row in records["R"] if row[0] in function_instruction_ids]
    assert len(function_blocks) == 22
    assert len(function_instructions) == 77
    assert len(function_terminators) == 22
    assert {row[4] for row in function_instructions} >= {14, 23, 24, 25}
    value_ids = {row[0] for row in records["V"] if row[1] == 0}
    assert all(row[2] in value_ids for row in function_operands)
    assert all(row[2] in value_ids for row in function_results)
    assert len(records["C"]) == 5
    assert len(records["A"]) == 11


def test_candidate_v3_nested_match_call_mixed_continuation_emits_complete_cfg() -> None:
    records = _hosted_candidate_v3_stream(
        NESTED_MATCH_CALL_WHILE_MIXED_CONTINUATION_SOURCE
    )
    function_blocks = [row for row in records["B"] if row[0] == 0]
    function_instructions = [row for row in records["I"] if row[1] == 0]
    function_instruction_ids = {row[0] for row in function_instructions}
    all_instruction_ids = {row[0] for row in records["I"]}
    block_ids = {row[1] for row in function_blocks}
    all_block_ids = {row[1] for row in records["B"]}
    terminator_by_instruction = {
        row[0]: row for row in records["T"] if row[0] in function_instruction_ids
    }
    terminator_ids = [row[4] for row in function_blocks]
    assert len(records["F"]) == 2
    assert len(function_blocks) >= 19
    assert len(terminator_by_instruction) >= 19
    assert any(row[4] == 25 for row in function_instructions)
    assert all(row[0] in all_instruction_ids for row in records["O"])
    assert all(row[0] in all_instruction_ids for row in records["R"])
    assert len(records["C"]) == 4
    assert len(terminator_ids) == len(set(terminator_ids))
    assert all(row[4] in function_instruction_ids for row in function_blocks)
    assert any(
        row[1] == 2 and row[2] in all_block_ids
        for row in terminator_by_instruction.values()
    )
    assert len([row for row in terminator_by_instruction.values() if row[1] == 1]) >= 2
    assert any(
        row[1] == 2 and row[2] in block_ids
        for row in terminator_by_instruction.values()
    )


def test_candidate_v3_loop_match_body_preserves_next_function_boundary() -> None:
    records = _hosted_candidate_v3_stream(
        LOOP_MATCH_BODY_WITH_NEXT_FUNCTION_SOURCE
    )
    all_instruction_ids = {row[0] for row in records["I"]}
    scan_instructions = [row for row in records["I"] if row[1] == 1]
    next_instructions = [row for row in records["I"] if row[1] == 2]
    all_block_records = records["B"]
    scan_blocks = [row for row in all_block_records if row[0] == 1]
    next_blocks = [row for row in all_block_records if row[0] == 2]
    scan_block_ids = {row[1] for row in scan_blocks}
    all_value_ids = {row[0] for row in records["V"]}
    function_names = {
        source[record[2] : record[2] + record[3]].decode("ascii")
        for record in records["F"]
        for source in (LOOP_MATCH_BODY_WITH_NEXT_FUNCTION_SOURCE,)
    }

    assert len(records["F"]) == 3
    assert {row[0] for row in records["F"]} == {0, 1, 2}
    assert function_names == {"classify", "scan", "next"}
    assert scan_instructions
    assert next_instructions
    assert any(row[4] == 25 for row in scan_instructions)
    assert any(row[4] == 24 for row in scan_instructions)
    assert any(row[4] == 23 for row in next_instructions)
    assert scan_blocks
    assert next_blocks
    assert len({row[0] for row in records["T"]}) == len(records["T"])
    scan_instruction_ids = {instruction[0] for instruction in scan_instructions}
    assert any(
        row[1] == 3 and row[0] in scan_instruction_ids
        for row in records["T"]
    )
    assert all(row[0] in all_instruction_ids for row in records["O"])
    assert all(row[0] in all_instruction_ids for row in records["R"])
    assert all(row[2] in all_value_ids for row in records["O"])
    assert all(row[2] in all_value_ids for row in records["R"])
    assert len({row[2] for row in records["R"]}) == len(records["R"])
    next_return_ids = {instruction[0] for instruction in next_instructions if instruction[4] == 23}
    assert next_return_ids
    assert all(
        terminator[1] == 1
        for terminator in records["T"]
        if terminator[0] in next_return_ids
    )


def test_candidate_v3_preserves_nested_match_successor_after_loop() -> None:
    records = _hosted_candidate_v3_stream(
        POST_LOOP_NESTED_MATCH_SUCCESSOR_SOURCE
    )
    source = POST_LOOP_NESTED_MATCH_SUCCESSOR_SOURCE
    function_headers = records["F"]
    assert [row[0] for row in function_headers] == [0, 1]
    assert function_headers[0][2] == source.index(b"scan_prefix")
    assert function_headers[1][2] == source.index(b"next_function")
    assert function_headers[1][2] > function_headers[0][2]

    function_blocks = [row for row in records["B"] if row[0] == 0]
    function_instructions = [row for row in records["I"] if row[1] == 0]
    function_instruction_ids = {row[0] for row in function_instructions}
    all_instruction_ids = {row[0] for row in records["I"]}
    all_value_ids = {row[0] for row in records["V"]}
    block_ids = {row[1] for row in function_blocks}
    function_terminators = [
        row for row in records["T"] if row[0] in function_instruction_ids
    ]
    instruction_block = {row[0]: row[2] for row in function_instructions}
    terminator_by_block = {
        instruction_block[row[0]]: row
        for row in function_terminators
        if row[0] in instruction_block
    }

    assert len(function_blocks) >= 20
    assert len(terminator_by_block) == len(function_blocks)
    assert len({row[0] for row in function_terminators}) == len(function_terminators)
    assert all(row[4] in function_instruction_ids for row in function_blocks)
    assert {row[4] for row in function_instructions} >= {14, 23, 24, 25}

    assert all(row[0] in all_instruction_ids for row in records["O"])
    assert all(row[0] in all_instruction_ids for row in records["R"])
    assert all(row[2] in all_value_ids for row in records["O"])
    assert all(row[2] in all_value_ids for row in records["R"])
    produced_values = [row[2] for row in records["R"]]
    assert len(produced_values) == len(set(produced_values))

    branch_blocks = {
        block_id
        for block_id, terminator in terminator_by_block.items()
        if terminator[1] == 3
    }
    assert len(branch_blocks) >= 3

    jump_edges = [
        (instruction_block[row[0]], row[2])
        for row in function_terminators
        if row[1] == 2 and row[0] in instruction_block
    ]
    assert jump_edges
    assert all(target in block_ids for _, target in jump_edges)
    loop_headers = {
        target
        for source_block, target in jump_edges
        if target in terminator_by_block
        and terminator_by_block[target][1] == 3
        and source_block > target
    }
    assert loop_headers

    outer_successor_edges = [
        (source_block, target)
        for source_block, target in jump_edges
        if target in branch_blocks
        and source_block > max(loop_headers)
    ]
    assert outer_successor_edges

    return_blocks = {
        row[2] for row in function_instructions if row[4] == 23
    }
    assert return_blocks
    assert all(terminator_by_block[block][1] == 1 for block in return_blocks)
    assert all(
        [row[4] for row in function_instructions if row[2] == block][-1] == 23
        for block in return_blocks
    )
    next_function_instructions = [row for row in records["I"] if row[1] == 1]
    assert any(row[4] == 23 for row in next_function_instructions)


def test_candidate_v3_main_finalizes_after_last_function() -> None:
    finalized = _hosted_candidate_v3_stream(
        FUNCTION_BOUNDARY_FINALIZATION_SOURCE, entry_point="main"
    )
    assert len(finalized["F"]) == 2
    assert finalized["Z"] == [(15,)]


def test_candidate_v3_dispatches_parameter_match_after_joined_successor() -> None:
    records = _hosted_candidate_v3_stream(POST_SUCCESSOR_PARAMETER_MATCH_SOURCE)
    function_blocks = [row for row in records["B"] if row[0] == 0]
    function_instructions = [row for row in records["I"] if row[1] == 0]
    function_instruction_ids = {row[0] for row in function_instructions}
    all_instruction_ids = {row[0] for row in records["I"]}
    terminator_by_instruction = {
        row[0]: row for row in records["T"] if row[0] in function_instruction_ids
    }
    block_ids = {row[1] for row in function_blocks}
    assert len(function_blocks) >= 23
    assert {0, 1, 2, 3, 4, 6, 7, 8, 9, 10, 11, 12, 13, 14} <= block_ids
    assert len({row[1] for row in function_blocks}) == len(function_blocks)
    assert len(terminator_by_instruction) == len(function_blocks)
    assert all(row[4] in function_instruction_ids for row in function_blocks)
    assert all(row[0] in all_instruction_ids for row in records["O"])
    assert all(row[0] in all_instruction_ids for row in records["R"])
    successor_terminator = terminator_by_instruction[
        next(row[4] for row in function_blocks if row[1] == max(block_ids))
    ]
    assert successor_terminator[1] == 1
    assert any(row[2] == 25 for row in function_instructions)
    assert any(row[2] == 23 for row in function_instructions)


def test_candidate_v3_dispatches_mutable_literal_match_after_joined_successor() -> None:
    records = _hosted_candidate_v3_stream(POST_SUCCESSOR_MUTABLE_LITERAL_MATCH_SOURCE)
    function_blocks = [row for row in records["B"] if row[0] == 0]
    function_instructions = [row for row in records["I"] if row[1] == 0]
    function_instruction_ids = {row[0] for row in function_instructions}
    function_values = [row for row in records["V"] if row[1] == 0]
    all_instruction_ids = {row[0] for row in records["I"]}
    all_value_ids = {row[0] for row in records["V"]}
    function_terminators = [
        row for row in records["T"] if row[0] in function_instruction_ids
    ]
    block_ids = {row[1] for row in function_blocks}
    terminator_by_block = {
        block[1]: next(row for row in function_terminators if row[0] == block[4])
        for block in function_blocks
    }
    assert len(function_blocks) >= 28
    assert len(terminator_by_block) == len(function_blocks)
    assert all(block[4] in function_instruction_ids for block in function_blocks)
    assert len({row[0] for row in function_terminators}) == len(function_terminators)
    assert len({row[0] for row in function_values}) == len(function_values)
    emitted_return_blocks = [
        block
        for block in function_blocks
        if [row[4] for row in function_instructions if row[2] == block[1]]
        == [1, 15, 1, 5, 1, 1, 14, 23]
    ]
    assert len(emitted_return_blocks) == 2
    assert all(
        block[3] == 8
        and block[4]
        == [row[0] for row in function_instructions if row[2] == block[1]][-1]
        for block in emitted_return_blocks
    )
    assert all(row[0] in all_instruction_ids for row in records["O"])
    assert all(row[0] in all_instruction_ids for row in records["R"])
    assert all(row[2] in all_value_ids for row in records["O"])
    assert all(row[2] in all_value_ids for row in records["R"])
    branch3_blocks = {
        block_id
        for block_id, terminator in terminator_by_block.items()
        if terminator[1] == 3
    }
    assert len(branch3_blocks) >= 2
    assert any(row[2] == 25 for row in function_instructions)
    assert any(row[2] == 23 for row in function_instructions)
    terminal_blocks = {
        block_id
        for block_id, terminator in terminator_by_block.items()
        if terminator[1] == 1
    }
    assert len(terminal_blocks) >= 4
    assert all(
        terminator[2:6] == (-1, -1, -1, -1)
        for terminator in terminator_by_block.values()
        if terminator[1] == 1
    )
    assert any(
        terminator[1] == 2 and terminator[2] in block_ids
        for terminator in terminator_by_block.values()
    )
    assert any(
        terminator[1] == 2 and terminator[2] == 1
        for terminator in terminator_by_block.values()
    )


def test_candidate_v3_preserves_successor_into_nested_identifier_scan() -> None:
    records = _hosted_candidate_v3_stream(POST_SUCCESSOR_COMPLEX_PREDICATE_MATCH_SOURCE)
    function_blocks = [row for row in records["B"] if row[0] == 0]
    function_instructions = [row for row in records["I"] if row[1] == 0]
    function_instruction_ids = {row[0] for row in function_instructions}
    value_ids = {row[0] for row in records["V"] if row[1] == 0}
    all_instruction_ids = {row[0] for row in records["I"]}
    all_value_ids = {row[0] for row in records["V"]}
    block_ids = {row[1] for row in function_blocks}
    function_terminators = [
        row for row in records["T"] if row[0] in function_instruction_ids
    ]
    assert len(records["F"]) == 2
    assert len(function_blocks) >= 20
    assert len(function_terminators) == len(function_blocks)
    assert len({row[0] for row in function_terminators}) == len(function_terminators)
    assert {1, 14, 15, 23, 24, 25} <= {
        row[4] for row in function_instructions
    }
    assert all(row[0] in all_instruction_ids for row in records["O"])
    assert all(row[0] in all_instruction_ids for row in records["R"])
    assert all(row[2] in all_value_ids for row in records["O"])
    assert all(row[2] in all_value_ids for row in records["R"])
    produced_values = [row[2] for row in records["R"]]
    assert len(produced_values) == len(set(produced_values))
    assert any(
        row[1] == 2 and row[2] in block_ids for row in function_terminators
    )
    instruction_block = {row[0]: row[2] for row in function_instructions}
    jump_edges = [
        (instruction_block[row[0]], row[2])
        for row in function_terminators
        if row[1] == 2 and row[0] in instruction_block and row[2] in block_ids
    ]
    terminator_by_block = {
        instruction_block[row[0]]: row
        for row in function_terminators
    }
    loop_headers = {
        target
        for source, target in jump_edges
        if terminator_by_block[target][1] == 3
        and any(
            entry_source < target
            for entry_source, entry_target in jump_edges
            if entry_target == target
        )
        and any(
            backedge_source > target
            for backedge_source, entry_target in jump_edges
            if entry_target == target
        )
    }
    assert len(loop_headers) == 1


def test_candidate_v3_preserves_function_boundary_after_nested_call_match() -> None:
    records = _hosted_candidate_v3_stream(FUNCTION_BOUNDARY_NESTED_CALL_SOURCE)
    function_headers = records["F"]
    source = FUNCTION_BOUNDARY_NESTED_CALL_SOURCE
    assert [row[0] for row in function_headers] == [0, 1]
    assert function_headers[0][2] == source.index(b"parse_unit")
    assert function_headers[1][2] == source.index(b"next_function")
    assert function_headers[1][2] > function_headers[0][2]

    instruction_ids = {row[0] for row in records["I"]}
    value_ids = [row[0] for row in records["V"]]
    value_id_set = set(value_ids)
    assert len(value_ids) == len(value_id_set)
    assert all(row[0] in instruction_ids and row[2] in value_id_set for row in records["O"])
    assert all(row[0] in instruction_ids and row[2] in value_id_set for row in records["R"])
    assert not records.get("Z")


def test_candidate_v3_all_terminal_match_preserves_function_boundary() -> None:
    records = _hosted_candidate_v3_stream(FUNCTION_BOUNDARY_ALL_TERMINAL_MATCH_SOURCE)
    function_headers = records["F"]
    source = FUNCTION_BOUNDARY_ALL_TERMINAL_MATCH_SOURCE

    assert [row[0] for row in function_headers] == [0, 1]
    assert function_headers[0][2] == source.index(b"classify")
    assert function_headers[1][2] == source.index(b"after")
    assert function_headers[1][2] > function_headers[0][2]
    assert records["T"]
    assert not records.get("Z")


def test_candidate_v3_preserves_boundary_after_nested_call_relation_match() -> None:
    records = _hosted_candidate_v3_stream(FUNCTION_BOUNDARY_NESTED_CALL_RELATION_SOURCE)
    source = FUNCTION_BOUNDARY_NESTED_CALL_RELATION_SOURCE
    function_headers = records["F"]
    assert [row[0] for row in function_headers] == [0, 1]
    assert function_headers[0][2] == source.index(b"first")
    assert function_headers[1][2] == source.index(b"second")
    assert function_headers[1][2] > function_headers[0][2]

    function_zero_instructions = [row for row in records["I"] if row[1] == 0]
    instruction_ids = {row[0] for row in records["I"]}
    value_ids = {row[0] for row in records["V"]}
    assert {row[4] for row in function_zero_instructions} >= {13, 14, 23, 24, 25}
    assert len(instruction_ids) == len(records["I"])
    assert len({row[0] for row in records["T"]}) == len(records["T"])
    assert all(row[0] in instruction_ids and row[2] in value_ids for row in records["O"])
    assert all(row[0] in instruction_ids and row[2] in value_ids for row in records["R"])
    assert len({row[2] for row in records["R"]}) == len(records["R"])

    terminator_by_instruction = {row[0]: row for row in records["T"]}
    branch_instructions = [row for row in function_zero_instructions if row[4] == 25]
    assert branch_instructions
    assert all(row[0] in terminator_by_instruction for row in branch_instructions)
    branch = terminator_by_instruction[branch_instructions[0][0]]
    assert all(
        any(block[1] == target for block in records["B"] if block[0] == 0)
        for target in branch[2:5]
    )
    assert any(row[4] == 23 for row in function_zero_instructions)
    assert any(row[4] == 23 for row in records["I"] if row[1] == 1)
    assert not records.get("Z")


def test_shared_call_relation_pipeline_accepts_generic_additive_argument() -> None:
    source = FUNCTION_BOUNDARY_NESTED_CALL_RELATION_SOURCE.replace(
        b"read_at", b"read_unit"
    ).replace(b"61", b"17").replace(b"62", b"42")
    match_start = source.index(b"match read_unit")
    match_stop = source.index(b"\n", match_start)
    header_start = source.index(b"fn first")
    header_stop = source.index(b"\n", header_start)
    callee_start = source.index(b"read_unit", match_start)
    callee_stop = callee_start + len(b"read_unit")

    descriptor = _hosted_candidate_function(
        "match_condition_descriptor", source, (match_start, match_stop)
    )
    assert _hosted_candidate_function("match_condition_kind", source, (descriptor,)) == 6
    assert _hosted_candidate_function(
        "match_condition_expression_kind", source, (descriptor,)
    ) == 4
    assert _hosted_candidate_function(
        "find_function_identity", source, (callee_start, callee_stop)
    ) > 0
    assert _hosted_candidate_function(
        "find_function_signature", source, (callee_start, callee_stop)
    ) > 0
    assert _hosted_candidate_function(
        "find_call_argument_type", source, (callee_start, header_start, header_stop)
    ) == 3
    assert _hosted_candidate_function(
        "parse_call_return_type", source, (callee_start, header_start, header_stop)
    ) == 2

    records = _hosted_candidate_v3_stream(source)
    assert [row[0] for row in records["F"]] == [0, 1]
    assert len({row[0] for row in records["I"]}) == len(records["I"])
    assert len({row[0] for row in records["T"]}) == len(records["T"])
    assert all(row[0] in {item[0] for item in records["I"]} for row in records["O"])
    assert all(row[0] in {item[0] for item in records["I"]} for row in records["R"])
    assert not records.get("Z")


def test_candidate_v3_crosses_boundary_after_additive_builtin_three_call() -> None:
    records = _hosted_candidate_v3_stream(FUNCTION_BOUNDARY_ADDITIVE_BUILTIN_CALL_SOURCE)
    function_headers = records["F"]
    source = FUNCTION_BOUNDARY_ADDITIVE_BUILTIN_CALL_SOURCE
    assert [row[0] for row in function_headers] == [0, 1]
    assert function_headers[0][2] == source.index(b"parse_unit")
    assert function_headers[1][2] == source.index(b"next_function")

    function_zero_instructions = [row for row in records["I"] if row[1] == 0]
    function_zero_instruction_ids = {row[0] for row in function_zero_instructions}
    assert any(row[4] == 10 for row in function_zero_instructions)
    assert any(row[4] == 10 for row in function_zero_instructions)
    assert sum(row[4] == 23 for row in function_zero_instructions) == 1
    return_ordinal = max(row[3] for row in function_zero_instructions if row[4] == 23)
    assert all(row[3] <= return_ordinal for row in function_zero_instructions)

    value_ids = [row[0] for row in records["V"]]
    assert len(value_ids) == len(set(value_ids))
    value_id_set = set(value_ids)
    result_values = [row[2] for row in records["R"] if row[0] in function_zero_instruction_ids]
    assert len(result_values) == len(set(result_values))
    assert set(result_values) <= value_id_set
    assert all(row[0] in function_zero_instruction_ids and row[2] in value_id_set for row in records["O"] if row[0] in function_zero_instruction_ids)
    assert not records.get("Z")


def test_candidate_v3_crosses_boundary_after_builtin_return_call() -> None:
    records = _hosted_candidate_v3_stream(FUNCTION_BOUNDARY_BUILTIN_RETURN_CALL_SOURCE)
    source = FUNCTION_BOUNDARY_BUILTIN_RETURN_CALL_SOURCE
    function_headers = records["F"]
    assert [row[0] for row in function_headers] == [0, 1, 2]
    assert [row[2] for row in function_headers] == [
        source.index(b"digit_value"),
        source.index(b"following"),
        source.index(b"main"),
    ]

    function_zero_instructions = [row for row in records["I"] if row[1] == 0]
    instruction_ids = {row[0] for row in records["I"]}
    value_ids = {row[0] for row in records["V"]}
    assert any(row[4] == 23 for row in function_zero_instructions)
    assert any(row[4] == 10 for row in function_zero_instructions)
    assert all(row[0] in instruction_ids and row[2] in value_ids for row in records["O"])
    assert all(row[0] in instruction_ids and row[2] in value_ids for row in records["R"])
    assert not records.get("Z")


def test_candidate_v3_crosses_boundary_after_declared_discard_call() -> None:
    source = FUNCTION_BOUNDARY_DECLARED_DISCARD_CALL_SOURCE
    records = _hosted_candidate_v3_stream(source)
    function_headers = records["F"]
    assert [row[0] for row in function_headers] == [0, 1, 2]
    assert [
        source[row[2] : row[2] + row[3]].decode("ascii")
        for row in function_headers
    ] == ["decimal_value", "emit_name", "following"]

    function_instructions = [row for row in records["I"] if row[1] == 1]
    instruction_ids = {row[0] for row in records["I"]}
    value_ids = {row[0] for row in records["V"]}
    assert any(row[4] == 14 for row in function_instructions)
    assert any(row[4] == 23 for row in function_instructions)
    assert all(row[0] in instruction_ids and row[2] in value_ids for row in records["O"])
    assert all(row[0] in instruction_ids and row[2] in value_ids for row in records["R"])
    assert len({row[0] for row in records["I"]}) == len(records["I"])
    assert len({row[0] for row in records["T"]}) == len(records["T"])
    assert len({row[2] for row in records["R"]}) == len(records["R"])
    assert not records.get("Z")


def test_candidate_v3_crosses_boundary_after_decimal_pipeline() -> None:
    source = FUNCTION_BOUNDARY_DECIMAL_PIPELINE_SOURCE
    records = _hosted_candidate_v3_stream(source)
    function_headers = records["F"]
    assert [row[0] for row in function_headers] == [0, 1]
    assert [
        source[row[2] : row[2] + row[3]].decode("ascii")
        for row in function_headers
    ] == ["decimal_value", "following"]

    function_instructions = [row for row in records["I"] if row[1] == 0]
    instruction_ids = {row[0] for row in records["I"]}
    value_ids = {row[0] for row in records["V"]}
    assert sum(row[4] == 25 for row in function_instructions) >= 3
    assert any(row[4] == 14 for row in function_instructions)
    assert any(row[4] == 23 for row in function_instructions)
    assert records["C"]
    assert all(row[0] in instruction_ids and row[2] in value_ids for row in records["O"])
    assert all(row[0] in instruction_ids and row[2] in value_ids for row in records["R"])
    assert len({row[0] for row in records["I"]}) == len(records["I"])
    assert len({row[0] for row in records["T"]}) == len(records["T"])
    assert len({row[2] for row in records["R"]}) == len(records["R"])
    assert not records.get("Z")


def test_candidate_v3_crosses_boundary_after_nested_mixed_three_way() -> None:
    records = _hosted_candidate_v3_stream(
        FUNCTION_BOUNDARY_NESTED_MIXED_THREE_WAY_SOURCE
    )
    source = FUNCTION_BOUNDARY_NESTED_MIXED_THREE_WAY_SOURCE
    function_headers = records["F"]
    assert [row[0] for row in function_headers] == [0, 1, 2]
    assert [
        source[row[2] : row[2] + row[3]].decode("ascii") for row in function_headers
    ] == [
        "render_value",
        "following",
        "main",
    ]

    function_instructions = [row for row in records["I"] if row[1] == 0]
    instruction_ids = {row[0] for row in records["I"]}
    value_ids = {row[0] for row in records["V"]}
    assert any(row[4] == 25 for row in function_instructions)
    assert sum(row[4] == 25 for row in function_instructions) >= 2
    assert records["C"]
    assert len({row[0] for row in records["I"]}) == len(records["I"])
    assert len({row[0] for row in records["T"]}) == len(records["T"])
    assert all(row[0] in instruction_ids and row[2] in value_ids for row in records["O"])
    assert all(row[0] in instruction_ids and row[2] in value_ids for row in records["R"])
    assert len({row[2] for row in records["R"]}) == len(records["R"])
    assert not records.get("Z")


def test_candidate_v3_preserves_compound_nested_match_loop_and_outer_successor() -> None:
    records = _hosted_candidate_v3_stream(COMPOUND_NESTED_MATCH_LOOP_BOUNDARY_SOURCE)
    source = COMPOUND_NESTED_MATCH_LOOP_BOUNDARY_SOURCE
    function_headers = records["F"]
    assert [row[0] for row in function_headers] == [0, 1]
    assert function_headers[0][2] == source.index(b"consume")
    assert function_headers[1][2] == source.index(b"next_function")
    assert function_headers[1][2] > function_headers[0][2]

    function_blocks = [row for row in records["B"] if row[0] == 0]
    function_instructions = [row for row in records["I"] if row[1] == 0]
    function_instruction_ids = {row[0] for row in function_instructions}
    all_instruction_ids = {row[0] for row in records["I"]}
    all_value_ids = {row[0] for row in records["V"]}
    block_ids = {row[1] for row in function_blocks}
    function_terminators = [
        row for row in records["T"] if row[0] in function_instruction_ids
    ]
    instruction_block = {row[0]: row[2] for row in function_instructions}
    terminator_by_block = {
        instruction_block[row[0]]: row
        for row in function_terminators
        if row[0] in instruction_block
    }

    assert len(function_blocks) >= 13
    assert len(terminator_by_block) == len(function_blocks)
    assert len({row[0] for row in function_terminators}) == len(function_terminators)
    assert all(row[4] in function_instruction_ids for row in function_blocks)
    assert {row[4] for row in function_instructions} >= {14, 23, 24, 25}

    assert all(row[0] in all_instruction_ids for row in records["O"])
    assert all(row[0] in all_instruction_ids for row in records["R"])
    assert all(row[2] in all_value_ids for row in records["O"])
    assert all(row[2] in all_value_ids for row in records["R"])
    produced_values = [row[2] for row in records["R"]]
    assert len(produced_values) == len(set(produced_values))

    branch_blocks = {
        block_id
        for block_id, terminator in terminator_by_block.items()
        if terminator[1] == 3
    }
    assert len(branch_blocks) >= 2

    jump_edges = [
        (instruction_block[row[0]], row[2])
        for row in function_terminators
        if row[1] == 2 and row[0] in instruction_block
    ]
    assert jump_edges
    assert all(target in block_ids for _, target in jump_edges)
    loop_headers = {
        target
        for source_block, target in jump_edges
        if target in terminator_by_block
        and terminator_by_block[target][1] == 3
        and source_block > target
    }
    assert loop_headers

    outer_successors: set[int] = set()
    break_successors: set[int] = set()
    for branch_block in branch_blocks:
        branch = terminator_by_block[branch_block]
        branch_targets = branch[2:5]
        if not all(target in terminator_by_block for target in branch_targets):
            continue
        negative, neutral, positive = branch_targets
        neutral_term = terminator_by_block[neutral]
        positive_term = terminator_by_block[positive]
        assert neutral_term[1] in {1, 2}
        assert positive_term[1] in {1, 2}
        if neutral_term[1] == 2 and positive_term[1] == 2:
            assert neutral_term[2] == positive_term[2]
            break_successors.add(neutral_term[2])
            if terminator_by_block[negative][1] == 3:
                outer_successors.add(neutral_term[2])

    assert len(break_successors) >= 1
    assert outer_successors
    assert all(
        terminator_by_block[successor][1] in {1, 2}
        for successor in outer_successors
    )

    return_blocks = {
        row[2] for row in function_instructions if row[4] == 23
    }
    assert return_blocks
    assert all(terminator_by_block[block][1] == 1 for block in return_blocks)
    assert all(
        [row[4] for row in function_instructions if row[2] == block][-1] == 23
        for block in return_blocks
    )


def test_candidate_v3_preserves_nested_match_terminal_return_boundary() -> None:
    records = _hosted_candidate_v3_stream(NESTED_MATCH_TERMINAL_RETURN_BOUNDARY_SOURCE)
    source = NESTED_MATCH_TERMINAL_RETURN_BOUNDARY_SOURCE
    function_headers = records["F"]
    assert [row[0] for row in function_headers] == [0, 1]
    assert function_headers[0][2] == source.index(b"parse_unit")
    assert function_headers[1][2] == source.index(b"next_function")
    assert function_headers[1][2] > function_headers[0][2]

    function_blocks = [row for row in records["B"] if row[0] == 0]
    function_instructions = [row for row in records["I"] if row[1] == 0]
    function_instruction_ids = {row[0] for row in function_instructions}
    all_instruction_ids = {row[0] for row in records["I"]}
    all_value_ids = {row[0] for row in records["V"]}
    block_ids = {row[1] for row in function_blocks}
    instruction_block = {row[0]: row[2] for row in function_instructions}
    function_terminators = [
        row for row in records["T"] if row[0] in function_instruction_ids
    ]
    terminator_by_block = {
        instruction_block[row[0]]: row
        for row in function_terminators
        if row[0] in instruction_block
    }

    assert len(function_blocks) >= 15
    assert block_ids == set(range(15))
    assert len(terminator_by_block) == len(function_blocks)
    assert len({row[0] for row in function_terminators}) == len(function_terminators)
    assert {row[4] for row in function_instructions} >= {14, 23, 24, 25}
    assert all(row[4] in function_instruction_ids for row in function_blocks)
    assert all(row[0] in all_instruction_ids for row in records["O"])
    assert all(row[0] in all_instruction_ids for row in records["R"])
    assert all(row[2] in all_value_ids for row in records["O"])
    assert all(row[2] in all_value_ids for row in records["R"])
    produced_values = [row[2] for row in records["R"]]
    assert len(produced_values) == len(set(produced_values))

    branch_blocks = {
        block_id
        for block_id, terminator in terminator_by_block.items()
        if terminator[1] == 3
    }
    assert len(branch_blocks) >= 3
    jump_edges = [
        (instruction_block[row[0]], row[2])
        for row in function_terminators
        if row[1] == 2 and row[0] in instruction_block
    ]
    assert jump_edges
    assert all(target in block_ids for _, target in jump_edges)

    terminal_return_blocks = {
        row[2] for row in function_instructions if row[4] == 23
    }
    assert terminal_return_blocks
    assert all(
        terminator_by_block[block][1] == 1 for block in terminal_return_blocks
    )
    assert all(
        [row[4] for row in function_instructions if row[2] == block][-1] == 23
        for block in terminal_return_blocks
    )
    assert any(
        terminator_by_block[source_block][1] == 2
        and terminator_by_block[source_block][2] == target
        and target in block_ids
        for source_block, target in jump_edges
    )
    assert not records.get("Z")


def _assert_candidate_v3_match_successor_integrity(
    records: dict[str, list[tuple[int, ...]]],
) -> None:
    function_blocks = [row for row in records["B"] if row[0] == 0]
    function_instructions = [row for row in records["I"] if row[1] == 0]
    function_instruction_ids = {row[0] for row in function_instructions}
    function_terminators = [row for row in records["T"] if row[0] in function_instruction_ids]
    function_operands = [row for row in records["O"] if row[0] in function_instruction_ids]
    function_results = [row for row in records["R"] if row[0] in function_instruction_ids]
    assert {row[1] for row in function_blocks} >= {0, 1, 2, 3, 4}
    assert any(row[2] == 4 for row in function_instructions)
    assert any(row[2] in {1, 2, 3} and row[4] == 24 for row in function_instructions)
    assert all(row[4] in function_instruction_ids for row in function_blocks)
    assert all(row[0] in function_instruction_ids for row in function_terminators)
    assert all(row[0] in function_instruction_ids for row in function_operands)
    assert all(row[0] in function_instruction_ids for row in function_results)


def test_candidate_v3_simple_match_emits_real_successor_for_fallthrough_arms() -> None:
    records = _hosted_candidate_v3_stream(MATCH_FALLTHROUGH_ASSIGNMENT_SOURCE)
    _assert_candidate_v3_match_successor_integrity(records)
    function_instructions = [row for row in records["I"] if row[1] == 0]
    assert sum(row[4] == 24 for row in function_instructions) == 3
    assert any(row[2] == 4 and row[4] == 23 for row in function_instructions)


def test_candidate_v3_terminating_match_arm_skips_synthetic_successor_jump() -> None:
    records = _hosted_candidate_v3_stream(MATCH_FALLTHROUGH_TERMINATING_ARM_SOURCE)
    _assert_candidate_v3_match_successor_integrity(records)
    function_instructions = [row for row in records["I"] if row[1] == 0]
    assert any(row[2] == 1 and row[4] == 23 for row in function_instructions)
    assert not any(row[2] == 1 and row[4] == 24 for row in function_instructions)
    assert sum(row[4] == 24 for row in function_instructions) == 2


@pytest.mark.parametrize("source", MATCH_PARAMETER_RELATION_SOURCES)
def test_hosted_v3_parameter_relation_match_materializes_s3_truth_values(
    source: bytes,
) -> None:
    compilation = compile_source(source.decode("ascii"), "O0")
    function = compilation.ir.functions[0]
    assert len(function.blocks) == 8
    assert len(function.registers) == 14
    assert len(function.memory_objects) == 1
    entry = function.blocks[0].instructions
    assert [instruction.opcode.value for instruction in entry] == [
        "const",
        "compare",
        "branch3",
    ]
    assert entry[1].operands == (0, 1)
    assert entry[2].targets == ("rel_neg_0", "rel_zero_1", "rel_pos_2")
    assert [block.instructions[1].immediate for block in function.blocks[1:4]] == {
        "<": [-1, 0, 0],
        "<=": [-1, -1, 0],
        ">": [0, 0, -1],
        ">=": [0, -1, -1],
        "==": [0, -1, 0],
        "!=": [-1, 0, -1],
    }[source.decode("ascii").split("match unit ")[1].split(" ")[0]]
    assert function.blocks[4].instructions[-1].targets == (
        "switch_negative_4",
        "switch_neutral_5",
        "switch_positive_6",
    )


@pytest.mark.parametrize("source", MATCH_LOCAL_RELATION_SOURCES)
def test_hosted_v3_mutable_local_relation_match_preserves_storage_load(
    source: bytes,
) -> None:
    compilation = compile_source(source.decode("ascii"), "O0")
    function = compilation.ir.functions[0]
    assert len(function.blocks) == 8
    assert len(function.registers) == 17
    assert len(function.memory_objects) == 2
    entry = function.blocks[0].instructions
    assert [instruction.opcode.value for instruction in entry] == [
        "const",
        "const",
        "store",
        "const",
        "load",
        "const",
        "compare",
        "branch3",
    ]
    assert entry[4].memory == 0
    assert entry[6].operands == (3, 4)
    assert entry[7].operands == (5,)
    assert function.blocks[4].instructions[-1].targets == (
        "switch_negative_4",
        "switch_neutral_5",
        "switch_positive_6",
    )


@pytest.mark.parametrize("source", WHILE_CONSTANT_SOURCES)
def test_hosted_v3_constant_while_elides_body_like_lowering(source: bytes) -> None:
    compilation = compile_source(source.decode("ascii"), "O0")
    function = compilation.ir.functions[0]
    assert len(function.blocks) == 1
    assert [instruction.opcode.value for instruction in function.blocks[0].instructions] == [
        "const",
        "const",
        "store",
        "const",
        "load",
        "return",
    ]


@pytest.mark.skipif(not LINUX_NATIVE, reason="requires Linux x86-64 native execution")
def test_native_v3_constant_while_elides_body_and_preserves_return(
    tmp_path: Path,
) -> None:
    executable = build_stage1(tmp_path / "s3c-stage1-v3-constant-while")
    for source in WHILE_CONSTANT_SOURCES:
        result = subprocess.run(
            [str(executable)],
            input=source,
            capture_output=True,
            check=False,
            shell=False,
        )
        assert result.returncode == 0
        records = _parse_v3_stream(result.stdout)
        assert records["B"] == [(0, 0, 0, 6, 5)]
        assert [row[4] for row in records["I"]] == [1, 1, 16, 1, 15, 23]
        assert records["T"] == [(5, 1, -1, -1, -1, -1, 3)]


def test_hosted_v3_truthy_while_has_explicit_relation_targets() -> None:
    compilation = compile_source(WHILE_TRUTHY_BREAK_SOURCE.decode("ascii"), "O0")
    function = compilation.ir.functions[0]
    assert [block.name for block in function.blocks] == [
        "entry",
        "while_condition_0",
        "while_body_1",
        "while_exit_0_2",
        "while_exit_1_3",
        "while_exit_4",
    ]
    condition = function.blocks[1].instructions
    assert [instruction.opcode.value for instruction in condition] == ["const", "load", "branch3"]
    assert condition[-1].operands == (3,)
    assert condition[-1].targets == (
        "while_body_1",
        "while_exit_0_2",
        "while_exit_1_3",
    )
    assert function.blocks[2].instructions[0].opcode.value == "jump"
    assert function.blocks[2].instructions[0].targets == ("while_exit_4",)


def test_hosted_v3_compare_while_preserves_storage_and_backedge() -> None:
    compilation = compile_source(
        WHILE_COMPARE_INCREMENT_SOURCE.decode("ascii"), "O0"
    )
    function = compilation.ir.functions[0]
    assert len(function.blocks) == 6
    assert len(function.registers) == 13
    assert [block.name for block in function.blocks] == [
        "entry",
        "while_condition_0",
        "while_body_1",
        "while_exit_0_2",
        "while_exit_1_3",
        "while_exit_4",
    ]
    condition = function.blocks[1].instructions
    assert [instruction.opcode.value for instruction in condition] == [
        "const",
        "load",
        "const",
        "compare",
        "branch3",
    ]
    assert condition[3].operands == (3, 4)
    assert condition[4].operands == (5,)
    body = function.blocks[2].instructions
    assert [instruction.opcode.value for instruction in body] == [
        "const",
        "load",
        "const",
        "add",
        "const",
        "store",
        "jump",
    ]
    assert body[5].memory == 0
    assert body[6].targets == ("while_condition_0",)
    assert function.blocks[3].instructions[0].targets == ("while_exit_4",)
    assert function.blocks[4].instructions[0].targets == ("while_exit_4",)
    assert function.blocks[5].instructions[-1].operands == (12,)


@pytest.mark.parametrize("source", WHILE_ITERATION_SOURCES)
def test_hosted_v3_compare_while_iteration_edges_are_value_independent(
    source: bytes,
) -> None:
    compilation = compile_source(source.decode("ascii"), "O0")
    function = compilation.ir.functions[0]
    condition = function.blocks[1].instructions
    assert condition[3].opcode.value == "compare"
    assert condition[4].opcode.value == "branch3"
    assert condition[4].operands == (5,)
    assert function.blocks[2].instructions[-1].opcode.value == "jump"
    assert function.blocks[2].instructions[-1].targets == ("while_condition_0",)
    assert function.blocks[5].instructions[-1].opcode.value == "return"


def test_hosted_v3_dependent_mutable_initializer_loads_before_compare() -> None:
    compilation = compile_source(WHILE_DEPENDENT_SOURCE.decode("ascii"), "O0")
    function = compilation.ir.functions[0]
    assert len(function.blocks) == 6
    assert len(function.registers) == 19
    assert [instruction.opcode.value for instruction in function.blocks[0].instructions] == [
        "const",
        "const",
        "store",
        "const",
        "load",
        "const",
        "add",
        "const",
        "store",
        "jump",
    ]
    condition = function.blocks[1].instructions
    assert [instruction.opcode.value for instruction in condition] == [
        "const",
        "load",
        "const",
        "load",
        "compare",
        "branch3",
    ]
    assert condition[1].memory == 0
    assert condition[3].memory == 1
    assert condition[4].operands == (8, 10)
    assert condition[5].operands == (11,)
    body = function.blocks[2].instructions
    assert body[1].memory == 0
    assert body[5].memory == 0
    assert body[-1].targets == ("while_condition_0",)


@pytest.mark.parametrize("source", RELATIONAL_RETURN_SOURCES)
def test_hosted_v3_relational_return_materializes_s3_truth_values(
    source: bytes,
) -> None:
    compilation = compile_source(source.decode("ascii"), "O0")
    function = compilation.ir.functions[0]
    assert len(function.blocks) == 5
    assert len(function.memory_objects) == 2
    assert [instruction.opcode.value for instruction in function.blocks[0].instructions] == [
        "const",
        "const",
        "store",
        "const",
        "load",
        "const",
        "compare",
        "branch3",
    ]
    assert function.blocks[0].instructions[6].results == (5,)
    assert function.blocks[0].instructions[7].operands == (5,)
    operator = source.decode("ascii").split(" value ")[1].split(" ")[0]
    expected_lanes = {
        "<": [-1, 0, 0],
        "<=": [-1, -1, 0],
        ">": [0, 0, -1],
        ">=": [0, -1, -1],
        "==": [0, -1, 0],
        "!=": [-1, 0, -1],
    }
    assert [block.instructions[1].immediate for block in function.blocks[1:4]] == expected_lanes[operator]
    assert function.blocks[4].instructions[-1].opcode.value == "return"


@pytest.mark.parametrize("source", RELATIONAL_WHILE_SOURCES)
def test_hosted_v3_relational_while_uses_two_branch3_edges(
    source: bytes,
) -> None:
    compilation = compile_source(source.decode("ascii"), "O0")
    function = compilation.ir.functions[0]
    assert len(function.blocks) == 10
    assert len(function.memory_objects) == 2
    condition = function.blocks[1].instructions
    assert condition[-1].opcode.value == "branch3"
    assert condition[-1].operands == (5,)
    assert condition[-1].targets == (
        "rel_neg_5",
        "rel_zero_6",
        "rel_pos_7",
    )
    relation_continuation = function.blocks[9].instructions
    assert relation_continuation[-1].opcode.value == "branch3"
    assert relation_continuation[-1].targets == (
        "while_body_1",
        "while_exit_0_2",
        "while_exit_1_3",
    )
    assert function.blocks[2].instructions[-1].targets == ("while_condition_0",)


@pytest.mark.parametrize("source", RELATIONAL_WHILE_DEPENDENT_SOURCES)
def test_hosted_v3_relational_while_loads_mutable_right_operand(
    source: bytes,
) -> None:
    compilation = compile_source(source.decode("ascii"), "O0")
    function = compilation.ir.functions[0]
    assert len(function.blocks) == 10
    assert len(function.registers) == 27
    assert len(function.memory_objects) == 3
    condition = function.blocks[1].instructions
    assert [instruction.opcode.value for instruction in condition] == [
        "const",
        "load",
        "const",
        "load",
        "compare",
        "branch3",
    ]
    assert condition[1].memory == 0
    assert condition[3].memory == 1
    assert condition[4].operands == (8, 10)
    assert condition[5].operands == (11,)
    assert condition[5].targets == (
        "rel_neg_5",
        "rel_zero_6",
        "rel_pos_7",
    )
    relation_continuation = function.blocks[9].instructions
    assert relation_continuation[-1].opcode.value == "branch3"
    assert relation_continuation[-1].targets == (
        "while_body_1",
        "while_exit_0_2",
        "while_exit_1_3",
    )
    assert [block.instructions[1].immediate for block in function.blocks[6:9]] == {
        "<": [-1, 0, 0],
        "<=": [-1, -1, 0],
        ">": [0, 0, -1],
        ">=": [0, -1, -1],
        "==": [0, -1, 0],
        "!=": [-1, 0, -1],
    }[source.decode("ascii").split("while position ")[1].split(" ")[0]]
    assert function.blocks[2].instructions[-1].targets == ("while_condition_0",)


def test_hosted_v3_relational_while_loads_parameter_right_operand_and_increments() -> None:
    compilation = compile_source(PARAMETER_RIGHT_INCREMENT_SOURCE.decode("ascii"), "O0")
    function = compilation.ir.functions[0]
    assert len(function.blocks) == 10
    assert len(function.registers) == 21
    assert len(function.memory_objects) == 2
    assert function.parameters[0].register == 0
    condition = function.blocks[1].instructions
    assert [instruction.opcode.value for instruction in condition] == [
        "const",
        "load",
        "compare",
        "branch3",
    ]
    assert condition[2].operands == (4, 0)
    assert condition[3].targets == (
        "rel_neg_5",
        "rel_zero_6",
        "rel_pos_7",
    )
    body = function.blocks[2].instructions
    assert [instruction.opcode.value for instruction in body] == [
        "const",
        "load",
        "const",
        "add",
        "const",
        "store",
        "jump",
    ]
    assert body[3].operands == (15, 16)
    assert body[-1].targets == ("while_condition_0",)
    assert function.blocks[9].instructions[-1].targets == (
        "while_body_1",
        "while_exit_0_2",
        "while_exit_1_3",
    )


@pytest.mark.skipif(not LINUX_NATIVE, reason="requires Linux x86-64 native execution")
def test_native_v3_truthy_while_emits_jump_branch3_and_break_target(
    tmp_path: Path,
) -> None:
    executable = build_stage1(tmp_path / "s3c-stage1-v3-truthy-while")
    result = subprocess.run(
        [str(executable)],
        input=WHILE_TRUTHY_BREAK_SOURCE,
        capture_output=True,
        check=False,
        shell=False,
    )
    assert result.returncode == 0
    records = _parse_v3_stream(result.stdout)
    declaration_start = WHILE_TRUTHY_BREAK_SOURCE.index(b"mut")
    name_start = WHILE_TRUTHY_BREAK_SOURCE.index(b"running")
    return_literal = WHILE_TRUTHY_BREAK_SOURCE.rindex(b"0")
    assert records["B"] == [
        (0, 0, 0, 4, 3),
        (0, 1, 1, 3, 6),
        (0, 2, 2, 1, 7),
        (0, 3, 3, 1, 8),
        (0, 4, 4, 1, 9),
        (0, 5, 5, 2, 11),
    ]
    assert records["D"] == [(0, 0, 2, 1, name_start, 7, 1, 2, 0)]
    assert records["M"] == [(0, 0, 1, 1, 1, declaration_start)]
    assert records["V"] == [
        (0, 0, 3, 1, WHILE_TRUTHY_BREAK_SOURCE.index(b"-1"), 0, 0, -1),
        (1, 0, 2, 2, declaration_start, 0, 0, -1),
        (2, 0, 2, 2, name_start, 0, 0, -1),
        (3, 0, 3, 1, name_start, 0, 0, -1),
        (4, 0, 2, 2, return_literal, 0, 0, -1),
    ]
    assert [row[4] for row in records["I"]] == [1, 1, 16, 24, 1, 15, 25, 24, 24, 24, 1, 23]
    assert records["T"] == [
        (3, 2, 1, -1, -1, -1, -1),
        (6, 3, 2, 3, 4, 3, -1),
        (7, 2, 5, -1, -1, -1, -1),
        (8, 2, 5, -1, -1, -1, -1),
        (9, 2, 5, -1, -1, -1, -1),
        (11, 1, -1, -1, -1, -1, 4),
    ]
    assert records["Z"] == [(15,)]


@pytest.mark.skipif(not LINUX_NATIVE, reason="requires Linux x86-64 native execution")
def test_native_v3_compare_while_preserves_storage_and_backedge(
    tmp_path: Path,
) -> None:
    executable = build_stage1(tmp_path / "s3c-stage1-v3-compare-while")
    result = subprocess.run(
        [str(executable)],
        input=WHILE_COMPARE_INCREMENT_SOURCE,
        capture_output=True,
        check=False,
        shell=False,
    )
    assert result.returncode == 0
    records = _parse_v3_stream(result.stdout)
    source = WHILE_COMPARE_INCREMENT_SOURCE
    declaration_start = source.index(b"mut")
    name_start = source.index(b"value")
    assignment_start = source.index(b"value", source.index(b"value", source.index(b"while")) + 1)
    return_start = source.rindex(b"value")
    operator = source.index(b"<=>")
    add_operator = source.index(b"+")
    assert records["F"] == [(0, 1, source.index(b"main"), 4, 0, 1)]
    assert records["D"] == [(0, 0, 2, 3, name_start, 5, 1, 2, 0)]
    assert records["M"] == [(0, 0, 3, 1, 1, declaration_start)]
    assert records["V"] == [
        (0, 0, 2, 3, source.index(b"0"), 0, 0, -1),
        (1, 0, 2, 2, declaration_start, 0, 0, -1),
        (2, 0, 2, 2, name_start, 0, 0, -1),
        (3, 0, 3, 3, name_start, 0, 0, -1),
        (4, 0, 2, 3, source.index(b"1"), 0, 0, -1),
        (5, 0, 3, 1, operator, 0, 0, -1),
        (6, 0, 2, 2, assignment_start, 0, 0, -1),
        (7, 0, 3, 3, assignment_start, 0, 0, -1),
        (8, 0, 2, 3, source.rindex(b"1"), 0, 0, -1),
        (9, 0, 3, 3, add_operator, 0, 0, -1),
        (10, 0, 2, 2, assignment_start, 0, 0, -1),
        (11, 0, 2, 2, return_start, 0, 0, -1),
        (12, 0, 3, 3, return_start, 0, 0, -1),
    ]
    assert records["I"] == [
        (0, 0, 0, 0, 1, 1, 0, -1, 0),
        (1, 0, 0, 1, 1, 1, 0, -1, 0),
        (2, 0, 0, 2, 16, 0, 2, 0, -1),
        (3, 0, 0, 3, 24, 0, 0, -1, -1),
        (4, 0, 1, 4, 1, 1, 0, -1, 0),
        (5, 0, 1, 5, 15, 1, 1, 0, -1),
        (6, 0, 1, 6, 1, 1, 0, -1, 1),
        (7, 0, 1, 7, 13, 1, 2, -1, -1),
        (8, 0, 1, 8, 25, 0, 1, -1, -1),
        (9, 0, 2, 9, 1, 1, 0, -1, 0),
        (10, 0, 2, 10, 15, 1, 1, 0, -1),
        (11, 0, 2, 11, 1, 1, 0, -1, 1),
        (12, 0, 2, 12, 5, 1, 2, -1, -1),
        (13, 0, 2, 13, 1, 1, 0, -1, 0),
        (14, 0, 2, 14, 16, 0, 2, 0, -1),
        (15, 0, 2, 15, 24, 0, 0, -1, -1),
        (16, 0, 3, 16, 24, 0, 0, -1, -1),
        (17, 0, 4, 17, 24, 0, 0, -1, -1),
        (18, 0, 5, 18, 1, 1, 0, -1, 0),
        (19, 0, 5, 19, 15, 1, 1, 0, -1),
        (20, 0, 5, 20, 23, 0, 1, -1, -1),
    ]
    assert records["O"] == [
        (2, 0, 1),
        (2, 1, 0),
        (5, 0, 2),
        (7, 0, 3),
        (7, 1, 4),
        (8, 0, 5),
        (10, 0, 6),
        (10, 1, 7),
        (12, 0, 8),
        (14, 0, 10),
        (14, 1, 9),
        (19, 0, 11),
        (20, 0, 12),
    ]
    assert records["R"] == [
        (0, 0, 0),
        (1, 0, 1),
        (4, 0, 2),
        (5, 0, 3),
        (6, 0, 4),
        (7, 0, 5),
        (9, 0, 6),
        (10, 0, 7),
        (11, 0, 8),
        (12, 0, 9),
        (13, 0, 10),
        (18, 0, 11),
        (19, 0, 12),
    ]
    assert records["B"] == [
        (0, 0, 0, 4, 3),
        (0, 1, 1, 5, 8),
        (0, 2, 2, 7, 15),
        (0, 3, 3, 1, 16),
        (0, 4, 4, 1, 17),
        (0, 5, 5, 3, 20),
    ]
    assert records["T"] == [
        (3, 2, 1, -1, -1, -1, -1),
        (8, 3, 2, 3, 4, 5, -1),
        (15, 2, 1, -1, -1, -1, -1),
        (16, 2, 5, -1, -1, -1, -1),
        (17, 2, 5, -1, -1, -1, -1),
        (20, 1, -1, -1, -1, -1, 12),
    ]
    assert records["Z"] == [(15,)]


@pytest.mark.skipif(not LINUX_NATIVE, reason="requires Linux x86-64 native execution")
def test_native_v3_dependent_mutable_initializer_feeds_compare_loads(
    tmp_path: Path,
) -> None:
    executable = build_stage1(tmp_path / "s3c-stage1-v3-dependent-while")
    result = subprocess.run(
        [str(executable)],
        input=WHILE_DEPENDENT_SOURCE,
        capture_output=True,
        check=False,
        shell=False,
    )
    assert result.returncode == 0
    records = _parse_v3_stream(result.stdout)
    source = WHILE_DEPENDENT_SOURCE
    assert records["D"] == [
        (0, 0, 2, 3, source.index(b"position"), 8, 1, 2, 0),
        (1, 0, 2, 3, source.index(b"end"), 3, 1, 2, 1),
    ]
    assert records["M"] == [
        (0, 0, 3, 1, 1, source.index(b"mut")),
        (0, 1, 3, 1, 1, source.index(b"mut", source.index(b"mut") + 1)),
    ]
    assert [row[4] for row in records["I"]] == [
        1, 1, 16, 1, 15, 1, 5, 1, 16, 24,
        1, 15, 1, 15, 13, 25,
        1, 15, 1, 5, 1, 16, 24,
        24, 24, 1, 15, 23,
    ]
    assert records["B"] == [
        (0, 0, 0, 10, 9),
        (0, 1, 1, 6, 15),
        (0, 2, 2, 7, 22),
        (0, 3, 3, 1, 23),
        (0, 4, 4, 1, 24),
        (0, 5, 5, 3, 27),
    ]
    assert records["T"] == [
        (9, 2, 1, -1, -1, -1, -1),
        (15, 3, 2, 3, 4, 11, -1),
        (22, 2, 1, -1, -1, -1, -1),
        (23, 2, 5, -1, -1, -1, -1),
        (24, 2, 5, -1, -1, -1, -1),
        (27, 1, -1, -1, -1, -1, 18),
    ]
    assert records["Z"] == [(15,)]


@pytest.mark.skipif(not LINUX_NATIVE, reason="requires Linux x86-64 native execution")
def test_native_v3_match_compare_emits_branch3_and_complete_targets(
    tmp_path: Path,
) -> None:
    executable = build_stage1(tmp_path / "s3c-stage1-v3-match-compare")
    result = subprocess.run(
        [str(executable)],
        input=MATCH_COMPARE_SOURCE,
        capture_output=True,
        check=False,
        shell=False,
    )
    assert result.returncode == 0
    records = _parse_v3_stream(result.stdout)
    declaration_start = MATCH_COMPARE_SOURCE.index(b"mut")
    name_start = MATCH_COMPARE_SOURCE.index(b"value")
    operator = MATCH_COMPARE_SOURCE.index(b"<=>")
    literal_two = MATCH_COMPARE_SOURCE.index(b"2")
    negative_label = MATCH_COMPARE_SOURCE.index(b"-1:")
    neutral_label = MATCH_COMPARE_SOURCE.index(b"0:")
    positive_label = MATCH_COMPARE_SOURCE.index(b"1:")
    negative_start = MATCH_COMPARE_SOURCE.index(b"-1", negative_label + len(b"-1:"))
    neutral_start = MATCH_COMPARE_SOURCE.index(b"0", neutral_label + len(b"0:"))
    positive_start = MATCH_COMPARE_SOURCE.index(b"1", positive_label + len(b"1:"))
    assert records["F"] == [(0, 1, MATCH_COMPARE_SOURCE.index(b"main"), 4, 0, 1)]
    assert records["B"] == [
        (0, 0, 0, 8, 7),
        (0, 1, 1, 2, 9),
        (0, 2, 2, 2, 11),
        (0, 3, 3, 2, 13),
    ]
    assert records["D"] == [(0, 0, 2, 3, name_start, 5, 1, 2, 0)]
    assert records["M"] == [(0, 0, 3, 1, 1, declaration_start)]
    assert records["V"] == [
        (0, 0, 2, 3, MATCH_COMPARE_SOURCE.index(b"1"), 0, 0, -1),
        (1, 0, 2, 2, declaration_start, 0, 0, -1),
        (2, 0, 2, 2, name_start, 0, 0, -1),
        (3, 0, 3, 3, name_start, 0, 0, -1),
        (4, 0, 2, 3, literal_two, 0, 0, -1),
        (5, 0, 3, 1, operator, 0, 0, -1),
        (6, 0, 2, 1, negative_start, 0, 0, -1),
        (7, 0, 2, 1, neutral_start, 0, 0, -1),
        (8, 0, 2, 1, positive_start, 0, 0, -1),
    ]
    assert records["I"] == [
        (0, 0, 0, 0, 1, 1, 0, -1, 1),
        (1, 0, 0, 1, 1, 1, 0, -1, 0),
        (2, 0, 0, 2, 16, 0, 2, 0, -1),
        (3, 0, 0, 3, 1, 1, 0, -1, 0),
        (4, 0, 0, 4, 15, 1, 1, 0, -1),
        (5, 0, 0, 5, 1, 1, 0, -1, 2),
        (6, 0, 0, 6, 13, 1, 2, -1, -1),
        (7, 0, 0, 7, 25, 0, 1, -1, -1),
        (8, 0, 1, 0, 1, 1, 0, -1, -1),
        (9, 0, 1, 1, 23, 0, 1, -1, -1),
        (10, 0, 2, 0, 1, 1, 0, -1, 0),
        (11, 0, 2, 1, 23, 0, 1, -1, -1),
        (12, 0, 3, 0, 1, 1, 0, -1, 1),
        (13, 0, 3, 1, 23, 0, 1, -1, -1),
    ]
    assert records["O"] == [
        (2, 0, 1),
        (2, 1, 0),
        (4, 0, 2),
        (6, 0, 3),
        (6, 1, 4),
        (7, 0, 5),
        (9, 0, 6),
        (11, 0, 7),
        (13, 0, 8),
    ]
    assert records["R"] == [
        (0, 0, 0),
        (1, 0, 1),
        (3, 0, 2),
        (4, 0, 3),
        (5, 0, 4),
        (6, 0, 5),
        (8, 0, 6),
        (10, 0, 7),
        (12, 0, 8),
    ]
    assert records["T"] == [
        (7, 3, 1, 2, 3, 5, -1),
        (9, 1, -1, -1, -1, -1, 6),
        (11, 1, -1, -1, -1, -1, 7),
        (13, 1, -1, -1, -1, -1, 8),
    ]
    assert records["Z"] == [(15,)]


@pytest.mark.skipif(not LINUX_NATIVE, reason="requires Linux x86-64 native execution")
def test_native_v3_mutable_storage_followups_preserve_hosted_contract(
    tmp_path: Path,
) -> None:
    executable = build_stage1(tmp_path / "s3c-stage1-v3-mutable-storage-followups")
    fixtures = (
        (
            "read",
            b"fn main() -> i64:\n"
            b"    mut value: i64 = 1\n"
            b"    result: i64 = value + value\n"
            b"    return result\n",
        ),
        (
            "assignment",
            b"fn main() -> i64:\n"
            b"    mut value: i64 = 1\n"
            b"    value = 2\n"
            b"    return value\n",
        ),
        (
            "arithmetic_initializer",
            b"fn main() -> i64:\n"
            b"    mut value: i64 = 1 + 2\n"
            b"    return value\n",
        ),
    )
    for name, source in fixtures:
        result = subprocess.run(
            [str(executable)],
            input=source,
            capture_output=True,
            check=False,
            shell=False,
        )
        assert result.returncode == 0, name
        records = _parse_v3_stream(result.stdout)
        declaration_start = source.index(b"mut")
        name_start = source.index(b"value")
        assert records["F"] == [(0, 1, source.index(b"main"), 4, 0, 1)]
        assert records["M"] == [(0, 0, 3, 1, 1, declaration_start)]
        if name == "read":
            result_name_start = source.index(b"result")
            first_use = source.index(b"value", result_name_start)
            second_use = source.index(b"value", first_use + 1)
            operator = source.index(b"+")
            assert records["D"] == [
                (0, 0, 2, 3, name_start, 5, 1, 2, 0),
                (result_name_start, 0, 2, 3, result_name_start, 6, 0, 1, 7),
            ]
            assert records["V"] == [
                (0, 0, 2, 3, source.index(b"1"), 0, 0, -1),
                (1, 0, 2, 2, declaration_start, 0, 0, -1),
                (2, 0, 2, 2, first_use, 0, 0, -1),
                (3, 0, 3, 3, first_use, 0, 0, -1),
                (4, 0, 2, 2, second_use, 0, 0, -1),
                (5, 0, 3, 3, second_use, 0, 0, -1),
                (6, 0, 3, 3, operator, 0, 0, -1),
                (7, 0, 3, 3, result_name_start, 0, 0, -1),
            ]
            assert records["I"] == [
                (0, 0, 0, 0, 1, 1, 0, -1, 1),
                (1, 0, 0, 1, 1, 1, 0, -1, 0),
                (2, 0, 0, 2, 16, 0, 2, 0, -1),
                (3, 0, 0, 3, 1, 1, 0, -1, 0),
                (4, 0, 0, 4, 15, 1, 1, 0, -1),
                (5, 0, 0, 5, 1, 1, 0, -1, 0),
                (6, 0, 0, 6, 15, 1, 1, 0, -1),
                (7, 0, 0, 7, 5, 1, 2, -1, -1),
                (8, 0, 0, 8, 3, 1, 1, -1, -1),
                (9, 0, 0, 9, 23, 0, 1, -1, -1),
            ]
            assert records["O"] == [
                (2, 0, 1),
                (2, 1, 0),
                (4, 0, 2),
                (6, 0, 4),
                (7, 0, 3),
                (7, 1, 5),
                (8, 0, 6),
                (9, 0, 7),
            ]
            assert records["R"] == [
                (0, 0, 0),
                (1, 0, 1),
                (3, 0, 2),
                (4, 0, 3),
                (5, 0, 4),
                (6, 0, 5),
                (7, 0, 6),
                (8, 0, 7),
            ]
            assert records["T"] == [(9, 1, -1, -1, -1, -1, 7)]
        elif name == "assignment":
            assignment_start = source.index(b"value", source.index(b"value") + 1)
            return_start = source.index(b"value", source.index(b"return"))
            assert records["D"] == [(0, 0, 2, 3, name_start, 5, 1, 2, 0)]
            assert records["V"] == [
                (0, 0, 2, 3, source.index(b"1"), 0, 0, -1),
                (1, 0, 2, 2, declaration_start, 0, 0, -1),
                (2, 0, 3, 3, source.index(b"2"), 0, 0, -1),
                (3, 0, 2, 2, assignment_start, 0, 0, -1),
                (4, 0, 2, 2, return_start, 0, 0, -1),
                (5, 0, 3, 3, return_start, 0, 0, -1),
            ]
            assert records["I"] == [
                (0, 0, 0, 0, 1, 1, 0, -1, 1),
                (1, 0, 0, 1, 1, 1, 0, -1, 0),
                (2, 0, 0, 2, 16, 0, 2, 0, -1),
                (3, 0, 0, 3, 1, 1, 0, -1, 2),
                (4, 0, 0, 4, 1, 1, 0, -1, 0),
                (5, 0, 0, 5, 16, 0, 2, 0, -1),
                (6, 0, 0, 6, 1, 1, 0, -1, 0),
                (7, 0, 0, 7, 15, 1, 1, 0, -1),
                (8, 0, 0, 8, 23, 0, 1, -1, -1),
            ]
            assert records["O"] == [
                (2, 0, 1),
                (2, 1, 0),
                (5, 0, 3),
                (5, 1, 2),
                (7, 0, 4),
                (8, 0, 5),
            ]
            assert records["R"] == [
                (0, 0, 0),
                (1, 0, 1),
                (3, 0, 2),
                (4, 0, 3),
                (6, 0, 4),
            ]
            assert records["T"] == [(8, 1, -1, -1, -1, -1, 5)]
        else:
            operator = source.index(b"+")
            return_start = source.index(b"value", source.index(b"return"))
            assert records["D"] == [(0, 0, 2, 3, name_start, 5, 1, 2, 0)]
            assert records["V"] == [
                (0, 0, 3, 3, operator, 0, 0, -1),
                (1, 0, 2, 2, declaration_start, 0, 0, -1),
                (2, 0, 2, 2, return_start, 0, 0, -1),
                (3, 0, 3, 3, return_start, 0, 0, -1),
            ]
            assert records["I"] == [
                (0, 0, 0, 0, 1, 1, 0, -1, 3),
                (1, 0, 0, 1, 1, 1, 0, -1, 0),
                (2, 0, 0, 2, 16, 0, 2, 0, -1),
                (3, 0, 0, 3, 1, 1, 0, -1, 0),
                (4, 0, 0, 4, 15, 1, 1, 0, -1),
                (5, 0, 0, 5, 23, 0, 1, -1, -1),
            ]
            assert records["O"] == [(2, 0, 1), (2, 1, 0), (4, 0, 2), (5, 0, 3)]
            assert records["R"] == [(0, 0, 0), (1, 0, 1), (3, 0, 2), (4, 0, 3)]
            assert records["T"] == [(5, 1, -1, -1, -1, -1, 3)]
        assert records["Z"] == [(15,)]


@pytest.mark.skipif(not LINUX_NATIVE, reason="requires Linux x86-64 native execution")
@pytest.mark.parametrize(
    ("name", "source"),
    (
        ("break_simple", BREAK_SIMPLE_SOURCE),
        ("break_nested_inner", BREAK_NESTED_INNER_SOURCE),
    ),
)
def test_native_event_spine_accepts_v3_break_canaries(
    tmp_path: Path,
    name: str,
    source: bytes,
) -> None:
    executable = build_stage1(tmp_path / f"s3c-stage1-semantic-event-spine-{name}")
    result = subprocess.run(
        [str(executable)],
        input=source,
        capture_output=True,
        check=False,
        shell=False,
    )
    assert result.returncode == 0
    assert result.stdout == b""
    assert _parse_rows(result.stderr)


@pytest.mark.skipif(not LINUX_NATIVE, reason="requires Linux x86-64 native execution")
@pytest.mark.parametrize(
    ("name", "source", "binding_kind", "mutable_flag", "target_kind"),
    (
        (
            "parameter_binding",
            b"fn identity(value: i64) -> i64:\n    return value\nfn main() -> i64:\n    return 0\n",
            1,
            0,
            1,
        ),
        (
            "immutable_local_binding",
            b"fn main() -> i64:\n    value: i64 = 1\n    return value\n",
            2,
            0,
            1,
        ),
        (
            "mutable_local_storage",
            b"fn main() -> i64:\n    mut value: i64 = 1\n    return value\n",
            2,
            1,
            2,
        ),
        (
            "mutable_additive_local_storage",
            b"fn worker(start: i64) -> i64:\n    mut value: i64 = start + 1\n    return value\nfn main() -> i64:\n    return 0\n",
            2,
            1,
            2,
        ),
    ),
)
def test_native_event_spine_emits_binding_and_storage_records(
    tmp_path: Path,
    name: str,
    source: bytes,
    binding_kind: int,
    mutable_flag: int,
    target_kind: int,
) -> None:
    executable = build_stage1(tmp_path / f"s3c-stage1-semantic-event-spine-{name}")
    result = subprocess.run(
        [str(executable)],
        input=source,
        capture_output=True,
        check=False,
        shell=False,
    )
    assert result.returncode == 0
    records = _parse_semantic_records(result.stderr)
    bindings = [row for row in records["D"] if row[2] == binding_kind]
    assert len(bindings) == 1
    binding = bindings[0]
    assert binding[6] == mutable_flag
    assert binding[7] == target_kind
    if target_kind == 1:
        values = {row[0] for row in records["V"]}
        assert binding[8] in values
        assert records["M"] == []
    else:
        assert len(records["M"]) == 1
        storage = records["M"][0]
        assert storage[0] == binding[1]
        assert storage[1] == binding[8]
        assert storage[4] == 1
        assert not any(row[2] == 2 for row in records["V"])


@pytest.mark.skipif(not LINUX_NATIVE, reason="requires Linux x86-64 native execution")
def test_native_event_spine_fails_closed_for_unsupported_canonical_source(
    tmp_path: Path,
) -> None:
    executable = build_stage1(tmp_path / "s3c-stage1-semantic-event-spine")
    result = subprocess.run(
        [str(executable)],
        input=CANONICAL_SOURCE.read_bytes(),
        capture_output=True,
        check=False,
        shell=False,
    )
    assert result.returncode == 2
    assert result.stdout == b""
    assert result.stderr == b"S3_STAGE1_V_REPLAY_BLOCKED\n"


@pytest.mark.skipif(not LINUX_NATIVE, reason="requires Linux x86-64 native execution")
@pytest.mark.parametrize(
    "source",
    [
        b"fn 7() -> tryte:\n    return 7\n",
        b"fn main(x: i64) -> tryte:\n    return x\n",
        b"fn main() -> tryte:\n    return 7\n    mut later: tryte = 8\n",
        b"foreign fn host(x: i64) -> i64\nfn read(x: i64) -> tryte:\n    return host(x)\nfn main() -> tryte:\n    return 7\n",
    ],
)
def test_native_event_spine_rejects_invalid_header_or_return_contract(
    tmp_path: Path,
    source: bytes,
) -> None:
    executable = build_stage1(tmp_path / "s3c-stage1-semantic-event-spine")
    result = subprocess.run(
        [str(executable)],
        input=source,
        capture_output=True,
        check=False,
        shell=False,
    )
    assert result.returncode == 2
    assert result.stdout == b""
    assert result.stderr == b"S3_STAGE1_V_REPLAY_BLOCKED\n"
