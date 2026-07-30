from __future__ import annotations

from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.metrics import measure_optimization
from bootstrap.s3.optimizer import OptimizationLevel, optimize_ir
from bootstrap.s3.pipeline import compile_source


def test_optimization_metrics_computation() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut a: tryte = 10\n"
        "    while 0:\n"
        "        a = a + 1\n"
        "    return a\n"
    )
    result_o0 = compile_source(source, optimization=OptimizationLevel.O0, mode=SyntaxMode.V0_6)
    result_o1 = compile_source(source, optimization=OptimizationLevel.O1, mode=SyntaxMode.V0_6)

    metrics = measure_optimization(result_o0.ir, result_o1.ir)
    assert metrics.before.block_count >= metrics.after.block_count
    assert metrics.before.instruction_count >= metrics.after.instruction_count
    assert metrics.blocks_removed >= 0
    assert metrics.instructions_removed >= 0
    assert "Blocks:" in metrics.summary()
