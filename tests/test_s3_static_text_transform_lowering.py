from __future__ import annotations

from bootstrap.s3.ir import IROpcode, IRType
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.lowering import lower
from bootstrap.s3.parser import parse
from bootstrap.s3.semantic import analyze
from bootstrap.s3.verifier import verify_ir


def _lower(source: str):
    program = parse(source, mode=SyntaxMode.V0_6)
    model = analyze(program)
    module = lower(program, model)
    verify_ir(module)
    return module


def _opcodes(module) -> list[IROpcode]:
    return [
        instruction.opcode
        for function in module.functions
        for block in function.blocks
        for instruction in block.instructions
    ]


def test_lowering_static_text_transforms_emit_const_str_no_call() -> None:
    module = _lower(
        "fn main() -> tryte:\n"
        '    s1: string = upper("hello")\n'
        '    s2: string = lower("WORLD")\n'
        '    s3: string = trim("  test  ")\n'
        '    s4: string = repeat("a", 3)\n'
        '    s5: string = replace("foo", "o", "x")\n'
        "    return len(s1) + len(s2) + len(s3) + len(s4) + len(s5)\n"
    )

    opcodes = _opcodes(module)
    assert IROpcode.CALL not in opcodes
    assert opcodes.count(IROpcode.CONST_STR) == 5
    assert [(entry.id, entry.value) for entry in module.static_strings] == [
        ("s0", "HELLO"),
        ("s1", "world"),
        ("s2", "test"),
        ("s3", "aaa"),
        ("s4", "fxx"),
    ]


def test_lowering_upper_abc_emits_const_str_and_no_call() -> None:
    module = _lower(
        "fn main() -> tryte:\n"
        '    s: string = upper("abc")\n'
        "    return len(s)\n"
    )
    opcodes = _opcodes(module)
    assert IROpcode.CONST_STR in opcodes
    assert IROpcode.CALL not in opcodes
    assert module.static_strings[0].value == "ABC"


def test_lowering_static_text_transform_inside_len_does_not_intern_string() -> None:
    module = _lower(
        "fn main() -> tryte:\n"
        '    return len(upper("hello"))\n'
    )
    assert module.static_strings == ()
    assert IROpcode.CONST_STR not in _opcodes(module)
    assert IROpcode.CALL not in _opcodes(module)


def test_lowering_user_function_call_when_not_constant_emits_call_opcode() -> None:
    module = _lower(
        "fn custom_upper(s: string) -> string:\n"
        "    return s\n"
        "fn test_fn(p: string) -> string:\n"
        "    msg: string = custom_upper(p)\n"
        "    return msg\n"
        "fn main() -> tryte:\n"
        "    return 0\n"
    )
    opcodes = _opcodes(module)
    assert IROpcode.CALL in opcodes
