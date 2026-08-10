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

exec(compile(code, str(script), "exec"), {"__name__": "__main__", "__file__": str(script)})
