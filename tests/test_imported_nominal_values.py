from __future__ import annotations

import pytest

from bootstrap.s3.diagnostics import DiagnosticCode, SemanticError
from bootstrap.s3.optimizer import OptimizationLevel
from bootstrap.s3.pipeline import compile_sources
from bootstrap.s3.backends._hosted_execution import _execute_hosted_assembly


def _run_sources(
    sources: dict[str, str],
    optimization: OptimizationLevel,
) -> int:
    compilation = compile_sources(sources, optimization=optimization)
    return _execute_hosted_assembly(compilation.assembly, "main")


def test_imported_record_value_flows_through_local_variable_parameter_return_and_field_access() -> None:
    sources = {
        "main.s3": (
            "module main\n"
            "from geometry import Point\n"
            "from geometry import make\n"
            "from consumer import x_of\n"
            "fn main() -> tryte:\n"
            "    point: Point = make()\n"
            "    return x_of(point)\n"
        ),
        "geometry.s3": (
            "module geometry\n"
            "export record Point:\n"
            "    x: tryte\n"
            "export fn make() -> Point:\n"
            "    return Point(x=7)\n"
        ),
        "consumer.s3": (
            "module consumer\n"
            "from geometry import Point\n"
            "export fn x_of(point: Point) -> tryte:\n"
            "    return point.x\n"
        ),
    }

    assert _run_sources(sources, OptimizationLevel.O0) == 7
    assert _run_sources(sources, OptimizationLevel.O1) == 7


def test_module_qualified_record_constructor_and_type_annotation_preserve_origin_identity() -> None:
    sources = {
        "main.s3": (
            "module main\n"
            "from geometry import make\n"
            "fn main() -> tryte:\n"
            "    point: geometry.Point = geometry.Point(x=5)\n"
            "    return point.x\n"
        ),
        "geometry.s3": (
            "module geometry\n"
            "export record Point:\n"
            "    x: tryte\n"
            "export fn make() -> Point:\n"
            "    return Point(x=1)\n"
        ),
    }

    compilation = compile_sources(sources)

    assert "__s3mod_geometry__type_Point" in compilation.semantic_model.records
    assert _execute_hosted_assembly(compilation.assembly, "main") == 5


def test_imported_enum_value_flows_through_variable_parameter_return_variant_and_match() -> None:
    sources = {
        "main.s3": (
            "module main\n"
            "from signs import Sign\n"
            "from signs import positive\n"
            "from consumer import score\n"
            "fn main() -> tryte:\n"
            "    value: Sign = positive()\n"
            "    return score(value)\n"
        ),
        "signs.s3": (
            "module signs\n"
            "export enum Sign:\n"
            "    Negative\n"
            "    Zero\n"
            "    Positive\n"
            "export fn positive() -> Sign:\n"
            "    return Sign.Positive\n"
        ),
        "consumer.s3": (
            "module consumer\n"
            "from signs import Sign\n"
            "export fn score(value: Sign) -> tryte:\n"
            "    match value:\n"
            "        Sign.Negative:\n"
            "            return -1\n"
            "        Sign.Zero:\n"
            "            return 0\n"
            "        Sign.Positive:\n"
            "            return 1\n"
        ),
    }

    assert _run_sources(sources, OptimizationLevel.O0) == 1
    assert _run_sources(sources, OptimizationLevel.O1) == 1


def test_imported_record_fields_cover_trit_tryte_and_enum_values() -> None:
    sources = {
        "main.s3": (
            "module main\n"
            "from model import Flag\n"
            "from model import Sign\n"
            "from consumer import score\n"
            "fn main() -> tryte:\n"
            "    flag: Flag = Flag(active=-1, amount=8, sign=Sign.Positive)\n"
            "    return score(flag)\n"
        ),
        "model.s3": (
            "module model\n"
            "export enum Sign:\n"
            "    Negative\n"
            "    Positive\n"
            "export record Flag:\n"
            "    active: trit\n"
            "    amount: tryte\n"
            "    sign: Sign\n"
            "export fn marker() -> tryte:\n"
            "    return 0\n"
        ),
        "consumer.s3": (
            "module consumer\n"
            "from model import Flag\n"
            "from model import Sign\n"
            "export fn score(flag: Flag) -> tryte:\n"
            "    match flag.sign:\n"
            "        Sign.Negative:\n"
            "            return 0\n"
            "        Sign.Positive:\n"
            "            return flag.amount\n"
        ),
    }

    assert _run_sources(sources, OptimizationLevel.O0) == 8
    assert _run_sources(sources, OptimizationLevel.O1) == 8


def test_module_qualified_enum_annotation_and_variant_preserve_origin_identity() -> None:
    compilation = compile_sources(
        {
            "main.s3": (
                "module main\n"
                "from signs import marker\n"
                "fn main() -> tryte:\n"
                "    value: signs.Sign = signs.Sign.Positive\n"
                "    match value:\n"
                "        signs.Sign.Negative:\n"
                "            return -1\n"
                "        signs.Sign.Positive:\n"
                "            return 1\n"
            ),
            "signs.s3": (
                "module signs\n"
                "export enum Sign:\n"
                "    Negative\n"
                "    Positive\n"
                "export fn marker() -> tryte:\n"
                "    return 0\n"
            ),
        },
    )

    assert "__s3mod_signs__type_Sign" in compilation.semantic_model.enums
    assert _execute_hosted_assembly(compilation.assembly, "main") == 1


def test_same_name_imported_records_from_different_modules_are_not_interchangeable() -> None:
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
                    "    x: tryte\n"
                    "export fn make() -> Point:\n"
                    "    return Point(x=1)\n"
                ),
                "right.s3": (
                    "module right\n"
                    "export record Point:\n"
                    "    x: tryte\n"
                    "export fn consume(point: Point) -> tryte:\n"
                    "    return point.x\n"
                ),
            },
        )

    assert "has type __s3mod_left__type_Point" in str(error.value)
    assert "expected __s3mod_right__type_Point" in str(error.value)
    assert error.value.diagnostic_code is DiagnosticCode.SEMANTIC_TYPE_MISMATCH


def test_imported_record_field_remains_rejected_until_nested_records() -> None:
    with pytest.raises(SemanticError) as error:
        compile_sources(
            {
                "main.s3": (
                    "module main\n"
                    "from geometry import Point\n"
                    "record Box:\n"
                    "    point: Point\n"
                    "fn main() -> tryte:\n"
                    "    return 0\n"
                ),
                "geometry.s3": (
                    "module geometry\n"
                    "export record Point:\n"
                    "    x: tryte\n"
                    "export fn marker() -> tryte:\n"
                    "    return 0\n"
                ),
            },
        )

    assert "nested record fields are not supported yet" in str(error.value)


def test_private_qualified_record_constructor_is_rejected() -> None:
    with pytest.raises(SemanticError) as error:
        compile_sources(
            {
                "main.s3": (
                    "module main\n"
                    "from geometry import marker\n"
                    "fn main() -> tryte:\n"
                    "    point: geometry.Point = geometry.Point(x=5)\n"
                    "    return point.x\n"
                ),
                "geometry.s3": (
                    "module geometry\n"
                    "record Point:\n"
                    "    x: tryte\n"
                    "export fn marker() -> tryte:\n"
                    "    return 0\n"
                ),
            },
        )

    assert "type 'Point' in module 'geometry' is private" in str(error.value)
    assert error.value.diagnostic_code is DiagnosticCode.IMPORT_PRIVATE_SYMBOL
