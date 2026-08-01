from __future__ import annotations

import pytest

from bootstrap.s3.diagnostics import DiagnosticCode, SemanticError
from bootstrap.s3.emulator import execute_assembly
from bootstrap.s3.ir import IROpcode, IRType
from bootstrap.s3.pipeline import compile_source, compile_sources, run_source
from bootstrap.s3.verifier import verify_ir


def _assert_o0_o1(source: str, expected: int) -> None:
    assert run_source(source, optimization="O0") == expected
    assert run_source(source, optimization="O1") == expected


def test_nested_record_local_copy_and_member_chain_execute_o0_o1() -> None:
    source = (
        "enum Sign:\n"
        "    Negative\n"
        "    Positive\n"
        "record Coordinates:\n"
        "    y: tryte\n"
        "    x: trit\n"
        "record Point:\n"
        "    visible: trit\n"
        "    coordinates: Coordinates\n"
        "    sign: Sign\n"
        "fn main() -> tryte:\n"
        "    point: Point = Point(visible=-1, coordinates=Coordinates(y=8, x=-1), sign=Sign.Positive)\n"
        "    copy: Point = point\n"
        "    while copy.coordinates.x:\n"
        "        match copy.sign:\n"
        "            Sign.Negative:\n"
        "                return 0\n"
        "            Sign.Positive:\n"
        "                return copy.coordinates.y + 1\n"
        "    return 0\n"
    )

    _assert_o0_o1(source, 9)


def test_deep_nested_record_parameter_and_literal_argument_execute_o0_o1() -> None:
    source = (
        "record Leaf:\n"
        "    value: tryte\n"
        "record Middle:\n"
        "    leaf: Leaf\n"
        "record Root:\n"
        "    prefix: trit\n"
        "    middle: Middle\n"
        "fn score(root: Root) -> tryte:\n"
        "    while root.prefix:\n"
        "        return root.middle.leaf.value - 1\n"
        "    return root.middle.leaf.value\n"
        "fn main() -> tryte:\n"
        "    return score(Root(prefix=-1, middle=Middle(leaf=Leaf(value=7))))\n"
    )

    compilation = compile_source(source, "O0")
    verify_ir(compilation.ir)
    score = next(function for function in compilation.ir.functions if function.name == "score")
    assert [(parameter.name, parameter.type) for parameter in score.parameters] == [
        ("root__prefix", IRType.TRIT),
        ("root__middle__leaf__value", IRType.TRYTE),
    ]
    assert execute_assembly(compilation.assembly) == 6
    assert run_source(source, optimization="O1") == 6


def test_nested_record_values_flow_through_branch_and_loop() -> None:
    source = (
        "record Inner:\n"
        "    value: tryte\n"
        "record Outer:\n"
        "    flag: trit\n"
        "    inner: Inner\n"
        "fn pick(flag: trit) -> tryte:\n"
        "    item: Outer = Outer(flag=flag, inner=Inner(value=4))\n"
        "    while item.flag:\n"
        "        return item.inner.value + 1\n"
        "    return item.inner.value\n"
        "fn main() -> tryte:\n"
        "    return pick(-1)\n"
    )

    _assert_o0_o1(source, 5)


def test_qualified_nested_constructors_and_imported_values_execute() -> None:
    sources = {
        "main.s3": (
            "module main\n"
            "from model import Inner\n"
            "from model import Outer\n"
            "from consumer import score\n"
            "fn main() -> tryte:\n"
            "    return consumer.score(model.Outer(inner=model.Inner(value=10), flag=-1))\n"
        ),
        "model.s3": (
            "module model\n"
            "export record Inner:\n"
            "    value: tryte\n"
            "export record Outer:\n"
            "    inner: Inner\n"
            "    flag: trit\n"
            "export fn marker() -> tryte:\n"
            "    return 0\n"
        ),
        "consumer.s3": (
            "module consumer\n"
            "from model import Outer\n"
            "export fn score(value: Outer) -> tryte:\n"
            "    while value.flag:\n"
            "        return value.inner.value - 1\n"
            "    return value.inner.value\n"
        ),
    }

    for optimization in ("O0", "O1"):
        compilation = compile_sources(sources, optimization)
        verify_ir(compilation.ir)
        assert execute_assembly(compilation.assembly) == 9


def test_member_access_after_nested_single_leaf_record_call_reuses_scalar_result() -> None:
    source = (
        "record Inner:\n"
        "    value: tryte\n"
        "record Box:\n"
        "    inner: Inner\n"
        "fn make() -> Box:\n"
        "    return Box(inner=Inner(value=8))\n"
        "fn main() -> tryte:\n"
        "    return make().inner.value\n"
    )

    compilation = compile_source(source, "O0")
    main = next(function for function in compilation.ir.functions if function.name == "main")
    assert [instruction.opcode for instruction in main.instructions] == [
        IROpcode.CALL,
        IROpcode.RETURN,
    ]
    assert execute_assembly(compilation.assembly) == 8


@pytest.mark.parametrize(
    "source",
    (
        (
            "record Inner:\n"
            "    left: tryte\n"
            "    right: tryte\n"
            "record Box:\n"
            "    inner: Inner\n"
            "fn make() -> Box:\n"
            "    return Box(inner=Inner(left=1, right=2))\n"
            "fn main() -> tryte:\n"
            "    return 0\n"
        ),
        (
            "record Inner:\n"
            "    left: tryte\n"
            "    right: tryte\n"
            "record Box:\n"
            "    flag: trit\n"
            "    inner: Inner\n"
            "fn main() -> Box:\n"
            "    return Box(flag=-1, inner=Inner(left=1, right=2))\n"
        ),
    ),
)
def test_nested_multi_leaf_record_returns_are_rejected_before_lowering(source: str) -> None:
    with pytest.raises(SemanticError) as captured:
        compile_source(source)

    assert "multi-field record returns require a future aggregate ABI" in str(
        captured.value
    )
    assert captured.value.diagnostic_code is DiagnosticCode.SEMANTIC_INVALID_PROGRAM


def test_nested_record_constructor_rejects_same_shape_nominal_mismatch() -> None:
    with pytest.raises(SemanticError) as captured:
        compile_source(
            "record Left:\n"
            "    value: tryte\n"
            "record Right:\n"
            "    value: tryte\n"
            "record Box:\n"
            "    left: Left\n"
            "fn main() -> tryte:\n"
            "    box: Box = Box(left=Right(value=1))\n"
            "    return 0\n"
        )

    assert "record literal 'Right' has type Right; expected Left" in str(captured.value)
