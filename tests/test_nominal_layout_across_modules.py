from __future__ import annotations

import pytest

from bootstrap.s3.assembly import AssemblyType
from bootstrap.s3.diagnostics import SemanticError
from bootstrap.s3.ir import IRType
from bootstrap.s3.optimizer import OptimizationLevel
from bootstrap.s3.pipeline import compile_sources
from bootstrap.s3.backends._hosted_execution import _execute_hosted_assembly


def _run_sources(
    sources: dict[str, str] | tuple[tuple[str, str], ...],
    optimization: OptimizationLevel,
) -> int:
    compilation = compile_sources(sources, optimization=optimization)
    return _execute_hosted_assembly(compilation.assembly, "main")


def test_imported_multifield_record_parameters_preserve_declared_field_order() -> None:
    sources = {
        "main.s3": (
            "module main\n"
            "from model import Packet\n"
            "from model import Sign\n"
            "from hop import relay\n"
            "fn main() -> tryte:\n"
            "    packet: Packet = Packet(zeta=5, flag=-1, sign=Sign.Positive)\n"
            "    return relay(packet)\n"
        ),
        "model.s3": (
            "module model\n"
            "export enum Sign:\n"
            "    Negative\n"
            "    Positive\n"
            "export record Packet:\n"
            "    zeta: tryte\n"
            "    flag: trit\n"
            "    sign: Sign\n"
            "export fn marker() -> tryte:\n"
            "    return 0\n"
        ),
        "hop.s3": (
            "module hop\n"
            "from model import Packet\n"
            "from model import Sign\n"
            "from sink import score\n"
            "export fn relay(packet: Packet) -> tryte:\n"
            "    return score(packet)\n"
        ),
        "sink.s3": (
            "module sink\n"
            "from model import Packet\n"
            "from model import Sign\n"
            "export fn score(packet: Packet) -> tryte:\n"
            "    match packet.sign:\n"
            "        Sign.Negative:\n"
            "            return 0\n"
            "        Sign.Positive:\n"
            "            return packet.zeta\n"
        ),
    }

    compilation = compile_sources(sources)
    score = next(
        function
        for function in compilation.ir.functions
        if function.name == "__s3mod_sink__score"
    )

    assert [parameter.name for parameter in score.parameters] == [
        "packet__zeta",
        "packet__flag",
        "packet__sign",
    ]
    assert [parameter.type for parameter in score.parameters] == [
        IRType.TRYTE,
        IRType.TRIT,
        IRType.TRYTE,
    ]
    assembly_score = next(
        function
        for function in compilation.assembly.functions
        if function.name == "__s3mod_sink__score"
    )
    assert [parameter.type for parameter in assembly_score.parameters] == [
        AssemblyType.TRYTE,
        AssemblyType.TRIT,
        AssemblyType.TRYTE,
    ]
    assert _execute_hosted_assembly(compilation.assembly, "main") == 5
    assert _run_sources(sources, OptimizationLevel.O1) == 5


def test_imported_nominal_layout_is_deterministic_across_source_order() -> None:
    ordered = (
        (
            "main.s3",
            "module main\n"
            "from geometry import Point\n"
            "from consumer import x_of\n"
            "fn main() -> tryte:\n"
            "    point: Point = Point(later=9, early=-1)\n"
            "    return x_of(point)\n",
        ),
        (
            "geometry.s3",
            "module geometry\n"
            "export record Point:\n"
            "    later: tryte\n"
            "    early: trit\n"
            "export fn marker() -> tryte:\n"
            "    return 0\n",
        ),
        (
            "consumer.s3",
            "module consumer\n"
            "from geometry import Point\n"
            "export fn x_of(point: Point) -> tryte:\n"
            "    return point.later\n",
        ),
    )
    reversed_order = tuple(reversed(ordered))

    first = compile_sources(ordered, OptimizationLevel.O1)
    second = compile_sources(reversed_order, OptimizationLevel.O1)

    assert first.ir.to_dict() == second.ir.to_dict()
    assert first.assembly.render() == second.assembly.render()
    assert _execute_hosted_assembly(first.assembly, "main") == 9
    assert _execute_hosted_assembly(second.assembly, "main") == 9


def test_imported_enum_discriminants_are_owned_by_defining_module_order() -> None:
    sources = {
        "main.s3": (
            "module main\n"
            "from signs import Sign\n"
            "from signs import middle\n"
            "fn main() -> tryte:\n"
            "    value: Sign = middle()\n"
            "    match value:\n"
            "        Sign.Last:\n"
            "            return 2\n"
            "        Sign.First:\n"
            "            return 0\n"
            "        Sign.Middle:\n"
            "            return 1\n"
        ),
        "signs.s3": (
            "module signs\n"
            "export enum Sign:\n"
            "    Last\n"
            "    First\n"
            "    Middle\n"
            "export fn middle() -> Sign:\n"
            "    return Sign.Middle\n"
        ),
    }

    compilation = compile_sources(sources)
    enum = compilation.semantic_model.enum("__s3mod_signs__type_Sign")

    assert enum.discriminant("Last") == 0
    assert enum.discriminant("First") == 1
    assert enum.discriminant("Middle") == 2
    assert _execute_hosted_assembly(compilation.assembly, "main") == 1
    assert _run_sources(sources, OptimizationLevel.O1) == 1


def test_same_shape_imported_records_from_different_modules_keep_distinct_identity() -> None:
    with pytest.raises(SemanticError) as error:
        compile_sources(
            {
                "main.s3": (
                    "module main\n"
                    "from left import Point\n"
                    "from left import make\n"
                    "from right import consume\n"
                    "fn main() -> tryte:\n"
                    "    point: Point = make()\n"
                    "    return consume(point)\n"
                ),
                "left.s3": (
                    "module left\n"
                    "export record Point:\n"
                    "    value: tryte\n"
                    "export fn make() -> Point:\n"
                    "    return Point(value=3)\n"
                ),
                "right.s3": (
                    "module right\n"
                    "export record Point:\n"
                    "    value: tryte\n"
                    "export fn consume(point: Point) -> tryte:\n"
                    "    return point.value\n"
                ),
            },
        )

    assert "__s3mod_left__type_Point" in str(error.value)
    assert "__s3mod_right__type_Point" in str(error.value)


def test_imported_multifield_record_return_remains_blocked_by_aggregate_abi() -> None:
    with pytest.raises(SemanticError) as error:
        compile_sources(
            {
                "main.s3": (
                    "module main\n"
                    "from geometry import Pair\n"
                    "from geometry import make\n"
                    "fn main() -> tryte:\n"
                    "    pair: Pair = make()\n"
                    "    return pair.left\n"
                ),
                "geometry.s3": (
                    "module geometry\n"
                    "export record Pair:\n"
                    "    left: tryte\n"
                    "    right: tryte\n"
                    "export fn make() -> Pair:\n"
                    "    return Pair(left=1, right=2)\n"
                ),
            },
        )

    assert "multi-field record returns require a future aggregate ABI" in str(error.value)


def test_nominal_type_text_does_not_escape_to_runtime_ir_or_assembly() -> None:
    compilation = compile_sources(
        {
            "main.s3": (
                "module main\n"
                "from geometry import Point\n"
                "from geometry import make\n"
                "fn main() -> tryte:\n"
                "    point: geometry.Point = make()\n"
                "    return point.x\n"
            ),
            "geometry.s3": (
                "module geometry\n"
                "export record Point:\n"
                "    x: tryte\n"
                "export fn make() -> Point:\n"
                "    return Point(x=4)\n"
            ),
        },
    )

    assert "geometry.Point" not in repr(compilation.ir.to_dict())
    assert "geometry.Point" not in compilation.assembly.render()
    assert _execute_hosted_assembly(compilation.assembly, "main") == 4
