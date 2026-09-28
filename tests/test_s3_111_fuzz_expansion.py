from tools.s3_111_fuzz_expansion import SEEDS, run_corpus


def test_expanded_memory_transform_fuzz_and_alias_metamorphic_controls() -> None:
    result = run_corpus()

    assert result["cases_expected"] == len(SEEDS) * 2 == 100
    assert result["cases_completed"] == 100
    assert result["array_lengths_covered"] == list(range(2, 17))
    assert result["loop_limits_covered"] == list(range(9))
    assert result["metamorphic_independent_write_pairs"] == 50
    assert result["same_storage_order_controls"] == 50
    assert result["same_storage_controls_proved_order_sensitive"] == 50
    assert result["failures"] == []
    assert result["passed"] is True
