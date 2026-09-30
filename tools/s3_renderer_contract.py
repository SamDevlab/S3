from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True, slots=True)
class RendererBufferLayout:
    buffer_names: tuple[str, ...]
    capacities: tuple[int, ...]

    def __post_init__(self) -> None:
        if len(self.buffer_names) != len(self.capacities):
            raise ValueError("buffer_names and capacities must match")
        if not self.buffer_names:
            raise ValueError("at least one buffer required")


@dataclass(frozen=True, slots=True)
class FixtureMetadata:
    s3_path: str
    golden_path: str
    expected_sha256: str
    expected_bytes: int
    expected_lines: int
    buffer_count: int
    buffer_offset: int
    entry: str
    buffer_layout: RendererBufferLayout
    max_instructions: int = 100000


FIXTURE_FRAGMENTS: dict[str, dict[int, tuple[str, bytes]]] = {
    "first": {
        1: (".s3asm", b".s3asm"),
        2: (".function", b".function"),
        3: (".register", b".register"),
        4: (".label", b".label"),
        5: (".end", b".end"),
        6: ("->", b"->"),
        7: (" ", b" "),
        8: (",", b","),
        9: ("; source=", b"; source="),
        10: ("newline", b"\n"),
        11: ("cr", b"\r"),
    },
    "simple_call": {
        1: (".s3asm", b".s3asm"),
        2: (".function", b".function"),
        3: (".param", b".param"),
        4: (".register", b".register"),
        5: (".label", b".label"),
        6: (".end", b".end"),
        7: ("; source=", b"; source="),
    },
    "sign": {
        1: (".s3asm", b".s3asm"),
        2: (".function", b".function"),
        3: (".param", b".param"),
        4: (".register", b".register"),
        5: (".label", b".label"),
        6: (".end", b".end"),
        7: ("; source=", b"; source="),
    },
}


COMMON_FRAGMENT_NAMES: dict[int, str] = {
    1: ".s3asm",
    2: ".function",
    4: ".register",
    5: ".label",
    6: ".end",
}

FIXTURE_SPECIFIC_FRAGMENTS: dict[str, dict[int, str]] = {
    "first": {
        3: ".register",
        7: " ",
        8: ",",
        9: "; source=",
        10: "newline",
        11: "cr",
    },
    "simple_call": {
        3: ".param",
        7: "; source=",
    },
    "sign": {
        3: ".param",
        7: "; source=",
    },
}


FIXTURE_SYMBOLS: dict[str, dict[int, str]] = {
    "first": {
        12: "tryte",
        100: "main",
        101: "entry",
        130: "r0",
        131: "r1",
        132: "r2",
        133: "r3",
        134: "r4",
        135: "r5",
    },
    "simple_call": {
        1: "add",
        2: "main",
        3: "entry",
        4: "r0",
        5: "r1",
        6: "r2",
        7: "tryte",
    },
    "sign": {
        1: "sign",
        2: "trit",
        3: "tryte",
        4: "r0",
        5: "r1",
        6: "r2",
        7: "r3",
        8: "r4",
        9: "r5",
        10: "r6",
        11: "entry",
        12: "main",
        13: "switch_negative_0",
        14: "switch_neutral_1",
        15: "switch_positive_2",
    },
}


FIXTURE_OPCODES: dict[str, dict[int, str]] = {
    "first": {
        120: "TCONST",
        121: "TMOV",
        123: "TADD",
        124: "TRET",
    },
    "simple_call": {
        1: "TADD",
        2: "TRET",
        3: "TCONST",
        4: "TCALL",
    },
    "sign": {
        1: "TCONST",
        2: "TCMP",
        3: "TBR3",
        5: "TRET",
        6: "TCALL",
    },
}


COMMON_SYMBOL_NAMES: dict[str, int] = {
    "tryte": 12 if False else 0,
    "r0": 130 if False else 0,
    "r1": 131 if False else 0,
    "r2": 132 if False else 0,
    "entry": 101 if False else 0,
    "main": 100 if False else 0,
}

COMMON_OPCODE_NAMES: dict[str, int] = {
    "TRET": 124 if False else 0,
    "TCONST": 120 if False else 0,
}


FIXTURE_METADATA: dict[str, FixtureMetadata] = {
    "first": FixtureMetadata(
        s3_path="examples/self_hosting/assembly_renderer_generic_text.s3",
        golden_path="tests/golden/inspect/first.assembly.txt",
        expected_sha256="d50d859255b8b5cffff19b1806346cb3172ef160715e1aa6797382c8ff230804",
        expected_bytes=377,
        expected_lines=16,
        buffer_count=2,
        buffer_offset=0,
        entry="render_first",
        buffer_layout=RendererBufferLayout(
            buffer_names=("buffer_low", "buffer_high"),
            capacities=(300, 300),
        ),
        max_instructions=500000,
    ),
    "first_generic": FixtureMetadata(
        s3_path="examples/self_hosting/assembly_renderer_generic_text.s3",
        golden_path="tests/golden/inspect/first.assembly.txt",
        expected_sha256="d50d859255b8b5cffff19b1806346cb3172ef160715e1aa6797382c8ff230804",
        expected_bytes=377,
        expected_lines=16,
        buffer_count=2,
        buffer_offset=0,
        entry="render_first",
        buffer_layout=RendererBufferLayout(
            buffer_names=("buffer_low", "buffer_high"),
            capacities=(300, 300),
        ),
        max_instructions=500000,
    ),
    "simple_call_generic": FixtureMetadata(
        s3_path="examples/self_hosting/assembly_renderer_generic_text.s3",
        golden_path="tests/golden/inspect/simple_call.assembly.txt",
        expected_sha256="63760cea3c47f413a17fe2b4834cd929ac3909e8f34fd80685b003d272ce55e7",
        expected_bytes=448,
        expected_lines=21,
        buffer_count=2,
        buffer_offset=0,
        entry="render_simple_call",
        buffer_layout=RendererBufferLayout(
            buffer_names=("buffer_low", "buffer_high"),
            capacities=(300, 300),
        ),
        max_instructions=500000,
    ),
    "simple_call": FixtureMetadata(
        s3_path="examples/self_hosting/assembly_renderer_simple_call_text.s3",
        golden_path="tests/golden/inspect/simple_call.assembly.txt",
        expected_sha256="63760cea3c47f413a17fe2b4834cd929ac3909e8f34fd80685b003d272ce55e7",
        expected_bytes=448,
        expected_lines=21,
        buffer_count=2,
        buffer_offset=0,
        entry="main",
        buffer_layout=RendererBufferLayout(
            buffer_names=("buffer_low", "buffer_high"),
            capacities=(300, 300),
        ),
    ),
    "sign": FixtureMetadata(
        s3_path="examples/self_hosting/assembly_renderer_generic_text.s3",
        golden_path="tests/golden/inspect/sign.assembly.txt",
        expected_sha256="5f3e9329782012bccfcbf9e1d005b7b7c5c3739ccee9e35f558d9422e1b49caf",
        expected_bytes=829,
        expected_lines=32,
        buffer_count=4,
        buffer_offset=0,
        entry="render_sign",
        buffer_layout=RendererBufferLayout(
            buffer_names=("buffer_low", "buffer_mid", "buffer_high", "buffer_tail"),
            capacities=(300, 300, 300, 46),
        ),
        max_instructions=1100000,
    ),
    "sign_generic": FixtureMetadata(
        s3_path="examples/self_hosting/assembly_renderer_generic_text.s3",
        golden_path="tests/golden/inspect/sign.assembly.txt",
        expected_sha256="5f3e9329782012bccfcbf9e1d005b7b7c5c3739ccee9e35f558d9422e1b49caf",
        expected_bytes=829,
        expected_lines=32,
        buffer_count=4,
        buffer_offset=0,
        entry="render_sign",
        buffer_layout=RendererBufferLayout(
            buffer_names=("buffer_low", "buffer_mid", "buffer_high", "buffer_tail"),
            capacities=(300, 300, 300, 46),
        ),
        max_instructions=1100000,
    ),
}


def _golden_file_bytes(relative_path: str) -> bytes:
    path = REPO_ROOT / relative_path
    try:
        return path.read_bytes()
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"golden file not found: {relative_path}") from exc


def flatten_capture(memory: dict[int, list[int | None]], buffer_count: int, buffer_offset: int = 0, expected_bytes: int | None = None) -> bytes:
    out = bytearray()
    for buf_idx in range(buffer_count):
        buf = memory.get(buffer_offset + buf_idx, [])
        for v in buf:
            if v is None:
                # Se encontrarmos None, não lemos mais deste buffer.
                # Se isso nos deixar com menos bytes do que o esperado, o erro será lançado no final.
                break
            out.append(v)

    if expected_bytes is not None:
        if len(out) < expected_bytes:
            raise ValueError(f"insufficient data: got {len(out)}, expected {expected_bytes}")
        return bytes(out[:expected_bytes])
    else:
        while out and out[-1] == 0:
            out.pop()
        return bytes(out)


import functools

@functools.lru_cache(maxsize=None)
def _capture_fixture_output(source: str, buffer_count: int, buffer_offset: int = 0, entry: str = "main", max_instructions: int = 100000, expected_bytes: int | None = None) -> bytes:
    from bootstrap.s3.pipeline import run_source_with_buffer_capture
    result, capture = run_source_with_buffer_capture(source, entry=entry, max_instructions=max_instructions)
    if result != 0:
        raise ValueError(f"S3 program returned non-zero: {result}")
    if not capture:
        raise ValueError("memory capture is empty")
    return flatten_capture(capture[-1], buffer_count, buffer_offset, expected_bytes)


def verify_fixture_metadata(name: str) -> tuple[bool, str]:
    meta = FIXTURE_METADATA.get(name)
    if meta is None:
        return False, f"unknown fixture: {name}"
    path = REPO_ROOT / meta.s3_path
    if not path.is_file():
        return False, f"missing S3 program: {meta.s3_path}"
    source = path.read_text(encoding="utf-8")
    try:
        output = _capture_fixture_output(source, meta.buffer_count, meta.buffer_offset, meta.entry, meta.max_instructions, meta.expected_bytes)
    except (ValueError, Exception) as error:
        return False, f"execution failed: {error}"
    sha256 = hashlib.sha256(output).hexdigest()
    if sha256 != meta.expected_sha256:
        return False, f"SHA-256 mismatch: expected {meta.expected_sha256}, got {sha256}"
    if len(output) != meta.expected_bytes:
        return False, f"byte count mismatch: expected {meta.expected_bytes}, got {len(output)}"
    lines = output.count(10)
    if lines != meta.expected_lines:
        return False, f"line count mismatch: expected {meta.expected_lines}, got {lines}"
    golden = _golden_file_bytes(meta.golden_path)
    if output != golden:
        return False, "output differs from golden blob"
    return True, "ok"


def audit_duplication() -> dict[str, object]:
    import os
    result: dict[str, object] = {}
    total_lines_before = 0
    for name in ("first", "simple_call", "sign"):
        meta = FIXTURE_METADATA[name]
        path = REPO_ROOT / meta.s3_path
        with open(path, encoding="utf-8") as f:
            text = f.read()
        lines = text.count("\n")
        total_lines_before += lines
        result[f"{name}_lines"] = lines
    result["total_lines_before"] = total_lines_before
    for name in ("first", "simple_call", "sign"):
        meta = FIXTURE_METADATA[name]
        result[f"{name}_bytes"] = meta.expected_bytes
        result[f"{name}_sha256"] = meta.expected_sha256
        result[f"{name}_buffer_count"] = meta.buffer_count
        result[f"{name}_fragment_count"] = len(FIXTURE_FRAGMENTS.get(name, {}))
        result[f"{name}_symbol_count"] = len(FIXTURE_SYMBOLS.get(name, {}))
        result[f"{name}_opcode_count"] = len(FIXTURE_OPCODES.get(name, {}))
    result["strategy"] = "C — consolidação conceitual sem compartilhamento físico"
    return result
