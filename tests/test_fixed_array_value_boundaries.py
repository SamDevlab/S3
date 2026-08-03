from __future__ import annotations

import pytest

from bootstrap.s3 import ast
from bootstrap.s3.diagnostics import DiagnosticCode, SemanticError
from bootstrap.s3.pipeline import compile_source, run_source
from bootstrap.s3.semantic import ReturnClass, ValueLayoutKind


def test_fixed_array_layout_uses_increasing_index_paths() -> None:
    source = (
        "fn copy(values: trit[3]) -> trit[3]:\n"
        "    return values\n"
        "fn main() -> tryte:\n"
        "    return 0\n"
    )
    compilation = compile_source(source)
    type_name = compilation.ast.functions[0].return_type

    layout = compilation.semantic_model.fixed_value_layout(type_name)

    assert layout.kind is ValueLayoutKind.FIXED_ARRAY
    assert [cell.path for cell in layout.cells] == [
        ("index0",),
        ("index1",),
        ("index2",),
    ]
    assert [cell.type_name for cell in layout.cells] == [ast.TypeName.TRIT] * 3
    assert (
        compilation.semantic_model.return_classification(type_name)
        is ReturnClass.AGGREGATE_FIXED_LAYOUT
    )


@pytest.mark.parametrize("optimization", ("O0", "O1"))
def test_array_parameter_and_result_are_complete_value_groups(
    optimization: str,
) -> None:
    source = (
        "fn copy(values: tryte[3]) -> tryte[3]:\n"
        "    return values\n"
        "fn main() -> tryte:\n"
        "    input: tryte[3] = [4, 5, 6]\n"
        "    output: tryte[3] = copy(input)\n"
        "    return output[0] + output[2]\n"
    )

    assert run_source(source, optimization=optimization) == 10
    compilation = compile_source(source, optimization=optimization)
    copy = compilation.ir.functions[0]
    assert len(copy.parameters) == 3
    assert len(copy.result_types) == 3


def test_whole_array_assignment_copies_without_aliasing() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut source: tryte[2] = [1, 2]\n"
        "    mut target: tryte[2] = [0, 0]\n"
        "    target = source\n"
        "    source[0] = 9\n"
        "    return target[0] + target[1]\n"
    )

    assert run_source(source, optimization="O0") == 3
    assert run_source(source, optimization="O1") == 3


def test_record_field_and_enum_payload_share_array_layout() -> None:
    source = (
        "record Packet:\n"
        "    prefix: trit\n"
        "    bytes: tryte[3]\n"
        "enum Result:\n"
        "    Ok(bytes: tryte[3])\n"
        "    Empty\n"
        "fn inspect(result: Result) -> tryte:\n"
        "    match result:\n"
        "        Result.Ok(bytes):\n"
        "            return bytes[1]\n"
        "        Result.Empty:\n"
        "            return 0\n"
        "fn main() -> tryte:\n"
        "    values: tryte[3] = [5, 7, 9]\n"
        "    packet: Packet = Packet(prefix=-1, bytes=values)\n"
        "    result: Result = Result.Ok(bytes=packet.bytes)\n"
        "    return inspect(result) + packet.bytes[2]\n"
    )

    assert run_source(source, optimization="O0") == 16
    assert run_source(source, optimization="O1") == 16


def test_recursive_array_result_and_ignored_result_execute_once() -> None:
    source = (
        "fn descend(depth: tryte, values: tryte[2]) -> tryte[2]:\n"
        "    match depth <=> 0:\n"
        "        -1:\n"
        "            return values\n"
        "        0:\n"
        "            return values\n"
        "        1:\n"
        "            return descend(depth - 1, values)\n"
        "fn main() -> tryte:\n"
        "    values: tryte[2] = [3, 8]\n"
        "    discard descend(2, values)\n"
        "    result: tryte[2] = descend(2, values)\n"
        "    return result[1]\n"
    )

    assert run_source(source, optimization="O0") == 8
    assert run_source(source, optimization="O1") == 8


@pytest.mark.parametrize(
    "source, expected",
    (
        (
            "fn accept(values: tryte[4]) -> tryte:\n"
            "    return values[0]\n"
            "fn main() -> tryte:\n"
            "    values: tryte[5] = [1, 2, 3, 4, 5]\n"
            "    return accept(values)\n",
            r"expected tryte\[4\]",
        ),
        (
            "fn accept(values: trit[2]) -> tryte:\n"
            "    return 0\n"
            "fn main() -> tryte:\n"
            "    values: tryte[2] = [0, 1]\n"
            "    return accept(values)\n",
            r"expected trit\[2\]",
        ),
    ),
)
def test_array_boundary_type_mismatches_are_rejected(
    source: str,
    expected: str,
) -> None:
    with pytest.raises(SemanticError, match=expected):
        compile_source(source)


def test_array_result_from_main_is_rejected_even_at_width_one() -> None:
    source = (
        "fn main() -> tryte[1]:\n"
        "    values: tryte[1] = [0]\n"
        "    return values\n"
    )

    with pytest.raises(SemanticError) as error:
        compile_source(source)

    assert error.value.diagnostic_code is DiagnosticCode.SEMANTIC_INVALID_RETURN_TYPE
    assert "one scalar cell" in str(error.value)
