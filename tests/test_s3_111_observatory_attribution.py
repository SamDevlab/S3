from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.s3_111_observatory_attribution import _memory_address_form


@pytest.mark.parametrize(
    ("operands", "expected"),
    [
        ("QWORD PTR [rip+0x10]", "RIP_RELATIVE"),
        ("QWORD PTR [r14+0x20]", "BASE_DISPLACEMENT"),
        ("QWORD PTR [r14+rbx]", "BASE_INDEX"),
        ("QWORD PTR [r14+rbx*8+0x8]", "BASE_INDEX_SCALE"),
        ("rax, rbx", "NO_BRACKETED_MEMORY_OPERAND"),
        ("QWORD PTR [unknown]", "ADDRESS_FORM_UNKNOWN"),
    ],
)
def test_memory_operand_shapes_are_classified_conservatively(
    operands: str, expected: str
) -> None:
    assert _memory_address_form(operands) == expected


def test_profile_join_rejects_wrong_source_identity(tmp_path: Path) -> None:
    from tools.s3_111_observatory_attribution import analyze

    profile = tmp_path / "profile.json"
    profile.write_text(json.dumps({"results": {"w": {"source_sha256": "source", "hot_blocks": []}}}))
    observatory = tmp_path / "obs.json"
    observatory.write_text(json.dumps({"provenance": {
        "git_commit": "wrong", "git_tree": "tree", "git_worktree_dirty": False,
        "workload_id": "w", "source_sha256": "source",
    }, "native_instructions": []}))
    with pytest.raises(ValueError, match="source commit"):
        analyze([observatory], profile, expected_commit="commit", expected_tree="tree")


def test_profile_join_weights_only_instruction_rows_in_profiled_blocks(
    tmp_path: Path,
) -> None:
    from tools.s3_111_observatory_attribution import analyze

    profile = tmp_path / "profile.json"
    profile.write_text(json.dumps({"results": {"w": {
        "source_sha256": "source",
        "hot_blocks": [{
            "function": "f", "block": "hot", "logical_block_executions": 4,
        }],
    }}}))
    observatory = tmp_path / "obs.json"
    observatory.write_text(json.dumps({
        "provenance": {
            "git_head": "commit", "git_tree": "tree", "git_worktree_dirty": False,
            "source_sha256": "source",
        },
        "native_instructions": [
            {
                "native_category": "MOVE", "function": "f", "assembly_block": "hot",
                "origin_status": "MAPPED", "assembly_opcodes": ["TMOV"],
                "mnemonic": "mov", "operands": "rax, rbx",
            },
            {
                "native_category": "MOVE", "function": "f", "assembly_block": "cold",
                "origin_status": "MAPPED", "assembly_opcodes": ["TMOV"],
                "mnemonic": "mov", "operands": "rax, rbx",
            },
            {
                "native_category": "CONTROL_FLOW", "function": "f", "assembly_block": "hot",
                "origin_status": "MAPPED", "assembly_opcodes": ["TBR3"],
                "mnemonic": "jne", "operands": "0x20",
            },
        ],
    }))
    result = analyze([observatory], profile, expected_commit="commit", expected_tree="tree")
    row = result["workloads"][0]
    assert row["move_provenance"]["hot_block_subset_lineage_visit_weight"] == {"TMOV": 4}
    assert row["control_provenance"]["hot_block_subset_lineage_visit_weight"] == {"TBR3": 4}
    assert row["hot_block_subset_join"]["visit_weight_by_native_category"] == {
        "CONTROL_FLOW": 4, "MOVE": 4,
    }
