from __future__ import annotations

from bootstrap.s3.assembly import (
    AssemblyOpcode,
    AssemblyType,
    parse_assembly,
)
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import compile_source


def test_codegen_emits_data_section_and_tconst_str() -> None:
    assembly = compile_source(
        "fn main() -> tryte:\n"
        r'    first: string = "line\nnext"'
        "\n"
        '    second: string = "olá"\n'
        "    return 0\n",
        mode=SyntaxMode.V0_6,
    ).assembly
    rendered = assembly.render()

    assert '\n.data\ns0 "line\\nnext"\ns1 "olá"\n\n.function main -> tryte\n' in rendered
    assert "    .register r0, string\n" in rendered
    assert "    TCONST_STR r0, s0" in rendered
    assert "    TCONST_STR r2, s1" in rendered
    assert parse_assembly(rendered) == assembly
    assert parse_assembly(rendered).render() == rendered


def test_parse_assembly_accepts_static_string_data_and_string_types() -> None:
    program = parse_assembly(
        ".s3asm 0.5.0\n"
        "\n"
        ".data\n"
        r's0 "quote: \" slash: \\"'
        "\n"
        "\n"
        ".function main -> tryte\n"
        "    .register r0, string\n"
        "    .register r1, tryte\n"
        ".label entry\n"
        "    TCONST_STR r0, s0\n"
        "    TCONST r1, 0\n"
        "    TRET r1\n"
        ".end\n"
    )

    assert [(entry.id, entry.value) for entry in program.static_strings] == [
        ("s0", 'quote: " slash: \\'),
    ]
    function = program.functions[0]
    assert function.register_types[0] == (0, AssemblyType.STRING)
    assert function.instructions[0].opcode is AssemblyOpcode.TCONST_STR
    assert function.instructions[0].static_string == "s0"
    assert parse_assembly(program.render()) == program


def test_code_generated_string_function_signature_round_trips() -> None:
    assembly = compile_source(
        "fn identity(value: string) -> string:\n"
        "    return value\n"
        "fn main() -> tryte:\n"
        '    text: string = identity("x")\n'
        "    return 0\n",
        mode=SyntaxMode.V0_6,
    ).assembly

    identity = assembly.functions[0]
    assert identity.return_type is AssemblyType.STRING
    assert identity.parameters[0].type is AssemblyType.STRING
    assert parse_assembly(assembly.render()) == assembly
