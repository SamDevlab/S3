from __future__ import annotations

from types import SimpleNamespace

import pytest

from bootstrap.s3.assembly import AssemblyOpcode
from bootstrap.s3.backends.x86_64.emitter import mangle_block
from tools.s3_111_hot_fallthrough_experiment import (
    _candidate_edges,
    reorder_and_remove_fallthrough_jump,
)


def test_reorder_places_target_after_source_and_removes_only_its_direct_jump() -> None:
    source_label = mangle_block("f", "source")
    target_label = mangle_block("f", "target")
    other_label = mangle_block("f", "other")
    assembly = "\n".join(
        [
            ".text",
            "f:",
            f"{target_label}:",
            "    mov rax, 1",
            "    jmp " + other_label,
            f"{source_label}:",
            "    inc rax",
            "    jmp " + target_label,
            f"{other_label}:",
            "    ret",
            ".size f, .-f",
            "",
        ]
    )

    result = reorder_and_remove_fallthrough_jump(
        assembly,
        function_name="f",
        block_labels=["target", "source", "other"],
        source_block="source",
        target_block="target",
    )

    source_index = result.index(f"{source_label}:")
    target_index = result.index(f"{target_label}:")
    assert target_index > source_index
    between = result[source_index:target_index]
    assert "inc rax" in between
    assert f"jmp {target_label}" not in between
    assert f"jmp {other_label}" in result


def test_rejects_source_block_without_the_expected_jump() -> None:
    source_label = mangle_block("f", "source")
    target_label = mangle_block("f", "target")
    assembly = "\n".join(
        [f"{source_label}:", "    ret", f"{target_label}:", "    ret", ".size f, .-f", ""]
    )

    with pytest.raises(ValueError, match="does not end in the expected jump"):
        reorder_and_remove_fallthrough_jump(
            assembly,
            function_name="f",
            block_labels=["source", "target"],
            source_block="source",
            target_block="target",
        )


def test_duplicate_labels_fail_closed() -> None:
    with pytest.raises(ValueError, match="block labels must be unique"):
        reorder_and_remove_fallthrough_jump(
            "",
            function_name="f",
            block_labels=["x", "x"],
            source_block="x",
            target_block="x",
        )


def test_hot_backedge_selector_excludes_already_adjacent_target() -> None:
    def block(label: str, opcode: AssemblyOpcode, *targets: str) -> SimpleNamespace:
        return SimpleNamespace(
            label=label,
            instructions=[SimpleNamespace(opcode=opcode, labels=tuple(targets))],
        )

    function = SimpleNamespace(
        name="f",
        external=False,
        blocks=[
            block("entry", AssemblyOpcode.TJMP, "header"),
            block("header", AssemblyOpcode.TBR3, "body", "exit_a", "exit_b"),
            block("body", AssemblyOpcode.TJMP, "header"),
            block("exit_a", AssemblyOpcode.TRET),
            block("exit_b", AssemblyOpcode.TRET),
        ],
    )
    program = SimpleNamespace(functions=[function])
    assert len(_candidate_edges("w", program, {("f", "body"): 12})) == 1

    function.blocks = [
        function.blocks[0],
        function.blocks[2],
        function.blocks[1],
        function.blocks[3],
        function.blocks[4],
    ]
    assert _candidate_edges("w", program, {("f", "body"): 12}) == []
