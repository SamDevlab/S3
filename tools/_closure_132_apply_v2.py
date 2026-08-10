from __future__ import annotations

from pathlib import Path

script = Path(__file__).with_name("_closure_132_apply.py")
code = script.read_text(encoding="utf-8")

old = '''replace_once(\n    "bootstrap/s3/semantic.py",\n    \'\'\'                ast.BinaryOperator.ADD,\\n                ast.BinaryOperator.SUBTRACT,\\n                ast.BinaryOperator.MINIMUM,\\n\'\'\',\n    \'\'\'                ast.BinaryOperator.ADD,\\n                ast.BinaryOperator.SUBTRACT,\\n                ast.BinaryOperator.MULTIPLY,\\n                ast.BinaryOperator.DIVIDE,\\n                ast.BinaryOperator.MINIMUM,\\n\'\'\',\n)'''

new = '''replace_once(\n    "bootstrap/s3/semantic.py",\n    \'\'\'        if (\\n            isinstance(expression, ast.BinaryExpression)\\n            and expression.operator\\n            in (\\n                ast.BinaryOperator.ADD,\\n                ast.BinaryOperator.SUBTRACT,\\n                ast.BinaryOperator.MINIMUM,\\n                ast.BinaryOperator.MAXIMUM,\\n            )\\n        ):\\n            left = self._known_expression_type(expression.left)\\n            right = self._known_expression_type(expression.right)\\n\'\'\',\n    \'\'\'        if (\\n            isinstance(expression, ast.BinaryExpression)\\n            and expression.operator\\n            in (\\n                ast.BinaryOperator.ADD,\\n                ast.BinaryOperator.SUBTRACT,\\n                ast.BinaryOperator.MULTIPLY,\\n                ast.BinaryOperator.DIVIDE,\\n                ast.BinaryOperator.MINIMUM,\\n                ast.BinaryOperator.MAXIMUM,\\n            )\\n        ):\\n            left = self._known_expression_type(expression.left)\\n            right = self._known_expression_type(expression.right)\\n\'\'\',\n)'''

count = code.count(old)
if count != 1:
    raise RuntimeError(f"expected one ambiguous semantic codemod block, found {count}")
code = code.replace(old, new, 1)

# Append corrections discovered by the first executable closure proof.  These run
# after the main codemod has created the E2E test file and modified semantics.
code += r'''
replace_once(
    "bootstrap/s3/semantic.py",
    '''    def _binary_operand_type(self, expression: ast.BinaryExpression) -> ast.DeclaredType:\n        left = self._known_expression_type(expression.left)\n        right = self._known_expression_type(expression.right)\n        if left is ast.TypeName.STRING or right is ast.TypeName.STRING:\n            return ast.TypeName.STRING\n        if left is not None and right is not None:\n            self._require_type(left, right, expression.location, "binary operands")\n        return left or right or ast.TypeName.TRYTE\n''',
    '''    def _binary_operand_type(self, expression: ast.BinaryExpression) -> ast.DeclaredType:\n        left = self._known_expression_type(expression.left)\n        right = self._known_expression_type(expression.right)\n        if left is ast.TypeName.STRING or right is ast.TypeName.STRING:\n            return ast.TypeName.STRING\n        if left is not None and right is not None and left is not right:\n            # Integer literals begin life in the legacy tryte domain, but machine\n            # numeric expressions provide a stronger context.  This keeps\n            # `counter: i64; counter + 1` ergonomic without introducing implicit\n            # conversions between already-typed values.\n            if (\n                isinstance(expression.left, ast.IntegerLiteral)\n                and right in (ast.TypeName.I64, ast.TypeName.F64)\n            ):\n                return right\n            if (\n                isinstance(expression.right, ast.IntegerLiteral)\n                and left in (ast.TypeName.I64, ast.TypeName.F64)\n            ):\n                return left\n            self._require_type(left, right, expression.location, "binary operands")\n        return left or right or ast.TypeName.TRYTE\n''',
)
replace_once(
    "tests/test_numeric_capability_e2e.py",
    '        "    return score(2.0, 300.0, 2.0, 50.0) == -4.55\\n"\n',
    '        "    return (score(2.0, 300.0, 2.0, 50.0) > -4.551) & (score(2.0, 300.0, 2.0, 50.0) < -4.549)\\n"\n',
)
'''

exec(compile(code, str(script), "exec"), {"__name__": "__main__", "__file__": str(script)})
