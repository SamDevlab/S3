from __future__ import annotations

from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import compile_source, run_source
from bootstrap.s3.ssa import SSABuilder
from bootstrap.s3.ssa_opt import run_fixpoint_pipeline


def _ssa_function(source: str, function_name: str = "main"):
    compilation = compile_source(source, mode=SyntaxMode.V0_6)
    fn = next(
        function
        for function in compilation.ir.functions
        if function.name == function_name
    )
    return SSABuilder.build_function(fn)


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
        "fn combine(a: tryte, b: tryte) -> tryte:\n"
        "    x: tryte = a + b\n"
        "    y: tryte = a + b\n"
        "    return x + y\n"
        "fn main() -> tryte:\n"
        "    return combine(2, 3)\n"
    )
    compilation = compile_source(source, mode=SyntaxMode.V0_6)
    fn = next(function for function in compilation.ir.functions if function.name == "combine")
    ssa_fn = SSABuilder.build_function(fn)
    opt_ssa, telemetry = run_fixpoint_pipeline(ssa_fn, max_iterations=1)

    assert telemetry.iterations == 1
    assert telemetry.converged is False
    assert telemetry.max_iterations_reached is True


def test_fixpoint_pipeline_converges_when_no_pass_changes_structure() -> None:
    ssa_fn = _ssa_function(
        "fn main() -> tryte:\n"
        "    return 7\n"
    )

    opt_ssa, telemetry = run_fixpoint_pipeline(ssa_fn, max_iterations=5)

    assert opt_ssa.blocks == ssa_fn.blocks
    assert telemetry.iterations == 1
    assert telemetry.converged is True
    assert telemetry.max_iterations_reached is False


def test_strength_reduction_telemetry_counts_only_real_changes() -> None:
    ssa_fn = _ssa_function(
        "fn main() -> tryte:\n"
        "    value: tryte = 4\n"
        "    return value + value\n"
    )

    _opt_ssa, telemetry = run_fixpoint_pipeline(ssa_fn, max_iterations=5)

    assert telemetry.strength_reductions == 0
    assert telemetry.converged is True
    assert telemetry.max_iterations_reached is False


def test_fixpoint_pipeline_supports_internal_pass_ablation() -> None:
    ssa_fn = _ssa_function(
        "fn combine(a: tryte, b: tryte) -> tryte:\n"
        "    x: tryte = a + b\n"
        "    y: tryte = a + b\n"
        "    return x + y\n"
        "fn main() -> tryte:\n"
        "    return combine(2, 3)\n",
        function_name="combine",
    )

    _with_gvn, telemetry_with_gvn = run_fixpoint_pipeline(ssa_fn, max_iterations=5)
    _without_gvn, telemetry_without_gvn = run_fixpoint_pipeline(
        ssa_fn,
        max_iterations=5,
        disabled_passes={"gvn"},
    )

    assert telemetry_with_gvn.expressions_eliminated >= 1
    assert telemetry_without_gvn.expressions_eliminated == 0


def test_fixpoint_pipeline_can_verify_between_passes() -> None:
    ssa_fn = _ssa_function(
        "fn choose(value: tryte) -> tryte:\n"
        "    mut result: tryte = 0\n"
        "    match value <=> 0:\n"
        "        -1:\n"
        "            result = 3\n"
        "        0:\n"
        "            result = 5\n"
        "        else:\n"
        "            result = 7\n"
        "    return result\n"
        "fn main() -> tryte:\n"
        "    return choose(1)\n",
        function_name="choose",
    )

    _opt_ssa, telemetry = run_fixpoint_pipeline(
        ssa_fn,
        max_iterations=5,
        verify_each_pass=True,
    )

    assert telemetry.converged is True
