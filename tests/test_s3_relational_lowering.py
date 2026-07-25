from __future__ import annotations

from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.lowering import lower
from bootstrap.s3.parser import parse
from bootstrap.s3.semantic import analyze
from bootstrap.s3.verifier import verify_ir


def test_lower_relational_operators() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut a: tryte = 10\n"
        "    mut b: tryte = 20\n"
        "    mut r1: trit = a == b\n"
        "    mut r2: trit = a != b\n"
        "    mut r3: trit = a < b\n"
        "    mut r4: trit = a <= b\n"
        "    mut r5: trit = a > b\n"
        "    mut r6: trit = a >= b\n"
        "    return 0\n"
    )
    program = parse(source, mode=SyntaxMode.V0_6)
    model = analyze(program)
    ir_module = lower(program, model)
    verify_ir(ir_module)
