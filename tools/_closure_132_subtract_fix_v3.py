from __future__ import annotations

from pathlib import Path
import re
import runpy

ROOT = Path(__file__).resolve().parents[1]
runpy.run_path(str(Path(__file__).with_name("_closure_132_subtract_fix_v2.py")), run_name="__main__")

path = ROOT / "tests/test_numeric_capability_e2e.py"
text = path.read_text(encoding="utf-8")
pattern = re.compile(
    r"def test_i64_subtraction_handles_int64_min_without_false_intermediate_overflow\(\) -> None:\n"
    r".*?"
    r"(?=\ndef test_f64_arithmetic_and_ieee_special_values_are_preserved\(\) -> None:)",
    re.DOTALL,
)
replacement = '''@pytest.mark.s3_native
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
'''
text, count = pattern.subn(replacement, text, count=1)
if count != 1:
    raise RuntimeError(f"expected one generated subtraction-boundary test, got {count}")
path.write_text(text, encoding="utf-8")

print("M1.32 subtraction boundary proof refined")
