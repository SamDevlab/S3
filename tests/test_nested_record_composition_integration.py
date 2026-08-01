from __future__ import annotations

import pytest

from bootstrap.s3.diagnostics import (
    DiagnosticCategory,
    DiagnosticCode,
    DiagnosticPhase,
    SemanticError,
    diagnostic_from_exception,
)
from bootstrap.s3.emulator import execute_assembly
from bootstrap.s3.ir import IROpcode, IRType
from bootstrap.s3.optimizer import OptimizationLevel
from bootstrap.s3.pipeline import compile_source, compile_sources
from bootstrap.s3.verifier import verify_ir


LOCAL_NESTED_SOURCE = (
    "enum Sign:\n"
    "    Negative\n"
    "    Positive\n"
    "record Leaf:\n"
    "    third: trit\n"
    "    fourth: tryte\n"
    "record Middle:\n"
    "    second: Leaf\n"
    "    first: tryte\n"
    "record Outer:\n"
    "    suffix: tryte\n"
    "    inner: Middle\n"
    "    prefix: trit\n"
    "    sign: Sign\n"
    "fn score(value: Outer) -> tryte:\n"
    "    local: Outer = value\n"
    "    copy: Outer = local\n"
    "    while copy.prefix:\n"
    "        match copy.inner.second.third:\n"
    "            -1:\n"
    "                match copy.sign:\n"
    "                    Sign.Negative:\n"
    "                        return 0\n"
    "                    Sign.Positive:\n"
    "                        return copy.inner.second.fourth + copy.inner.first + copy.suffix\n"
    "            0:\n"
    "                return 1\n"
    "            else:\n"
    "                return 2\n"
    "    return 0\n"
    "fn main() -> tryte:\n"
    "    item: Outer = Outer(sign=Sign.Positive, prefix=-1, inner=Middle(first=3, second=Leaf(fourth=7, third=-1)), suffix=2)\n"
    "    return score(item)\n"
)


MULTIMODULE_SOURCES = (
    (
        "main.s3",
        "module main\n"
        "from geometry import Leaf\n"
        "from model import Inner\n"
        "from model import Outer\n"
        "from consumer import score\n"
        "fn main() -> tryte:\n"
        "    value: Outer = model.Outer(tail=4, inner=model.Inner(leaf=geometry.Leaf(value=6)), flag=-1)\n"
        "    return consumer.score(value)\n",
    ),
    (
        "model.s3",
        "module model\n"
        "from geometry import Leaf\n"
        "export record Inner:\n"
        "    leaf: Leaf\n"
        "export record Outer:\n"
        "    tail: tryte\n"
        "    inner: Inner\n"
        "    flag: trit\n"
        "export fn marker() -> tryte:\n"
        "    return 0\n",
    ),
    (
        "geometry.s3",
        "module geometry\n"
        "export record Leaf:\n"
        "    value: tryte\n"
        "export fn marker() -> tryte:\n"
        "    return 0\n",
    ),
    (
        "consumer.s3",
        "module consumer\n"
        "from model import Outer\n"
        "export fn score(value: Outer) -> tryte:\n"
        "    while value.flag:\n"
        "        return value.inner.leaf.value + value.tail\n"
        "    return 0\n",
    ),
)


def _run_source_o0_o1(source: str) -> tuple[int, int]:
    return tuple(
        execute_assembly(compile_source(source, optimization).assembly)
        for optimization in (OptimizationLevel.O0, OptimizationLevel.O1)
    )


def _run_sources_o0_o1(
    sources: tuple[tuple[str, str], ...],
) -> tuple[int, int]:
    return tuple(
        execute_assembly(compile_sources(sources, optimization).assembly)
        for optimization in (OptimizationLevel.O0, OptimizationLevel.O1)
    )


def test_local_nested_record_composition_is_equivalent_o0_o1() -> None:
    assert _run_source_o0_o1(LOCAL_NESTED_SOURCE) == (12, 12)

    compilation = compile_source(LOCAL_NESTED_SOURCE, OptimizationLevel.O0)
    verify_ir(compilation.ir)
    score = next(function for function in compilation.ir.functions if function.name == "score")

    assert [(parameter.name, parameter.type) for parameter in score.parameters] == [
        ("value__suffix", IRType.TRYTE),
        ("value__inner__second__third", IRType.TRIT),
        ("value__inner__second__fourth", IRType.TRYTE),
        ("value__inner__first", IRType.TRYTE),
        ("value__prefix", IRType.TRIT),
        ("value__sign", IRType.TRYTE),
    ]


def test_multimodule_nested_record_pipeline_is_equivalent_o0_o1() -> None:
    assert _run_sources_o0_o1(MULTIMODULE_SOURCES) == (10, 10)

    compilation = compile_sources(MULTIMODULE_SOURCES, OptimizationLevel.O0)
    verify_ir(compilation.ir)
    score = next(
        function
        for function in compilation.ir.functions
        if function.name == "__s3mod_consumer__score"
    )
    assert [(parameter.name, parameter.type) for parameter in score.parameters] == [
        ("value__tail", IRType.TRYTE),
        ("value__inner__leaf__value", IRType.TRYTE),
        ("value__flag", IRType.TRIT),
    ]


def test_nested_record_source_order_does_not_change_ir_or_flattening() -> None:
    orders = (
        MULTIMODULE_SOURCES,
        (
            MULTIMODULE_SOURCES[3],
            MULTIMODULE_SOURCES[0],
            MULTIMODULE_SOURCES[1],
            MULTIMODULE_SOURCES[2],
        ),
        (
            MULTIMODULE_SOURCES[1],
            MULTIMODULE_SOURCES[2],
            MULTIMODULE_SOURCES[3],
            MULTIMODULE_SOURCES[0],
        ),
    )

    compilations = [
        compile_sources(order, OptimizationLevel.O1)
        for order in orders
    ]

    assert [execute_assembly(compilation.assembly) for compilation in compilations] == [
        10,
        10,
        10,
    ]
    assert compilations[0].ir.to_dict() == compilations[1].ir.to_dict()
    assert compilations[0].ir.to_dict() == compilations[2].ir.to_dict()
    assert compilations[0].assembly.render() == compilations[1].assembly.render()
    assert compilations[0].assembly.render() == compilations[2].assembly.render()
    assert [
        leaf.path
        for leaf in compilations[0].semantic_model.record_leaves(
            "__s3mod_model__type_Outer"
        )
    ] == [
        ("tail",),
        ("inner", "leaf", "value"),
        ("flag",),
    ]


def test_nested_member_chains_after_constructor_parentheses_and_arguments() -> None:
    source = (
        "record Leaf:\n"
        "    value: tryte\n"
        "record Box:\n"
        "    leaf: Leaf\n"
        "fn take(value: tryte) -> tryte:\n"
        "    return value + 1\n"
        "fn main() -> tryte:\n"
        "    return take((Box(leaf=Leaf(value=8))).leaf.value)\n"
    )

    assert _run_source_o0_o1(source) == (9, 9)


def test_nested_single_leaf_return_produces_one_ir_return_value() -> None:
    source = (
        "record Leaf:\n"
        "    value: tryte\n"
        "record Box:\n"
        "    leaf: Leaf\n"
        "fn make() -> Box:\n"
        "    return Box(leaf=Leaf(value=5))\n"
        "fn main() -> tryte:\n"
        "    return make().leaf.value\n"
    )

    compilation = compile_source(source, OptimizationLevel.O0)
    make = next(function for function in compilation.ir.functions if function.name == "make")
    return_instructions = [
        instruction
        for instruction in make.instructions
        if instruction.opcode is IROpcode.RETURN
    ]
    assert len(return_instructions) == 1
    assert len(return_instructions[0].operands) == 1
    assert execute_assembly(compilation.assembly) == 5


def test_static_text_record_fields_are_scalar_nested_leaves() -> None:
    source = (
        "record Label:\n"
        "    text: string\n"
        "record Packet:\n"
        "    flag: trit\n"
        "    label: Label\n"
        "    tail: tryte\n"
        "fn pick(packet: Packet) -> string:\n"
        "    return packet.label.text\n"
        "fn main() -> tryte:\n"
        "    packet: Packet = Packet(tail=4, label=Label(text=\"hello\"), flag=-1)\n"
        "    selected: string = pick(packet)\n"
        "    return len(\"hello\")\n"
    )

    compilation = compile_source(source, OptimizationLevel.O0)
    verify_ir(compilation.ir)
    assert execute_assembly(compilation.assembly) == 5

    pick = next(function for function in compilation.ir.functions if function.name == "pick")
    assert [(parameter.name, parameter.type) for parameter in pick.parameters] == [
        ("packet__flag", IRType.TRIT),
        ("packet__label__text", IRType.STRING),
        ("packet__tail", IRType.TRYTE),
    ]
    assert [
        leaf.path
        for leaf in compilation.semantic_model.record_leaves("Packet")
    ] == [
        ("flag",),
        ("label", "text"),
        ("tail",),
    ]


def test_imported_static_text_record_fields_compose_across_modules() -> None:
    sources = (
        (
            "main.s3",
            "module main\n"
            "from model import Packet\n"
            "from model import Label\n"
            "from consumer import pick\n"
            "fn main() -> tryte:\n"
            "    packet: Packet = model.Packet(flag=-1, label=model.Label(text=\"hello\"))\n"
            "    selected: string = consumer.pick(packet)\n"
            "    return len(\"hello\")\n",
        ),
        (
            "model.s3",
            "module model\n"
            "export record Label:\n"
            "    text: string\n"
            "export record Packet:\n"
            "    flag: trit\n"
            "    label: Label\n"
            "export fn marker() -> tryte:\n"
            "    return 0\n",
        ),
        (
            "consumer.s3",
            "module consumer\n"
            "from model import Packet\n"
            "export fn pick(packet: Packet) -> string:\n"
            "    return packet.label.text\n",
        ),
    )

    assert _run_sources_o0_o1(sources) == (5, 5)


@pytest.mark.parametrize(
    ("source", "message", "code"),
    (
        (
            "record Leaf:\n"
            "    left: tryte\n"
            "    right: tryte\n"
            "record Box:\n"
            "    leaf: Leaf\n"
            "fn make() -> Box:\n"
            "    return Box(leaf=Leaf(left=1, right=2))\n"
            "fn main() -> tryte:\n"
            "    return 0\n",
            "multi-field record returns require a future aggregate ABI",
            DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
        ),
        (
            "record Inner:\n"
            "    value: tryte\n"
            "record Outer:\n"
            "    inner: Inner\n"
            "    flag: trit\n"
            "fn main() -> tryte:\n"
            "    item: Outer = Outer(flag=-1)\n"
            "    return 0\n",
            "record 'Outer' literal is missing field(s): inner",
            DiagnosticCode.RECORD_FIELD_MISSING,
        ),
        (
            "record Inner:\n"
            "    value: tryte\n"
            "record Outer:\n"
            "    inner: Inner\n"
            "fn main() -> tryte:\n"
            "    item: Outer = Outer(inner=Inner(value=1), extra=2)\n"
            "    return 0\n",
            "record 'Outer' has no field 'extra'",
            DiagnosticCode.RECORD_FIELD_UNKNOWN,
        ),
        (
            "record Inner:\n"
            "    value: tryte\n"
            "record Outer:\n"
            "    inner: Inner\n"
            "fn main() -> tryte:\n"
            "    item: Outer = Outer(inner=1)\n"
            "    return 0\n",
            "field 'inner' has type tryte; expected Inner",
            DiagnosticCode.SEMANTIC_TYPE_MISMATCH,
        ),
        (
            "record Left:\n"
            "    value: tryte\n"
            "record Right:\n"
            "    value: tryte\n"
            "record Outer:\n"
            "    left: Left\n"
            "fn main() -> tryte:\n"
            "    item: Outer = Outer(left=Right(value=1))\n"
            "    return 0\n",
            "record literal 'Right' has type Right; expected Left",
            DiagnosticCode.SEMANTIC_TYPE_MISMATCH,
        ),
        (
            "record Inner:\n"
            "    value: tryte\n"
            "record Outer:\n"
            "    inner: Inner\n"
            "fn main() -> tryte:\n"
            "    item: Outer = Outer(inner=Inner(value=1))\n"
            "    return item.inner.missing\n",
            "record 'Inner' has no field 'missing'",
            DiagnosticCode.RECORD_FIELD_UNKNOWN,
        ),
        (
            "record Inner:\n"
            "    value: tryte\n"
            "record Outer:\n"
            "    inner: Inner\n"
            "fn main() -> tryte:\n"
            "    item: Outer = Outer(inner=Inner(value=1))\n"
            "    return item.inner.value.missing\n",
            "field access requires a record value",
            DiagnosticCode.RECORD_FIELD_UNKNOWN,
        ),
        (
            "record Node:\n"
            "    next: Node\n"
            "fn main() -> tryte:\n"
            "    return 0\n",
            "recursive record layout cycle: Node -> Node",
            DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
        ),
        (
            "record Inner:\n"
            "    value: tryte\n"
            "record Outer:\n"
            "    inner: Inner\n"
            "fn main() -> tryte:\n"
            "    values: Inner[1] = [Inner(value=1)]\n"
            "    return 0\n",
            "arrays of nominal types are not supported",
            DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
        ),
    ),
)
def test_nested_record_negative_diagnostics_are_stable(
    source: str,
    message: str,
    code: DiagnosticCode,
) -> None:
    for optimization in (OptimizationLevel.O0, OptimizationLevel.O1):
        with pytest.raises(SemanticError) as captured:
            compile_source(source, optimization)

        diagnostic = diagnostic_from_exception(captured.value)
        assert diagnostic.phase is DiagnosticPhase.SEMANTIC
        assert diagnostic.category is DiagnosticCategory.SEMANTIC
        assert diagnostic.code is code
        assert diagnostic.message == message


def test_private_nested_type_is_rejected_before_lowering() -> None:
    with pytest.raises(SemanticError) as captured:
        compile_sources(
            {
                "main.s3": (
                    "module main\n"
                    "from model import Inner\n"
                    "record Outer:\n"
                    "    inner: Inner\n"
                    "fn main() -> tryte:\n"
                    "    return 0\n"
                ),
                "model.s3": (
                    "module model\n"
                    "record Inner:\n"
                    "    value: tryte\n"
                    "export fn marker() -> tryte:\n"
                    "    return 0\n"
                ),
            }
        )

    diagnostic = diagnostic_from_exception(captured.value)
    assert diagnostic.phase is DiagnosticPhase.SEMANTIC
    assert diagnostic.code is DiagnosticCode.IMPORT_PRIVATE_SYMBOL
    assert "type 'Inner' in module 'model' is private" in diagnostic.message


def test_cross_module_cycle_is_rejected_by_module_graph_before_lowering() -> None:
    with pytest.raises(SemanticError) as captured:
        compile_sources(
            {
                "main.s3": (
                    "module main\n"
                    "from graph import B\n"
                    "export record A:\n"
                    "    b: B\n"
                    "fn main() -> tryte:\n"
                    "    return 0\n"
                ),
                "graph.s3": (
                    "module graph\n"
                    "from main import A\n"
                    "export record B:\n"
                    "    a: A\n"
                    "export fn marker() -> tryte:\n"
                    "    return 0\n"
                ),
            }
        )

    diagnostic = diagnostic_from_exception(captured.value)
    assert diagnostic.phase is DiagnosticPhase.SEMANTIC
    assert diagnostic.code is DiagnosticCode.MODULE_CYCLE
