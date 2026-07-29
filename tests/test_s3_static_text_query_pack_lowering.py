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


def _const_immediates(source: str) -> list[int]:
    function = _lower(source).functions[0]
    return [
        instruction.immediate
        for instruction in function.instructions
        if instruction.opcode is IROpcode.CONST
        and instruction.immediate is not None
    ]


def test_lowering_materialized_slice_uses_only_final_static_string() -> None:
    module = _lower(
        "fn main() -> tryte:\n"
        '    part: string = "hello"[1:4]\n'
        "    return len(part)\n"
    )

    assert [(entry.id, entry.value) for entry in module.static_strings] == [
        ("s0", "ell"),
    ]
    opcodes = _opcodes(module)
    assert opcodes.count(IROpcode.CONST_STR) == 1
    assert IROpcode.LOAD not in opcodes
    const_str = next(
        instruction
        for instruction in module.functions[0].instructions
        if instruction.opcode is IROpcode.CONST_STR
    )
    assert const_str.static_string == "s0"
    assert const_str.result is not None
    assert module.functions[0].registers[const_str.result].type is IRType.STRING


def test_lowering_slice_in_len_and_equality_does_not_intern_strings() -> None:
    len_module = _lower(
        "fn main() -> tryte:\n"
        '    return len("hello"[1:4])\n'
    )
    assert len_module.static_strings == ()
    assert IROpcode.CONST_STR not in _opcodes(len_module)
    assert _const_immediates(
        "fn main() -> tryte:\n"
        '    return len("hello"[1:4])\n'
    ) == [3]

    equality_module = _lower(
        "fn main() -> trit:\n"
        '    return "hello"[1:4] == "ell"\n'
    )
    assert equality_module.static_strings == ()
    assert IROpcode.CONST_STR not in _opcodes(equality_module)
    assert IROpcode.COMPARE not in _opcodes(equality_module)
    assert [
        instruction.immediate
        for instruction in equality_module.functions[0].instructions
        if instruction.opcode is IROpcode.CONST
    ] == [-1]


def test_lowering_query_builtins_emit_only_scalar_consts() -> None:
    cases = [
        ('contains("hello", "ell")', -1),
        ('contains("hello", "xyz")', 0),
        ('starts_with("hello", "he")', -1),
        ('ends_with("hello", "lo")', -1),
        ('find("hello", "ll")', 2),
        ('find("hello", "xyz")', -1),
    ]
    for expression, expected in cases:
        result_type = "tryte" if expression.startswith("find") else "trit"
        module = _lower(
            f"fn main() -> {result_type}:\n"
            f"    return {expression}\n"
        )
        opcodes = _opcodes(module)
        assert module.static_strings == ()
        assert IROpcode.CALL not in opcodes
        assert IROpcode.CONST_STR not in opcodes
        assert IROpcode.LOAD not in opcodes
        assert IROpcode.BRANCH3 not in opcodes
        assert [
            instruction.immediate
            for instruction in module.functions[0].instructions
            if instruction.opcode is IROpcode.CONST
        ] == [expected]


def test_lowering_queries_accept_slices_without_intermediate_strings() -> None:
    module = _lower(
        "fn main() -> trit:\n"
        '    return contains("hello"[1:4], "ll")\n'
    )

    assert module.static_strings == ()
    assert IROpcode.CALL not in _opcodes(module)
    assert IROpcode.CONST_STR not in _opcodes(module)
    assert [
        instruction.immediate
        for instruction in module.functions[0].instructions
        if instruction.opcode is IROpcode.CONST
    ] == [-1]


def test_lowering_array_indexing_still_uses_load_and_store() -> None:
    module = _lower(
        "fn main() -> tryte:\n"
        "    mut values: tryte[3] = [1, 2, 3]\n"
        "    index: tryte = 1\n"
        "    values[index] = 5\n"
        "    return values[index]\n"
    )

    opcodes = _opcodes(module)
    assert IROpcode.LOAD in opcodes
    assert IROpcode.STORE in opcodes
