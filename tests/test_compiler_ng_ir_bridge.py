from __future__ import annotations

import json
import platform
from pathlib import Path
import subprocess
import sys
from collections import Counter

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
from bootstrap.s3.ir import IRModule, IRType
from bootstrap.s3.ir_emulator import execute_ir
from bootstrap.s3 import ir_emulator
from bootstrap.s3.host_services import HostExecutionContext
from bootstrap.s3.pipeline import compile_source, compile_sources
from bootstrap.s3.verifier import verify_ir
from tests.test_compiler_ng_ir import _NG_SOURCE
from tools.qbe_oracle import translate_verified_ir


_ROOT = Path(__file__).parents[1]

_REAL_NG_MODULE_SOURCES = {
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


def _execute_ir_with_step_budget(
    module: IRModule,
    *,
    source_text: str,
    max_steps: int = 10_000_000,
) -> object:
    # The generated compiler harness is trusted test support; verify_ir is
    # required on the NG-produced target IR below, not on this large harness.
    functions = {function.name: function for function in module.functions}
    if "main" not in functions:
        raise AssertionError("compiler harness is missing main")
    static_strings = {item.id: item.value for item in module.static_strings}
    target_code = ir_emulator._execute_function.__code__
    steps = 0
    calls: Counter[str] = Counter()
    call_edges: Counter[tuple[str, str]] = Counter()
    previous_trace = sys.gettrace()

    def trace(frame, event, _argument):
        nonlocal steps
        if frame.f_code is target_code:
            function = frame.f_locals.get("function")
            if event == "call" and function is not None:
                calls[function.name] += 1
                parent = frame.f_back
                if parent is not None and parent.f_code is target_code:
                    caller = parent.f_locals.get("function")
                    if caller is not None:
                        call_edges[(caller.name, function.name)] += 1
            if event == "line":
                steps += 1
                if steps > max_steps:
                    execution = frame.f_locals["frame"]
                    function = frame.f_locals["function"]
                    arguments = []
                    for parameter in function.parameters:
                        cell = execution.registers[parameter.register]
                        value = cell.value
                        reference_cell = getattr(value, "cell", None)
                        owner = reference_cell.value if reference_cell is not None else value
                        owner = getattr(owner, "owner", owner)
                        length = getattr(owner, "length", None)
                        capacity = getattr(owner, "capacity", None)
                        arguments.append(
                            f"{parameter.name}={type(owner).__name__}"
                            f"(length={length},capacity={capacity})"
                        )
                    registers = []
                    for register in execution.function.registers:
                        cell = execution.registers[register.index]
                        if not cell.initialized:
                            continue
                        value = cell.value
                        reference_cell = getattr(value, "cell", None)
                        owner = reference_cell.value if reference_cell is not None else value
                        owner = getattr(owner, "owner", owner)
                        registers.append(
                            f"r{register.index}={type(owner).__name__}"
                            f"({getattr(owner, 'length', owner)})"
                        )
                    caller_frame = frame.f_back
                    caller_state = None
                    if caller_frame is not None and caller_frame.f_code is target_code:
                        caller_execution = caller_frame.f_locals["frame"]
                        caller_function = caller_frame.f_locals["function"]
                        caller_block = next(
                            item for item in caller_function.blocks
                            if item.name == caller_execution.block
                        )
                        caller_instruction = caller_block.instructions[caller_execution.index]
                        location = caller_instruction.location
                        source_line = None
                        if location is not None:
                            lines = source_text.splitlines()
                            if 0 < location.line <= len(lines):
                                source_line = lines[location.line - 1].strip()
                        caller_registers = []
                        for register in caller_function.registers:
                            cell = caller_execution.registers[register.index]
                            if not cell.initialized:
                                continue
                            value = cell.value
                            reference_cell = getattr(value, "cell", None)
                            owner = reference_cell.value if reference_cell is not None else value
                            owner = getattr(owner, "owner", owner)
                            if type(owner).__name__ in {"DynamicVector", "DynamicBytes"}:
                                caller_registers.append(
                                    f"r{register.index}={type(owner).__name__}"
                                    f"(length={getattr(owner, 'length', None)})"
                                )
                        caller_state = (
                            f"{caller_function.name}:{caller_execution.block}"
                            f"[{caller_execution.index}] {caller_instruction.opcode.value}; "
                            f"location={location}; source={source_line!r}; "
                            f"vectors={caller_registers}"
                        )
                    raise AssertionError(
                        f"IR execution exceeded {max_steps} steps in "
                        f"{function.name}:{execution.block}[{execution.index}]; "
                        f"arguments={arguments}; registers={registers}; "
                        f"calls={calls.most_common(12)}; "
                        f"call_edges={call_edges.most_common(12)}; "
                        f"caller={caller_state}"
                    )
            return trace
        return None

    sys.settrace(trace)
    try:
        try:
            return ir_emulator._execute_function(
                functions,
                functions["main"],
                (),
                (),
                static_strings,
                HostExecutionContext(),
            )
        except Exception as exc:
            traceback = exc.__traceback__
            last_s3_frame = None
            s3_stack = []
            while traceback is not None:
                if traceback.tb_frame.f_code is target_code:
                    last_s3_frame = traceback.tb_frame
                    stack_execution = traceback.tb_frame.f_locals["frame"]
                    stack_function = traceback.tb_frame.f_locals["function"]
                    stack_arguments = []
                    for parameter in stack_function.parameters:
                        cell = stack_execution.registers[parameter.register]
                        value = cell.value
                        reference_cell = getattr(value, "cell", None)
                        value = reference_cell.value if reference_cell is not None else value
                        value = getattr(value, "owner", value)
                        if type(value).__name__ in {"DynamicVector", "DynamicBytes", "DynamicCompositeVector"}:
                            description = f"{type(value).__name__}(length={getattr(value, 'length', None)})"
                        else:
                            description = repr(value)[:240]
                        stack_arguments.append(f"{parameter.name}={description}")
                    s3_stack.append(
                        f"{stack_function.name}:{stack_execution.block}"
                        f"[{stack_execution.index}] args={stack_arguments}"
                    )
                traceback = traceback.tb_next
            if last_s3_frame is None:
                raise
            execution = last_s3_frame.f_locals["frame"]
            function = last_s3_frame.f_locals["function"]
            block = next(item for item in function.blocks if item.name == execution.block)
            instruction = block.instructions[execution.index]
            arguments = []
            for parameter in function.parameters:
                cell = execution.registers[parameter.register]
                value = cell.value
                reference_cell = getattr(value, "cell", None)
                owner = reference_cell.value if reference_cell is not None else value
                owner = getattr(owner, "owner", owner)
                details = f"{type(owner).__name__}(length={getattr(owner, 'length', None)})"
                if type(owner).__name__ == "DynamicVector" and getattr(owner, "length", 0) <= 32:
                    details += f"(values={[owner.get(i) for i in range(owner.length)]})"
                arguments.append(f"{parameter.name}={details}")
            caller = last_s3_frame.f_back
            caller_details = None
            if caller is not None and caller.f_code is target_code:
                caller_execution = caller.f_locals["frame"]
                caller_function = caller.f_locals["function"]
                caller_block = next(item for item in caller_function.blocks if item.name == caller_execution.block)
                caller_instruction = caller_block.instructions[caller_execution.index]
                caller_details = (
                    f"{caller_function.name}:{caller_execution.block}"
                    f"[{caller_execution.index}] {caller_instruction.opcode.value} "
                    f"operands={caller_instruction.operands} "
                    f"location={caller_instruction.location}"
                )
            raise AssertionError(
                f"compiler harness raised {type(exc).__name__}: {exc}; "
                f"at {function.name}:{execution.block}[{execution.index}] "
                f"{instruction.opcode.value} operands={instruction.operands} "
                f"location={instruction.location}; arguments={arguments}; "
                f"caller={caller_details}; s3_stack={s3_stack}"
            ) from exc
    finally:
        sys.settrace(previous_trace)


def _emit_ng_events(source: str) -> list[int]:
    wrapper = f'''
fn main() -> vector<i64>:
    mut source_text: text = text_from_static({json.dumps(source)})
    mut source_bytes: bytes = bytes_from_text(&source_text)
    mut tokens: vector<NgToken> = vector_new<NgToken>(8192)
    mut types: vector<NgTypeDescriptor> = vector_new<NgTypeDescriptor>(16)
    mut records: vector<NgRecord> = vector_new<NgRecord>(1)
    mut fields: vector<NgField> = vector_new<NgField>(1)
    mut functions: vector<NgFunction> = vector_new<NgFunction>(128)
    mut parameters: vector<NgParameter> = vector_new<NgParameter>(512)
    mut nodes: vector<NgAstNode> = vector_new<NgAstNode>(16384)
    mut events: vector<i64> = vector_new<i64>(262144)
    discard ng_initialize_type_table(&mut types)
    mut status: i64 = ng_lex(&source_bytes, &mut tokens)
    match status <=> 0:
        -1:
            discard vector_push<i64>(&mut events, status)
            return events
        0:
            status = ng_parse_program_typed(&source_bytes, &tokens, &mut types, -1, -1, &mut functions, &mut parameters, &mut nodes)
            match status <=> 0:
                -1:
                    discard vector_push<i64>(&mut events, status)
                    return events
                0:
                    status = ng_emit_program(&source_bytes, &types, &records, &fields, &functions, &parameters, &nodes, &mut events)
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


def _run_ng_source_set_events(
    sources: dict[str, str],
    *,
    entry_module: str = "main",
    max_steps: int = 10_000_000,
) -> tuple[int, bytes, list[int]]:
    unit_initializers: list[str] = []
    for index, (path, contents) in enumerate(sources.items()):
        unit_initializers.extend(
            (
                f"mut path_{index}: text = text_from_static({json.dumps(path)})",
                f"mut text_{index}: text = text_from_static({json.dumps(contents)})",
                f"mut contents_{index}: bytes = bytes_from_text(&text_{index})",
                f"discard vector_push<NgSourceUnit>(&mut units, NgSourceUnit(path=path_{index}, contents=contents_{index}))",
            )
        )
    wrapper = f'''
fn main() -> vector<i64>:
    mut units: vector<NgSourceUnit> = vector_new<NgSourceUnit>({len(sources) + 1})
{chr(10).join("    " + line for line in unit_initializers)}
    mut source: bytes = bytes_new(32768)
    mut events: vector<i64> = vector_new<i64>(32768)
    mut result: vector<i64> = vector_new<i64>(65540)
    mut status: i64 = ng_emit_source_set(&units, text_from_static({json.dumps(entry_module)}), &mut source, &mut events)
    mut index: i64 = 0
    discard vector_push<i64>(&mut result, status)
    discard vector_push<i64>(&mut result, bytes_len(&source))
    while index < bytes_len(&source):
        discard vector_push<i64>(&mut result, to_i64(bytes_get(&source, index)))
        index = index + 1
    discard vector_push<i64>(&mut result, vector_len<i64>(&events))
    index = 0
    while index < vector_len<i64>(&events):
        discard vector_push<i64>(&mut result, vector_get<i64>(&events, index))
        index = index + 1
    return result
'''
    compilation = compile_source(_NG_SOURCE + "\n" + wrapper)
    assert compilation.ir is not None
    output = _execute_ir_with_step_budget(
        compilation.ir,
        source_text=_NG_SOURCE + "\n" + wrapper,
        max_steps=max_steps,
    )
    assert isinstance(output, DynamicVector)
    values = [int(value) for value in output]
    assert len(values) >= 2
    status, source_length = values[:2]
    source_end = 2 + source_length
    assert source_end < len(values)
    source = bytes(values[2:source_end])
    event_length = values[source_end]
    cells = values[source_end + 1 :]
    assert len(cells) == event_length
    return status, source, cells


def _emit_ng_source_set_events(
    sources: dict[str, str],
    *,
    entry_module: str = "main",
    max_steps: int = 10_000_000,
) -> tuple[bytes, list[int]]:
    status, source, cells = _run_ng_source_set_events(
        sources,
        entry_module=entry_module,
        max_steps=max_steps,
    )
    assert status == 0, f"S3C-NG source-set compilation failed with status {status}"
    return source, cells


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


def test_ng_ir_v3_preserves_bytes_text_and_decodes_v2() -> None:
    source = (
        "fn echo_bytes(value: bytes) -> bytes:\n    return value\n"
        "fn echo_text(value: text) -> text:\n    return value\n"
        "fn main() -> i64:\n    return 0\n"
    )
    reference_ir = compile_source(source).ir
    assert reference_ir is not None
    events = _emit_ng_events(source)
    assert _event_records(events)[0] == [0, 3, 8, 0, 0, 0, 0, 0]
    ng_ir = decode_ng_ir_events(source.encode("utf-8"), events)

    verify_ir(ng_ir)
    assert _canonical_structure(ng_ir) == _canonical_structure(reference_ir)

    legacy_source = b"main"
    legacy_events = [
        0, 1, 8, 0, 0, 0, 0, 0,
        1, 0, 5, 0, 0, 4, 1, 1,
    ]
    with pytest.raises(NGIRDecodeError, match="unknown type code 5"):
        decode_ng_ir_events(legacy_source, legacy_events)

    v2_events = [
        0, 2, 8, 0, 0, 0, 0, 0,
        1, 0, 6, 0, 0, 4, 1, 1,
        5, 0, 0, 0, 0, 0, 0, 0,
    ]
    v2_ir = decode_ng_ir_events(legacy_source, v2_events)
    assert v2_ir.functions[0].return_type is IRType.TEXT


def test_ng_ir_v3_preserves_vector_and_reference_signature_categories() -> None:
    source = (
        "fn identity(value: vector<i64>) -> vector<i64>:\n    return value\n"
        "fn borrow(value: &mut bytes) -> tryte:\n    return 0\n"
        "fn main() -> i64:\n    return 0\n"
    )
    reference_ir = compile_source(source).ir
    assert reference_ir is not None
    events = _emit_ng_events(source)
    records = _event_records(events)
    assert records[0] == [0, 3, 8, 0, 0, 0, 0, 0]
    assert any(record[0] == 12 and record[2] == 8 for record in records)
    assert any(record[0] == 12 and record[2] == 9 for record in records)

    ng_ir = decode_ng_ir_events(source.encode("utf-8"), events)
    verify_ir(ng_ir)
    assert _canonical_structure(ng_ir) == _canonical_structure(reference_ir)


def test_ng_ir_v3_transports_record_fields_without_semantic_resolution() -> None:
    sources = {
        "app.s3": (
            "module app\n"
            "record Pair:\n"
            "    left: i64\n"
            "    right: bytes\n"
            "fn main() -> i64:\n"
            "    return 0\n"
        ),
    }
    reference_ir = compile_sources(sources, entry_module="app").ir
    assert reference_ir is not None
    source, events = _emit_ng_source_set_events(sources, entry_module="app")
    records = _event_records(events)
    field_rows = [row for row in records if row[0] == 14]
    assert len(field_rows) == 2
    assert [source[row[3]:row[4]].decode("utf-8") for row in field_rows] == ["left", "right"]
    assert [row[2] for row in field_rows] == [0, 1]

    ng_ir = decode_ng_ir_events(source, events)
    verify_ir(ng_ir)
    assert _canonical_structure(ng_ir) == _canonical_structure(reference_ir)
    assert execute_ir(ng_ir) == execute_ir(reference_ir) == 0


def test_ng_ir_v3_fails_closed_for_unlowered_nominal_value() -> None:
    sources = {
        "app.s3": (
            "module app\n"
            "record Pair:\n"
            "    left: i64\n"
            "fn identity(value: Pair) -> Pair:\n"
            "    return value\n"
            "fn main() -> i64:\n"
            "    return 0\n"
        ),
    }
    source, events = _emit_ng_source_set_events(sources, entry_module="app")
    with pytest.raises(NGIRDecodeError, match="must be lowered to field cells"):
        decode_ng_ir_events(source, events)


def test_ng_ir_v3_rejects_malformed_composite_descriptors() -> None:
    source_text = (
        "fn identity(value: vector<i64>) -> vector<i64>:\n    return value\n"
        "fn borrow(value: &mut bytes) -> tryte:\n    return 0\n"
        "fn main() -> i64:\n    return 0\n"
    )
    source = source_text.encode("utf-8")
    events = _emit_ng_events(source_text)

    vector_events = _event_records(events)
    vector_descriptor = next(row for row in vector_events if row[0] == 12 and row[2] == 8)
    vector_descriptor[7] = 999
    with pytest.raises(NGIRDecodeError, match="malformed vector type descriptor"):
        decode_ng_ir_events(source, _flatten(vector_events))

    reference_events = _event_records(events)
    reference_descriptor = next(row for row in reference_events if row[0] == 12 and row[2] == 9)
    reference_details = next(row for row in reference_events if row[0] == 13 and row[1] == reference_descriptor[1])
    reference_details[3] = 2
    with pytest.raises(NGIRDecodeError, match="malformed reference type descriptor"):
        decode_ng_ir_events(source, _flatten(reference_events))


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


def test_ng_source_set_imports_exported_function_and_matches_reference() -> None:
    sources = {
        "main.s3": (
            "module main\n"
            "from math import increment as add_one\n"
            "fn main() -> i64:\n"
            "    return add_one(6)\n"
        ),
        "math.s3": (
            "module math\n"
            "export fn increment(value: i64) -> i64:\n"
            "    return value + 1\n"
        ),
    }
    reference = compile_sources(sources, entry_module="main").ir
    assert reference is not None

    source, cells = _emit_ng_source_set_events(sources)
    ng_ir = decode_ng_ir_events(source, cells)

    verify_ir(ng_ir)
    assert _canonical_structure(ng_ir) == _canonical_structure(reference)
    assert execute_ir(ng_ir) == execute_ir(reference) == 7
    assembly = generate_assembly(ng_ir)
    assert ".globl s3_main" in generate_native_assembly(assembly)
    assert "function" in translate_verified_ir(ng_ir)


def test_ng_source_set_accepts_qualified_module_identity() -> None:
    module_name = "selfhost.compiler_ng.lexer"
    sources = {
        "lexer.s3": (
            f"module {module_name}\n"
            "export fn main() -> i64:\n"
            "    return 7\n"
        ),
    }
    reference = compile_sources(sources, entry_module=module_name).ir
    assert reference is not None

    source, cells = _emit_ng_source_set_events(sources, entry_module=module_name)
    ng_ir = decode_ng_ir_events(source, cells)

    verify_ir(ng_ir)
    assert _canonical_structure(ng_ir) == _canonical_structure(reference)
    assert execute_ir(ng_ir) == execute_ir(reference) == 7


def _character_class_self_module_sources() -> dict[str, str]:
    character_module = (_ROOT / "selfhost/compiler_ng/character_classes.s3").read_text(
        encoding="utf-8"
    )
    return {
        "app.s3": (
            "module app\n"
            "from selfhost.compiler_ng.character_classes import ng_is_digit\n"
            "fn main() -> i64:\n"
            "    match ng_is_digit(52):\n"
            "        -1:\n"
            "            return 1\n"
            "        0:\n"
            "            return 0\n"
            "        1:\n"
            "            return 0\n"
        ),
        "character_classes.s3": character_module,
    }


def test_ng_compiles_its_own_character_class_module_through_source_set() -> None:
    sources = _character_class_self_module_sources()
    reference = compile_sources(sources, entry_module="app").ir
    assert reference is not None

    source, cells = _emit_ng_source_set_events(sources, entry_module="app", max_steps=50_000_000)
    ng_ir = decode_ng_ir_events(source, cells)
    verify_ir(ng_ir)

    assert _canonical_structure(ng_ir) == _canonical_structure(reference)
    assert len(ng_ir.functions) == 3
    assert execute_ir(ng_ir) == execute_ir(reference) == 1

    reversed_source, reversed_cells = _emit_ng_source_set_events(
        dict(reversed(tuple(sources.items()))), entry_module="app", max_steps=50_000_000
    )
    reversed_ir = decode_ng_ir_events(reversed_source, reversed_cells)
    verify_ir(reversed_ir)
    assert _canonical_structure(reversed_ir) == _canonical_structure(ng_ir)

    assembly = generate_assembly(ng_ir)
    emulator = Emulator()
    emulator.validate(assembly, entry="main")
    assert emulator.execute(assembly) == 1
    assert ".globl s3_main" in generate_native_assembly(assembly)
    assert "function" in translate_verified_ir(ng_ir)


@pytest.mark.s3_native
@pytest.mark.skipif(
    platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"},
    reason="S3 x86-64 native execution is qualified on Linux x86-64",
)
def test_ng_compiled_self_module_executes_linux_x86_64(tmp_path: Path) -> None:
    sources = _character_class_self_module_sources()
    reference = compile_sources(sources, entry_module="app").ir
    assert reference is not None
    source, cells = _emit_ng_source_set_events(sources, entry_module="app", max_steps=50_000_000)
    ng_ir = decode_ng_ir_events(source, cells)
    verify_ir(ng_ir)
    assert _canonical_structure(ng_ir) == _canonical_structure(reference)
    assert execute_ir(ng_ir) == execute_ir(reference) == 1

    native_source = generate_native_assembly(generate_assembly(ng_ir))
    executable = NativeToolchain.detect().build(native_source, tmp_path / "ng-self-module")
    completed = subprocess.run([str(executable)], check=False, capture_output=True, text=True, timeout=30)
    assert completed.returncode == 0, completed.stderr
    assert completed.stderr == ""
    assert completed.stdout == "program returned: 1\n"


@pytest.mark.parametrize(
    ("sources", "expected_status"),
    (
        (
            {
                "main.s3": "module main\nfrom absent import value\nfn main() -> i64:\n    return value()\n",
            },
            -3,
        ),
        (
            {
                "main.s3": "module main\nfrom math import missing\nfn main() -> i64:\n    return missing()\n",
                "math.s3": "module math\nexport fn present() -> i64:\n    return 1\n",
            },
            -4,
        ),
        (
            {
                "main.s3": "module main\nfrom math import hidden\nfn main() -> i64:\n    return hidden()\n",
                "math.s3": "module math\nfn hidden() -> i64:\n    return 1\n",
            },
            -5,
        ),
        (
            {
                "main.s3": "module main\nfn main() -> i64:\n    return 1\n",
                "first.s3": "module math\nexport fn first() -> i64:\n    return 1\n",
                "second.s3": "module math\nexport fn second() -> i64:\n    return 2\n",
            },
            -2,
        ),
        (
            {
                "main.s3": "module main\nfrom helper import value\nfn main() -> i64:\n    return value()\n",
                "helper.s3": "module helper\nfrom main import main as entry\nexport fn value() -> i64:\n    return entry()\n",
            },
            -6,
        ),
        (
            {
                "main.s3": "module main\nfrom math import value\nfn main() -> i64:\n    return value()\n",
                "math.s3": "module math\nexport fn value(argument: i64) -> i64:\n    return argument\n",
            },
            -14,
        ),
        (
            {
                "main.s3": "module main\nfrom math import value\nfn flag() -> trit:\n    return 1\nfn main() -> i64:\n    return value(flag())\n",
                "math.s3": "module math\nexport fn value(argument: i64) -> i64:\n    return argument\n",
            },
            -14,
        ),
    ),
    ids=(
        "missing-module",
        "missing-symbol",
        "private-symbol",
        "duplicate-module-identity",
        "dependency-cycle",
        "cross-module-arity",
        "cross-module-type",
    ),
)
def test_ng_source_set_rejects_invalid_module_graphs_and_calls(
    sources: dict[str, str], expected_status: int
) -> None:
    status, _source, _cells = _run_ng_source_set_events(sources)
    assert status == expected_status


def test_ng_real_multimodule_program_is_order_independent_and_matches_reference() -> None:
    reference = compile_sources(_REAL_NG_MODULE_SOURCES, entry_module="app").ir
    assert reference is not None

    source, cells = _emit_ng_source_set_events(_REAL_NG_MODULE_SOURCES, entry_module="app")
    ng_ir = decode_ng_ir_events(source, cells)
    verify_ir(ng_ir)
    assert _canonical_structure(ng_ir) == _canonical_structure(reference)
    assert execute_ir(ng_ir) == execute_ir(reference) == 16

    reversed_sources = dict(reversed(tuple(_REAL_NG_MODULE_SOURCES.items())))
    reversed_source, reversed_cells = _emit_ng_source_set_events(reversed_sources, entry_module="app")
    reversed_ir = decode_ng_ir_events(reversed_source, reversed_cells)
    verify_ir(reversed_ir)
    assert _canonical_structure(reversed_ir) == _canonical_structure(ng_ir)

    assembly = generate_assembly(ng_ir)
    emulator = Emulator()
    emulator.validate(assembly, entry="main")
    assert emulator.execute(assembly) == 16
    assert ".globl s3_main" in generate_native_assembly(assembly)
    assert "function" in translate_verified_ir(ng_ir)


@pytest.mark.s3_native
@pytest.mark.skipif(
    platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"},
    reason="S3 x86-64 native execution is qualified on Linux x86-64",
)
def test_ng_real_multimodule_program_executes_linux_x86_64(tmp_path: Path) -> None:
    reference = compile_sources(_REAL_NG_MODULE_SOURCES, entry_module="app").ir
    assert reference is not None
    source, cells = _emit_ng_source_set_events(_REAL_NG_MODULE_SOURCES, entry_module="app")
    ng_ir = decode_ng_ir_events(source, cells)
    verify_ir(ng_ir)
    assert _canonical_structure(ng_ir) == _canonical_structure(reference)
    assert execute_ir(ng_ir) == execute_ir(reference) == 16

    native_source = generate_native_assembly(generate_assembly(ng_ir))
    executable = NativeToolchain.detect().build(native_source, tmp_path / "ng-multimodule")
    completed = subprocess.run([str(executable)], check=False, capture_output=True, text=True, timeout=30)
    assert completed.returncode == 0, completed.stderr
    assert completed.stderr == ""
    assert completed.stdout == "program returned: 16\n"


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
        decode_ng_ir_events(source, [0, 4, 8, 0, 0, 0, 0, 0])
    with pytest.raises(NGIRDecodeError, match="partial record"):
        decode_ng_ir_events(source, [0, 1])
