from __future__ import annotations

import pytest

from tools.s3_native_dynamic_profile import instrument_block_entries


def test_block_instrumentation_preserves_flags_and_adds_deterministic_counters() -> None:
    assembly = ".intel_syntax noprefix\n.section .text\n.L_s3_f1_f_b5_entry:\n    jne .Ldone\n.Ldone:\n    ret\n"
    labels = [".L_s3_f1_f_b5_entry", ".L_s3_f1_f_b4_done"]
    # Only labels present in this assembly are legal instrumentation targets.
    with pytest.raises(ValueError, match="absent"):
        instrument_block_entries(assembly, labels)

    instrumented, counters = instrument_block_entries(
        assembly, labels[:1]
    )
    assert counters == {labels[0]: "__s3_profile_read_0000"}
    assert (
        ".L_s3_f1_f_b5_entry:\n"
        "    pushfq\n"
        "    inc qword ptr [rip + .L__s3_profile_count_0000]\n"
        "    popfq\n"
        "    jne .Ldone\n"
    ) in instrumented
    assert ".section .bss\n.p2align 3\n.local .L__s3_profile_count_0000" in instrumented
    assert ".globl __s3_profile_read_0000" in instrumented
    assert assembly.count("pushfq") == 0


def test_block_instrumentation_rejects_duplicate_and_non_s3_labels() -> None:
    with pytest.raises(ValueError, match="unique"):
        instrument_block_entries("", [".L_s3_f1_f_b1_entry"] * 2)
    with pytest.raises(ValueError, match="unique"):
        instrument_block_entries("", ["external_label"])
