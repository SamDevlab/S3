from __future__ import annotations

from tools.patch_stage1_seventh_parameter_return import SOURCE, transform


def test_seventh_parameter_candidate_is_bounded_and_deterministic() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    candidate = transform(source)

    assert candidate != source
    assert transform(source) == candidate
    assert source.count("ir_function_param_count[general_parameter_scan] < 7") == 2
    assert candidate.count("ir_function_param_count[general_parameter_scan] < 7") == 0
    assert candidate.count("ir_function_param_count[general_parameter_scan] < 8") == 2
    assert candidate.count("match ordinal == 5:") == 1


def test_seventh_parameter_candidate_preserves_existing_register_lowerings() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    candidate = transform(source)

    for register_bytes in (
        "discard write_byte(100)\n            discard write_byte(105)",
        "discard write_byte(115)\n                    discard write_byte(105)",
        "discard write_byte(100)\n                            discard write_byte(120)",
        "discard write_byte(99)\n                                    discard write_byte(120)",
    ):
        assert register_bytes in candidate

    assert "discard write_byte(56)" in candidate  # r8
    assert "discard write_byte(57)" in candidate  # r9


def test_seventh_parameter_candidate_encodes_first_stack_argument() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    candidate = transform(source)

    stack_operand_bytes = (
        "discard write_byte(113)\n"  # q
        "                                                    discard write_byte(119)\n"  # w
        "                                                    discard write_byte(111)\n"  # o
        "                                                    discard write_byte(114)\n"  # r
        "                                                    discard write_byte(100)\n"  # d
        "                                                    discard write_byte(32)\n"
        "                                                    discard write_byte(112)\n"  # p
        "                                                    discard write_byte(116)\n"  # t
        "                                                    discard write_byte(114)\n"  # r
        "                                                    discard write_byte(32)\n"
        "                                                    discard write_byte(91)\n"   # [
        "                                                    discard write_byte(114)\n"  # r
        "                                                    discard write_byte(115)\n"  # s
        "                                                    discard write_byte(112)\n"  # p
        "                                                    discard write_byte(32)\n"
        "                                                    discard write_byte(43)\n"   # +
        "                                                    discard write_byte(32)\n"
        "                                                    discard write_byte(56)\n"   # 8
        "                                                    discard write_byte(93)"      # ]
    )
    assert candidate.count(stack_operand_bytes) == 2
