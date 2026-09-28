from __future__ import annotations

from dataclasses import replace

from bootstrap.s3.ir import IRType
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.optimizer import OptimizationLevel
from bootstrap.s3.pipeline import compile_source
from bootstrap.s3.ssa_optimizer.loops import analyze_loop_facts
from bootstrap.s3.vector_legality import analyze_vector_legality


def _compile(source: str):
    return compile_source(
        source,
        OptimizationLevel.O0,
        mode=SyntaxMode.V0_6,
    )


def _function(compilation, name: str):
    return next(item for item in compilation.ir.functions if item.name == name)


def _counted_loop_source(
    index_name: str,
    bound_name: str,
    *,
    initial: int,
    step: int,
    with_match: bool,
) -> str:
    update = f"{index_name} = {index_name} + {step}\n"
    if with_match:
        body = (
            f"        match {index_name} == {initial}:\n"
            f"            -1:\n                {update}"
            f"            0:\n                {update}"
            f"            1:\n                {update}"
        )
    else:
        body = "        " + update
    return (
        f"fn count_{index_name}({bound_name}: i64) -> i64:\n"
        f"    mut {index_name}: i64 = {initial}\n"
        f"    while {index_name} < {bound_name}:\n"
        f"{body}"
        f"    return {index_name}\n"
        "fn main() -> i64:\n"
        f"    return count_{index_name}(100)\n"
    )


def _recurrence_signature(source: str, function_name: str):
    function = _function(_compile(source), function_name)
    analysis = analyze_loop_facts(function)
    recurrence = next(item for item in analysis.recurrences if item.kind == "INDUCTION")
    return (
        recurrence.kind,
        recurrence.element_type,
        recurrence.initial_value,
        recurrence.step,
        len(recurrence.update_sites),
        tuple(sorted(count for _tail, count in recurrence.backedge_updates)),
    )


def test_single_block_counted_loop_proves_induction_recurrence() -> None:
    compilation = _compile(
        "fn count(limit: i64) -> i64:\n"
        "    mut index: i64 = 0\n"
        "    while index < limit:\n"
        "        index = index + 1\n"
        "    return index\n"
        "fn main() -> i64:\n"
        "    return count(4)\n"
    )
    function = _function(compilation, "count")

    analysis = analyze_loop_facts(function)

    assert len(analysis.loops) == 1
    recurrence = next(item for item in analysis.recurrences if item.kind == "INDUCTION")
    assert recurrence.element_type is IRType.I64
    assert recurrence.initial_value == 0
    assert recurrence.step == 1
    assert len(recurrence.update_sites) == 1
    assert {count for _tail, count in recurrence.backedge_updates} == {1}


def test_switch_continuation_proves_one_update_on_each_backedge() -> None:
    compilation = _compile(
        "fn count(limit: i64) -> i64:\n"
        "    mut index: i64 = 0\n"
        "    while index < limit:\n"
        "        match index == 0:\n"
        "            -1:\n"
        "                index = index + 1\n"
        "            0:\n"
        "                index = index + 1\n"
        "            1:\n"
        "                index = index + 1\n"
        "    return index\n"
        "fn main() -> i64:\n"
        "    return count(4)\n"
    )
    function = _function(compilation, "count")
    analysis = analyze_loop_facts(function)

    loop = analysis.loops[0]
    recurrence = next(item for item in analysis.recurrences if item.kind == "INDUCTION")
    assert len(loop.blocks) > 4
    assert recurrence.loop_header == loop.header
    assert recurrence.update_sites
    assert {count for _tail, count in recurrence.backedge_updates} == {1}


def test_sequential_loops_can_reinitialize_and_reuse_one_scalar() -> None:
    compilation = _compile(
        "fn count_twice(limit: i64) -> i64:\n"
        "    mut index: i64 = 0\n"
        "    while index < limit:\n"
        "        index = index + 1\n"
        "    index = 0\n"
        "    while index < limit:\n"
        "        index = index + 1\n"
        "    return index\n"
        "fn main() -> i64:\n"
        "    return count_twice(4)\n"
    )
    function = _function(compilation, "count_twice")

    analysis = analyze_loop_facts(function)
    inductions = [item for item in analysis.recurrences if item.kind == "INDUCTION"]

    assert len(analysis.loops) == 2
    assert len(inductions) == 2
    assert len({item.memory for item in inductions}) == 1
    assert {count for item in inductions for _tail, count in item.backedge_updates} == {1}


def test_missing_update_on_a_match_path_does_not_prove_induction() -> None:
    compilation = _compile(
        "fn count(limit: i64) -> i64:\n"
        "    mut index: i64 = 0\n"
        "    while index < limit:\n"
        "        match index == 0:\n"
        "            -1:\n"
        "                index = index + 1\n"
        "            0:\n"
        "                discard 0\n"
        "            1:\n"
        "                index = index + 1\n"
        "    return index\n"
        "fn main() -> i64:\n"
        "    return count(4)\n"
    )
    function = _function(compilation, "count")

    analysis = analyze_loop_facts(function)

    assert not any(item.kind == "INDUCTION" for item in analysis.recurrences)


def test_two_updates_on_one_backedge_path_do_not_prove_unit_induction() -> None:
    compilation = _compile(
        "fn count(limit: i64) -> i64:\n"
        "    mut index: i64 = 0\n"
        "    while index < limit:\n"
        "        match index == 0:\n"
        "            -1:\n"
        "                index = index + 1\n"
        "                index = index + 1\n"
        "            0:\n"
        "                index = index + 1\n"
        "            1:\n"
        "                index = index + 1\n"
        "    return index\n"
        "fn main() -> i64:\n"
        "    return count(4)\n"
    )
    function = _function(compilation, "count")

    analysis = analyze_loop_facts(function)

    assert not any(item.kind == "INDUCTION" for item in analysis.recurrences)


def test_ordered_f64_recurrence_is_not_vectorizable_under_strict_fp() -> None:
    compilation = _compile(
        "fn total(values: &f64_vector) -> f64:\n"
        "    mut index: i64 = 0\n"
        "    mut total: f64 = 0.0\n"
        "    while index < f64_vector_len(values):\n"
        "        total = total + f64_vector_get(values, index)\n"
        "        index = index + 1\n"
        "    return total\n"
        "fn main() -> i64:\n"
        "    return 0\n"
    )
    function = _function(compilation, "total")
    analysis = analyze_loop_facts(function)
    report = analyze_vector_legality(function)

    assert any(
        item.kind == "REDUCTION"
        and item.operation == "add"
        and item.element_type is IRType.F64
        and item.ordered
        for item in analysis.recurrences
    )
    assert report["loops"][0]["status"] == "NOT_VECTORIZABLE"
    assert report["summary"]["vectorizable_loops"] == 0


def test_integer_reduction_is_recognized_without_claiming_vector_legality() -> None:
    compilation = _compile(
        "fn total(values: &i64_vector) -> i64:\n"
        "    mut index: i64 = 0\n"
        "    mut total: i64 = 0\n"
        "    while index < i64_vector_len(values):\n"
        "        total = total + i64_vector_get(values, index)\n"
        "        index = index + 1\n"
        "    return total\n"
        "fn main() -> i64:\n"
        "    return 0\n"
    )
    function = _function(compilation, "total")
    analysis = analyze_loop_facts(function)
    report = analyze_vector_legality(function)

    assert any(item.kind == "REDUCTION" and item.element_type is IRType.I64 for item in analysis.recurrences)
    assert report["loops"][0]["status"] == "UNKNOWN"
    assert report["summary"]["vectorizable_loops"] == 0


def test_independent_read_only_scan_remains_unknown_without_range_proof() -> None:
    compilation = _compile(
        "fn scan(values: &i64_vector) -> i64:\n"
        "    mut index: i64 = 0\n"
        "    while index < i64_vector_len(values):\n"
        "        discard i64_vector_get(values, index)\n"
        "        index = index + 1\n"
        "    return index\n"
        "fn main() -> i64:\n"
        "    return 0\n"
    )
    function = _function(compilation, "scan")
    analysis = analyze_loop_facts(function)
    report = analyze_vector_legality(function)

    assert any(item.kind == "INDUCTION" for item in analysis.recurrences)
    assert report["loops"][0]["status"] == "UNKNOWN"
    assert "GENERAL_INTER_ITERATION_MEMORY_DEPENDENCE_NOT_MODELED" in report["loops"][0]["reasons"]


def test_carried_vector_write_does_not_gain_vector_legality() -> None:
    compilation = _compile(
        "fn fill() -> i64:\n"
        "    mut values: i64_vector = i64_vector_new(4)\n"
        "    mut index: i64 = 0\n"
        "    while index < i64_vector_len(&values):\n"
        "        discard i64_vector_set(&mut values, index, index)\n"
        "        index = index + 1\n"
        "    return index\n"
        "fn main() -> i64:\n"
        "    return 0\n"
    )
    function = _function(compilation, "fill")
    analysis = analyze_loop_facts(function)
    report = analyze_vector_legality(function)

    assert any(item.kind == "INDUCTION" for item in analysis.recurrences)
    assert report["loops"][0]["status"] == "UNKNOWN"
    assert report["loops"][0]["unknown_or_mutating_calls"]
    assert "UNKNOWN_OR_MUTATING_CALL_EFFECT" in report["loops"][0]["reasons"]
    assert report["summary"]["vectorizable_loops"] == 0


def test_unknown_call_effect_is_explicit_and_fails_closed() -> None:
    compilation = _compile(
        "fn scan(values: &i64_vector) -> i64:\n"
        "    mut index: i64 = 0\n"
        "    while index < i64_vector_len(values):\n"
        "        discard i64_vector_get(values, index)\n"
        "        index = index + 1\n"
        "    return index\n"
        "fn main() -> i64:\n"
        "    return 0\n"
    )
    function = _function(compilation, "scan")
    blocks = tuple(
        replace(
            block,
            instructions=tuple(
                replace(instruction, callee="unknown_effect")
                if instruction.callee == "i64_vector_get"
                else instruction
                for instruction in block.instructions
            ),
        )
        for block in function.blocks
    )
    mutated_function = replace(function, blocks=blocks)
    report = analyze_vector_legality(mutated_function)

    assert report["loops"][0]["status"] == "UNKNOWN"
    assert report["loops"][0]["unknown_or_mutating_calls"] == ["unknown_effect"]
    assert "UNKNOWN_OR_MUTATING_CALL_EFFECT" in report["loops"][0]["reasons"]
    assert report["summary"]["vectorizable_loops"] == 0


def test_deterministic_generated_counted_loops_prove_exact_backedge_updates() -> None:
    for seed in range(32):
        initial = seed % 7
        step = 1 + (seed * 5) % 4
        source = _counted_loop_source(
            f"index_{seed}",
            f"limit_{seed}",
            initial=initial,
            step=step,
            with_match=seed % 2 == 0,
        )

        signature = _recurrence_signature(source, f"count_index_{seed}")

        assert signature[0] == "INDUCTION"
        assert signature[2] == initial
        assert signature[3] == step
        assert signature[4] >= 1
        assert signature[5] and set(signature[5]) == {1}


def test_loop_renaming_metamorphism_preserves_recurrence_facts() -> None:
    for seed in range(12):
        initial = seed % 5
        step = 1 + seed % 3
        with_match = seed % 2 == 0
        first = _counted_loop_source(
            "counter",
            "ceiling",
            initial=initial,
            step=step,
            with_match=with_match,
        )
        renamed = _counted_loop_source(
            f"cursor_{seed}",
            f"bound_{seed}",
            initial=initial,
            step=step,
            with_match=with_match,
        )

        assert _recurrence_signature(first, "count_counter") == _recurrence_signature(
            renamed, f"count_cursor_{seed}"
        )
