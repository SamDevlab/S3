from __future__ import annotations

from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parents[1]
runpy.run_path(str(Path(__file__).with_name("_closure_132_subtract_fix_v2.py")), run_name="__main__")


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly one anchor, got {count}: {old[:120]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


# Build INT64_MIN through an i64-typed parameter so the test exercises the
# subtraction boundary instead of depending on contextual typing of a negated
# huge literal inside multiplication. The same probe must also execute natively.
replace_once(
    "tests/test_numeric_capability_e2e.py",
    '''def test_i64_subtraction_handles_int64_min_without_false_intermediate_overflow() -> None:
    source = (
        "fn minimum() -> i64:\n"
        "    return -4611686018427387904 * 2\n"
        "fn subtract(a: i64, b: i64) -> i64:\n"
        "    return a - b\n"
        "fn main() -> trit:\n"
        "    return (subtract(minimum(), minimum()) == 0) & (subtract(-1, minimum()) == 9223372036854775807)\n"
    )
    for optimization in ("O0", "O1"):
        compilation = compile_program(source, optimization)
        assert execute_ir(compilation.ir) == -1
        assert Emulator().execute(compilation.assembly) == -1
        assert any(
            instruction.opcode is IROpcode.NUMERIC_SUBTRACT
            for function in compilation.ir.functions
            for instruction in function.instructions
        )
''',
    '''@pytest.mark.s3_native
def test_i64_subtraction_handles_int64_min_without_false_intermediate_overflow(tmp_path: Path) -> None:
    source = (
        "fn minimum(seed: i64) -> i64:\n"
        "    return seed * 2\n"
        "fn subtract(a: i64, b: i64) -> i64:\n"
        "    return a - b\n"
        "fn main() -> trit:\n"
        "    return (subtract(minimum(-4611686018427387904), minimum(-4611686018427387904)) == 0) & (subtract(-1, minimum(-4611686018427387904)) == 9223372036854775807)\n"
    )
    toolchain = NativeToolchain.detect()
    for optimization in ("O0", "O1"):
        compilation = compile_program(source, optimization)
        assert execute_ir(compilation.ir) == -1
        assert Emulator().execute(compilation.assembly) == -1
        assert any(
            instruction.opcode is IROpcode.NUMERIC_SUBTRACT
            for function in compilation.ir.functions
            for instruction in function.instructions
        )
        native_source = generate_native_assembly(compilation.assembly)
        assert "sub rax, r10" in native_source
        executable = toolchain.build(native_source, tmp_path / f"subtract-{optimization.lower()}")
        completed = toolchain.run(executable)
        assert completed.returncode == 0
        assert completed.stderr == ""
        assert completed.stdout.strip() == "program returned: -1"
''',
)

print("M1.32 subtraction boundary proof refined")
