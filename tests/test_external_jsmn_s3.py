from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

import pytest

from bootstrap.s3.pipeline import compile_source, run_source_with_buffer_capture


SOURCE_PATH = Path("examples/external/jsmn/jsmn_demo.s3")
INPUT_CAPACITY = 96
TOKEN_CAPACITY = 32

JSMN_OBJECT = 1
JSMN_ARRAY = 2
JSMN_STRING = 4
JSMN_PRIMITIVE = 8
JSMN_ERROR_NOMEM = -1
JSMN_ERROR_INVAL = -2
JSMN_ERROR_PART = -3


@dataclass
class Token:
    type: int
    start: int
    end: int
    size: int = 0
    parent: int = -1


def _reference_jsmn(data: bytes) -> tuple[int, list[Token]]:
    """Independent oracle for upstream jsmn's default non-strict token contract."""
    tokens: list[Token] = []
    pos = 0
    toksuper = -1

    def allocate(type_: int, start: int, end: int = -1) -> int:
        nonlocal toksuper
        if len(tokens) >= TOKEN_CAPACITY:
            return JSMN_ERROR_NOMEM
        parent = toksuper
        tokens.append(Token(type_, start, end, 0, parent))
        if parent >= 0:
            tokens[parent].size += 1
        return len(tokens) - 1

    while pos < len(data):
        ch = data[pos]

        if ch in (ord("{"), ord("[")):
            type_ = JSMN_OBJECT if ch == ord("{") else JSMN_ARRAY
            index = allocate(type_, pos)
            if index < 0:
                return index, tokens
            toksuper = index

        elif ch in (ord("}"), ord("]")):
            type_ = JSMN_OBJECT if ch == ord("}") else JSMN_ARRAY
            index = len(tokens) - 1
            while index >= 0 and tokens[index].end != -1:
                index -= 1
            if index < 0 or tokens[index].type != type_:
                return JSMN_ERROR_INVAL, tokens
            tokens[index].end = pos + 1
            toksuper = tokens[index].parent

        elif ch == ord('"'):
            start_quote = pos
            pos += 1
            while pos < len(data):
                ch = data[pos]
                if ch == ord('"'):
                    index = allocate(JSMN_STRING, start_quote + 1, pos)
                    if index < 0:
                        return index, tokens
                    break
                if ch == ord("\\"):
                    pos += 1
                    if pos >= len(data):
                        return JSMN_ERROR_PART, tokens
                    escaped = data[pos]
                    if escaped == ord("u"):
                        for _ in range(4):
                            pos += 1
                            if pos >= len(data):
                                return JSMN_ERROR_PART, tokens
                            digit = data[pos]
                            if not (
                                ord("0") <= digit <= ord("9")
                                or ord("A") <= digit <= ord("F")
                                or ord("a") <= digit <= ord("f")
                            ):
                                return JSMN_ERROR_INVAL, tokens
                    elif escaped not in b'"/\\bfrnt':
                        return JSMN_ERROR_INVAL, tokens
                pos += 1
            else:
                return JSMN_ERROR_PART, tokens

        elif ch in b"\t\r\n ":
            pass

        elif ch == ord(":"):
            toksuper = len(tokens) - 1

        elif ch == ord(","):
            if toksuper >= 0 and tokens[toksuper].type not in (JSMN_ARRAY, JSMN_OBJECT):
                toksuper = tokens[toksuper].parent

        else:
            start = pos
            while pos < len(data):
                primitive = data[pos]
                if primitive in b"\t\r\n ,]}:":
                    break
                if primitive < 32 or primitive >= 127:
                    return JSMN_ERROR_INVAL, tokens
                pos += 1
            index = allocate(JSMN_PRIMITIVE, start, pos)
            if index < 0:
                return index, tokens
            pos -= 1

        pos += 1

    if any(token.end == -1 for token in tokens):
        return JSMN_ERROR_PART, tokens
    return len(tokens), tokens


def _render_source(text: str) -> str:
    data = text.encode("ascii")
    assert len(data) <= INPUT_CAPACITY
    values = list(data) + [0] * (INPUT_CAPACITY - len(data))
    source = SOURCE_PATH.read_text(encoding="utf-8")
    source = re.sub(
        r"(?m)^    input_length: tryte = \d+$",
        f"    input_length: tryte = {len(data)}",
        source,
        count=1,
    )
    source = re.sub(
        r"(?m)^    input: tryte\[96\] = \[[^\n]+\]$",
        "    input: tryte[96] = [" + ", ".join(map(str, values)) + "]",
        source,
        count=1,
    )
    return source


def _run_s3(text: str, optimization: str = "O0") -> tuple[int, list[Token]]:
    source = _render_source(text)
    compilation = compile_source(source, optimization)
    main = next(function for function in compilation.ir.functions if function.name == "main")

    input_memories = sorted(
        (memory for memory in main.memory_objects if memory.length == INPUT_CAPACITY),
        key=lambda memory: memory.index,
    )
    token_memories = sorted(
        (memory for memory in main.memory_objects if memory.length == TOKEN_CAPACITY),
        key=lambda memory: memory.index,
    )
    assert len(input_memories) == 1
    assert len(token_memories) == 5
    tracked_memory_ids = {
        input_memories[0].index,
        *(memory.index for memory in token_memories),
    }

    result, captures = run_source_with_buffer_capture(source, optimization=optimization)
    main_capture = next(
        frame
        for frame in reversed(captures)
        if tracked_memory_ids.issubset(frame.keys())
    )
    if result < 0:
        return result, []

    types, starts, ends, sizes, _parents = (
        main_capture[memory.index] for memory in token_memories
    )
    tokens = [
        Token(int(types[i]), int(starts[i]), int(ends[i]), int(sizes[i]))
        for i in range(result)
    ]
    return result, tokens


@pytest.mark.parametrize(
    "text",
    [
        "{}",
        "[]",
        '{"a":1}',
        '{"a":[1,2,3]}',
        '{"a":{"b":true},"c":null}',
        '["a","b",false,-12]',
        '{ "escaped": "a\\n\\t\\\"b" }',
        '{"unicode":"\\u0041"}',
        '"raw\tcontrol"',
    ],
)
def test_s3_jsmn_matches_reference_tokens(text: str) -> None:
    expected_status, expected_tokens = _reference_jsmn(text.encode("ascii"))
    actual_status, actual_tokens = _run_s3(text)
    assert actual_status == expected_status
    assert [(t.type, t.start, t.end, t.size) for t in actual_tokens] == [
        (t.type, t.start, t.end, t.size) for t in expected_tokens
    ]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ('{"a":1]', JSMN_ERROR_INVAL),
        ('{"a":', JSMN_ERROR_PART),
        ('"unterminated', JSMN_ERROR_PART),
        ('"bad\\q"', JSMN_ERROR_INVAL),
        ('"bad\\u00xz"', JSMN_ERROR_INVAL),
    ],
)
def test_s3_jsmn_matches_reference_errors(text: str, expected: int) -> None:
    reference_status, _ = _reference_jsmn(text.encode("ascii"))
    assert reference_status == expected
    actual_status, _ = _run_s3(text)
    assert actual_status == expected


def test_s3_jsmn_reports_token_capacity_exhaustion() -> None:
    text = "[" + ",".join("0" for _ in range(40)) + "]"
    assert len(text) <= INPUT_CAPACITY
    reference_status, _ = _reference_jsmn(text.encode("ascii"))
    assert reference_status == JSMN_ERROR_NOMEM
    actual_status, _ = _run_s3(text)
    assert actual_status == JSMN_ERROR_NOMEM


@pytest.mark.parametrize("optimization", ["O0", "O1"])
def test_s3_jsmn_representative_fixture_is_stable_across_optimization(optimization: str) -> None:
    text = '{"a":[1,{"b":"x"}],"c":false}'
    expected_status, expected_tokens = _reference_jsmn(text.encode("ascii"))
    actual_status, actual_tokens = _run_s3(text, optimization)
    assert actual_status == expected_status
    assert [(t.type, t.start, t.end, t.size) for t in actual_tokens] == [
        (t.type, t.start, t.end, t.size) for t in expected_tokens
    ]


def test_demo_source_is_zero_allocation_fixed_capacity_workload() -> None:
    source = SOURCE_PATH.read_text(encoding="utf-8")
    assert "input: tryte[96]" in source
    assert "token_type: tryte[32]" in source
    assert "token_parent: tryte[32]" in source
    assert "heap" not in source.lower()
    assert "malloc" not in source.lower()
