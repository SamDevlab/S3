from __future__ import annotations

from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import run_source


def test_pipeline_stability_with_loops_and_branches() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut total: tryte = 0\n"
        "    mut i: tryte = 0\n"
        "    while i < 3:\n"
        "        match i <=> 1:\n"
        "            -1:\n"
        "                total = total + 10\n"
        "            0:\n"
        "                total = total + 20\n"
        "            else:\n"
        "                total = total + 30\n"
        "        i = i + 1\n"
        "    return total\n"
    )
    res_o0 = run_source(source, optimization="O0", mode=SyntaxMode.V0_6)
    res_o1 = run_source(source, optimization="O1", mode=SyntaxMode.V0_6)
    assert res_o0 == 60
    assert res_o1 == 60
