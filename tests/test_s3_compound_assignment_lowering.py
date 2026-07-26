from __future__ import annotations

from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.lowering import lower
from bootstrap.s3.parser import parse
from bootstrap.s3.semantic import analyze
from bootstrap.s3.verifier import verify_ir


def test_lower_compound_assignment() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut x: tryte = 10\n"
        "    x += 5\n"
        "    mut arr: tryte[3] = [1, 2, 3]\n"
        "    arr[1] += 20\n"
        "    return x + arr[1]\n"
    )
    program = parse(source, mode=SyntaxMode.V0_6)
    model = analyze(program)
    ir_module = lower(program, model)
    verify_ir(ir_module)
