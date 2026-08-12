from bootstrap.s3.backends.x86_64.backend import generate_native_assembly
from bootstrap.s3.pipeline import compile_source


def test_scalar_move_stays_in_assembly_but_is_not_frame_materialized_natively() -> None:
    compilation = compile_source(
        "fn main() -> tryte:\n"
        "    a: tryte = 10\n"
        "    return a\n",
        "O0",
    )

    instructions = compilation.assembly.functions[0].instructions
    assert sum(item.opcode.value == "TMOV" for item in instructions) == 1

    native = generate_native_assembly(compilation.assembly)
    assert "mov qword ptr [rbp" not in native


def test_reference_move_retains_native_storage_materialization() -> None:
    compilation = compile_source(
        "fn main() -> tryte:\n"
        "    mut value: tryte = 1\n"
        "    r: &mut tryte = &mut value\n"
        "    s: &mut tryte = &mut *r\n"
        "    *s = 7\n"
        "    return *r\n",
        "O0",
    )

    instructions = compilation.assembly.functions[0].instructions
    assert any(item.opcode.value == "TMOV" for item in instructions)
    native = generate_native_assembly(compilation.assembly)
    assert "mov word ptr [rbp" in native
