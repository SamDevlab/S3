from __future__ import annotations

import pytest

from bootstrap.s3.diagnostics import DiagnosticCode, SemanticError
from bootstrap.s3.lexer import SyntaxMode, tokenize
from bootstrap.s3.module_compilation import prepare_module_compilation
from bootstrap.s3.parser import parse_tokens
from bootstrap.s3.semantic import analyze


def _assert_semantic_rejection(source: str, message: str) -> None:
    with pytest.raises(SemanticError) as error:
        analyze(
            parse_tokens(
                tokenize(source, mode=SyntaxMode.V0_6),
                mode=SyntaxMode.V0_6,
            )
        )

    assert error.value.message == message


def test_direct_enum_payload_cycle_is_rejected_before_layout_recursion() -> None:
    _assert_semantic_rejection(
        "enum Node:\n"
        "    Next(value: Node)\n"
        "fn main() -> tryte:\n"
        "    return 0\n",
        "recursive enum payload layout cycle: Node -> Node",
    )


def test_indirect_enum_payload_cycle_through_record_is_rejected() -> None:
    _assert_semantic_rejection(
        "record Box:\n"
        "    value: Node\n"
        "enum Node:\n"
        "    Next(box: Box)\n"
        "fn main() -> tryte:\n"
        "    return 0\n",
        "recursive enum payload layout cycle: Node -> Node",
    )


def test_indirect_enum_payload_cycle_between_enums_is_rejected() -> None:
    _assert_semantic_rejection(
        "enum Left:\n"
        "    Wrap(value: Right)\n"
        "enum Right:\n"
        "    Wrap(value: Left)\n"
        "fn main() -> tryte:\n"
        "    return 0\n",
        "recursive enum payload layout cycle: Left -> Right -> Left",
    )


def test_cross_module_enum_payload_cycle_is_rejected_by_module_graph_first() -> None:
    with pytest.raises(SemanticError) as error:
        prepare_module_compilation(
            {
                "main.s3": (
                    "module main\n"
                    "from left import Left\n"
                    "from right import Right\n"
                    "fn main() -> tryte:\n"
                    "    return 0\n"
                ),
                "left.s3": (
                    "module left\n"
                    "from right import Right\n"
                    "export enum Left:\n"
                    "    Wrap(value: Right)\n"
                    "export fn marker() -> tryte:\n"
                    "    return 0\n"
                ),
                "right.s3": (
                    "module right\n"
                    "from left import Left\n"
                    "export enum Right:\n"
                    "    Wrap(value: Left)\n"
                    "export fn marker() -> tryte:\n"
                    "    return 0\n"
                ),
            }
        )

    assert error.value.diagnostic_code is DiagnosticCode.MODULE_CYCLE
    assert error.value.message == "module import cycle: left -> right -> left"
