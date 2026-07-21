from __future__ import annotations

import hashlib
import subprocess
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
        122: "TINV",
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
        4: "TINV",
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
        s3_path="examples/self_hosting/assembly_renderer_first_text.s3",
        golden_path="tests/golden/inspect/first.assembly.txt",
        expected_sha256="46ebd2aef715d7a7e9f7ada01ca844b8ae23494ff6a5333f78c75db2eaca2f67",
        expected_bytes=441,
        expected_lines=18,
        buffer_count=2,
        buffer_offset=0,
        entry="main",
        buffer_layout=RendererBufferLayout(
            buffer_names=("buffer_low", "buffer_high"),
            capacities=(300, 300),
        ),
    ),
    "first_generic": FixtureMetadata(
        s3_path="examples/self_hosting/assembly_renderer_generic_text.s3",
        golden_path="tests/golden/inspect/first.assembly.txt",
        expected_sha256="46ebd2aef715d7a7e9f7ada01ca844b8ae23494ff6a5333f78c75db2eaca2f67",
        expected_bytes=441,
        expected_lines=18,
        buffer_count=2,
        buffer_offset=0,
        entry="render_first",
        buffer_layout=RendererBufferLayout(
            buffer_names=("buffer_low", "buffer_high"),
            capacities=(300, 300),
        ),
        max_instructions=500000,
    ),
    "simple_call": FixtureMetadata(
        s3_path="examples/self_hosting/assembly_renderer_simple_call_text.s3",
        golden_path="tests/golden/inspect/simple_call.assembly.txt",
        expected_sha256="d6de00c8c50618bcc8f3a458267eb8590956a9451980084b1add2f59d3267c0f",
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
        s3_path="examples/self_hosting/assembly_renderer_sign_text.s3",
        golden_path="tests/golden/inspect/sign.assembly.txt",
        expected_sha256="c077d2c49639b1a033505ec8c1ba1c60c78242e6e09c43f60a8aa5ed8b49e2d9",
        expected_bytes=946,
        expected_lines=36,
        buffer_count=3,
        buffer_offset=0,
        entry="main",
        buffer_layout=RendererBufferLayout(
            buffer_names=("buffer_low", "buffer_mid", "buffer_high"),
            capacities=(364, 364, 218),
        ),
    ),
}


def _git_blob_bytes(relative_path: str) -> bytes:
    result = subprocess.run(
        ["git", "show", f"HEAD:{relative_path}"],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise FileNotFoundError(f"git blob not found: {relative_path}")
    return result.stdout


def _capture_fixture_output(source: str, buffer_count: int, buffer_offset: int = 0, entry: str = "main", max_instructions: int = 100000, expected_bytes: int | None = None) -> bytes:
    from bootstrap.s3.pipeline import run_source_with_buffer_capture
    result, capture = run_source_with_buffer_capture(source, entry=entry, max_instructions=max_instructions)
    if result != 0:
        raise ValueError(f"S3 program returned non-zero: {result}")
    if not capture:
        raise ValueError("memory capture is empty")
    memory = capture[-1]
    out = bytearray()
    for buf_idx in range(buffer_count):
        buf = memory.get(buffer_offset + buf_idx, [])
        for v in buf:
            if v is None:
                break
            out.append(v)
    if expected_bytes is not None:
        if any(v is None for v in out[:expected_bytes]):
            raise ValueError("unexpected None in captured output within expected byte range")
        out = out[:expected_bytes]
    else:
        while out and out[-1] == 0:
            out.pop()
    return bytes(out)


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
    golden = _git_blob_bytes(meta.golden_path)
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
