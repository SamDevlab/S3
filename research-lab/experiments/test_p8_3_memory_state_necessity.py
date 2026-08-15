from p8_3_memory_state_necessity import (
    classify_register_check,
    classify_register_mark,
    controls,
)


def test_register_check_negative_controls_are_conservative():
    assert classify_register_check(False, False, False, False) == "NECESSARY"
    assert classify_register_check(True, True, False, False) == "NECESSARY"
    assert classify_register_check(True, False, True, False) == "UNKNOWN"
    assert classify_register_check(True, False, False, True) == "UNKNOWN"


def test_register_mark_negative_and_positive_controls():
    assert classify_register_mark(False, False, False, False) == "CONDITIONALLY_NECESSARY"
    assert classify_register_mark(True, True, False, False) == "CONDITIONALLY_NECESSARY"
    assert classify_register_mark(True, False, True, False) == "UNKNOWN"
    assert classify_register_mark(True, False, False, False) == "PROVABLY_ACCIDENTAL"


def test_control_catalog_records_required_boundary_cases():
    result = controls()
    assert result["negative_controls_pass"] is True
    assert result["positive_controls_pass"] is True
    assert result["read_before_overwrite"] == "NECESSARY"
    assert result["unknown_alias_or_loop"] == "UNKNOWN"
