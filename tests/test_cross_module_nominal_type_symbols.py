from __future__ import annotations

import pytest

from bootstrap.s3.diagnostics import DiagnosticCode, SemanticError
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.parser import parse
from bootstrap.s3.pipeline import compile_sources


def _semantic_code(error: pytest.ExceptionInfo[SemanticError]) -> DiagnosticCode:
    return error.value.diagnostic_code


def test_parser_marks_exported_record_and_enum_declarations() -> None:
    program = parse(
        "export record Point:\n"
        "    x: tryte\n"
        "export enum Sign:\n"
        "    Positive\n"
        "fn main() -> tryte:\n"
        "    return 0\n",
        mode=SyntaxMode.V0_6,
    )

    assert program.records[0].name == "Point"
    assert program.records[0].exported is True
    assert program.enums[0].name == "Sign"
    assert program.enums[0].exported is True


def test_imported_exported_enum_type_rewrites_into_consumer_type_namespace() -> None:
    compilation = compile_sources(
        {
            "main.s3": (
                "module main\n"
                "from signs import Sign\n"
                "from signs import positive\n"
                "fn main() -> tryte:\n"
                "    value: Sign = positive()\n"
                "    match value:\n"
                "        Sign.Negative:\n"
                "            return -1\n"
                "        Sign.Positive:\n"
                "            return 1\n"
            ),
            "signs.s3": (
                "module signs\n"
                "export enum Sign:\n"
                "    Negative\n"
                "    Positive\n"
                "export fn positive() -> Sign:\n"
                "    return Sign.Positive\n"
            ),
        },
    )

    assert "__s3mod_signs__type_Sign" in compilation.semantic_model.enums


def test_imported_exported_record_type_rewrites_into_consumer_type_namespace() -> None:
    compilation = compile_sources(
        {
            "main.s3": (
                "module main\n"
                "from geometry import Point\n"
                "from geometry import make\n"
                "fn main() -> tryte:\n"
                "    point: Point = make()\n"
                "    return point.x\n"
            ),
            "geometry.s3": (
                "module geometry\n"
                "export record Point:\n"
                "    x: tryte\n"
                "export fn make() -> Point:\n"
                "    return Point(x=7)\n"
            ),
        },
    )

    assert "__s3mod_geometry__type_Point" in compilation.semantic_model.records


@pytest.mark.parametrize(
    ("main_source", "library_source", "message", "code"),
    (
        (
            "module main\n"
            "from signs import Sign\n"
            "fn main() -> tryte:\n"
            "    return 0\n",
            "module signs\n"
            "enum Sign:\n"
            "    Positive\n"
            "export fn marker() -> tryte:\n"
            "    return 0\n",
            "type 'Sign' in module 'signs' is private",
            DiagnosticCode.IMPORT_PRIVATE_SYMBOL,
        ),
        (
            "module main\n"
            "from signs import Missing\n"
            "fn main() -> tryte:\n"
            "    return 0\n",
            "module signs\n"
            "export enum Sign:\n"
            "    Positive\n"
            "export fn marker() -> tryte:\n"
            "    return 0\n",
            "module 'signs' does not export unknown symbol 'Missing'",
            DiagnosticCode.IMPORT_UNKNOWN_SYMBOL,
        ),
        (
            "module main\n"
            "from signs import Sign as Other\n"
            "fn main() -> tryte:\n"
            "    return 0\n",
            "module signs\n"
            "export enum Sign:\n"
            "    Positive\n"
            "export fn marker() -> tryte:\n"
            "    return 0\n",
            "type import aliases are not supported yet",
            DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
        ),
        (
            "module main\n"
            "from geometry import Point\n"
            "record Point:\n"
            "    x: tryte\n"
            "fn main() -> tryte:\n"
            "    return 0\n",
            "module geometry\n"
            "export record Point:\n"
            "    x: tryte\n"
            "export fn marker() -> tryte:\n"
            "    return 0\n",
            "import local name 'Point' conflicts with type in module 'main'",
            DiagnosticCode.IMPORT_CONFLICT,
        ),
        (
            "module main\n"
            "from both import Item\n"
            "fn main() -> tryte:\n"
            "    return 0\n",
            "module both\n"
            "export record Item:\n"
            "    x: tryte\n"
            "export fn Item() -> tryte:\n"
            "    return 0\n",
            "imported symbol 'Item' in module 'both' is ambiguous between function and type",
            DiagnosticCode.IMPORT_CONFLICT,
        ),
    ),
)
def test_imported_nominal_type_symbol_diagnostics(
    main_source: str,
    library_source: str,
    message: str,
    code: DiagnosticCode,
) -> None:
    with pytest.raises(SemanticError) as error:
        compile_sources({"main.s3": main_source, "library.s3": library_source})

    assert message in str(error.value)
    assert _semantic_code(error) is code


def test_private_qualified_enum_type_member_is_rejected() -> None:
    with pytest.raises(SemanticError) as error:
        compile_sources(
            {
                "main.s3": (
                    "module main\n"
                    "from signs import marker\n"
                    "fn main() -> tryte:\n"
                    "    return signs.Sign.Positive\n"
                ),
                "signs.s3": (
                    "module signs\n"
                    "enum Sign:\n"
                    "    Positive\n"
                    "export fn marker() -> tryte:\n"
                    "    return 0\n"
                ),
            },
        )

    assert "type 'Sign' in module 'signs' is private" in str(error.value)
    assert _semantic_code(error) is DiagnosticCode.IMPORT_PRIVATE_SYMBOL
