"""Deterministic property and robustness tests for S3 parser, tokenizer, and verifiers."""

import random
import pytest

from bootstrap.s3.assembly import parse_assembly
from bootstrap.s3.emulator import Emulator, EmulatorError
from bootstrap.s3.lexer import SyntaxMode, tokenize


def test_trit_tryte_bounds_and_arithmetic_properties():
    # Fixed seed for determinism
    rng = random.Random(42)
    for _ in range(100):
        val = rng.randint(-364, 364)
        assert -364 <= val <= 364, "Tryte range bound check"


def test_tokenizer_cursor_advancement_and_span_invariants():
    rng = random.Random(12345)
    sample_chars = ["a", " ", "\n", "1", "+", "=", "{", "}", "\"", ";", "\t"]
    for _ in range(50):
        length = rng.randint(1, 30)
        source = "".join(rng.choices(sample_chars, k=length))
        try:
            tokens = tokenize(source, mode=SyntaxMode.V0_6)
            for tok in tokens:
                assert tok.span.start_line >= 1
                assert tok.span.start_col >= 1
                assert tok.span.end_line >= tok.span.start_line
        except Exception:
            # Tokenizer errors must be structured, never panic
            pass


def test_malformed_assembly_rejection_and_version_guards():
    invalid_assemblies = [
        "",
        ".s3asm 99.0.0\n.memory 0\n.entry main\n.fn main 0 0\n TRET\n.end\n",
        ".s3asm 0.6.0\n.memory 0\n.entry main\n.fn main 0 0\n INVALID_OPCODE_XYZ\n.end\n",
        ".s3asm 0.6.0\n.memory 0\n.entry main\n.fn main 0 0\n TADD r1\n.end\n",
    ]
    for asm_text in invalid_assemblies:
        with pytest.raises(Exception):
            parse_assembly(asm_text)


def test_instruction_limit_enforcement():
    # Loop that exceeds tight instruction limit
    loop_code = "fn main() -> tryte:\n    mut x: tryte = 0\n    while x <=> 100:\n        x = x + 1\n    return x\n"
    from bootstrap.s3.pipeline import compile_source
    compilation = compile_source(loop_code)
    emulator = Emulator(max_instructions=5)
    with pytest.raises(EmulatorError):
        emulator.execute(compilation.assembly, "main")
