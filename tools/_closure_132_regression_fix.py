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


# Preserve the established COMPARE-based lowering for trit/tryte/i64 relations.
# f64 alone uses RELATE because IEEE unordered (NaN) semantics cannot be encoded
# faithfully by the legacy three-way comparison result.
replace_once(
    "bootstrap/s3/lowering.py",
    '''        RELATIONAL_OPS = (\n            ast.BinaryOperator.EQUAL,\n            ast.BinaryOperator.NOT_EQUAL,\n            ast.BinaryOperator.LESS,\n            ast.BinaryOperator.LESS_EQUAL,\n            ast.BinaryOperator.GREATER,\n            ast.BinaryOperator.GREATER_EQUAL,\n        )\n        left = self._lower_expression(expression.left)\n''',
    '''        RELATIONAL_OPS = (\n            ast.BinaryOperator.EQUAL,\n            ast.BinaryOperator.NOT_EQUAL,\n            ast.BinaryOperator.LESS,\n            ast.BinaryOperator.LESS_EQUAL,\n            ast.BinaryOperator.GREATER,\n            ast.BinaryOperator.GREATER_EQUAL,\n        )\n        if expression.operator in RELATIONAL_OPS:\n            operand_type = self._storage_type(\n                self.semantic_model.declared_type_of(expression.left),\n                expression.left.location,\n            )\n            if operand_type is not ast.TypeName.F64:\n                return self._lower_relational_expression(expression)\n        left = self._lower_expression(expression.left)\n''',
)
replace_once(
    "bootstrap/s3/lowering.py",
    '''        if expression.operator in (\n            ast.BinaryOperator.EQUAL,\n            ast.BinaryOperator.NOT_EQUAL,\n            ast.BinaryOperator.LESS,\n            ast.BinaryOperator.LESS_EQUAL,\n            ast.BinaryOperator.GREATER,\n            ast.BinaryOperator.GREATER_EQUAL,\n        ):\n''',
    '''        if expression.operator in RELATIONAL_OPS:\n''',
)

# New assembly operations participate in the same closed liveness contract.
replace_once(
    "bootstrap/s3/backends/x86_64/liveness.py",
    '''    elif opcode is AssemblyOpcode.TINV:\n        return frozenset({regs[1]}), frozenset({regs[0]})\n    elif opcode in (AssemblyOpcode.TADD, AssemblyOpcode.TMIN, AssemblyOpcode.TMAX, AssemblyOpcode.TCMP):\n        return frozenset({regs[1], regs[2]}), frozenset({regs[0]})\n''',
    '''    elif opcode in (AssemblyOpcode.TINV, AssemblyOpcode.TCVT):\n        return frozenset({regs[1]}), frozenset({regs[0]})\n    elif opcode in (\n        AssemblyOpcode.TADD,\n        AssemblyOpcode.TMUL,\n        AssemblyOpcode.TDIV,\n        AssemblyOpcode.TREL,\n        AssemblyOpcode.TMIN,\n        AssemblyOpcode.TMAX,\n        AssemblyOpcode.TCMP,\n    ):\n        return frozenset({regs[1], regs[2]}), frozenset({regs[0]})\n''',
)

# Exhaustive IR-enum tests are intentionally exhaustive; extend their expected
# closed set rather than weakening/removing the assertions.
for path in ("tests/test_compiler.py", "tests/test_s3_static_text_concatenation_ir.py"):
    replace_once(
        path,
        '''        IROpcode.INVERT,\n        IROpcode.ADD,\n        IROpcode.MINIMUM,\n''',
        '''        IROpcode.INVERT,\n        IROpcode.ADD,\n        IROpcode.MULTIPLY,\n        IROpcode.DIVIDE,\n        IROpcode.RELATE,\n        IROpcode.CONVERT,\n        IROpcode.MINIMUM,\n''',
    )

# V0.5 keeps // comments. In V0.6 '/' is now a real division token, therefore
# two slashes are two operators rather than an invalid character/comment.
replace_once(
    "tests/test_lexer_indentation.py",
    '''    # // does NOT work in 0.6\n    # in 0.6, / is not a valid token in the operator set currently except if we add it. \n    # Actually our lexer throws LexError for / if it's not a valid single token and not skipped.\n    with pytest.raises(Exception) as excinfo:\n        tokenize("x = 1 // comment\\n", mode=SyntaxMode.V0_6)\n    assert "invalid character" in str(excinfo.value)\n''',
    '''    # V0.6 does not treat // as a comment; slash is the numeric division token.\n    assert [t.kind for t in tokenize("x = 1 // comment\\n", mode=SyntaxMode.V0_6)] == [\n        TokenKind.IDENTIFIER,\n        TokenKind.EQUAL,\n        TokenKind.INTEGER,\n        TokenKind.SLASH,\n        TokenKind.SLASH,\n        TokenKind.IDENTIFIER,\n        TokenKind.NEWLINE,\n        TokenKind.EOF,\n    ]\n''',
)

# The native opcode-coverage corpus must actually exercise every newly supported
# operation, rather than suppressing the exhaustive assertion.
replace_once(
    "tests/test_native_x86_64.py",
    '''    seen = {\n        instruction.opcode\n''',
    '''    programs.append(\n        compile_source(\n            "fn numeric(x: tryte, y: f64) -> trit:\\n"\n            "    widened: i64 = to_i64(x)\\n"\n            "    value: f64 = to_f64(widened)\\n"\n            "    return (value * y / y) != 0.0\\n"\n            "fn main() -> trit:\\n"\n            "    return numeric(2, 2.0)\\n",\n            mode=SyntaxMode.V0_6,\n        ).assembly\n    )\n    seen = {\n        instruction.opcode\n''',
)

# i64 relations intentionally keep the established COMPARE path. RELATE remains
# directly proven by the f64/NaN cases where it is semantically required.
replace_once(
    "tests/test_numeric_capability_e2e.py",
    '''        assert IROpcode.MULTIPLY in opcodes\n        assert IROpcode.DIVIDE in opcodes\n        assert IROpcode.RELATE in opcodes\n''',
    '''        assert IROpcode.MULTIPLY in opcodes\n        assert IROpcode.DIVIDE in opcodes\n        assert IROpcode.COMPARE in opcodes\n''',
)
replace_once(
    "tests/test_numeric_capability_e2e.py",
    '''    compilation = compile_program(source)\n    assert execute_ir(compilation.ir) == -1\n    assert Emulator().execute(compilation.assembly) == -1\n\n    false_relation = compile_program(\n''',
    '''    compilation = compile_program(source)\n    assert execute_ir(compilation.ir) == -1\n    assert Emulator().execute(compilation.assembly) == -1\n    assert any(\n        instruction.opcode is IROpcode.RELATE\n        for function in compilation.ir.functions\n        for instruction in function.instructions\n    )\n\n    false_relation = compile_program(\n''',
)

print("M1.32 regression closure fixes applied")
