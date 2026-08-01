from __future__ import annotations

import pytest

from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import compile_source


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Milestone 1.05 enum payloads require a public syntax and layout "
        "decision before implementation."
    ),
)
def test_enum_payload_result_flow_requires_architectural_decision() -> None:
    compile_source(
        "enum Result:\n"
        "    Ok(value: tryte)\n"
        "    Err(code: tryte)\n"
        "fn classify(value: tryte) -> Result:\n"
        "    match value <=> 0:\n"
        "        -1:\n"
        "            return Result.Err(code=-1)\n"
        "        0:\n"
        "            return Result.Ok(value=0)\n"
        "        1:\n"
        "            return Result.Ok(value=value)\n"
        "fn main() -> tryte:\n"
        "    result: Result = classify(2)\n"
        "    match result:\n"
        "        Result.Ok(value):\n"
        "            return value\n"
        "        Result.Err(code):\n"
        "            return code\n",
        mode=SyntaxMode.V0_6,
    )
