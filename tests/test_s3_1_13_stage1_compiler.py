from __future__ import annotations

from dataclasses import replace
import hashlib
import platform
from pathlib import Path

import pytest

from bootstrap.s3 import run_source
from bootstrap.s3.assembly import parse_assembly
from bootstrap.s3.backends.x86_64 import (
    NativeBackendError,
    NativeToolchain,
    generate_native_assembly,
)
from bootstrap.s3.diagnostics import S3Error
from bootstrap.s3.emulator import Emulator
from bootstrap.s3.ir_emulator import execute_ir
from bootstrap.s3.pipeline import compile_sources


_STAGE1_MODULES = (
    "selfhost/substrate/generic_lexer_state.s3",
    "selfhost/substrate/verifier_kernel.s3",
    "selfhost/substrate/output_sink.s3",
    "selfhost/compiler/stage1_compiler_v1.s3",
)


def _stage1_artifact(
    source: str,
    *,
    compiler_version: str = "v1",
    diagnostics: list[int] | None = None,
) -> bytes:
    repository = Path(__file__).parents[1]
    compiler_module = f"stage1_compiler_{compiler_version}"
    module_paths = (
        *_STAGE1_MODULES[:-1],
        f"selfhost/compiler/{compiler_module}.s3",
    )
    modules = {
        path: (repository / path).read_text(encoding="utf-8")
        for path in module_paths
    }
    source_bytes = source.encode("ascii")
    main_lines = [
        "module main",
        f"from selfhost.compiler.{compiler_module} import Stage1CompileResult",
        f"from selfhost.compiler.{compiler_module} import stage1_compile",
        "fn main() -> vector<i64>:",
        f"    mut source: vector<i64> = vector_new<i64>({len(source_bytes)})",
    ]
    main_lines.extend(
        f"    discard vector_push<i64>(&mut source, {byte})"
        for byte in source_bytes
    )
    main_lines.extend(
        (
            "    mut result: Stage1CompileResult = stage1_compile(source)",
            "    mut envelope: vector<i64> = vector_new<i64>(result.output_length + 4)",
            "    discard vector_push<i64>(&mut envelope, result.status)",
            "    discard vector_push<i64>(&mut envelope, result.phase)",
            "    discard vector_push<i64>(&mut envelope, result.error_code)",
            "    discard vector_push<i64>(&mut envelope, result.output_length)",
            "    mut output_index: i64 = 0",
            "    while output_index < result.output_length:",
            "        discard vector_push<i64>(&mut envelope, vector_get<i64>(&result.output, output_index))",
            "        output_index = output_index + 1",
            "    return envelope",
        )
    )
    modules["main.s3"] = "\n".join(main_lines) + "\n"

    stage0 = compile_sources(modules, entry_module="main")
    output = execute_ir(stage0.ir)
    envelope = tuple(int(output[index]) for index in range(output.length))
    status, phase, error_code, output_length = envelope[:4]
    if diagnostics is not None:
        diagnostics.extend(envelope[:4])
    if status == 0:
        assert output_length == 0, f"failed Stage1 compilation emitted {output_length} bytes"
        return b""
    assert status == 1, f"Stage1 compilation failed: phase={phase}, error_code={error_code}"
    return bytes(envelope[4 : 4 + output_length])


def _stage1_v2_emit_three_way_cfg() -> bytes:
    repository = Path(__file__).parents[1]
    modules = {
        path: (repository / path).read_text(encoding="utf-8")
        for path in (
            "selfhost/substrate/generic_lexer_state.s3",
            "selfhost/substrate/verifier_kernel.s3",
            "selfhost/substrate/output_sink.s3",
            "selfhost/compiler/stage1_compiler_v2.s3",
        )
    }
    modules["main.s3"] = r"""
module main
from selfhost.substrate.verifier_kernel import NativeIR
from selfhost.substrate.verifier_kernel import NativeIRAppendResult
from selfhost.substrate.verifier_kernel import NativeIRVerifiedResult
from selfhost.substrate.verifier_kernel import native_ir_empty
from selfhost.substrate.verifier_kernel import native_ir_append_function_source
from selfhost.substrate.verifier_kernel import native_ir_set_function_result_type
from selfhost.substrate.verifier_kernel import native_ir_append_block_for_function
from selfhost.substrate.verifier_kernel import native_ir_append_typed_instruction_for_function
from selfhost.substrate.verifier_kernel import native_ir_append_branch_for_function
from selfhost.substrate.verifier_kernel import native_ir_append_instruction_for_function
from selfhost.substrate.verifier_kernel import native_ir_append_jump_for_function
from selfhost.substrate.verifier_kernel import native_ir_append_memory
from selfhost.substrate.verifier_kernel import native_ir_append_load_for_function
from selfhost.substrate.verifier_kernel import native_ir_append_store_for_function
from selfhost.substrate.verifier_kernel import verify_program
from selfhost.compiler.stage1_compiler_v2 import stage1_emit_verified_native_program

fn append_i64(program: NativeIR, block_id: i64, value: i64) -> NativeIRAppendResult:
    return native_ir_append_typed_instruction_for_function(
        program, 0, block_id, 0, value, -1, -1, 0
    )

fn append_return(program: NativeIR, block_id: i64, value_id: i64) -> NativeIR:
    mut returned: NativeIRAppendResult = native_ir_append_instruction_for_function(
        program, 0, block_id, 1, 0, value_id, -1, -1
    )
    return returned.program

fn append_store_then_jump(
    program: NativeIR, block_id: i64, value_id: i64
) -> NativeIR:
    mut index: NativeIRAppendResult = append_i64(program, block_id, 0)
    mut index_id: i64 = index.value_id
    mut stored: NativeIRAppendResult = native_ir_append_store_for_function(
        index.program, 0, block_id, 0, index_id, value_id
    )
    mut jumped: NativeIRAppendResult = native_ir_append_jump_for_function(
        stored.program, 0, block_id, 4
    )
    return jumped.program

fn main() -> vector<i64>:
    mut name: vector<i64> = vector_new<i64>(4)
    discard vector_push<i64>(&mut name, 109)
    discard vector_push<i64>(&mut name, 97)
    discard vector_push<i64>(&mut name, 105)
    discard vector_push<i64>(&mut name, 110)
    mut program: NativeIR = native_ir_empty()
    mut function: NativeIRAppendResult = native_ir_append_function_source(
        program, 0, 1, &name, 0, 4
    )
    program = function.program
    mut result_type: NativeIRAppendResult = native_ir_set_function_result_type(
        program, 0, 0
    )
    program = result_type.program
    mut memory: NativeIRAppendResult = native_ir_append_memory(
        program, 0, 0, 1
    )
    program = memory.program
    mut entry: NativeIRAppendResult = native_ir_append_block_for_function(
        program, 0, 0, 2
    )
    program = entry.program
    mut negative: NativeIRAppendResult = native_ir_append_block_for_function(
        program, 0, 1, 3
    )
    program = negative.program
    mut neutral: NativeIRAppendResult = native_ir_append_block_for_function(
        program, 0, 2, 3
    )
    program = neutral.program
    mut positive: NativeIRAppendResult = native_ir_append_block_for_function(
        program, 0, 3, 3
    )
    program = positive.program
    mut join: NativeIRAppendResult = native_ir_append_block_for_function(
        program, 0, 4, 1
    )
    program = join.program
    mut left: NativeIRAppendResult = append_i64(program, 0, 1)
    mut left_id: i64 = left.value_id
    program = left.program
    mut right: NativeIRAppendResult = append_i64(program, 0, 2)
    mut right_id: i64 = right.value_id
    program = right.program
    mut condition: NativeIRAppendResult = native_ir_append_typed_instruction_for_function(
        program, 0, 0, 11, 2, left_id, right_id, 1
    )
    mut condition_id: i64 = condition.value_id
    program = condition.program
    mut branch: NativeIRAppendResult = native_ir_append_branch_for_function(
        program, 0, 0, condition_id, 1, 2, 3
    )
    program = branch.program
    mut negative_value: NativeIRAppendResult = append_i64(program, 1, 11)
    mut negative_id: i64 = negative_value.value_id
    program = append_store_then_jump(negative_value.program, 1, negative_id)
    mut neutral_value: NativeIRAppendResult = append_i64(program, 2, 22)
    mut neutral_id: i64 = neutral_value.value_id
    program = append_store_then_jump(neutral_value.program, 2, neutral_id)
    mut positive_value: NativeIRAppendResult = append_i64(program, 3, 33)
    mut positive_id: i64 = positive_value.value_id
    program = append_store_then_jump(positive_value.program, 3, positive_id)
    mut load_index: NativeIRAppendResult = append_i64(program, 4, 0)
    mut load_index_id: i64 = load_index.value_id
    mut loaded: NativeIRAppendResult = native_ir_append_load_for_function(
        load_index.program, 0, 4, 0, load_index_id
    )
    mut loaded_id: i64 = loaded.value_id
    program = append_return(loaded.program, 4, loaded_id)
    mut output: vector<i64> = vector_new<i64>(16384)
    mut verified: NativeIRVerifiedResult = verify_program(program)
    mut diagnostics: vector<i64> = vector_new<i64>(5)
    discard vector_push<i64>(&mut diagnostics, 0)
    discard vector_push<i64>(&mut diagnostics, verified.verification.accepted)
    discard vector_push<i64>(&mut diagnostics, verified.verification.diagnostic_code)
    discard vector_push<i64>(&mut diagnostics, verified.verification.digest_before)
    discard vector_push<i64>(&mut diagnostics, verified.verification.digest_after)
    match verified.verification.accepted == 1:
        -1:
            match stage1_emit_verified_native_program(verified.program, &mut output) == 1:
                -1:
                    return output
                0:
                    return diagnostics
                1:
                    return diagnostics
        0:
            return diagnostics
        1:
            return diagnostics
"""
    stage0 = compile_sources(modules, entry_module="main")
    output = execute_ir(stage0.ir)
    first = int(output[0]) if output.length else -1
    if first != 46:
        diagnostic = tuple(int(output[index]) for index in range(output.length))
        raise AssertionError(f"Stage1 V2 CFG/memory diagnostic envelope: {diagnostic}")
    return bytes(int(output[index]) for index in range(output.length))


def _stage1_v2_emit_loop_carried_memory_cfg() -> bytes:
    repository = Path(__file__).parents[1]
    modules = {
        path: (repository / path).read_text(encoding="utf-8")
        for path in (
            "selfhost/substrate/generic_lexer_state.s3",
            "selfhost/substrate/verifier_kernel.s3",
            "selfhost/substrate/output_sink.s3",
            "selfhost/compiler/stage1_compiler_v2.s3",
        )
    }
    modules["main.s3"] = r"""
module main
from selfhost.substrate.verifier_kernel import NativeIR
from selfhost.substrate.verifier_kernel import NativeIRAppendResult
from selfhost.substrate.verifier_kernel import native_ir_empty
from selfhost.substrate.verifier_kernel import native_ir_append_function_source
from selfhost.substrate.verifier_kernel import native_ir_set_function_result_type
from selfhost.substrate.verifier_kernel import native_ir_append_block_for_function
from selfhost.substrate.verifier_kernel import native_ir_append_typed_instruction_for_function
from selfhost.substrate.verifier_kernel import native_ir_append_instruction_for_function
from selfhost.substrate.verifier_kernel import native_ir_append_branch_for_function
from selfhost.substrate.verifier_kernel import native_ir_append_jump_for_function
from selfhost.substrate.verifier_kernel import native_ir_append_memory
from selfhost.substrate.verifier_kernel import native_ir_append_load_for_function
from selfhost.substrate.verifier_kernel import native_ir_append_store_for_function
from selfhost.compiler.stage1_compiler_v2 import stage1_emit_verified_native_program

fn append_i64(program: NativeIR, block_id: i64, value: i64) -> NativeIRAppendResult:
    return native_ir_append_typed_instruction_for_function(
        program, 0, block_id, 0, value, -1, -1, 0
    )

fn append_load(program: NativeIR, block_id: i64, index_id: i64) -> NativeIRAppendResult:
    return native_ir_append_load_for_function(program, 0, block_id, 0, index_id)

fn append_store(
    program: NativeIR, block_id: i64, index_id: i64, value_id: i64
) -> NativeIR:
    mut stored: NativeIRAppendResult = native_ir_append_store_for_function(
        program, 0, block_id, 0, index_id, value_id
    )
    return stored.program

fn main() -> vector<i64>:
    mut name: vector<i64> = vector_new<i64>(4)
    discard vector_push<i64>(&mut name, 109)
    discard vector_push<i64>(&mut name, 97)
    discard vector_push<i64>(&mut name, 105)
    discard vector_push<i64>(&mut name, 110)
    mut program: NativeIR = native_ir_empty()
    mut function: NativeIRAppendResult = native_ir_append_function_source(
        program, 0, 1, &name, 0, 4
    )
    program = function.program
    mut result_type: NativeIRAppendResult = native_ir_set_function_result_type(
        program, 0, 0
    )
    program = result_type.program
    mut memory: NativeIRAppendResult = native_ir_append_memory(program, 0, 0, 1)
    program = memory.program
    mut entry: NativeIRAppendResult = native_ir_append_block_for_function(
        program, 0, 0, 3
    )
    program = entry.program
    mut header: NativeIRAppendResult = native_ir_append_block_for_function(
        program, 0, 1, 2
    )
    program = header.program
    mut body: NativeIRAppendResult = native_ir_append_block_for_function(
        program, 0, 2, 3
    )
    program = body.program
    mut exit_block: NativeIRAppendResult = native_ir_append_block_for_function(
        program, 0, 3, 1
    )
    program = exit_block.program
    mut neutral_exit: NativeIRAppendResult = native_ir_append_block_for_function(
        program, 0, 4, 3
    )
    program = neutral_exit.program

    mut entry_index: NativeIRAppendResult = append_i64(program, 0, 0)
    mut entry_index_id: i64 = entry_index.value_id
    program = entry_index.program
    mut initial: NativeIRAppendResult = append_i64(program, 0, 0)
    mut initial_id: i64 = initial.value_id
    program = append_store(initial.program, 0, entry_index_id, initial_id)
    mut enter_loop: NativeIRAppendResult = native_ir_append_jump_for_function(
        program, 0, 0, 1
    )
    program = enter_loop.program

    mut header_index: NativeIRAppendResult = append_i64(program, 1, 0)
    mut header_index_id: i64 = header_index.value_id
    mut current: NativeIRAppendResult = append_load(
        header_index.program, 1, header_index_id
    )
    mut current_id: i64 = current.value_id
    mut limit: NativeIRAppendResult = append_i64(current.program, 1, 3)
    mut limit_id: i64 = limit.value_id
    mut condition: NativeIRAppendResult = native_ir_append_typed_instruction_for_function(
        limit.program, 0, 1, 11, 2, current_id, limit_id, 1
    )
    mut condition_id: i64 = condition.value_id
    mut branch: NativeIRAppendResult = native_ir_append_branch_for_function(
        condition.program, 0, 1, condition_id, 2, 4, 3
    )
    program = branch.program

    mut body_index: NativeIRAppendResult = append_i64(program, 2, 0)
    mut body_index_id: i64 = body_index.value_id
    mut body_value: NativeIRAppendResult = append_load(
        body_index.program, 2, body_index_id
    )
    mut body_value_id: i64 = body_value.value_id
    mut one: NativeIRAppendResult = append_i64(body_value.program, 2, 1)
    mut one_id: i64 = one.value_id
    mut next_value: NativeIRAppendResult = native_ir_append_typed_instruction_for_function(
        one.program, 0, 2, 9, 0, body_value_id, one_id, 0
    )
    mut next_value_id: i64 = next_value.value_id
    program = append_store(next_value.program, 2, body_index_id, next_value_id)
    mut backedge: NativeIRAppendResult = native_ir_append_jump_for_function(
        program, 0, 2, 1
    )
    program = backedge.program

    mut exit_index: NativeIRAppendResult = append_i64(program, 3, 0)
    mut exit_index_id: i64 = exit_index.value_id
    mut final_value: NativeIRAppendResult = append_load(
        exit_index.program, 3, exit_index_id
    )
    mut final_value_id: i64 = final_value.value_id
    mut returned: NativeIRAppendResult = native_ir_append_instruction_for_function(
        final_value.program, 0, 3, 1, 0, final_value_id, -1, -1
    )
    program = returned.program
    mut neutral_jump: NativeIRAppendResult = native_ir_append_jump_for_function(
        program, 0, 4, 3
    )
    program = neutral_jump.program

    mut output: vector<i64> = vector_new<i64>(8192)
    mut emitted: i64 = stage1_emit_verified_native_program(program, &mut output)
    match emitted == 1:
        -1:
            return output
        0:
            mut failure: vector<i64> = vector_new<i64>(1)
            discard vector_push<i64>(&mut failure, 0)
            return failure
        1:
            mut failure: vector<i64> = vector_new<i64>(1)
            discard vector_push<i64>(&mut failure, 0)
            return failure
"""
    stage0 = compile_sources(modules, entry_module="main")
    output = execute_ir(stage0.ir)
    first = int(output[0]) if output.length else -1
    if first != 46:
        diagnostic = tuple(int(output[index]) for index in range(output.length))
        raise AssertionError(f"Stage1 V2 loop CFG diagnostic envelope: {diagnostic}")
    return bytes(int(output[index]) for index in range(output.length))


def _reference_accepts(source: str) -> bool:
    try:
        compile_sources({"main.s3": source}, entry_module="main")
    except S3Error:
        return False
    return True


@pytest.mark.parametrize(
    "source",
    (
        "fn main() -> i64:\n    return 2 + 3\n",
        "fn main() -> i64:\n    return 12 + 30\n",
    ),
)
def test_stage1_candidate_emits_executable_assembly_for_arithmetic(source: str) -> None:
    artifact_bytes = _stage1_artifact(source)
    assert artifact_bytes

    artifact = parse_assembly(artifact_bytes.decode("ascii"))
    assert Emulator().execute(artifact) == run_source(source)


def test_stage1_candidate_composes_two_functions_with_a_zero_argument_call() -> None:
    source = (
        "fn helper() -> i64:\n"
        "    return 37\n"
        "\n"
        "fn main() -> i64:\n"
        "    return helper()\n"
    )
    artifact_bytes = _stage1_artifact(source)
    assert artifact_bytes
    assert b"TCALL" in artifact_bytes

    artifact = parse_assembly(artifact_bytes.decode("ascii"))
    assert Emulator().execute(artifact) == run_source(source) == 37


def test_stage1_candidate_resolves_forward_function_references() -> None:
    source = (
        "fn main() -> i64:\n"
        "    return add(19, 23)\n"
        "\n"
        "fn add(a: i64, b: i64) -> i64:\n"
        "    return a + b\n"
    )
    artifact_bytes = _stage1_artifact(source)
    assert artifact_bytes
    artifact = parse_assembly(artifact_bytes.decode("ascii"))
    assert Emulator().execute(artifact) == run_source(source) == 42


def test_stage1_candidate_lowers_typed_parameters_and_positional_call_arguments() -> None:
    source = (
        "fn add(a: i64, b: i64) -> i64:\n"
        "    return a + b\n"
        "\n"
        "fn main() -> i64:\n"
        "    return add(17, 25)\n"
    )
    artifact_bytes = _stage1_artifact(source)
    assert artifact_bytes
    assert b"TCALL" in artifact_bytes

    artifact = parse_assembly(artifact_bytes.decode("ascii"))
    assert Emulator().execute(artifact) == run_source(source) == 42


def test_stage1_candidate_lowers_immutable_locals_across_function_calls() -> None:
    source = (
        "fn add(a: i64, b: i64) -> i64:\n"
        "    total: i64 = a + b\n"
        "    return total\n"
        "\n"
        "fn main() -> i64:\n"
        "    answer: i64 = add(17, 25)\n"
        "    return answer\n"
    )
    artifact_bytes = _stage1_artifact(source)
    assert artifact_bytes

    artifact = parse_assembly(artifact_bytes.decode("ascii"))
    assert Emulator().execute(artifact) == run_source(source) == 42


def test_stage1_candidate_composes_nested_calls_and_parenthesized_arithmetic() -> None:
    source = (
        "fn multiply(a: i64, b: i64) -> i64:\n"
        "    return (a * b)\n"
        "\n"
        "fn add(a: i64, b: i64) -> i64:\n"
        "    return a + b\n"
        "\n"
        "fn main() -> i64:\n"
        "    return add(multiply(3, 4), 2)\n"
    )
    artifact_bytes = _stage1_artifact(source)
    assert artifact_bytes
    assert b"TCALL" in artifact_bytes
    assert b"TMUL" in artifact_bytes

    artifact = parse_assembly(artifact_bytes.decode("ascii"))
    assert Emulator().execute(artifact) == run_source(source) == 14


@pytest.mark.parametrize(
    "source",
    (
        "fn main() -> i64:\n    return missing + 1\n",
        "fn main() -> i64:\n    value: i64 = 1\n    value: i64 = 2\n    return value\n",
        "fn add(value: i64, value: i64) -> i64:\n    return value\nfn main() -> i64:\n    return add(1, 2)\n",
        "fn add(a: i64, b: i64) -> i64:\n    return a + b\nfn main() -> i64:\n    return add(1)\n",
        "fn main() -> i64:\n    value: i64 = 1\n",
        "fn main() -> i64:\n    return 1\n    value: i64 = 2\n",
        "fn main() -> i64:\n    return true\n",
        "fn main() -> i64:\n    return (1 + 2\n",
    ),
)
def test_stage1_candidate_rejects_unsupported_or_invalid_bindings(source: str) -> None:
    assert not _reference_accepts(source)
    assert _stage1_artifact(source) == b""


def test_stage1_candidate_has_no_host_compiler_fallbacks() -> None:
    repository = Path(__file__).parents[1]
    candidate_sources = "\n".join(
        (repository / path).read_text(encoding="utf-8")
        for path in _STAGE1_MODULES
    ).casefold()
    for forbidden in (
        "bootstrap.s3",
        "compile_source(",
        "compile_program(",
        "run_source(",
        "reference_lowerer",
        "host_compiler_callback",
    ):
        assert forbidden not in candidate_sources


def test_stage1_candidate_output_is_deterministic() -> None:
    source = "fn main() -> i64:\n    return 12 + 30\n"
    assert _stage1_artifact(source) == _stage1_artifact(source)


def test_stage1_candidate_rejects_unlowered_identifier_without_artifact() -> None:
    source = "fn main() -> i64:\n    return value + 1\n"
    assert _stage1_artifact(source) == b""


@pytest.mark.parametrize(
    ("function_name", "signature", "dependencies"),
    (
        ("stage1_emission_value_count", "view: &vector<i64>", ()),
        ("stage1_emission_instruction_count", "view: &vector<i64>", ()),
        ("stage1_emission_value_id", "view: &vector<i64>, index: i64", ()),
        (
            "stage1_emission_operand_id",
            "view: &vector<i64>, index: i64",
            ("stage1_emission_value_count",),
        ),
        (
            "stage1_emission_instruction_field",
            "view: &vector<i64>, index: i64, field: i64",
            ("stage1_emission_value_count",),
        ),
    ),
)
def test_stage1_v2_compiles_real_reference_vector_helpers(
    function_name: str,
    signature: str,
    dependencies: tuple[str, ...],
) -> None:
    repository = Path(__file__).parents[1]
    raw = (repository / "selfhost/compiler/stage1_compiler_v1.s3").read_text(
        encoding="utf-8"
    )
    selected_functions = []
    for name in (*dependencies, function_name):
        start = raw.index(f"fn {name}(")
        end = raw.index("\n\n", start)
        selected_functions.append(raw[start:end])
    original_function = selected_functions[-1]
    assert f"fn {function_name}({signature}) -> i64:" in original_function
    source = "\n\n".join(
        (*selected_functions, "fn main() -> i64:\n    return 0")
    ) + "\n"

    diagnostics: list[int] = []
    artifact_bytes = _stage1_artifact(
        source, compiler_version="v2", diagnostics=diagnostics
    )
    assert artifact_bytes, f"Stage1 compile envelope: {diagnostics}"
    assert artifact_bytes.startswith(b".s3asm 0.7.0\n")
    assert b".param r0, reference, vector, immutable, value\n" in artifact_bytes
    assert b"TCALL r" in artifact_bytes
    if function_name in {
        "stage1_emission_value_id",
        "stage1_emission_operand_id",
        "stage1_emission_instruction_field",
    }:
        assert b"TADD r" in artifact_bytes

    artifact = parse_assembly(artifact_bytes.decode("ascii"))
    assert Emulator().execute(artifact) == 0


@pytest.mark.parametrize(
    "source",
    (
        "fn main() -> i64:\n    return vector_get<f64>(1, 0)\n",
        "fn main() -> i64:\n    return vector_get<i64>(1, 0)\n",
        "fn main() -> i64:\n    return vector_get<i64>(1)\n",
        "fn main() -> i64:\n    return vector_get<i64>(1, 0, 2)\n",
        "fn read(view: &vector<i64>) -> i64:\n    return vector_len<f64>(view)\n"
        "fn main() -> i64:\n    return 0\n",
        "fn read(view: &vector<i64>) -> i64:\n    return vector_len<i64>()\n"
        "fn main() -> i64:\n    return 0\n",
        "fn read(view: &vector<i64>) -> i64:\n    return vector_len<i64>(view, 0)\n"
        "fn main() -> i64:\n    return 0\n",
        "fn read(view: &vector<i64>) -> i64:\n    return vector_get<i64>(view, 0)\n"
        "fn main() -> i64:\n    return read(1)\n",
    ),
)
def test_stage1_v2_rejects_invalid_typed_vector_calls(source: str) -> None:
    assert _stage1_artifact(source, compiler_version="v2") == b""


def test_stage1_v2_lowers_mutable_local_reassignment() -> None:
    source = (
        "fn main() -> i64:\n"
        "    mut value: i64 = 1\n"
        "    value = 2\n"
        "    return value\n"
    )
    artifact_bytes = _stage1_artifact(source, compiler_version="v2")
    assert artifact_bytes
    artifact = parse_assembly(artifact_bytes.decode("ascii"))
    assert Emulator().execute(artifact) == 2


@pytest.mark.parametrize(
    ("operator", "relation_code", "left", "right", "expected"),
    (("<", 2, 1, 2, -1), ("==", 0, 1, 1, -1), ("==", 0, 1, 2, 0)),
)
def test_stage1_v2_lowers_typed_scalar_comparisons(
    operator: str,
    relation_code: int,
    left: int,
    right: int,
    expected: int,
) -> None:
    source = (
        "fn compare(left: i64, right: i64) -> trit:\n"
        f"    return left {operator} right\n"
        "fn main() -> trit:\n"
        f"    return compare({left}, {right})\n"
    )

    diagnostics: list[int] = []
    artifact_bytes = _stage1_artifact(
        source,
        compiler_version="v2",
        diagnostics=diagnostics,
    )
    assert artifact_bytes, f"Stage1 compile envelope: {diagnostics}"
    artifact = parse_assembly(artifact_bytes.decode("ascii"))
    compare = next(function for function in artifact.functions if function.name == "compare")
    relations = [
        instruction
        for instruction in compare.instructions
        if instruction.opcode.value == "TREL"
    ]

    assert len(relations) == 1
    assert relations[0].immediate == relation_code
    assert Emulator().execute(artifact) == expected
    assert Emulator().execute(artifact) == run_source(source)


def test_stage1_v2_rejects_comparison_between_incompatible_scalar_types() -> None:
    source = (
        "fn compare(left: trit, right: i64) -> trit:\n"
        "    return left < right\n"
        "fn main() -> trit:\n"
        "    return 0\n"
    )

    assert _stage1_artifact(source, compiler_version="v2") == b""


def test_stage1_v2_emits_and_executes_verified_three_way_cfg() -> None:
    artifact_bytes = _stage1_v2_emit_three_way_cfg()
    assert artifact_bytes
    assembly_text = artifact_bytes.decode("ascii")
    assert ".label entry\n" in assembly_text
    assert ".label b1\n" in assembly_text
    assert ".label b2\n" in assembly_text
    assert ".label b3\n" in assembly_text
    assert ".label b4\n" in assembly_text
    assert ".memory m0, i64, 1, mutable\n" in assembly_text
    assert "TBR3 " in assembly_text
    assert "TSTORE m0," in assembly_text
    assert "TLOAD" in assembly_text
    artifact = parse_assembly(assembly_text)
    assert Emulator().execute(artifact) == 11


def test_stage1_v2_loop_carried_memory_cfg_is_deterministic_and_executes() -> None:
    first_bytes = _stage1_v2_emit_loop_carried_memory_cfg()
    second_bytes = _stage1_v2_emit_loop_carried_memory_cfg()

    assert first_bytes == second_bytes
    first_sha = hashlib.sha256(first_bytes).hexdigest()
    second_sha = hashlib.sha256(second_bytes).hexdigest()
    assert first_sha == second_sha
    artifact = parse_assembly(first_bytes.decode("ascii"))
    assert ".label b1" in first_bytes.decode("ascii")
    assert "TBR3 " in first_bytes.decode("ascii")
    assert "TJMP b1" in first_bytes.decode("ascii")
    assert "TLOAD" in first_bytes.decode("ascii")
    assert "TSTORE m0," in first_bytes.decode("ascii")
    assert Emulator().execute(artifact) == 3


@pytest.mark.s3_native
@pytest.mark.skipif(
    platform.system() != "Linux"
    or platform.machine().lower() not in {"x86_64", "amd64"},
    reason="requires Linux x86-64 native toolchain",
)
def test_stage1_v2_three_way_cfg_executes_natively(tmp_path: Path) -> None:
    try:
        toolchain = NativeToolchain.detect()
    except NativeBackendError as error:
        pytest.skip(str(error))
    artifact = parse_assembly(_stage1_v2_emit_three_way_cfg().decode("ascii"))
    executable = toolchain.build(
        generate_native_assembly(artifact), tmp_path / "stage1-v2-three-way-cfg"
    )
    completed = toolchain.run(executable)
    assert completed.returncode == 0
    assert completed.stderr == ""
    assert completed.stdout.strip() == "program returned: 11"


@pytest.mark.s3_native
@pytest.mark.skipif(
    platform.system() != "Linux"
    or platform.machine().lower() not in {"x86_64", "amd64"},
    reason="requires Linux x86-64 native toolchain",
)
def test_stage1_v2_loop_carried_memory_cfg_executes_natively(tmp_path: Path) -> None:
    try:
        toolchain = NativeToolchain.detect()
    except NativeBackendError as error:
        pytest.skip(str(error))
    artifact = parse_assembly(
        _stage1_v2_emit_loop_carried_memory_cfg().decode("ascii")
    )
    executable = toolchain.build(
        generate_native_assembly(artifact), tmp_path / "stage1-v2-loop-carried-cfg"
    )
    completed = toolchain.run(executable)
    assert completed.returncode == 0
    assert completed.stderr == ""
    assert completed.stdout.strip() == "program returned: 3"


def test_stage1_v2_rejects_reassignment_of_immutable_local() -> None:
    source = (
        "fn main() -> i64:\n"
        "    value: i64 = 1\n"
        "    value = 2\n"
        "    return value\n"
    )
    assert _stage1_artifact(source, compiler_version="v2") == b""


def test_stage1_v2_lowers_typed_vector_len_builtin() -> None:
    source = (
        "fn vector_count(view: &vector<i64>) -> i64:\n"
        "    return vector_len<i64>(view)\n"
        "fn main() -> i64:\n"
        "    return 0\n"
    )
    artifact_bytes = _stage1_artifact(source, compiler_version="v2")
    assert artifact_bytes
    artifact = parse_assembly(artifact_bytes.decode("ascii"))
    count_function = next(
        function for function in artifact.functions
        if function.name == "vector_count"
    )
    assert any(
        instruction.callee == "i64_vector_len"
        for instruction in count_function.instructions
    )
    assert Emulator().execute(artifact) == 0


@pytest.mark.s3_native
@pytest.mark.skipif(
    platform.system() != "Linux"
    or platform.machine().lower() not in {"x86_64", "amd64"},
    reason="requires Linux x86-64 native toolchain",
)
def test_stage1_v2_real_reference_vector_helpers_execute_natively(
    tmp_path: Path,
) -> None:
    repository = Path(__file__).parents[1]
    raw = (repository / "selfhost/compiler/stage1_compiler_v1.s3").read_text(
        encoding="utf-8"
    )
    function_names = (
        "stage1_emission_value_count",
        "stage1_emission_instruction_count",
        "stage1_emission_value_id",
        "stage1_emission_operand_id",
        "stage1_emission_instruction_field",
    )
    vector_len_probe_name = "stage1_v2_vector_len_probe"
    vector_len_probe = (
        f"fn {vector_len_probe_name}(view: &vector<i64>) -> i64:\n"
        "    return vector_len<i64>(view)"
    )
    source_functions = []
    for name in function_names:
        start = raw.index(f"fn {name}(")
        end = raw.index("\n\n", start)
        source_functions.append(raw[start:end])

    candidate_source = (
        "\n\n".join((*source_functions, vector_len_probe))
        + "\n\nfn main() -> i64:\n    return 0\n"
    )
    candidate = parse_assembly(
        _stage1_artifact(candidate_source, compiler_version="v2").decode("ascii")
    )

    def vector_setup(name: str, values: list[int]) -> str:
        lines = [
            f"    mut {name}: vector<i64> = vector_new<i64>({len(values)})"
        ]
        lines.extend(
            f"    discard vector_push<i64>(&mut {name}, {value})"
            for value in values
        )
        return "\n".join(lines)

    reference_source = "\n\n".join(source_functions) + f"""
{vector_len_probe}

fn main() -> i64:
    mut count_view: vector<i64> = vector_new<i64>(2)
    discard vector_push<i64>(&mut count_view, 41)
    discard vector_push<i64>(&mut count_view, 3)
    mut instruction_count_view: vector<i64> = vector_new<i64>(2)
    discard vector_push<i64>(&mut instruction_count_view, 41)
    discard vector_push<i64>(&mut instruction_count_view, 7)
    mut value_view: vector<i64> = vector_new<i64>(5)
    discard vector_push<i64>(&mut value_view, 41)
    discard vector_push<i64>(&mut value_view, 7)
    discard vector_push<i64>(&mut value_view, 13)
    discard vector_push<i64>(&mut value_view, 17)
    discard vector_push<i64>(&mut value_view, 99)
{vector_setup("operand_view", [41, *([0] * 44), 73])}
{vector_setup("instruction_view", [2, 0, 1, 0, 0, 0, 0, 0, 88])}
    return stage1_emission_value_count(&count_view) + stage1_emission_instruction_count(&instruction_count_view) * 100 + stage1_emission_value_id(&value_view, 1) * 10000 + stage1_emission_operand_id(&operand_view, 1) * 1000000 + stage1_emission_instruction_field(&instruction_view, 0, 2) * 100000000 + stage1_v2_vector_len_probe(&count_view) * 10000000000
"""
    reference = compile_sources(
        {"main.s3": reference_source}, entry_module="main"
    )
    candidate_function_names = (*function_names, vector_len_probe_name)
    candidate_by_name = {}
    for function in candidate.functions:
        if function.name not in candidate_function_names:
            continue
        renamed_name = f"__s3mod_main__{function.name}"
        renamed_blocks = tuple(
            replace(
                block,
                instructions=tuple(
                    replace(
                        instruction,
                        callee=f"__s3mod_main__{instruction.callee}"
                        if instruction.callee in candidate_function_names
                        else instruction.callee,
                    )
                    if instruction.callee is not None
                    else instruction
                    for instruction in block.instructions
                ),
            )
            for block in function.blocks
        )
        candidate_by_name[renamed_name] = replace(
            function, name=renamed_name, blocks=renamed_blocks
        )
    assert set(candidate_by_name) == {
        f"__s3mod_main__{name}" for name in candidate_function_names
    }
    composed_functions = tuple(
        candidate_by_name.get(function.name, function)
        for function in reference.assembly.functions
    )
    composed = replace(reference.assembly, functions=composed_functions)

    native_source = generate_native_assembly(composed)
    toolchain = NativeToolchain.detect()
    executable = toolchain.build(
        native_source, tmp_path / "stage1-v2-real-helpers"
    )
    completed = toolchain.run(executable)

    assert completed.returncode == 0
    assert completed.stderr == ""
    assert completed.stdout.strip() == "program returned: 28873990741"
    assert execute_ir(reference.ir) == 28_873_990_741


def test_s3_output_sink_append_bytes_overflow_is_transactional() -> None:
    repository = Path(__file__).parents[1]
    source = """\
module main
from selfhost.substrate.output_sink import OutputSinkState
from selfhost.substrate.output_sink import output_sink_new
from selfhost.substrate.output_sink import output_sink_append
from selfhost.substrate.output_sink import output_sink_append_bytes
fn main() -> i64:
    mut sink: OutputSinkState = output_sink_new(2)
    sink = output_sink_append(sink, 65)
    mut bytes: vector<i64> = vector_new<i64>(2)
    discard vector_push<i64>(&mut bytes, 66)
    discard vector_push<i64>(&mut bytes, 67)
    sink = output_sink_append_bytes(sink, bytes)
    mut failed: i64 = 0
    match sink.failed == 1:
        -1:
            failed = 1
        0:
            discard 0
        1:
            discard 0
    return failed * 1000000 + vector_len<i64>(&sink.buffer) * 10000 + vector_get<i64>(&sink.buffer, 0)
"""
    compilation = compile_sources(
        {
            "selfhost/substrate/output_sink.s3": (
                repository / "selfhost/substrate/output_sink.s3"
            ).read_text(encoding="utf-8"),
            "main.s3": source,
        },
        entry_module="main",
    )

    assert execute_ir(compilation.ir) == 1_010_065
