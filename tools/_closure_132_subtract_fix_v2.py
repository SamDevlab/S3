from __future__ import annotations

from pathlib import Path

script = Path(__file__).with_name("_closure_132_subtract_fix.py")
code = script.read_text(encoding="utf-8")

old = '''# Runtime helper contract is independently pinned at the boundary values.\nreplace_once(\n    "tests/test_numeric_closure.py",\n    \'\'\'def test_i64_subtraction_and_multiplication_are_checked() -> None:\\n\'\'\',\n    \'\'\'def test_i64_subtraction_preserves_valid_int64_min_cases() -> None:\\n    assert checked_i64_sub(I64_MIN, I64_MIN) == 0\\n    assert checked_i64_sub(-1, I64_MIN) == I64_MAX\\n\\n\\ndef test_i64_subtraction_and_multiplication_are_checked() -> None:\\n\'\'\',\n)'''
new = '''# Runtime helper contract is independently pinned at the boundary values.\nreplace_once(\n    "tests/test_numeric_closure.py",\n    \'\'\'    assert checked_i64_neg(7) == -7\\n\'\'\',\n    \'\'\'    assert checked_i64_neg(7) == -7\\n    assert checked_i64_sub(I64_MIN, I64_MIN) == 0\\n    assert checked_i64_sub(-1, I64_MIN) == I64_MAX\\n\'\'\',\n)'''

count = code.count(old)
if count != 1:
    raise RuntimeError(f"expected one stale test-anchor block, found {count}")
code = code.replace(old, new, 1)
exec(compile(code, str(script), "exec"), {"__name__": "__main__", "__file__": str(script)})
