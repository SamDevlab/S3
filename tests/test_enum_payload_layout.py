from __future__ import annotations

from bootstrap.s3.lexer import SyntaxMode, tokenize
from bootstrap.s3.parser import parse_tokens
from bootstrap.s3.semantic import SemanticModel, analyze


def _semantic_model(source: str) -> SemanticModel:
    return analyze(
        parse_tokens(
            tokenize(source, mode=SyntaxMode.V0_6),
            mode=SyntaxMode.V0_6,
        )
    )


def test_enum_without_payload_keeps_scalar_tag_layout() -> None:
    model = _semantic_model(
        "enum Sign:\n"
        "    Negative\n"
        "    Zero\n"
        "    Positive\n"
        "fn main() -> tryte:\n"
        "    return 0\n"
    )

    layout = model.enum_layout("Sign")
    assert layout.cell_count == 1
    assert layout.payload_cell_count == 0
    assert layout.tag_type.value == "tryte"
    assert [variant.discriminant for variant in layout.variants] == [0, 1, 2]
    assert all(variant.payload_leaves == () for variant in layout.variants)


def test_enum_payload_layout_uses_largest_variant_width_and_source_order() -> None:
    model = _semantic_model(
        "record Inner:\n"
        "    flag: trit\n"
        "    amount: tryte\n"
        "record Outer:\n"
        "    inner: Inner\n"
        "    text: string\n"
        "enum Result:\n"
        "    Empty\n"
        "    One(value: trit)\n"
        "    Many(payload: Outer)\n"
        "    Code(code: tryte)\n"
        "fn main() -> tryte:\n"
        "    return 0\n"
    )

    layout = model.enum_layout("Result")
    assert layout.cell_count == 4
    assert layout.payload_cell_count == 3
    assert layout.inactive_slot_policy == "zero-equivalent scalar cells"
    assert [variant.name for variant in layout.variants] == [
        "Empty",
        "One",
        "Many",
        "Code",
    ]
    assert [leaf.path for leaf in layout.variant("Many").payload_leaves] == [
        ("payload", "inner", "flag"),
        ("payload", "inner", "amount"),
        ("payload", "text"),
    ]
    assert [leaf.type_name.value for leaf in layout.variant("Many").payload_leaves] == [
        "trit",
        "tryte",
        "string",
    ]


def test_enum_payload_can_contain_statically_sized_enum_payload() -> None:
    model = _semantic_model(
        "enum Inner:\n"
        "    Empty\n"
        "    Value(value: trit)\n"
        "enum Outer:\n"
        "    Wrap(inner: Inner)\n"
        "    Plain(value: tryte)\n"
        "fn main() -> tryte:\n"
        "    return 0\n"
    )

    inner = model.enum_layout("Inner")
    outer = model.enum_layout("Outer")
    assert inner.cell_count == 2
    assert outer.cell_count == 3
    assert [leaf.path for leaf in outer.variant("Wrap").payload_leaves] == [
        ("inner", "cell0"),
        ("inner", "cell1"),
    ]
    assert model.enum_payload_leaves("Outer", "Plain")[0].path == ("value",)


def test_record_payload_containing_enum_payload_uses_enum_width() -> None:
    model = _semantic_model(
        "enum Status:\n"
        "    Empty\n"
        "    Code(value: tryte)\n"
        "record Wrapper:\n"
        "    status: Status\n"
        "    flag: trit\n"
        "enum Envelope:\n"
        "    Wrap(value: Wrapper)\n"
        "fn main() -> tryte:\n"
        "    return 0\n"
    )

    assert [leaf.path for leaf in model.record_leaves("Wrapper")] == [
        ("status", "cell0"),
        ("status", "cell1"),
        ("flag",),
    ]
    assert model.enum_cell_count("Envelope") == 4
