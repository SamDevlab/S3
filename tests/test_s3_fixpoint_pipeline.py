from __future__ import annotations

from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import compile_source, run_source
from bootstrap.s3.ssa import SSABuilder
from bootstrap.s3.ssa_opt import run_fixpoint_pipeline


def test_fixpoint_pipeline_convergence_and_telemetry() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut i: tryte = 0\n"
        "    mut sum: tryte = 0\n"
        "    a: tryte = 5\n"
        "    b: tryte = 10\n"
        "    while i < 3:\n"
        "        inv: tryte = a + b\n"
        "        sum = sum + inv\n"
        "        i = i + 1\n"
        "    return sum\n"
    )
    compilation = compile_source(source, mode=SyntaxMode.V0_6)
    fn = compilation.ir.functions[0]
    ssa_fn = SSABuilder.build_function(fn)
    opt_ssa, telemetry = run_fixpoint_pipeline(ssa_fn, max_iterations=10)

    assert telemetry.converged is True
    assert telemetry.iterations >= 1
    res = run_source(source, optimization="O1", mode=SyntaxMode.V0_6)
    assert res == 45


def test_fixpoint_pipeline_respects_max_iterations() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut a: tryte = 10\n"
        "    a = a + 1\n"
        "    return a\n"
    )
    compilation = compile_source(source, mode=SyntaxMode.V0_6)
    fn = compilation.ir.functions[0]
    ssa_fn = SSABuilder.build_function(fn)
    opt_ssa, telemetry = run_fixpoint_pipeline(ssa_fn, max_iterations=1)

    assert telemetry.iterations == 1
