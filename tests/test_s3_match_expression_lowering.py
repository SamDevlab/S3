from __future__ import annotations

from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.lowering import lower
from bootstrap.s3.parser import parse
from bootstrap.s3.semantic import analyze
from bootstrap.s3.verifier import verify_ir


def test_lower_match_expression() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut sel: trit = -1\n"
        "    val: tryte = match sel:\n"
        "        -1: 10\n"
        "        0: 20\n"
        "        1: 30\n"
        "    return val\n"
    )
    program = parse(source, mode=SyntaxMode.V0_6)
    model = analyze(program)
    ir_module = lower(program, model)
    verify_ir(ir_module)
