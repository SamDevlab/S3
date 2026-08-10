from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly one anchor, got {count}: {old[:100]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


# Machine-numeric subtraction cannot be represented as negate+add for all i64
# values: -INT64_MIN is not representable although INT64_MIN-INT64_MIN == 0 is.
# Keep balanced ternary subtraction on the established INVERT+ADD path and give
# i64/f64 a dedicated typed opcode.
replace_once(
    "bootstrap/s3/ir.py",
    '''    INVERT = "invert"\n    ADD = "add"\n    MULTIPLY = "multiply"\n''',
    '''    INVERT = "invert"\n    ADD = "add"\n    NUMERIC_SUBTRACT = "numeric_subtract"\n    MULTIPLY = "multiply"\n''',
)

replace_once(
    "bootstrap/s3/lowering.py",
    '''        if expression.operator is ast.BinaryOperator.SUBTRACT:\n            inverted = self._allocate(\n                self._storage_type(\n                    self.semantic_model.declared_type_of(expression.right),\n                    expression.right.location,\n                ),\n                expression.right.location,\n            )\n            self._emit(\n                IRInstruction(\n                    IROpcode.INVERT,\n                    result=inverted,\n                    operands=(right,),\n                    location=expression.location,\n                )\n            )\n            result = self._allocate(result_type, expression.location)\n            self._emit(\n                IRInstruction(\n                    IROpcode.ADD,\n                    result=result,\n                    operands=(left, inverted),\n                    location=expression.location,\n                )\n            )\n            return result\n''',
    '''        if expression.operator is ast.BinaryOperator.SUBTRACT:\n            if result_type in (ast.TypeName.I64, ast.TypeName.F64):\n                result = self._allocate(result_type, expression.location)\n                self._emit(\n                    IRInstruction(\n                        IROpcode.NUMERIC_SUBTRACT,\n                        result=result,\n                        operands=(left, right),\n                        location=expression.location,\n                    )\n                )\n                return result\n            inverted = self._allocate(\n                self._storage_type(\n                    self.semantic_model.declared_type_of(expression.right),\n                    expression.right.location,\n                ),\n                expression.right.location,\n            )\n            self._emit(\n                IRInstruction(\n                    IROpcode.INVERT,\n                    result=inverted,\n                    operands=(right,),\n                    location=expression.location,\n                )\n            )\n            result = self._allocate(result_type, expression.location)\n            self._emit(\n                IRInstruction(\n                    IROpcode.ADD,\n                    result=result,\n                    operands=(left, inverted),\n                    location=expression.location,\n                )\n            )\n            return result\n''',
)

replace_once(
    "bootstrap/s3/verifier.py",
    '''            IROpcode.ADD,\n            IROpcode.MULTIPLY,\n            IROpcode.DIVIDE,\n''',
    '''            IROpcode.ADD,\n            IROpcode.NUMERIC_SUBTRACT,\n            IROpcode.MULTIPLY,\n            IROpcode.DIVIDE,\n''',
)
replace_once(
    "bootstrap/s3/verifier.py",
    '''                opcode in {IROpcode.MULTIPLY, IROpcode.DIVIDE}\n                and result_type not in {IRType.I64, IRType.F64}\n''',
    '''                opcode in {IROpcode.NUMERIC_SUBTRACT, IROpcode.MULTIPLY, IROpcode.DIVIDE}\n                and result_type not in {IRType.I64, IRType.F64}\n''',
)

replace_once(
    "bootstrap/s3/ir_emulator.py",
    '''    NumericError, NumericValue, checked_i64_add, checked_i64_mul,\n    checked_i64_div, checked_i64_neg, checked_i64_to_tryte,\n''',
    '''    NumericError, NumericValue, checked_i64_add, checked_i64_sub, checked_i64_mul,\n    checked_i64_div, checked_i64_neg, checked_i64_to_tryte,\n''',
)
replace_once(
    "bootstrap/s3/ir_emulator.py",
    '''        elif op in {IROpcode.ADD, IROpcode.MULTIPLY, IROpcode.DIVIDE}:\n''',
    '''        elif op in {IROpcode.ADD, IROpcode.NUMERIC_SUBTRACT, IROpcode.MULTIPLY, IROpcode.DIVIDE}:\n''',
)
replace_once(
    "bootstrap/s3/ir_emulator.py",
    '''                if op is IROpcode.ADD:\n                    result = checked_i64_add(left, right)\n                elif op is IROpcode.MULTIPLY:\n''',
    '''                if op is IROpcode.ADD:\n                    result = checked_i64_add(left, right)\n                elif op is IROpcode.NUMERIC_SUBTRACT:\n                    result = checked_i64_sub(left, right)\n                elif op is IROpcode.MULTIPLY:\n''',
)
replace_once(
    "bootstrap/s3/ir_emulator.py",
    '''                if op is IROpcode.ADD:\n                    result = validate_f64(float(left) + float(right))\n                elif op is IROpcode.MULTIPLY:\n''',
    '''                if op is IROpcode.ADD:\n                    result = validate_f64(float(left) + float(right))\n                elif op is IROpcode.NUMERIC_SUBTRACT:\n                    result = validate_f64(float(left) - float(right))\n                elif op is IROpcode.MULTIPLY:\n''',
)

# Assembly name is deliberately TNSUB, not TSUB. TSUB remains absent so the
# longstanding balanced-ternary subtraction invariant remains true.
replace_once(
    "bootstrap/s3/assembly.py",
    '''    TINV = "TINV"\n    TADD = "TADD"\n    TMUL = "TMUL"\n''',
    '''    TINV = "TINV"\n    TADD = "TADD"\n    TNSUB = "TNSUB"\n    TMUL = "TMUL"\n''',
)
replace_once(
    "bootstrap/s3/assembly.py",
    '''        AssemblyOpcode.TADD: 3,\n        AssemblyOpcode.TMUL: 3,\n''',
    '''        AssemblyOpcode.TADD: 3,\n        AssemblyOpcode.TNSUB: 3,\n        AssemblyOpcode.TMUL: 3,\n''',
)

replace_once(
    "bootstrap/s3/codegen.py",
    '''    IROpcode.ADD: AssemblyOpcode.TADD,\n    IROpcode.MULTIPLY: AssemblyOpcode.TMUL,\n''',
    '''    IROpcode.ADD: AssemblyOpcode.TADD,\n    IROpcode.NUMERIC_SUBTRACT: AssemblyOpcode.TNSUB,\n    IROpcode.MULTIPLY: AssemblyOpcode.TMUL,\n''',
)

replace_once(
    "bootstrap/s3/assembly_verifier.py",
    '''            AssemblyOpcode.TADD,\n            AssemblyOpcode.TMUL,\n            AssemblyOpcode.TDIV,\n''',
    '''            AssemblyOpcode.TADD,\n            AssemblyOpcode.TNSUB,\n            AssemblyOpcode.TMUL,\n            AssemblyOpcode.TDIV,\n''',
)
replace_once(
    "bootstrap/s3/assembly_verifier.py",
    '''                opcode in {AssemblyOpcode.TMUL, AssemblyOpcode.TDIV}\n                and type_name not in {AssemblyType.I64, AssemblyType.F64}\n''',
    '''                opcode in {AssemblyOpcode.TNSUB, AssemblyOpcode.TMUL, AssemblyOpcode.TDIV}\n                and type_name not in {AssemblyType.I64, AssemblyType.F64}\n''',
)

replace_once(
    "bootstrap/s3/emulator.py",
    '''    NumericError, NumericValue, checked_i64_add, checked_i64_mul,\n    checked_i64_div, checked_i64_neg, checked_i64_to_tryte,\n''',
    '''    NumericError, NumericValue, checked_i64_add, checked_i64_sub, checked_i64_mul,\n    checked_i64_div, checked_i64_neg, checked_i64_to_tryte,\n''',
)
replace_once(
    "bootstrap/s3/emulator.py",
    '''                    AssemblyOpcode.TADD,\n                    AssemblyOpcode.TMUL,\n                    AssemblyOpcode.TDIV,\n''',
    '''                    AssemblyOpcode.TADD,\n                    AssemblyOpcode.TNSUB,\n                    AssemblyOpcode.TMUL,\n                    AssemblyOpcode.TDIV,\n''',
)
replace_once(
    "bootstrap/s3/emulator.py",
    '''                        if opcode is AssemblyOpcode.TADD:\n                            result = checked_i64_add(left, right)\n                        elif opcode is AssemblyOpcode.TMUL:\n''',
    '''                        if opcode is AssemblyOpcode.TADD:\n                            result = checked_i64_add(left, right)\n                        elif opcode is AssemblyOpcode.TNSUB:\n                            result = checked_i64_sub(left, right)\n                        elif opcode is AssemblyOpcode.TMUL:\n''',
)
replace_once(
    "bootstrap/s3/emulator.py",
    '''                        if opcode is AssemblyOpcode.TADD:\n                            result = validate_f64(float(left) + float(right))\n                        elif opcode is AssemblyOpcode.TMUL:\n''',
    '''                        if opcode is AssemblyOpcode.TADD:\n                            result = validate_f64(float(left) + float(right))\n                        elif opcode is AssemblyOpcode.TNSUB:\n                            result = validate_f64(float(left) - float(right))\n                        elif opcode is AssemblyOpcode.TMUL:\n''',
)

replace_once(
    "bootstrap/s3/backends/x86_64/liveness.py",
    '''        AssemblyOpcode.TADD,\n        AssemblyOpcode.TMUL,\n''',
    '''        AssemblyOpcode.TADD,\n        AssemblyOpcode.TNSUB,\n        AssemblyOpcode.TMUL,\n''',
)

replace_once(
    "bootstrap/s3/backends/x86_64/emitter.py",
    '''        if opcode in {AssemblyOpcode.TMUL, AssemblyOpcode.TDIV}:\n''',
    '''        if opcode is AssemblyOpcode.TNSUB:\n            type_name = function.type_of(registers[0])\n            assert type_name in {AssemblyType.I64, AssemblyType.F64}\n            if type_name is AssemblyType.F64:\n                return instrumentation + [\n                    *self._read_register(layout, registers[1], "rax"),\n                    *self._read_register(layout, registers[2], "r10"),\n                    "    movq xmm0, rax",\n                    "    movq xmm1, r10",\n                    "    subsd xmm0, xmm1",\n                    "    movq rax, xmm0",\n                    *self._write_register(layout, registers[0], "rax"),\n                ]\n            overflow = self._instruction_failure(\n                "overflow",\n                detail="i64 subtraction overflow\\n",\n            )\n            return instrumentation + [\n                *self._read_register(layout, registers[1], "rax"),\n                *self._read_register(layout, registers[2], "r10"),\n                "    sub rax, r10",\n                f"    jo {overflow}",\n                *self._write_register(layout, registers[0], "rax"),\n            ]\n        if opcode in {AssemblyOpcode.TMUL, AssemblyOpcode.TDIV}:\n''',
)

# Keep exhaustive opcode-contract tests exhaustive.
for path in ("tests/test_compiler.py", "tests/test_s3_static_text_concatenation_ir.py"):
    replace_once(
        path,
        '''        IROpcode.ADD,\n        IROpcode.MULTIPLY,\n''',
        '''        IROpcode.ADD,\n        IROpcode.NUMERIC_SUBTRACT,\n        IROpcode.MULTIPLY,\n''',
    )

# Make the native exhaustive corpus emit TNSUB as well as the other numeric ops.
replace_once(
    "tests/test_native_x86_64.py",
    '''            "    return (value * y / y) != 0.0\\n"\n''',
    '''            "    return (value * y / y - 1.0) != 0.0\\n"\n''',
)

# Strengthen the public capability proof with the exact case negate+add gets wrong.
replace_once(
    "tests/test_numeric_capability_e2e.py",
    '''        assert IROpcode.MULTIPLY in opcodes\n        assert IROpcode.DIVIDE in opcodes\n        assert IROpcode.COMPARE in opcodes\n\n\ndef test_f64_arithmetic_and_ieee_special_values_are_preserved() -> None:\n''',
    '''        assert IROpcode.NUMERIC_SUBTRACT in opcodes\n        assert IROpcode.MULTIPLY in opcodes\n        assert IROpcode.DIVIDE in opcodes\n        assert IROpcode.COMPARE in opcodes\n\n\ndef test_i64_subtraction_handles_int64_min_without_false_intermediate_overflow() -> None:\n    source = (\n        "fn minimum() -> i64:\\n"\n        "    return -4611686018427387904 * 2\\n"\n        "fn subtract(a: i64, b: i64) -> i64:\\n"\n        "    return a - b\\n"\n        "fn main() -> trit:\\n"\n        "    return (subtract(minimum(), minimum()) == 0) & (subtract(-1, minimum()) == 9223372036854775807)\\n"\n    )\n    for optimization in ("O0", "O1"):\n        compilation = compile_program(source, optimization)\n        assert execute_ir(compilation.ir) == -1\n        assert Emulator().execute(compilation.assembly) == -1\n        assert any(\n            instruction.opcode is IROpcode.NUMERIC_SUBTRACT\n            for function in compilation.ir.functions\n            for instruction in function.instructions\n        )\n\n\ndef test_f64_arithmetic_and_ieee_special_values_are_preserved() -> None:\n''',
)

# Runtime helper contract is independently pinned at the boundary values.
replace_once(
    "tests/test_numeric_closure.py",
    '''def test_i64_subtraction_and_multiplication_are_checked() -> None:\n''',
    '''def test_i64_subtraction_preserves_valid_int64_min_cases() -> None:\n    assert checked_i64_sub(I64_MIN, I64_MIN) == 0\n    assert checked_i64_sub(-1, I64_MIN) == I64_MAX\n\n\ndef test_i64_subtraction_and_multiplication_are_checked() -> None:\n''',
)

# Document why machine subtraction has its own typed operation while balanced
# ternary subtraction retains the historical lowering.
replace_once(
    "docs/milestone-1.32.md",
    '''Integer and balanced-ternary relational operators preserve the established\n`COMPARE` lowering path. `f64` relations use the typed `RELATE` path so IEEE-754\nunordered comparisons involving NaN can be represented without collapsing them\ninto an artificial three-way ordering.\n''',
    '''Machine-numeric subtraction uses its own checked typed operation rather than\nnegate-then-add. This is required for valid expressions such as\n`INT64_MIN - INT64_MIN`, where negating the right operand would create a false\nintermediate overflow. Balanced `trit`/`tryte` subtraction retains the historic\n`INVERT` + `ADD` lowering, and the legacy `TSUB` opcode remains absent.\n\nInteger and balanced-ternary relational operators preserve the established\n`COMPARE` lowering path. `f64` relations use the typed `RELATE` path so IEEE-754\nunordered comparisons involving NaN can be represented without collapsing them\ninto an artificial three-way ordering.\n''',
)

print("M1.32 exact checked subtraction fix applied")
