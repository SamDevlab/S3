from __future__ import annotations

import hashlib
import platform
from pathlib import Path

import pytest

from bootstrap.s3.backends.x86_64 import NativeToolchain, generate_native_assembly
from bootstrap.s3.codegen import generate_assembly
from bootstrap.s3.compiler_ng_ir_bridge import decode_ng_ir_events
from bootstrap.s3.ir import IRModule
from bootstrap.s3.pipeline import compile_sources
from bootstrap.s3.ir_serialization import serialize_ir
from bootstrap.s3.verifier import verify_ir
from tools.native_s3c_ng import (
    NativeSourceSetResult,
    build_native_s3c,
    compile_reference_b_ir,
    compiler_source_set,
    run_native_source_set,
)


_ROOT = Path(__file__).parents[1]
_MULTIMODULE_SOURCES = {
    "app.s3": """\
module app
from math import transform as increment
from policy import transform as augment
from decision import choose as choose_value
fn selector() -> i64:
    return 0
fn main() -> i64:
    mut total: i64 = increment(1)
    total = total + augment(2)
    total = total + choose_value(selector())
    return total
""",
    "math.s3": """\
module math
export fn transform(value: i64) -> i64:
    mut result: i64 = value
    result = result + 1
    return result
""",
    "policy.s3": """\
module policy
export fn transform(value: i64) -> i64:
    return value + 10
""",
    "decision.s3": """\
module decision
export fn choose(value: i64) -> i64:
    match value <=> 0:
        -1:
            return 1
        0:
            return 2
        1:
            return 3
""",
}


def _canonical_structure(module: IRModule) -> tuple[object, ...]:
    functions: list[object] = []
    for function in module.functions:
        block_names = {block.name: f"b{index}" for index, block in enumerate(function.blocks)}
        blocks = tuple(
            (
                block_names[block.name],
                tuple(
                    (
                        instruction.opcode.value,
                        None
                        if instruction.opcode.value == "call" and instruction.results
                        else instruction.result,
                        instruction.results,
                        instruction.operands,
                        instruction.immediate,
                        instruction.static_string,
                        instruction.callee,
                        tuple(block_names[target] for target in instruction.targets),
                        instruction.memory,
                        instruction.initialization,
                        instruction.reference_target,
                        instruction.reference_mutable,
                        instruction.reference_is_slice,
                        instruction.slice_length_result,
                        instruction.reference_aggregate,
                        instruction.aggregate_field_paths,
                        instruction.aggregate_field_path,
                    )
                    for instruction in block.instructions
                ),
            )
            for block in function.blocks
        )
        functions.append(
            (
                function.name,
                tuple((param.name, param.register, param.type) for param in function.parameters),
                function.return_type,
                function.result_types,
                tuple((register.index, register.type) for register in function.registers),
                tuple(
                    (memory.index, memory.element_type, memory.length, memory.mutable)
                    for memory in function.memory_objects
                ),
                blocks,
                function.external,
                function.exported,
            )
        )
    return tuple(functions), tuple((item.id, item.value) for item in module.static_strings)


def _source_location_count(module: IRModule) -> int:
    return sum(
        instruction.location is not None
        for function in module.functions
        for block in function.blocks
        for instruction in block.instructions
    )


def _source_location_structure(module: IRModule) -> tuple[object, ...]:
    return tuple(
        (
            function.name,
            function.location,
            tuple(parameter.location for parameter in function.parameters),
            tuple(register.location for register in function.registers),
            tuple(memory.location for memory in function.memory_objects),
            tuple(
                (
                    block.location,
                    tuple(instruction.location for instruction in block.instructions),
                )
                for block in function.blocks
            ),
        )
        for function in module.functions
    )


def _assert_native_compile(
    artifact,
    sources: dict[str, str],
    *,
    expected_result: int,
    tmp_path: Path,
) -> NativeSourceSetResult:
    reference = compile_sources(sources, "O0", entry_module="app").ir
    assert reference is not None

    result = run_native_source_set(artifact, sources, entry_module="app")
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    assert result.status == 0
    actual = decode_ng_ir_events(result.source, result.events)
    verify_ir(actual)
    assert _canonical_structure(actual) == _canonical_structure(reference)
    assert _source_location_structure(actual) == _source_location_structure(reference)

    assembly = generate_native_assembly(generate_assembly(actual))
    executable = NativeToolchain.detect().build(
        assembly,
        tmp_path / f"compiled-{expected_result}",
    )
    completed = NativeToolchain.detect().run(executable)
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == f"program returned: {expected_result}\n"
    assert completed.stderr == ""
    return result


def _assert_native_outputs_equal(
    left: NativeSourceSetResult,
    right: NativeSourceSetResult,
    *,
    workload: str,
) -> None:
    assert left.status == right.status, workload
    assert left.source == right.source, workload
    assert left.events == right.events, workload
    assert left.output_envelope_bytes == right.output_envelope_bytes, workload
    assert left.output_envelope_sha256 == right.output_envelope_sha256, workload


@pytest.mark.s3_native
@pytest.mark.skipif(
    platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"},
    reason="native S3C-NG qualification requires Linux x86-64",
)
def test_native_s3c_ng_reaches_native_compiler_fixed_point(tmp_path: Path) -> None:
    compiler_ir = compile_reference_b_ir(_ROOT)
    artifact_b = build_native_s3c(compiler_ir, tmp_path / "native-b", label="s3c-ng-b")
    assert artifact_b.compiler_ir_sha256
    assert artifact_b.assembly_sha256
    assert artifact_b.object_sha256
    assert artifact_b.executable_bytes > 0
    assert artifact_b.executable.read_bytes()[:4] == b"\x7fELF"
    assert artifact_b.executable.read_bytes()[16:18] == b"\x02\x00"

    small = {
        "app.s3": (
            "module app\n"
            "fn answer(value: i64) -> i64:\n"
            "    return value\n"
            "fn main() -> i64:\n"
            "    return answer(42)\n"
        ),
    }
    b_small = _assert_native_compile(
        artifact_b, small, expected_result=42, tmp_path=tmp_path
    )

    b_multimodule = _assert_native_compile(
        artifact_b,
        _MULTIMODULE_SOURCES,
        expected_result=16,
        tmp_path=tmp_path,
    )

    compiler_sources = compiler_source_set(_ROOT)
    compiler_source_bytes = sum(len(source.encode("utf-8")) for source in compiler_sources.values())
    native_b_to_c = run_native_source_set(
        artifact_b,
        compiler_sources,
        entry_module="app",
        timeout=900.0,
    )
    assert native_b_to_c.returncode == 0, native_b_to_c.stderr.decode(errors="replace")
    assert native_b_to_c.status == 0
    generation_c = decode_ng_ir_events(native_b_to_c.source, native_b_to_c.events)
    verify_ir(generation_c)
    assert len(compiler_sources) == 8
    assert compiler_source_bytes > 0
    assert len(generation_c.functions) == len(compiler_ir.functions)
    assert _canonical_structure(generation_c) == _canonical_structure(compiler_ir)
    assert _source_location_structure(generation_c) == _source_location_structure(
        compiler_ir
    )

    artifact_c = build_native_s3c(generation_c, tmp_path / "native-c", label="s3c-ng-c")
    c_small = _assert_native_compile(
        artifact_c, small, expected_result=42, tmp_path=tmp_path
    )
    c_multimodule = _assert_native_compile(
        artifact_c,
        _MULTIMODULE_SOURCES,
        expected_result=16,
        tmp_path=tmp_path,
    )
    _assert_native_outputs_equal(
        b_small, c_small, workload="B/C small program"
    )
    _assert_native_outputs_equal(
        b_multimodule,
        c_multimodule,
        workload="B/C multi-module program",
    )

    native_c_to_d = run_native_source_set(
        artifact_c,
        compiler_sources,
        entry_module="app",
        timeout=900.0,
    )
    assert native_c_to_d.returncode == 0, native_c_to_d.stderr.decode(errors="replace")
    assert native_c_to_d.status == 0
    generation_d = decode_ng_ir_events(native_c_to_d.source, native_c_to_d.events)
    verify_ir(generation_d)
    assert _canonical_structure(generation_d) == _canonical_structure(generation_c)
    assert serialize_ir(generation_d) == serialize_ir(generation_c)
    assert serialize_ir(generation_c) == serialize_ir(compiler_ir)
    assert native_c_to_d.output_envelope_sha256 == native_b_to_c.output_envelope_sha256
    assert native_c_to_d.output_envelope_bytes == native_b_to_c.output_envelope_bytes

    artifact_b_repeat = build_native_s3c(
        compiler_ir,
        tmp_path / "native-b-repeat",
        label="s3c-ng-b",
    )
    artifact_c_repeat = build_native_s3c(
        generation_c,
        tmp_path / "native-c-repeat",
        label="s3c-ng-c",
    )
    assert artifact_b_repeat.assembly_sha256 == artifact_b.assembly_sha256
    assert artifact_b_repeat.object_sha256 == artifact_b.object_sha256
    assert artifact_b_repeat.executable_sha256 == artifact_b.executable_sha256
    assert artifact_c_repeat.assembly_sha256 == artifact_c.assembly_sha256
    assert artifact_c_repeat.object_sha256 == artifact_c.object_sha256
    assert artifact_c_repeat.executable_sha256 == artifact_c.executable_sha256

    hosted_serialized = serialize_ir(compiler_ir).encode("utf-8")
    native_serialized = serialize_ir(generation_c).encode("utf-8")
    assembly_equal = artifact_c.assembly_sha256 == artifact_b.assembly_sha256
    object_equal = artifact_c.object_sha256 == artifact_b.object_sha256
    elf_equal = artifact_c.executable_sha256 == artifact_b.executable_sha256
    print(f"NATIVE_B_ELF_SHA256={artifact_b.executable_sha256}")
    print(f"NATIVE_C_ELF_SHA256={artifact_c.executable_sha256}")
    print(f"NATIVE_B_TO_C_OUTPUT_SHA256={native_b_to_c.output_envelope_sha256}")
    print(f"NATIVE_C_TO_D_OUTPUT_SHA256={native_c_to_d.output_envelope_sha256}")
    print("NATIVE_B_TO_C_C_TO_D_OUTPUT_BYTE_EQUAL=True")
    print(f"NATIVE_COMPILER_SOURCE_MODULES={len(compiler_sources)}")
    print(f"NATIVE_COMPILER_SOURCE_BYTES={compiler_source_bytes}")
    print(f"NATIVE_COMPILER_SOURCE_FUNCTIONS={len(generation_c.functions)}")
    print(f"HOSTED_REFERENCE_IR_SHA256={hashlib.sha256(hosted_serialized).hexdigest()}")
    print(f"NATIVE_C_IR_SHA256={hashlib.sha256(native_serialized).hexdigest()}")
    print(f"HOSTED_REFERENCE_SOURCE_LOCATIONS={_source_location_count(compiler_ir)}")
    print(f"NATIVE_C_SOURCE_LOCATIONS={_source_location_count(generation_c)}")
    print(f"HOSTED_NATIVE_SERIALIZED_IR_EQUAL={hosted_serialized == native_serialized}")
    print(
        "B_C_SOURCE_LOCATION_AND_CANONICAL_SERIALIZATION_EQUAL="
        f"{hosted_serialized == native_serialized}"
    )
    print(f"NATIVE_B_TO_C_SECONDS={native_b_to_c.elapsed_seconds:.6f}")
    print(f"NATIVE_C_TO_D_SECONDS={native_c_to_d.elapsed_seconds:.6f}")
    print(f"B_REPEAT_ASSEMBLY_OBJECT_ELF_EQUAL=True")
    print(f"C_REPEAT_ASSEMBLY_OBJECT_ELF_EQUAL=True")
    print(f"ASSEMBLY_SHA256_EQUAL={assembly_equal}")
    print(f"OBJECT_SHA256_EQUAL={object_equal}")
    print(f"ELF_SHA256_EQUAL={elf_equal}")
    print(
        "B_C_ASSEMBLY_TEXT_BYTE_IDENTICAL="
        f"{artifact_b.assembly.encode() == artifact_c.assembly.encode()}"
    )
    print(
        "B_C_OBJECT_BYTE_IDENTICAL="
        f"{artifact_b.object_path.read_bytes() == artifact_c.object_path.read_bytes()}"
    )
    print(
        "B_C_ELF_BYTE_IDENTICAL="
        f"{artifact_b.executable.read_bytes() == artifact_c.executable.read_bytes()}"
    )
    print("ASSEMBLY_DIFFERENCE_CLASS=SOURCE_LOCATION_DIAGNOSTIC_METADATA")
