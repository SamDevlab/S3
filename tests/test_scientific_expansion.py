from __future__ import annotations

import math

import pytest

from bootstrap.s3.backends.x86_64 import X8664Backend
from bootstrap.s3.ir_emulator import execute_ir
from bootstrap.s3.builtin_effects import BuiltinEffect, builtin_effect
from bootstrap.s3.cfg import ControlFlowGraph
from bootstrap.s3.dominance import DominatorTree
from bootstrap.s3.optimizer import OptimizationLevel
from bootstrap.s3.pipeline import compile_sources
from bootstrap.s3.stdlib import standard_library_sources


def _compile(body: str, optimization: OptimizationLevel):
    sources = standard_library_sources(modules=("s3.v1.science",))
    sources["main.s3"] = "module main\n" + body
    return compile_sources(sources, optimization=optimization)


def _run(body: str, optimization: OptimizationLevel = OptimizationLevel.O0):
    return execute_ir(_compile(body, optimization).ir)


def _setup_vectors() -> str:
    return (
        "    mut left: f64_vector = f64_vector_new(3)\n"
        "    mut right: f64_vector = f64_vector_new(3)\n"
        "    discard f64_vector_push(&mut left, 1.0)\n"
        "    discard f64_vector_push(&mut left, -2.0)\n"
        "    discard f64_vector_push(&mut left, 3.0)\n"
        "    discard f64_vector_push(&mut right, 0.0)\n"
        "    discard f64_vector_push(&mut right, 2.0)\n"
        "    discard f64_vector_push(&mut right, 1.0)\n"
    )


_MISMATCH = (
    "fn mismatch(value: trit) -> i64:\n"
    "    match value:\n"
    "        -1:\n"
    "            return 0\n"
    "        0:\n"
    "            return 1\n"
    "        1:\n"
    "            return 1\n"
)


def test_reduction_and_extrema_family_has_explicit_empty_contract() -> None:
    body = (
        "from s3.v1.science import F64Result\n"
        "from s3.v1.science import sum\n"
        "from s3.v1.science import sum_squares\n"
        "from s3.v1.science import sum_abs\n"
        "from s3.v1.science import l1_norm\n"
        "from s3.v1.science import min\n"
        "from s3.v1.science import max\n"
        "from s3.v1.science import max_abs\n"
        + _MISMATCH
        + "fn main() -> i64:\n"
        + _setup_vectors()
        + "    low: F64Result = min(&left)\n"
        + "    high: F64Result = max(&left)\n"
        + "    magnitude: F64Result = max_abs(&left)\n"
        + "    mut failures: i64 = mismatch(sum(&left) == 2.0)\n"
        + "    failures = failures + mismatch(sum_squares(&left) == 14.0)\n"
        + "    failures = failures + mismatch(sum_abs(&left) == 6.0)\n"
        + "    failures = failures + mismatch(l1_norm(&left) == 6.0)\n"
        + "    failures = failures + mismatch(low.status == 0)\n"
        + "    failures = failures + mismatch(low.value == -2.0)\n"
        + "    failures = failures + mismatch(high.status == 0)\n"
        + "    failures = failures + mismatch(high.value == 3.0)\n"
        + "    failures = failures + mismatch(magnitude.status == 0)\n"
        + "    failures = failures + mismatch(magnitude.value == 3.0)\n"
        + "    mut empty: f64_vector = f64_vector_new(0)\n"
        + "    failures = failures + mismatch(min(&empty).status == 2)\n"
        + "    failures = failures + mismatch(max(&empty).status == 2)\n"
        + "    failures = failures + mismatch(max_abs(&empty).status == 2)\n"
        + "    return failures\n"
    )
    assert _run(body, OptimizationLevel.O0) == 0
    assert _run(body, OptimizationLevel.O1) == 0


def test_error_statistical_and_similarity_families_compose_without_fp_reassociation() -> None:
    body = (
        "from s3.v1.science import F64Result\n"
        "from s3.v1.science import mae\n"
        "from s3.v1.science import mse\n"
        "from s3.v1.science import rmse\n"
        "from s3.v1.science import sum_squared_difference\n"
        "from s3.v1.science import standard_deviation\n"
        "from s3.v1.science import covariance\n"
        "from s3.v1.science import correlation\n"
        "from s3.v1.science import cosine_similarity\n"
        + _MISMATCH
        + "fn main() -> i64:\n"
        + _setup_vectors()
        + "    absolute_error: F64Result = mae(&left, &right)\n"
        + "    square_error: F64Result = mse(&left, &right)\n"
        + "    root_error: F64Result = rmse(&left, &right)\n"
        + "    squared: F64Result = sum_squared_difference(&left, &right)\n"
        + "    deviation: F64Result = standard_deviation(&left)\n"
        + "    cov: F64Result = covariance(&left, &right)\n"
        + "    corr: F64Result = correlation(&left, &right)\n"
        + "    cosine: F64Result = cosine_similarity(&left, &right)\n"
        + "    mut failures: i64 = mismatch(absolute_error.status == 0)\n"
        + "    failures = failures + mismatch(absolute_error.value * 3.0 == 7.0)\n"
        + "    failures = failures + mismatch(square_error.status == 0)\n"
        + "    failures = failures + mismatch(square_error.value == 7.0)\n"
        + "    failures = failures + mismatch(root_error.value == sqrt(7.0))\n"
        + "    failures = failures + mismatch(squared.value == 21.0)\n"
        + "    failures = failures + mismatch(deviation.value == sqrt(38.0 / 9.0))\n"
        + "    failures = failures + mismatch(cov.status == 0)\n"
        + "    failures = failures + mismatch(cov.value == -1.0)\n"
        + "    failures = failures + mismatch(corr.status == 0)\n"
        + "    failures = failures + mismatch(corr.value < -0.59)\n"
        + "    failures = failures + mismatch(corr.value > -0.61)\n"
        + "    failures = failures + mismatch(cosine.status == 0)\n"
        + "    failures = failures + mismatch(cosine.value < -0.11)\n"
        + "    failures = failures + mismatch(cosine.value > -0.13)\n"
        + "    mut short: f64_vector = f64_vector_new(1)\n"
        + "    discard f64_vector_push(&mut short, 1.0)\n"
        + "    failures = failures + mismatch(mae(&left, &short).status == 1)\n"
        + "    failures = failures + mismatch(mse(&left, &short).status == 1)\n"
        + "    failures = failures + mismatch(covariance(&left, &short).status == 1)\n"
        + "    failures = failures + mismatch(correlation(&left, &short).status == 1)\n"
        + "    failures = failures + mismatch(cosine_similarity(&left, &short).status == 1)\n"
        + "    return failures\n"
    )
    assert _run(body, OptimizationLevel.O0) == 0
    assert _run(body, OptimizationLevel.O1) == 0


def test_empty_singleton_zero_norm_and_zero_variance_are_structured() -> None:
    body = (
        "from s3.v1.science import F64Result\n"
        "from s3.v1.science import mae\n"
        "from s3.v1.science import mse\n"
        "from s3.v1.science import rmse\n"
        "from s3.v1.science import standard_deviation\n"
        "from s3.v1.science import covariance\n"
        "from s3.v1.science import correlation\n"
        "from s3.v1.science import cosine_similarity\n"
        + _MISMATCH
        + "fn main() -> i64:\n"
        + "    mut empty_a: f64_vector = f64_vector_new(0)\n"
        + "    mut empty_b: f64_vector = f64_vector_new(0)\n"
        + "    mut zero: f64_vector = f64_vector_new(2)\n"
        + "    mut constant: f64_vector = f64_vector_new(2)\n"
        + "    discard f64_vector_push(&mut zero, 0.0)\n"
        + "    discard f64_vector_push(&mut zero, -0.0)\n"
        + "    discard f64_vector_push(&mut constant, 5.0)\n"
        + "    discard f64_vector_push(&mut constant, 5.0)\n"
        + "    mut failures: i64 = mismatch(mae(&empty_a, &empty_b).status == 2)\n"
        + "    failures = failures + mismatch(mse(&empty_a, &empty_b).status == 2)\n"
        + "    failures = failures + mismatch(rmse(&empty_a, &empty_b).status == 2)\n"
        + "    failures = failures + mismatch(standard_deviation(&empty_a).status == 2)\n"
        + "    failures = failures + mismatch(covariance(&empty_a, &empty_b).status == 2)\n"
        + "    failures = failures + mismatch(correlation(&empty_a, &empty_b).status == 2)\n"
        + "    failures = failures + mismatch(cosine_similarity(&empty_a, &empty_b).status == 2)\n"
        + "    failures = failures + mismatch(cosine_similarity(&zero, &constant).status == 3)\n"
        + "    failures = failures + mismatch(correlation(&zero, &constant).status == 3)\n"
        + "    failures = failures + mismatch(standard_deviation(&constant).value == 0.0)\n"
        + "    return failures\n"
    )
    assert _run(body, OptimizationLevel.O0) == 0
    assert _run(body, OptimizationLevel.O1) == 0


@pytest.mark.parametrize("optimization", [OptimizationLevel.O0, OptimizationLevel.O1])
def test_sum_squares_propagates_nan_and_large_finite_inputs(optimization) -> None:
    nan_body = (
        "from s3.v1.science import sum_squares\n"
        "fn main() -> f64:\n"
        "    mut values: f64_vector = f64_vector_new(2)\n"
        "    discard f64_vector_push(&mut values, sqrt(-1.0))\n"
        "    discard f64_vector_push(&mut values, 2.0)\n"
        "    return sum_squares(&values)\n"
    )
    assert math.isnan(_run(nan_body, optimization))

    large_body = (
        "from s3.v1.science import sum_squares\n"
        "fn main() -> f64:\n"
        "    mut values: f64_vector = f64_vector_new(1)\n"
        "    discard f64_vector_push(&mut values, 1000000000.0)\n"
        "    return sum_squares(&values)\n"
    )
    result = _run(large_body, optimization)
    assert math.isfinite(result)
    assert result == 1e18


def _loop_blocks(function) -> set[str]:
    cfg = ControlFlowGraph.build(function)
    dominators = DominatorTree.build(cfg)
    members: set[str] = set()
    for tail, node in cfg.nodes.items():
        for head in node.successors:
            if not dominators.dominates(head, tail):
                continue
            loop = {head, tail}
            worklist = [tail]
            while worklist:
                current = worklist.pop()
                for predecessor in cfg.nodes[current].predecessors:
                    if predecessor not in loop and dominators.dominates(head, predecessor):
                        loop.add(predecessor)
                        worklist.append(predecessor)
            members.update(loop)
    return members


def _function(compilation, short_name: str):
    return next(
        fn
        for fn in compilation.ir.functions
        if fn.name == short_name or fn.name.endswith(f"__{short_name}")
    )


def test_readonly_builtin_effect_contract_is_closed_world() -> None:
    assert builtin_effect("f64_vector_len") is BuiltinEffect.READ_ONLY
    assert builtin_effect("f64_vector_get") is BuiltinEffect.READ_ONLY
    assert builtin_effect("f64_vector_push") is BuiltinEffect.MUTATES
    assert builtin_effect("user_supplied_callback") is BuiltinEffect.UNKNOWN


def test_o1_hoists_vector_length_from_readonly_scientific_loop() -> None:
    body = (
        "fn total(values: &f64_vector) -> f64:\n"
        "    mut index: i64 = 0\n"
        "    mut result: f64 = 0.0\n"
        "    while index < f64_vector_len(values):\n"
        "        result = result + f64_vector_get(values, index)\n"
        "        index = index + 1\n"
        "    return result\n"
        "fn main() -> f64:\n"
        "    mut values: f64_vector = f64_vector_new(2)\n"
        "    mut empty: f64_vector = f64_vector_new(0)\n"
        "    discard f64_vector_push(&mut values, 1.5)\n"
        "    discard f64_vector_push(&mut values, 2.5)\n"
        "    return total(&empty) + total(&values)\n"
    )
    unoptimized = _compile(body, OptimizationLevel.O0)
    optimized = _compile(body, OptimizationLevel.O1)
    assert optimized.semantic_model.contains_dynamic
    unoptimized_fn = _function(unoptimized, "total")
    optimized_fn = _function(optimized, "total")
    original_loop = _loop_blocks(unoptimized_fn)
    optimized_loop = _loop_blocks(optimized_fn)
    original_len_blocks = {
        block.name
        for block in unoptimized_fn.blocks
        if any(inst.callee == "f64_vector_len" for inst in block.instructions)
    }
    optimized_len_blocks = {
        block.name
        for block in optimized_fn.blocks
        if any(inst.callee == "f64_vector_len" for inst in block.instructions)
    }
    assert original_len_blocks & original_loop
    assert optimized_len_blocks.isdisjoint(optimized_loop)
    assert execute_ir(unoptimized.ir) == execute_ir(optimized.ir) == 4.0


def test_o1_does_not_hoist_vector_length_across_unknown_or_mutating_calls() -> None:
    unknown_body = (
        "fn inspect(values: &f64_vector) -> i64:\n"
        "    return f64_vector_len(values)\n"
        "fn total(values: &f64_vector) -> f64:\n"
        "    mut index: i64 = 0\n"
        "    mut result: f64 = 0.0\n"
        "    while index < f64_vector_len(values):\n"
        "        result = result + to_f64(inspect(values))\n"
        "        index = index + 1\n"
        "    return result\n"
        "fn main() -> f64:\n"
        "    mut values: f64_vector = f64_vector_new(1)\n"
        "    discard f64_vector_push(&mut values, 2.0)\n"
        "    return total(&values)\n"
    )
    mutation_body = (
        "fn main() -> i64:\n"
        "    mut values: f64_vector = f64_vector_new(1)\n"
        "    discard f64_vector_push(&mut values, 2.0)\n"
        "    mut index: i64 = 0\n"
        "    mut result: i64 = 0\n"
        "    while index < 2:\n"
        "        result = result + f64_vector_len(&values)\n"
        "        discard f64_vector_push(&mut values, to_f64(index))\n"
        "        index = index + 1\n"
        "    return result\n"
    )
    for body, function_name in ((unknown_body, "total"), (mutation_body, "main")):
        optimized = _compile(body, OptimizationLevel.O1)
        function = _function(optimized, function_name)
        loop = _loop_blocks(function)
        length_blocks = {
            block.name
            for block in function.blocks
            if any(inst.callee == "f64_vector_len" for inst in block.instructions)
        }
        assert length_blocks & loop


@pytest.mark.parametrize("register_allocation", [False, True])
def test_native_primitive_vector_access_is_inlined_and_get_remains_checked(
    register_allocation: bool,
) -> None:
    body = (
        "fn at(values: &f64_vector, index: i64) -> f64:\n"
        "    return f64_vector_get(values, index)\n"
        "fn length(values: &f64_vector) -> i64:\n"
        "    return f64_vector_len(values)\n"
        "fn main() -> i64:\n"
        "    return 0\n"
    )
    compilation = _compile(body, OptimizationLevel.O0)
    native = X8664Backend(register_allocation=register_allocation).generate(
        compilation.assembly
    )

    get_body = native.split(".globl s3___s3mod_main__at\n", 1)[1].split(
        ".globl s3___s3mod_main__length\n", 1
    )[0]
    length_body = native.split(".globl s3___s3mod_main__length\n", 1)[1].split(
        ".globl s3_main\n", 1
    )[0]
    assert "call __s3_builtin_f64_vector_get" not in get_body
    assert "js __s3_fail_bounds" in get_body
    assert "jc __s3_fail_bounds" in get_body
    assert "jae __s3_fail_bounds" in get_body
    assert "mov rax, qword ptr [r11 + rax]" in get_body
    assert "call __s3_builtin_f64_vector_len" not in length_body
    assert "mov r11, qword ptr [r10]" in length_body
    assert "mov rax, qword ptr [r11 + 8]" in length_body
    assert "sar rax, 3" in length_body
