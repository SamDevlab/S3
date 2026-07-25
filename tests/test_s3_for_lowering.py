from __future__ import annotations

from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.lowering import lower
from bootstrap.s3.parser import parse
from bootstrap.s3.semantic import analyze
from bootstrap.s3.verifier import verify_ir


def test_lower_for_statement() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut sum: tryte = 0\n"
        "    for i: tryte in range(0, 5):\n"
        "        sum = sum + i\n"
        "    return sum\n"
    )
    program = parse(source, mode=SyntaxMode.V0_6)
    model = analyze(program)
    ir_module = lower(program, model)
    verify_ir(ir_module)
