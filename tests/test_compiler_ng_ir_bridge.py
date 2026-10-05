from __future__ import annotations

import json
import platform
from pathlib import Path
import subprocess

import pytest

from bootstrap.s3.compiler_ng_ir_bridge import (
    NGIRDecodeError,
    decode_ng_ir_events,
)
from bootstrap.s3.backends.x86_64 import generate_native_assembly
from bootstrap.s3.codegen import generate_assembly
from bootstrap.s3.backends.x86_64 import NativeToolchain
from bootstrap.s3.dynamic import DynamicVector
from bootstrap.s3.emulator import Emulator
from bootstrap.s3.ir import IRModule
from bootstrap.s3.ir_emulator import execute_ir
from bootstrap.s3.pipeline import compile_source
from bootstrap.s3.verifier import verify_ir
from tests.test_compiler_ng_ir import _NG_SOURCE
from tools.qbe_oracle import translate_verified_ir


_ROOT = Path(__file__).parents[1]


def _emit_ng_events(source: str) -> list[int]:
    wrapper = f'''
fn main() -> vector<i64>:
    mut source_text: text = text_from_static({json.dumps(source)})
    mut source_bytes: bytes = bytes_from_text(&source_text)
    mut tokens: vector<NgToken> = vector_new<NgToken>(8192)
    mut functions: vector<NgFunction> = vector_new<NgFunction>(128)
    mut parameters: vector<NgParameter> = vector_new<NgParameter>(512)
    mut nodes: vector<NgAstNode> = vector_new<NgAstNode>(16384)
    mut events: vector<i64> = vector_new<i64>(262144)
    mut status: i64 = ng_lex(&source_bytes, &mut tokens)
    match status <=> 0:
        -1:
            discard vector_push<i64>(&mut events, status)
            return events
        0:
            status = ng_parse_program(&source_bytes, &tokens, &mut functions, &mut parameters, &mut nodes)
            match status <=> 0:
                -1:
                    discard vector_push<i64>(&mut events, status)
                    return events
                0:
                    status = ng_emit_program(&source_bytes, &functions, &parameters, &nodes, &mut events)
                    match status <=> 0:
                        -1:
                            discard vector_push<i64>(&mut events, status)
                            return events
                        0:
                            return events
                        1:
                            discard vector_push<i64>(&mut events, status)
                            return events
                1:
                    discard vector_push<i64>(&mut events, status)
                    return events
        1:
            discard vector_push<i64>(&mut events, status)
            return events
'''
    compilation = compile_source(_NG_SOURCE + "\n" + wrapper)
    assert compilation.ir is not None
    events = execute_ir(compilation.ir)
    assert isinstance(events, DynamicVector)
    assert events.element_type == "i64"
    cells = [int(value) for value in events]
    assert cells and cells[0] == 0, f"S3C-NG failed during lex/parse/emit: {cells}"
    return cells


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
                        instruction.result,
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


def _event_records(cells: list[int]) -> list[list[int]]:
    assert len(cells) % 8 == 0
    return [cells[index : index + 8] for index in range(0, len(cells), 8)]


def _flatten(records: list[list[int]]) -> list[int]:
    return [cell for record in records for cell in record]


def test_branches_ng_output_decodes_verifies_executes_and_matches_reference() -> None:
    source = (_ROOT / "benchmarks/workloads/branches.s3").read_text(encoding="utf-8")
    reference_ir = compile_source(source).ir
    assert reference_ir is not None
    ng_serialized_ir = _emit_ng_events(source)
    ng_canonical_ir = decode_ng_ir_events(source.encode("utf-8"), ng_serialized_ir)

    verify_ir(ng_canonical_ir)
    assert _canonical_structure(ng_canonical_ir) == _canonical_structure(reference_ir)
    assert execute_ir(reference_ir) == execute_ir(ng_canonical_ir)


def test_branches_ng_origin_ir_flows_through_existing_backends() -> None:
    source = (_ROOT / "benchmarks/workloads/branches.s3").read_text(encoding="utf-8")
    reference_ir = compile_source(source).ir
    assert reference_ir is not None
    ng_serialized_ir = _emit_ng_events(source)
    ng_canonical_ir = decode_ng_ir_events(source.encode("utf-8"), ng_serialized_ir)
    verify_ir(ng_canonical_ir)

    assembly = generate_assembly(ng_canonical_ir)
    emulator = Emulator()
    emulator.validate(assembly, entry="main")
    assembly_result = emulator.execute(assembly)
    assert assembly_result == execute_ir(ng_canonical_ir) == execute_ir(reference_ir)

    native_assembly = generate_native_assembly(assembly)
    assert ".globl s3_main" in native_assembly
    assert native_assembly.strip()

    qbe_il = translate_verified_ir(ng_canonical_ir)
    assert "function" in qbe_il
    assert qbe_il.strip()


@pytest.mark.s3_native
@pytest.mark.parametrize("workload", ("branches.s3", "calls.s3"))
@pytest.mark.skipif(
    platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"},
    reason="S3 x86-64 native execution is qualified on Linux x86-64",
)
def test_ng_origin_ir_executes_through_linux_x86_64(workload: str, tmp_path: Path) -> None:
    source = (_ROOT / "benchmarks/workloads" / workload).read_text(encoding="utf-8")
    reference_ir = compile_source(source).ir
    assert reference_ir is not None
    ng_canonical_ir = decode_ng_ir_events(source.encode("utf-8"), _emit_ng_events(source))
    verify_ir(ng_canonical_ir)
    assembly = generate_assembly(ng_canonical_ir)
    native_source = generate_native_assembly(assembly)
    expected = execute_ir(reference_ir)
    assert execute_ir(ng_canonical_ir) == expected

    executable = NativeToolchain.detect().build(native_source, tmp_path / Path(workload).stem)
    completed = subprocess.run([str(executable)], check=False, capture_output=True, text=True, timeout=30)
    assert completed.returncode == 0, (
        f"NG-origin native executable failed with status {completed.returncode}: "
        f"stdout={completed.stdout!r} stderr={completed.stderr!r}"
    )
    assert completed.stderr == ""
    assert completed.stdout == f"program returned: {expected}\n", (
        f"NG-origin native result differs from reference {expected}: "
        f"stdout={completed.stdout!r} stderr={completed.stderr!r}"
    )


def test_second_real_workload_calls_uses_ng_origin_ir_end_to_end() -> None:
    source = (_ROOT / "benchmarks/workloads/calls.s3").read_text(encoding="utf-8")
    reference_ir = compile_source(source).ir
    assert reference_ir is not None
    ng_serialized_ir = _emit_ng_events(source)
    ng_canonical_ir = decode_ng_ir_events(source.encode("utf-8"), ng_serialized_ir)

    verify_ir(ng_canonical_ir)
    assert _canonical_structure(ng_canonical_ir) == _canonical_structure(reference_ir)
    reference_result = execute_ir(reference_ir)
    ng_result = execute_ir(ng_canonical_ir)
    assert ng_result == reference_result

    assembly = generate_assembly(ng_canonical_ir)
    emulator = Emulator()
    emulator.validate(assembly, entry="main")
    assert emulator.execute(assembly) == ng_result
    assert ".globl s3_main" in generate_native_assembly(assembly)
    assert "function" in translate_verified_ir(ng_canonical_ir)


def test_ng_canonical_ir_round_trip_covers_calls_mutation_matches_and_types() -> None:
    source = "\n".join(
        (
            "fn add(left: i64, right: i64) -> i64:",
            "    return left + right",
            "fn adjust(value: i64) -> i64:",
            "    mut current: i64 = value",
            "    current = current + 1",
            "    return current",
            "fn choose(value: trit) -> i64:",
            "    match value:",
            "        -1:",
            "            return 10",
            "        0:",
            "            return 20",
            "        1:",
            "            return 30",
            "fn pass_tryte(value: tryte) -> tryte:",
            "    return value",
            "fn pass_f64(value: f64) -> f64:",
            "    return value",
            "fn main() -> i64:",
            "    return add(adjust(3), 5)",
        )
    )
    reference_ir = compile_source(source).ir
    assert reference_ir is not None
    ng_canonical_ir = decode_ng_ir_events(source.encode(), _emit_ng_events(source))

    verify_ir(ng_canonical_ir)
    assert _canonical_structure(ng_canonical_ir) == _canonical_structure(reference_ir)
    assert execute_ir(ng_canonical_ir) == execute_ir(reference_ir)


def _branches_events() -> tuple[str, list[int]]:
    source = (_ROOT / "benchmarks/workloads/branches.s3").read_text(encoding="utf-8")
    return source, _emit_ng_events(source)


@pytest.mark.parametrize(
    ("corruption", "message"),
    (
        ("unknown-opcode", "unknown opcode"),
        ("unknown-type", "unknown type"),
        ("duplicate-block", "block identities"),
        ("missing-target", "missing branch target"),
        ("missing-register", "missing register"),
        ("missing-memory", "missing memory"),
        ("missing-target-record", "control-flow targets"),
    ),
)
def test_ng_ir_bridge_rejects_structural_corruption(corruption: str, message: str) -> None:
    source, cells = _branches_events()
    records = _event_records(cells)
    if corruption == "unknown-opcode":
        next(record for record in records if record[0] == 4)[2] = 999
    elif corruption == "unknown-type":
        next(record for record in records if record[0] == 3)[3] = 999
    elif corruption == "duplicate-block":
        blocks = [record for record in records if record[0] == 9]
        assert len(blocks) > 1
        blocks[1][2] = blocks[0][2]
    elif corruption == "missing-target":
        next(record for record in records if record[0] == 11)[3] = 999
    elif corruption == "missing-register":
        return_record = next(record for record in records if record[0] == 4 and record[2] == 6)
        return_record[5] = 999
    elif corruption == "missing-memory":
        store_record = next(record for record in records if record[0] == 4 and record[2] == 10)
        store_record[7] = 999
    elif corruption == "missing-target-record":
        target_index = next(index for index, record in enumerate(records) if record[0] == 11)
        del records[target_index]

    with pytest.raises(NGIRDecodeError, match=message):
        decode_ng_ir_events(source.encode("utf-8"), _flatten(records))


def test_ng_ir_bridge_rejects_invalid_call_function_and_argument_ranges() -> None:
    source = "\n".join(
        (
            "fn callee(value: i64) -> i64:",
            "    return value",
            "fn main() -> i64:",
            "    return callee(7)",
        )
    )
    cells = _emit_ng_events(source)
    records = _event_records(cells)
    call_record = next(record for record in records if record[0] == 4 and record[2] == 7)
    call_record[5] = 99
    with pytest.raises(NGIRDecodeError, match="invalid function index"):
        decode_ng_ir_events(source.encode(), _flatten(records))

    records = _event_records(cells)
    call_record = next(record for record in records if record[0] == 4 and record[2] == 7)
    call_record[6] = 99
    with pytest.raises(NGIRDecodeError, match="argument-pool offset"):
        decode_ng_ir_events(source.encode(), _flatten(records))


def test_ng_ir_bridge_rejects_unknown_schema_and_partial_records() -> None:
    source = b"fn main() -> i64:\n    return 0\n"
    with pytest.raises(NGIRDecodeError, match="format header"):
        decode_ng_ir_events(source, [0, 2, 8, 0, 0, 0, 0, 0])
    with pytest.raises(NGIRDecodeError, match="partial record"):
        decode_ng_ir_events(source, [0, 1])
