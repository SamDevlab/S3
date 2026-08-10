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

env: dict[str, object] = {"__name__": "__main__", "__file__": str(script)}
exec(compile(code, str(script), "exec"), env)
replace_once = env["replace_once"]
assert callable(replace_once)

replace_once(
    "bootstrap/s3/semantic.py",
    '''    def _binary_operand_type(self, expression: ast.BinaryExpression) -> ast.DeclaredType:
        left = self._known_expression_type(expression.left)
        right = self._known_expression_type(expression.right)
        if left is ast.TypeName.STRING or right is ast.TypeName.STRING:
            return ast.TypeName.STRING
        if left is not None and right is not None:
            self._require_type(left, right, expression.location, "binary operands")
        return left or right or ast.TypeName.TRYTE
''',
    '''    def _binary_operand_type(self, expression: ast.BinaryExpression) -> ast.DeclaredType:
        left = self._known_expression_type(expression.left)
        right = self._known_expression_type(expression.right)
        if left is ast.TypeName.STRING or right is ast.TypeName.STRING:
            return ast.TypeName.STRING
        if left is not None and right is not None and left is not right:
            # Integer literals begin in the legacy tryte domain, but a typed
            # machine-numeric peer provides the contextual literal domain.
            if (
                isinstance(expression.left, ast.IntegerLiteral)
                and right in (ast.TypeName.I64, ast.TypeName.F64)
            ):
                return right
            if (
                isinstance(expression.right, ast.IntegerLiteral)
                and left in (ast.TypeName.I64, ast.TypeName.F64)
            ):
                return left
            self._require_type(left, right, expression.location, "binary operands")
        return left or right or ast.TypeName.TRYTE
''',
)

replace_once(
    "tests/test_numeric_capability_e2e.py",
    '        "    return score(2.0, 300.0, 2.0, 50.0) == -4.55\\n"\n',
    '        "    return (score(2.0, 300.0, 2.0, 50.0) > -4.551) & (score(2.0, 300.0, 2.0, 50.0) < -4.549)\\n"\n',
)
