from __future__ import annotations

from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.lowering import lower
from bootstrap.s3.parser import parse
from bootstrap.s3.semantic import analyze
from bootstrap.s3.verifier import verify_ir


def test_lower_len_expression() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    values: tryte[5] = [1, 2, 3, 4, 5]\n"
        "    size: tryte = len(values)\n"
        "    return size\n"
    )
    program = parse(source, mode=SyntaxMode.V0_6)
    model = analyze(program)
    ir_module = lower(program, model)
    verify_ir(ir_module)
