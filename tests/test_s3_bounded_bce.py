from __future__ import annotations

import platform

import pytest

from bootstrap.s3.backends.x86_64 import (
    NativeToolchain,
    X8664Backend,
    generate_native_assembly,
)
from bootstrap.s3.assembly import parse_assembly
from bootstrap.s3.dynamic import BufferBoundsError
from bootstrap.s3.ir_emulator import execute_ir
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.numeric import NumericError
from bootstrap.s3.optimizer import OptimizationLevel
from bootstrap.s3.pipeline import compile_source
from bootstrap.s3.ssa_optimizer.loops import analyze_loop_facts


def _source(
    condition: str,
    increment: int = 1,
    *,
    initial: int = 0,
    access_index: str = "index",
    condition_vector: str = "values",
    access_before_increment: bool = True,
) -> str:
    access = f"result = result + f64_vector_get(values, {access_index})\n"
    update = (
        f"index = index - {-increment}\n"
        if increment < 0
        else f"index = index + {increment}\n"
    )
    loop_body = access + update if access_before_increment else update + access
    indented_body = "".join(
        f"        {line}\n" for line in loop_body.rstrip().splitlines()
    )
    return (
        "fn total(values: &f64_vector, bound: &f64_vector) -> f64:\n"
        + f"    mut index: i64 = {initial}\n"
        + "    mut result: f64 = 0.0\n"
        + f"    while {condition.format(vector=condition_vector)}:\n"
        + indented_body
        + "    return result\n"
        + "fn main() -> i64:\n"
        + "    return 0\n"
    )


def _get_call(compilation, function_name: str = "total"):
    function = next(
        function
        for function in compilation.ir.functions
        if function.name == function_name or function.name.endswith(f"__{function_name}")
    )
    return next(
        instruction
        for block in function.blocks
        for instruction in block.instructions
        if instruction.callee == "f64_vector_get"
    )


def _native_function_body(compilation, function_name: str = "total") -> str:
    function = next(
        function
        for function in compilation.assembly.functions
        if function.name == function_name or function.name.endswith(f"__{function_name}")
    )
    native = X8664Backend().generate(compilation.assembly)
    return native.split(f".globl s3_{function.name}\n", 1)[1].split("\n.globl", 1)[0]


def test_canonical_counted_vector_loop_elides_native_bounds_check() -> None:
    compilation = compile_source(
        _source("index < f64_vector_len(values)"),
        optimization=OptimizationLevel.O1,
        mode=SyntaxMode.V0_6,
    )

    assert _get_call(compilation).bounds_proven
    assembly_get = next(
        instruction
        for function in compilation.assembly.functions
        if function.name == "total" or function.name.endswith("__total")
        for block in function.blocks
        for instruction in block.instructions
        if instruction.callee == "f64_vector_get"
    )
    assert assembly_get.bounds_proven
    native = _native_function_body(compilation)
    assert "js __s3_fail_bounds" not in native
    assert "jc __s3_fail_bounds" not in native
    assert "jae __s3_fail_bounds" not in native
    assert "qword ptr [r11 + rsi*8]" in native
    assert "shl rax, 3" not in native
    total_function = next(
        function for function in compilation.ir.functions if function.name == "total"
    )
    metrics = analyze_loop_facts(total_function).metrics
    assert metrics.bounds_checks_seen == 1
    assert metrics.bounds_checks_proven_safe == 1
    assert metrics.bounds_checks_eliminated == 1
    assert metrics.bounds_checks_retained == 0

    parsed = parse_assembly(compilation.assembly.render())
    parsed_get = next(
        instruction
        for function in parsed.functions
        if function.name == "total"
        for block in function.blocks
        for instruction in block.instructions
        if instruction.callee == "f64_vector_get"
    )
    assert not parsed_get.bounds_proven


def test_metrics_distinguish_proven_from_transformed_checks() -> None:
    source = _source("index < f64_vector_len(values)")
    unoptimized = compile_source(
        source,
        optimization=OptimizationLevel.O0,
        mode=SyntaxMode.V0_6,
    )
    unoptimized_function = next(
        function for function in unoptimized.ir.functions if function.name == "total"
    )
    pending = analyze_loop_facts(unoptimized_function).metrics
    assert pending.bounds_checks_seen == 1
    assert pending.bounds_checks_proven_safe == 1
    assert pending.bounds_checks_eliminated == 0
    assert pending.bounds_checks_retained == 1

    optimized = compile_source(
        source,
        optimization=OptimizationLevel.O1,
        mode=SyntaxMode.V0_6,
    )
    optimized_function = next(
        function for function in optimized.ir.functions if function.name == "total"
    )
    applied = analyze_loop_facts(optimized_function).metrics
    assert applied.bounds_checks_proven_safe == 1
    assert applied.bounds_checks_eliminated == 1
    assert applied.bounds_checks_retained == 0


def test_ordered_add_reduction_is_recognized_without_reassociation() -> None:
    compilation = compile_source(
        _source("index < f64_vector_len(values)"),
        optimization=OptimizationLevel.O0,
        mode=SyntaxMode.V0_6,
    )
    function = next(
        function for function in compilation.ir.functions if function.name == "total"
    )
    analysis = analyze_loop_facts(function)

    reduction = next(item for item in analysis.reductions if item.element_type.value == "f64")
    assert reduction.operation == "add"
    assert reduction.initial_constant == 0.0
    assert reduction.ordered
    assert analysis.reduction_metrics.add_reductions == 1
    assert analysis.reduction_metrics.min_reductions == 0
    assert analysis.reduction_metrics.max_reductions == 0
    assert analysis.reduction_metrics.unsupported_reductions is None


def test_float_reduction_keeps_left_to_right_rounding_at_o0_and_o1() -> None:
    source = (
        "fn total(values: &f64_vector) -> f64:\n"
        "    mut index: i64 = 0\n"
        "    mut result: f64 = 0.0\n"
        "    while index < f64_vector_len(values):\n"
        "        result = result + f64_vector_get(values, index)\n"
        "        index = index + 1\n"
        "    return result\n"
        "fn main() -> f64:\n"
        "    mut values: f64_vector = f64_vector_new(3)\n"
        "    discard f64_vector_push(&mut values, 10000000000000000.0)\n"
        "    discard f64_vector_push(&mut values, -10000000000000000.0)\n"
        "    discard f64_vector_push(&mut values, 1.0)\n"
        "    return total(&values)\n"
    )
    outputs = []
    for level in (OptimizationLevel.O0, OptimizationLevel.O1):
        compilation = compile_source(source, optimization=level, mode=SyntaxMode.V0_6)
        outputs.append(execute_ir(compilation.ir))
        function = next(item for item in compilation.ir.functions if item.name == "total")
        analysis = analyze_loop_facts(function)
        assert any(item.operation == "add" and item.ordered for item in analysis.reductions)
    assert outputs == [1.0, 1.0]


@pytest.mark.parametrize(
    ("operator", "initial", "expected_operation", "metric_name"),
    [
        ("&", 1, "tritwise_minimum", "min_reductions"),
        ("|", -1, "tritwise_maximum", "max_reductions"),
    ],
)
def test_tryte_minimum_and_maximum_reductions_are_named_semantically(
    operator: str,
    initial: int,
    expected_operation: str,
    metric_name: str,
) -> None:
    source = (
        "fn fold(values: &tryte_vector) -> tryte:\n"
        "    mut index: i64 = 0\n"
        f"    mut result: tryte = {initial}\n"
        "    while index < tryte_vector_len(values):\n"
        f"        result = result {operator} tryte_vector_get(values, index)\n"
        "        index = index + 1\n"
        "    return result\n"
        "fn main() -> i64:\n"
        "    return 0\n"
    )
    compilation = compile_source(source, optimization=OptimizationLevel.O0, mode=SyntaxMode.V0_6)
    function = next(item for item in compilation.ir.functions if item.name == "fold")
    analysis = analyze_loop_facts(function)

    assert any(item.operation == expected_operation for item in analysis.reductions)
    assert getattr(analysis.reduction_metrics, metric_name) == 1


def test_greater_than_loop_does_not_reuse_less_than_range_proof() -> None:
    compilation = compile_source(
        _source("index > f64_vector_len({vector})", initial=1),
        optimization=OptimizationLevel.O1,
        mode=SyntaxMode.V0_6,
    )

    assert not _get_call(compilation).bounds_proven
    assert "jae __s3_fail_bounds" in _native_function_body(compilation)


def test_match_conditional_induction_updates_keep_vector_bounds_check() -> None:
    source = (
        "fn total(values: &f64_vector) -> f64:\n"
        "    mut index: i64 = 0\n"
        "    mut result: f64 = 0.0\n"
        "    while index < f64_vector_len(values):\n"
        "        match index == 0:\n"
        "            -1:\n"
        "                index = index + 1\n"
        "            0:\n"
        "                index = index + 1\n"
        "            1:\n"
        "                index = index + 1\n"
        "        result = result + f64_vector_get(values, index)\n"
        "    return result\n"
        "fn main() -> i64:\n"
        "    return 0\n"
    )
    compilation = compile_source(
        source,
        optimization=OptimizationLevel.O1,
        mode=SyntaxMode.V0_6,
    )

    assert not _get_call(compilation).bounds_proven
    assert "jae __s3_fail_bounds" in _native_function_body(compilation)


def test_preloop_mutable_reference_to_induction_variable_blocks_bce() -> None:
    source = (
        "fn set_negative(value: &mut i64) -> i64:\n"
        "    *value = -1\n"
        "    return 0\n"
        "fn total(values: &f64_vector) -> f64:\n"
        "    mut index: i64 = 0\n"
        "    mut result: f64 = 0.0\n"
        "    ref: &mut i64 = &mut index\n"
        "    discard set_negative(ref)\n"
        "    while index < f64_vector_len(values):\n"
        "        result = result + f64_vector_get(values, index)\n"
        "        index = index + 1\n"
        "    return result\n"
        "fn main() -> i64:\n"
        "    mut values: f64_vector = f64_vector_new(1)\n"
        "    discard f64_vector_push(&mut values, 42.0)\n"
        "    discard total(&values)\n"
        "    return 0\n"
    )
    for level in (OptimizationLevel.O0, OptimizationLevel.O1):
        compilation = compile_source(source, optimization=level, mode=SyntaxMode.V0_6)
        assert not _get_call(compilation).bounds_proven
        assert "jae __s3_fail_bounds" in _native_function_body(compilation)
        with pytest.raises(BufferBoundsError, match=r"outside \[0, length\)"):
            execute_ir(compilation.ir)


@pytest.mark.parametrize(
    ("condition", "increment", "initial", "access_index", "condition_vector", "access_before_increment"),
    [
        ("index <= f64_vector_len({vector})", 1, 0, "index", "values", True),
        ("index < f64_vector_len({vector})", -1, 0, "index", "values", True),
        ("index < f64_vector_len({vector})", 1, -1, "index", "values", True),
        ("index < f64_vector_len({vector})", 1, 0, "index + 1", "values", True),
        ("index < f64_vector_len({vector})", 1, 0, "index", "bound", True),
        ("index < f64_vector_len({vector})", 1, 0, "index", "values", False),
    ],
)
def test_noncanonical_range_keeps_native_bounds_check(
    condition: str,
    increment: int,
    initial: int,
    access_index: str,
    condition_vector: str,
    access_before_increment: bool,
) -> None:
    compilation = compile_source(
        _source(
            condition,
            increment,
            initial=initial,
            access_index=access_index,
            condition_vector=condition_vector,
            access_before_increment=access_before_increment,
        ),
        optimization=OptimizationLevel.O1,
        mode=SyntaxMode.V0_6,
    )

    assert not _get_call(compilation).bounds_proven
    native = _native_function_body(compilation)
    assert "jae __s3_fail_bounds" in native
    assert "qword ptr [r11 + rax]" in native


@pytest.mark.parametrize(("initial", "increment"), [(0, 2), (2, 3)])
def test_nonnegative_positive_stride_loop_proves_each_access(
    initial: int,
    increment: int,
) -> None:
    compilation = compile_source(
        _source("index < f64_vector_len({vector})", increment, initial=initial),
        optimization=OptimizationLevel.O1,
        mode=SyntaxMode.V0_6,
    )

    assert _get_call(compilation).bounds_proven
    assert "jae __s3_fail_bounds" not in _native_function_body(compilation)


def test_unknown_call_keeps_vector_bounds_check() -> None:
    source = _source("index < f64_vector_len(values)")
    source = source.replace(
        "        result = result + f64_vector_get(values, index)\n",
        "        discard inspect()\n"
        "        result = result + f64_vector_get(values, index)\n",
    )
    source += "fn inspect() -> i64:\n    return 0\n"
    compilation = compile_source(
        source,
        optimization=OptimizationLevel.O1,
        mode=SyntaxMode.V0_6,
    )

    assert not _get_call(compilation).bounds_proven
    assert "jae __s3_fail_bounds" in _native_function_body(compilation)


def test_vector_mutation_keeps_bounds_check() -> None:
    source = _source("index < f64_vector_len(values)")
    source = source.replace(
        "values: &f64_vector, bound:",
        "values: &f64_vector, mutable_values: &mut f64_vector, bound:",
    ).replace(
        "        result = result + f64_vector_get(values, index)\n",
        "        discard f64_vector_push(mutable_values, 0.0)\n"
        "        result = result + f64_vector_get(values, index)\n",
    )
    compilation = compile_source(
        source,
        optimization=OptimizationLevel.O1,
        mode=SyntaxMode.V0_6,
    )

    assert not _get_call(compilation).bounds_proven
    assert "jae __s3_fail_bounds" in _native_function_body(compilation)


def test_bounded_loop_result_is_identical_with_and_without_optimization() -> None:
    source = (
        "fn total(values: &f64_vector) -> f64:\n"
        "    mut index: i64 = 0\n"
        "    mut result: f64 = 0.0\n"
        "    while index < f64_vector_len(values):\n"
        "        result = result + f64_vector_get(values, index)\n"
        "        index = index + 1\n"
        "    return result\n"
        "fn main() -> f64:\n"
        "    mut values: f64_vector = f64_vector_new(3)\n"
        "    discard f64_vector_push(&mut values, 1.0)\n"
        "    discard f64_vector_push(&mut values, 2.0)\n"
        "    discard f64_vector_push(&mut values, 3.0)\n"
        "    return total(&values)\n"
    )
    results = [
        execute_ir(
            compile_source(source, optimization=level, mode=SyntaxMode.V0_6).ir
        )
        for level in (OptimizationLevel.O0, OptimizationLevel.O1)
    ]
    assert results == [6.0, 6.0]


def test_proven_bounds_do_not_suppress_checked_induction_overflow() -> None:
    source = (
        "fn total(values: &f64_vector) -> f64:\n"
        "    mut index: i64 = 1\n"
        "    mut result: f64 = 0.0\n"
        "    while index < f64_vector_len(values):\n"
        "        result = result + f64_vector_get(values, index)\n"
        "        index = index + 9223372036854775807\n"
        "    return result\n"
        "fn main() -> i64:\n"
        "    mut values: f64_vector = f64_vector_new(2)\n"
        "    discard f64_vector_push(&mut values, 1.0)\n"
        "    discard f64_vector_push(&mut values, 2.0)\n"
        "    discard total(&values)\n"
        "    return 0\n"
    )
    for optimization in (OptimizationLevel.O0, OptimizationLevel.O1):
        compilation = compile_source(source, optimization=optimization, mode=SyntaxMode.V0_6)
        if optimization is OptimizationLevel.O1:
            assert _get_call(compilation).bounds_proven
        with pytest.raises(
            NumericError,
            match=r"outside \[-9223372036854775808, 9223372036854775807\]",
        ):
            execute_ir(compilation.ir)


@pytest.mark.skipif(
    platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"},
    reason="BCE native execution requires Linux x86-64",
)
def test_native_bounded_loop_matches_with_and_without_bce(tmp_path) -> None:
    source = (
        "fn total(values: &f64_vector) -> f64:\n"
        "    mut index: i64 = 0\n"
        "    mut result: f64 = 0.0\n"
        "    while index < f64_vector_len(values):\n"
        "        result = result + f64_vector_get(values, index)\n"
        "        index = index + 1\n"
        "    return result\n"
        "fn mismatch(value: trit) -> i64:\n"
        "    match value:\n"
        "        -1:\n"
        "            return 0\n"
        "        0:\n"
        "            return 1\n"
        "        1:\n"
        "            return 1\n"
        "fn main() -> i64:\n"
        "    mut values: f64_vector = f64_vector_new(3)\n"
        "    discard f64_vector_push(&mut values, 1.0)\n"
        "    discard f64_vector_push(&mut values, 2.0)\n"
        "    discard f64_vector_push(&mut values, 3.0)\n"
        "    return mismatch(total(&values) == 6.0)\n"
    )
    toolchain = NativeToolchain.detect()

    for optimization in (OptimizationLevel.O0, OptimizationLevel.O1):
        compilation = compile_source(
            source,
            optimization=optimization,
            mode=SyntaxMode.V0_6,
        )
        executable = toolchain.build(
            generate_native_assembly(compilation.assembly),
            tmp_path / f"bounded-vector-{optimization.value.lower()}",
        )
        completed = toolchain.run(executable)
        assert completed.returncode == 0, completed.stderr
        assert completed.stderr == ""
        assert completed.stdout.strip() == "program returned: 0"
