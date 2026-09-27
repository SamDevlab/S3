from __future__ import annotations

import hashlib

from bootstrap.s3.assembly import (
    AssemblyBlock,
    AssemblyFunction,
    AssemblyInstruction,
    AssemblyOpcode,
    AssemblyProgram,
    AssemblyType,
)
from bootstrap.s3.backends.x86_64.emitter import mangle_block
from bootstrap.s3.backends.x86_64.emitter import X8664Emitter
from bootstrap.s3.backends.x86_64.instruction_budget import InstructionBudgetMode
from bootstrap.s3.codegen_report import build_codegen_report, compare_codegen_reports
from tools.s3_source_identity import canonical_source_sha256


def _program() -> AssemblyProgram:
    function = AssemblyFunction(
        name="main",
        return_type=AssemblyType.I64,
        parameters=(),
        register_types=((0, AssemblyType.I64),),
        blocks=(
            AssemblyBlock(
                "entry",
                (
                    AssemblyInstruction(AssemblyOpcode.TCONST, (0,), immediate=7),
                    AssemblyInstruction(AssemblyOpcode.TRET, (0,)),
                ),
            ),
        ),
    )
    return AssemblyProgram((function,))


def test_codegen_report_preserves_unknown_machine_origin_and_exact_regions() -> None:
    program = _program()
    block = mangle_block("main", "entry")
    native = (
        ".text\n"
        ".globl s3_main\n"
        "s3_main:\n"
        "    push rbp\n"
        "    mov rbp, rsp\n"
        f"{block}:\n"
        "    mov rax, 7\n"
        "    jmp .Ldone\n"
        ".Ldone:\n"
        "    ret\n"
    )
    report = build_codegen_report(
        program,
        native,
        source_sha256="a" * 64,
        optimization="O1",
        max_frames=64,
        max_instructions=1000,
    )

    assert report["summary"]["assembly_instruction_count"] == 2
    assert report["summary"]["native_assembly_instruction_count"] == 5
    assert report["summary"]["native_origin_attributed_instructions"] == 0
    assert report["summary"]["native_origin_unknown_instructions"] == 5
    assert report["summary"]["machine_text_bytes"] is None
    function = report["functions"][0]
    assert function["frame_bytes"] >= 0
    assert function["native_assembly"]["stack_traffic_instructions"] == 1
    block_report = function["blocks"][0]
    assert block_report["native_assembly"]["machine_instruction_count"] == 3
    assert block_report["native_origin_category"] == "UNKNOWN_PER_INSTRUCTION"
    assert block_report["native_assembly_line_range"] is not None


def test_codegen_comparison_pins_both_source_identities_without_runtime_claim() -> None:
    program = _program()
    native = f"s3_main:\n{mangle_block('main', 'entry')}:\n    ret\n"
    control = build_codegen_report(
        program,
        native,
        source_sha256="a" * 64,
        optimization="O1",
        max_frames=64,
        max_instructions=1000,
    )
    candidate = build_codegen_report(
        program,
        native + "    nop\n",
        source_sha256="b" * 64,
        optimization="O1",
        max_frames=64,
        max_instructions=1000,
    )

    comparison = compare_codegen_reports(control, candidate)
    assert comparison["control_source_sha256"] == "a" * 64
    assert comparison["candidate_source_sha256"] == "b" * 64
    assert comparison["metrics_are_static_not_runtime"]
    assert comparison["deltas_candidate_minus_control"]["native_assembly_instruction_count"] == 1


def test_emitter_origin_sidecar_preserves_text_and_maps_assembly_operations() -> None:
    program = _program()
    def new_emitter() -> X8664Emitter:
        return X8664Emitter(
            program,
            max_frames=64,
            max_instructions=1000,
            register_allocation=True,
            instruction_budget_mode=InstructionBudgetMode.PER_INSTRUCTION,
        )

    plain = new_emitter().emit()
    mapped, origins = new_emitter().emit_with_origins()

    assert mapped == plain
    assert len(origins) == 2
    assert [item["assembly_opcodes"] for item in origins] == [["TCONST"], ["TRET"]]
    assert all(item["mapping_status"] == "MAPPED" for item in origins)

    report = build_codegen_report(
        program,
        mapped,
        native_origins=origins,
        source_sha256="c" * 64,
        optimization="O1",
        max_frames=64,
        max_instructions=1000,
    )
    summary = report["summary"]
    assert summary["native_origin_attributed_instructions"] > 0
    assert summary["native_origin_unknown_instructions"] > 0
    assert (
        summary["native_origin_attributed_instructions"]
        + summary["native_origin_unknown_instructions"]
        == summary["native_assembly_instruction_count"]
    )
    block = report["functions"][0]["blocks"][0]
    assert block["assembly_to_native_attributed_instruction_count"] > 0
    assert len(block["assembly_to_native_origin_spans"]) == 2


def test_codegen_report_rejects_stale_emitter_opcode_origin() -> None:
    program = _program()
    emitted, origins = X8664Emitter(
        program,
        max_frames=64,
        max_instructions=1000,
        register_allocation=True,
        instruction_budget_mode=InstructionBudgetMode.PER_INSTRUCTION,
    ).emit_with_origins()
    stale = [dict(item) for item in origins]
    stale[0]["assembly_opcodes"] = ["TMUL"]

    try:
        build_codegen_report(
            program,
            emitted,
            native_origins=tuple(stale),
            source_sha256="d" * 64,
            optimization="O1",
            max_frames=64,
            max_instructions=1000,
        )
    except ValueError as exc:
        assert "does not match the AssemblyProgram" in str(exc)
    else:
        raise AssertionError("stale origin mapping must fail closed")


def test_source_identity_is_stable_across_windows_and_git_line_endings() -> None:
    lf_source = b"fn main() -> i64 {\n    return 1;\n}\n"
    crlf_source = lf_source.replace(b"\n", b"\r\n")

    assert canonical_source_sha256(lf_source) == canonical_source_sha256(crlf_source)
    assert canonical_source_sha256(lf_source) == hashlib.sha256(lf_source).hexdigest()
