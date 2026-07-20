from __future__ import annotations

from pathlib import Path

import pytest

from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import compile_source, run_source, run_source_with_buffer_capture

EVENT_PROOF_PATH = Path("examples/self_hosting/assembly_renderer_event_proof.s3")


@pytest.fixture(scope="module")
def proof_source() -> str:
    return EVENT_PROOF_PATH.read_text(encoding="utf-8")


def test_proof_file_exists() -> None:
    assert EVENT_PROOF_PATH.is_file()


def test_proof_compiles(proof_source: str) -> None:
    result = compile_source(proof_source, mode=SyntaxMode.V0_6)
    assert result.ir.functions


def test_proof_executes_and_returns_zero(proof_source: str) -> None:
    result = run_source(proof_source, mode=SyntaxMode.V0_6)
    assert result == 0


def test_proof_deterministic(proof_source: str) -> None:
    results = [run_source(proof_source, mode=SyntaxMode.V0_6) for _ in range(3)]
    assert all(r == 0 for r in results)


def test_proof_source_contains_while() -> None:
    source = EVENT_PROOF_PATH.read_text(encoding="utf-8")
    assert "while" in source


def test_proof_no_unrolled_assignments() -> None:
    source = EVENT_PROOF_PATH.read_text(encoding="utf-8")
    lines = source.splitlines()
    in_while = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("while "):
            in_while = True
            continue
        if in_while and stripped and not stripped.startswith("while") and not stripped.startswith("buffer_c[") and not stripped.startswith("i"):
            in_while = False
        if not in_while:
            if stripped.startswith("buffer_c[") and "=" in stripped:
                pytest.fail(f"unrolled assignment found: {stripped}")


def test_proof_no_event_raw_byte() -> None:
    source = EVENT_PROOF_PATH.read_text(encoding="utf-8")
    assert "EVENT_RAW_BYTE" not in source


def test_proof_structure_compute_byte_exists(proof_source: str) -> None:
    assert "fn compute_byte" in proof_source


def test_proof_structure_event_kind_exists(proof_source: str) -> None:
    assert "fn event_kind" in proof_source


def test_proof_structure_event_data_exists(proof_source: str) -> None:
    assert "fn event_data" in proof_source


def test_proof_structure_event_count_exists(proof_source: str) -> None:
    assert "fn event_count" in proof_source


def test_proof_structure_strategy_c_exists(proof_source: str) -> None:
    assert "fn strategy_c" in proof_source


def test_proof_structure_main_exists(proof_source: str) -> None:
    assert "fn main" in proof_source


def test_proof_ir_has_while_blocks(proof_source: str) -> None:
    result = compile_source(proof_source, mode=SyntaxMode.V0_6)
    strategy = [f for f in result.ir.functions if f.name == "strategy_c"]
    assert strategy
    block_names = [b.name for b in strategy[0].blocks]
    assert any("while" in name for name in block_names)


def test_proof_ir_entry_has_terminator(proof_source: str) -> None:
    result = compile_source(proof_source, mode=SyntaxMode.V0_6)
    for func in result.ir.functions:
        entry = func.blocks[0]
        assert entry.instructions
        assert entry.instructions[-1].opcode.name in {"JUMP", "BRANCH3", "RETURN"}


def test_proof_main_calls_strategy_c(proof_source: str) -> None:
    assert "return strategy_c()" in proof_source


def test_proof_events_are_structural() -> None:
    source = EVENT_PROOF_PATH.read_text(encoding="utf-8")
    assert "fn event_kind" in source
    assert "fn event_data" in source
    assert "fn event_count" in source


def test_proof_no_standalone_byte_values_outside_functions() -> None:
    source = EVENT_PROOF_PATH.read_text(encoding="utf-8")
    for keyword in ("EVENT_KIND", "EVENT_DATA", "RAW_BYTE", "EVENT_RAW_BYTE"):
        assert keyword not in source
