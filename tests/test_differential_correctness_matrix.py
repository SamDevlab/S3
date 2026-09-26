from __future__ import annotations

from dataclasses import dataclass

import pytest

from bootstrap.s3.diagnostics import DiagnosticCategory, DiagnosticCode
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.optimizer import _o1_passes
from bootstrap.s3.pipeline import compile_source
from bootstrap.s3.ssa import SSABuilder, SSAFunction
from bootstrap.s3.ssa_opt import _FIXPOINT_PASSES, run_fixpoint_pipeline
from tests.support.differential import (
    DifferentialCase,
    DifferentialExpectation,
    assert_hosted_equivalence,
)

pytestmark = pytest.mark.s3_differential


RECURSIVE_LIMIT_SOURCE = """\
fn countdown(value: tryte) -> tryte:
    match value <=> 0:
        -1:
            return 0
        0:
            return 0
        1:
            return countdown(value - 1)
fn main() -> tryte:
    return countdown(10)
"""


HOSTED_CORPUS = (
    DifferentialCase(
        "trit-minimum",
        "fn main() -> trit:\n    return -1\n",
        DifferentialExpectation(return_value=-1),
        tags=("type", "trit"),
    ),
    DifferentialCase(
        "trit-zero",
        "fn main() -> trit:\n    return 0\n",
        DifferentialExpectation(return_value=0),
        tags=("type", "trit"),
    ),
    DifferentialCase(
        "trit-maximum",
        "fn main() -> trit:\n    return 1\n",
        DifferentialExpectation(return_value=1),
        tags=("type", "trit"),
    ),
    DifferentialCase(
        "tryte-minimum",
        "fn main() -> tryte:\n    return -364\n",
        DifferentialExpectation(return_value=-364),
        tags=("type", "tryte"),
    ),
    DifferentialCase(
        "tryte-zero",
        "fn main() -> tryte:\n    return 0\n",
        DifferentialExpectation(return_value=0),
        tags=("type", "tryte"),
    ),
    DifferentialCase(
        "tryte-maximum",
        "fn main() -> tryte:\n    return 364\n",
        DifferentialExpectation(return_value=364),
        tags=("type", "tryte"),
    ),
    DifferentialCase(
        "tryte-addition",
        (
            "fn main() -> tryte:\n"
            "    mut left: tryte = 10\n"
            "    mut right: tryte = 4\n"
            "    return left + right\n"
        ),
        DifferentialExpectation(return_value=14),
        tags=("operation",),
    ),
    DifferentialCase(
        "tryte-subtraction",
        (
            "fn main() -> tryte:\n"
            "    mut left: tryte = 10\n"
            "    mut right: tryte = 4\n"
            "    return left - right\n"
        ),
        DifferentialExpectation(return_value=6),
        tags=("operation", "source-subtraction"),
    ),
    DifferentialCase(
        "tryte-negation",
        (
            "fn main() -> tryte:\n"
            "    mut value: tryte = 10\n"
            "    return -value\n"
        ),
        DifferentialExpectation(return_value=-10),
        tags=("operation",),
    ),
    DifferentialCase(
        "tryte-compare-positive",
        (
            "fn main() -> trit:\n"
            "    mut left: tryte = 10\n"
            "    mut right: tryte = 4\n"
            "    return left <=> right\n"
        ),
        DifferentialExpectation(return_value=1),
        tags=("operation", "compare"),
    ),
    DifferentialCase(
        "tryte-minimum-operation",
        (
            "fn main() -> tryte:\n"
            "    mut left: tryte = -100\n"
            "    mut right: tryte = 40\n"
            "    return left & right\n"
        ),
        DifferentialExpectation(return_value=-100),
        tags=("operation", "minimum"),
    ),
    DifferentialCase(
        "tryte-maximum-operation",
        (
            "fn main() -> tryte:\n"
            "    mut left: tryte = -100\n"
            "    mut right: tryte = 40\n"
            "    return left | right\n"
        ),
        DifferentialExpectation(return_value=40),
        tags=("operation", "maximum"),
    ),
    DifferentialCase(
        "copy-chain",
        (
            "fn helper(value: tryte) -> tryte:\n"
            "    first: tryte = value\n"
            "    second: tryte = first\n"
            "    return second\n"
            "fn main() -> tryte:\n"
            "    return helper(42)\n"
        ),
        DifferentialExpectation(return_value=42),
        tags=("operation", "copy"),
        exercised_passes=("copy_propagation",),
    ),
    DifferentialCase(
        "branch-negative",
        (
            "fn sign(value: tryte) -> trit:\n"
            "    match value <=> 0:\n"
            "        -1:\n"
            "            return -1\n"
            "        0:\n"
            "            return 0\n"
            "        1:\n"
            "            return 1\n"
            "fn main() -> trit:\n"
            "    return sign(-7)\n"
        ),
        DifferentialExpectation(return_value=-1),
        tags=("control", "branch"),
    ),
    DifferentialCase(
        "branch-zero",
        (
            "fn sign(value: tryte) -> trit:\n"
            "    match value <=> 0:\n"
            "        -1:\n"
            "            return -1\n"
            "        0:\n"
            "            return 0\n"
            "        1:\n"
            "            return 1\n"
            "fn main() -> trit:\n"
            "    return sign(0)\n"
        ),
        DifferentialExpectation(return_value=0),
        tags=("control", "branch"),
    ),
    DifferentialCase(
        "branch-positive",
        (
            "fn sign(value: tryte) -> trit:\n"
            "    match value <=> 0:\n"
            "        -1:\n"
            "            return -1\n"
            "        0:\n"
            "            return 0\n"
            "        1:\n"
            "            return 1\n"
            "fn main() -> trit:\n"
            "    return sign(7)\n"
        ),
        DifferentialExpectation(return_value=1),
        tags=("control", "branch"),
    ),
    DifferentialCase(
        "diamond-join",
        (
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
            "    return choose(1)\n"
        ),
        DifferentialExpectation(return_value=7),
        tags=("control", "diamond"),
        exercised_passes=("ssa", "de-ssa"),
    ),
    DifferentialCase(
        "nested-branch",
        (
            "fn choose(value: tryte) -> tryte:\n"
            "    mut result: tryte = 0\n"
            "    match value <=> 0:\n"
            "        -1:\n"
            "            result = 1\n"
            "        0:\n"
            "            result = 2\n"
            "        else:\n"
            "            match value <=> 5:\n"
            "                -1:\n"
            "                    result = 3\n"
            "                0:\n"
            "                    result = 4\n"
            "                else:\n"
            "                    result = 5\n"
            "    return result\n"
            "fn main() -> tryte:\n"
            "    return choose(6)\n"
        ),
        DifferentialExpectation(return_value=5),
        tags=("control", "nested-branch"),
    ),
    DifferentialCase(
        "loop-zero-times",
        (
            "fn main() -> tryte:\n"
            "    mut total: tryte = 3\n"
            "    while 0:\n"
            "        total = total + 1\n"
            "    return total\n"
        ),
        DifferentialExpectation(return_value=3),
        tags=("control", "loop"),
    ),
    DifferentialCase(
        "loop-one-time",
        (
            "fn main() -> tryte:\n"
            "    mut i: tryte = 0\n"
            "    mut total: tryte = 0\n"
            "    while i < 1:\n"
            "        total = total + 9\n"
            "        i = i + 1\n"
            "    return total\n"
        ),
        DifferentialExpectation(return_value=9),
        tags=("control", "loop"),
    ),
    DifferentialCase(
        "loop-multiple-times",
        (
            "fn main() -> tryte:\n"
            "    mut i: tryte = 0\n"
            "    mut total: tryte = 0\n"
            "    while i < 3:\n"
            "        total = total + 2\n"
            "        i = i + 1\n"
            "    return total\n"
        ),
        DifferentialExpectation(return_value=6),
        tags=("control", "loop"),
        exercised_passes=("licm", "ssa", "de-ssa"),
    ),
    DifferentialCase(
        "simple-call",
        (
            "fn add_one(value: tryte) -> tryte:\n"
            "    return value + 1\n"
            "fn main() -> tryte:\n"
            "    return add_one(8)\n"
        ),
        DifferentialExpectation(return_value=9),
        tags=("function", "call"),
    ),
    DifferentialCase(
        "nested-call",
        (
            "fn add_one(value: tryte) -> tryte:\n"
            "    return value + 1\n"
            "fn add_two(value: tryte) -> tryte:\n"
            "    return add_one(add_one(value))\n"
            "fn main() -> tryte:\n"
            "    return add_two(8)\n"
        ),
        DifferentialExpectation(return_value=10),
        tags=("function", "call"),
    ),
    DifferentialCase(
        "recursion",
        (
            "fn sum_to(value: tryte) -> tryte:\n"
            "    match value <=> 0:\n"
            "        -1:\n"
            "            return 0\n"
            "        0:\n"
            "            return 0\n"
            "        1:\n"
            "            return value + sum_to(value - 1)\n"
            "fn main() -> tryte:\n"
            "    return sum_to(4)\n"
        ),
        DifferentialExpectation(return_value=10),
        tags=("function", "recursion"),
    ),
    DifferentialCase(
        "multiple-parameters",
        (
            "fn combine(a: tryte, b: tryte, c: tryte) -> tryte:\n"
            "    return a + b + c\n"
            "fn main() -> tryte:\n"
            "    return combine(2, 3, 4)\n"
        ),
        DifferentialExpectation(return_value=9),
        tags=("function", "parameters"),
    ),
    DifferentialCase(
        "immutable-array-read",
        (
            "fn main() -> tryte:\n"
            "    values: tryte[3] = [5, 6, 7]\n"
            "    return values[2]\n"
        ),
        DifferentialExpectation(
            return_value=7,
            memory=((0, (5, 6, 7)),),
        ),
        observable_memory=(0,),
        tags=("memory", "array"),
    ),
    DifferentialCase(
        "mutable-array-dynamic-index",
        (
            "fn read(index: tryte) -> tryte:\n"
            "    mut values: tryte[3] = [2, 4, 6]\n"
            "    values[index] = values[index] + 1\n"
            "    return values[index]\n"
            "fn main() -> tryte:\n"
            "    return read(1)\n"
        ),
        DifferentialExpectation(return_value=5),
        tags=("memory", "array", "dynamic-index"),
    ),
    DifferentialCase(
        "different-array-cells",
        (
            "fn main() -> tryte:\n"
            "    mut values: tryte[3] = [0, 0, 0]\n"
            "    values[0] = 5\n"
            "    values[2] = 7\n"
            "    return values[0] + values[2]\n"
        ),
        DifferentialExpectation(
            return_value=12,
            memory=((0, (5, 0, 7)),),
        ),
        observable_memory=(0,),
        tags=("memory", "array"),
        exercised_passes=("dse",),
    ),
    DifferentialCase(
        "consecutive-stores",
        (
            "fn main() -> tryte:\n"
            "    mut value: tryte = 1\n"
            "    value = 2\n"
            "    value = 3\n"
            "    return value\n"
        ),
        DifferentialExpectation(
            return_value=3,
            memory=((0, (3,)),),
        ),
        observable_memory=(0,),
        tags=("memory", "store"),
        exercised_passes=("dse",),
    ),
    DifferentialCase(
        "load-between-stores",
        (
            "fn main() -> tryte:\n"
            "    mut value: tryte = 5\n"
            "    observed: tryte = value\n"
            "    value = 7\n"
            "    return observed\n"
        ),
        DifferentialExpectation(
            return_value=5,
            memory=((0, (7,)),),
        ),
        observable_memory=(0,),
        tags=("memory", "load-store"),
        exercised_passes=("dse",),
    ),
    DifferentialCase(
        "memory-in-loop",
        (
            "fn main() -> tryte:\n"
            "    mut i: tryte = 0\n"
            "    mut values: tryte[3] = [0, 0, 0]\n"
            "    while i < 3:\n"
            "        values[i] = i + 1\n"
            "        i = i + 1\n"
            "    return values[0] + values[1] + values[2]\n"
        ),
        DifferentialExpectation(
            return_value=6,
            memory=((0, (3,)), (1, (1, 2, 3))),
        ),
        observable_memory=(0, 1),
        tags=("memory", "loop"),
    ),
    DifferentialCase(
        "runtime-overflow",
        (
            "fn main() -> tryte:\n"
            "    mut value: tryte = 364\n"
            "    return value + 1\n"
        ),
        DifferentialExpectation(
            error_category=DiagnosticCategory.OVERFLOW,
            error_code=DiagnosticCode.RUNTIME_OVERFLOW,
        ),
        tags=("error", "overflow"),
    ),
    DifferentialCase(
        "runtime-bounds",
        (
            "fn read(index: tryte) -> tryte:\n"
            "    values: tryte[2] = [10, 20]\n"
            "    return values[index]\n"
            "fn main() -> tryte:\n"
            "    return read(2)\n"
        ),
        DifferentialExpectation(
            error_category=DiagnosticCategory.BOUNDS,
            error_code=DiagnosticCode.RUNTIME_BOUNDS,
        ),
        tags=("error", "bounds"),
    ),
    DifferentialCase(
        "frame-limit",
        RECURSIVE_LIMIT_SOURCE,
        DifferentialExpectation(
            error_category=DiagnosticCategory.FRAME_LIMIT,
            error_code=DiagnosticCode.RUNTIME_FRAME_LIMIT,
        ),
        max_frames=4,
        tags=("error", "frame-limit"),
    ),
    DifferentialCase(
        "instruction-limit",
        RECURSIVE_LIMIT_SOURCE,
        DifferentialExpectation(
            error_category=DiagnosticCategory.INSTRUCTION_LIMIT,
            error_code=DiagnosticCode.RUNTIME_INSTRUCTION_LIMIT,
        ),
        max_instructions=5,
        tags=("error", "instruction-limit"),
    ),
    DifferentialCase(
        "constant-infinite-loop-instruction-limit",
        (
            "fn main() -> tryte:\n"
            "    mut value: tryte = 0\n"
            "    while -1:\n"
            "        value = value + 0\n"
            "    return value\n"
        ),
        DifferentialExpectation(
            error_category=DiagnosticCategory.INSTRUCTION_LIMIT,
            error_code=DiagnosticCode.RUNTIME_INSTRUCTION_LIMIT,
        ),
        max_instructions=20,
        tags=("error", "instruction-limit", "sccp"),
        exercised_passes=("sccp",),
    ),
)


@dataclass(frozen=True, slots=True)
class PassProbe:
    name: str
    source: str
    expected_return: int
    function_name: str = "main"
    metric: str | None = None
    isolated: bool = True
    ablation_metric_zero: bool = False


PASS_PROBES = (
    PassProbe(
        "gvn",
        (
            "fn helper(a: tryte, b: tryte) -> tryte:\n"
            "    x: tryte = a + b\n"
            "    y: tryte = a + b\n"
            "    return x + y\n"
            "fn main() -> tryte:\n"
            "    return helper(9, 12)\n"
        ),
        42,
        function_name="helper",
        metric="expressions_eliminated",
        ablation_metric_zero=True,
    ),
    PassProbe(
        "copy_propagation",
        (
            "fn helper(value: tryte) -> tryte:\n"
            "    first: tryte = value\n"
            "    second: tryte = first\n"
            "    return second\n"
            "fn main() -> tryte:\n"
            "    return helper(8)\n"
        ),
        8,
        function_name="helper",
    ),
    PassProbe(
        "dse",
        (
            "fn main() -> tryte:\n"
            "    mut value: tryte = 10\n"
            "    value = 20\n"
            "    return value\n"
        ),
        20,
        metric="stores_removed",
        ablation_metric_zero=True,
    ),
    PassProbe(
        "dce",
        (
            "fn helper(value: tryte) -> tryte:\n"
            "    dead: tryte = value + 1\n"
            "    return value\n"
            "fn main() -> tryte:\n"
            "    return helper(12)\n"
        ),
        12,
        function_name="helper",
    ),
    PassProbe(
        "adce",
        (
            "fn helper(value: tryte) -> tryte:\n"
            "    a: tryte = value + 1\n"
            "    b: tryte = a + 1\n"
            "    c: tryte = b + 1\n"
            "    return value\n"
            "fn main() -> tryte:\n"
            "    return helper(12)\n"
        ),
        12,
        function_name="helper",
        metric="dead_instructions_removed",
    ),
    PassProbe(
        "licm",
        (
            "fn loop_sum(limit: tryte, left: tryte, right: tryte) -> tryte:\n"
            "    mut i: tryte = 0\n"
            "    mut total: tryte = 0\n"
            "    while i < limit:\n"
            "        invariant: tryte = left + right\n"
            "        total = total + invariant\n"
            "        i = i + 1\n"
            "    return total\n"
            "fn main() -> tryte:\n"
            "    return loop_sum(3, 10, 20)\n"
        ),
        90,
        function_name="loop_sum",
        metric="licm_moves",
        isolated=False,
        ablation_metric_zero=True,
    ),
    PassProbe(
        "sccp",
        (
            "fn main() -> tryte:\n"
            "    mut result: tryte = 0\n"
            "    selector: trit = 1\n"
            "    match selector:\n"
            "        -1:\n"
            "            result = 1\n"
            "        0:\n"
            "            result = 2\n"
            "        else:\n"
            "            result = 3\n"
            "    return result\n"
        ),
        3,
        metric="expressions_eliminated",
        ablation_metric_zero=True,
    ),
    PassProbe(
        "strength_reduction",
        (
            "fn helper(value: tryte) -> tryte:\n"
            "    inv: tryte = ~value\n"
            "    same: tryte = ~inv\n"
            "    return same\n"
            "fn main() -> tryte:\n"
            "    return helper(7)\n"
        ),
        7,
        function_name="helper",
        metric="strength_reductions",
        ablation_metric_zero=True,
    ),
    PassProbe(
        "peephole",
        (
            "fn helper(value: tryte) -> tryte:\n"
            "    same: tryte = value & value\n"
            "    return same\n"
            "fn main() -> tryte:\n"
            "    return helper(7)\n"
        ),
        7,
        function_name="helper",
    ),
)


def _ssa_function(source: str, function_name: str) -> SSAFunction:
    compilation = compile_source(source, "O0", mode=SyntaxMode.V0_6)
    return SSABuilder.build_function(
        next(
            function
            for function in compilation.ir.functions
            if function.name == function_name
        )
    )


def _ssa_structure(ssa_fn: SSAFunction) -> tuple[object, ...]:
    return (
        ssa_fn.parameters,
        ssa_fn.blocks,
        ssa_fn.memory_objects,
        ssa_fn.return_type,
    )


@pytest.mark.parametrize("case", HOSTED_CORPUS, ids=lambda case: case.name)
def test_hosted_differential_corpus(case: DifferentialCase) -> None:
    assert_hosted_equivalence(case)


def test_current_o1_pass_inventory_is_explicit() -> None:
    assert tuple(pass_.name for pass_ in _o1_passes()) == (
        "remove-unreachable-blocks",
        "thread-empty-jumps",
        "ssa-optimizations",
        "fold-constants",
        "eliminate-dead-pure-instructions",
        "bounded-vector-bounds-elimination",
    )
    assert _FIXPOINT_PASSES == {
        "gvn",
        "copy_propagation",
        "dse",
        "global_dse",
        "dce",
        "adce",
        "licm",
        "sccp",
        "strength_reduction",
        "peephole",
    }
    assert "cse" not in _FIXPOINT_PASSES


@pytest.mark.parametrize("probe", PASS_PROBES, ids=lambda probe: probe.name)
def test_active_ssa_passes_have_differential_probe(probe: PassProbe) -> None:
    assert_hosted_equivalence(
        DifferentialCase(
            probe.name,
            probe.source,
            DifferentialExpectation(return_value=probe.expected_return),
            exercised_passes=(probe.name,),
        )
    )

    before = _ssa_function(probe.source, probe.function_name)
    disabled = (
        set(_FIXPOINT_PASSES) - {probe.name}
        if probe.isolated
        else set()
    )
    after, telemetry = run_fixpoint_pipeline(
        before,
        max_iterations=5,
        disabled_passes=disabled,
        verify_each_pass=True,
    )

    assert _ssa_structure(after) != _ssa_structure(before)
    if probe.metric is not None:
        assert getattr(telemetry, probe.metric) >= 1

    if probe.ablation_metric_zero and probe.metric is not None:
        _ablated, ablated_telemetry = run_fixpoint_pipeline(
            before,
            max_iterations=5,
            disabled_passes={probe.name},
            verify_each_pass=True,
        )
        assert getattr(ablated_telemetry, probe.metric) == 0
