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
from bootstrap.s3.diagnostics import SemanticError
from bootstrap.s3.dynamic import (
    DynamicCompositeVector,
    DynamicBytes,
    DynamicVector,
    f64_vector_new,
    i64_vector_new,
    tryte_vector_new,
)
from bootstrap.s3.emulator import Emulator
from bootstrap.s3.ir import IRModule, IROpcode, IRType
from bootstrap.s3.ir_emulator import ReferenceValue, execute_ir
from bootstrap.s3 import ir_emulator
from bootstrap.s3.host_services import HostExecutionContext
from bootstrap.s3.pipeline import compile_source, compile_sources
from bootstrap.s3.verifier import verify_ir
from tests.test_compiler_ng_ir import _NG_SOURCE
from tools.qbe_oracle import QBETranslationError, translate_verified_ir


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
    entry: str = "main",
    metrics: dict[str, object] | None = None,
) -> object:
    # The generated compiler harness is trusted test support; verify_ir is
    # required on the NG-produced target IR below, not on this large harness.
    functions = {function.name: function for function in module.functions}
    if entry not in functions:
        raise AssertionError(f"compiler harness is missing entry function {entry!r}")
    static_strings = {item.id: item.value for item in module.static_strings}
    target_code = ir_emulator._execute_function.__code__
    steps = 0
    calls: Counter[str] = Counter()
    call_edges: Counter[tuple[str, str]] = Counter()
    line_counts: Counter[str] = Counter()
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
                if function is not None:
                    line_counts[function.name] += 1
                if steps > max_steps:
                    execution = frame.f_locals.get("frame")
                    function = frame.f_locals.get("function")
                    if execution is None or function is None:
                        return trace
                    if any(
                        not execution.registers[parameter.register].initialized
                        for parameter in function.parameters
                    ):
                        return trace
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
                        f"hot_functions={line_counts.most_common(12)}; "
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
                functions[entry],
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
                    stack_execution = traceback.tb_frame.f_locals.get("frame")
                    stack_function = traceback.tb_frame.f_locals.get("function")
                    if stack_execution is None or stack_function is None:
                        traceback = traceback.tb_next
                        continue
                    last_s3_frame = traceback.tb_frame
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
        if metrics is not None:
            metrics.update(
                {
                    "steps": steps,
                    "calls": dict(calls),
                    "call_edges": dict(call_edges),
                    "line_counts": dict(line_counts),
                }
            )
        sys.settrace(previous_trace)


def _emit_ng_events(source: str) -> list[int]:
    wrapper = f'''
fn main() -> vector<i64>:
    mut source_text: text = text_from_static({json.dumps(source, ensure_ascii=False)})
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
                    status = ng_resolve_address_nodes(&source_bytes, &mut types, &functions, &parameters, &mut nodes)
                    match status <=> 0:
                        -1:
                            discard vector_push<i64>(&mut events, status)
                            return events
                        0:
                            status = ng_emit_program(&source_bytes, &types, &records, &fields, &functions, &parameters, &mut nodes, &mut events)
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
    metrics: dict[str, object] | None = None,
) -> tuple[int, bytes, list[int]]:
    source_capacity = max(
        32768,
        sum(
            len(path.encode("utf-8")) + len(contents.encode("utf-8"))
            for path, contents in sources.items()
        )
        + 8192,
    )
    event_capacity = max(32768, source_capacity * 8)
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
record NgSourceSetOutput:
    status: i64
    source: bytes
    events: vector<i64>

fn main() -> i64:
    return 0

fn collect_ng_source_set() -> NgSourceSetOutput:
    mut units: vector<NgSourceUnit> = vector_new<NgSourceUnit>({len(sources) + 1})
{chr(10).join("    " + line for line in unit_initializers)}
    mut source: bytes = bytes_new({source_capacity})
    mut events: vector<i64> = vector_new<i64>({event_capacity})
    mut status: i64 = ng_emit_source_set(&units, text_from_static({json.dumps(entry_module)}), &mut source, &mut events)
    return NgSourceSetOutput(status=status, source=source, events=events)
'''
    compilation = compile_source(_NG_SOURCE + "\n" + wrapper)
    assert compilation.ir is not None
    output = _execute_ir_with_step_budget(
        compilation.ir,
        source_text=_NG_SOURCE + "\n" + wrapper,
        max_steps=max_steps,
        entry="collect_ng_source_set",
        metrics=metrics,
    )
    assert isinstance(output, tuple) and len(output) == 3
    status, source, events = output
    assert isinstance(source, DynamicBytes)
    assert isinstance(events, DynamicVector)
    return int(status), source.to_bytes(), [int(value) for value in events]


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
    if status != 0:
        raise AssertionError(
            f"S3C-NG source-set compilation failed with status {status}; "
            f"event_count={len(cells)}; event_tail={cells[-80:]}"
        )
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
                        (
                            None
                            if instruction.opcode.value == "call" and instruction.results
                            else instruction.result
                        ),
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


def _first_structure_difference(left: object, right: object, path: str = "root") -> str:
    if type(left) is not type(right):
        return f"{path}: {type(left).__name__} != {type(right).__name__}"
    if isinstance(left, tuple) and isinstance(right, tuple):
        if len(left) != len(right):
            return (
                f"{path}: tuple lengths {len(left)} != {len(right)}"
            )
        for index, (left_item, right_item) in enumerate(zip(left, right)):
            if left_item != right_item:
                return _first_structure_difference(left_item, right_item, f"{path}[{index}]")
        return f"{path}: values differ"
    left_text = repr(left)
    right_text = repr(right)
    return f"{path}: {left_text[:240]} != {right_text[:240]}"


def _event_records(cells: list[int]) -> list[list[int]]:
    assert len(cells) % 8 == 0
    return [cells[index : index + 8] for index in range(0, len(cells), 8)]


def _legacy_event_records(records: list[list[int]], version: int) -> list[list[int]]:
    legacy = [
        record.copy()
        for record in records
        if not (version < 14 and record[0] == 22)
        and not (version < 15 and record[0] == 23)
        and not (version < 17 and record[0] == 24)
    ]
    if version < 17:
        for record in legacy:
            if record[0] == 4 and record[2] == 6:
                record[6] = -1
    legacy[0][1] = version
    return legacy


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


def test_ng_ir_v7_preserves_bytes_text_and_decodes_v2() -> None:
    source = (
        "fn echo_bytes(value: bytes) -> bytes:\n    return value\n"
        "fn echo_text(value: text) -> text:\n    return value\n"
        "fn main() -> i64:\n    return 0\n"
    )
    reference_ir = compile_source(source).ir
    assert reference_ir is not None
    events = _emit_ng_events(source)
    assert _event_records(events)[0] == [0, 19, 8, 0, 0, 0, 0, 0]
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


def test_ng_ir_v7_preserves_vector_and_reference_signature_categories() -> None:
    source = (
        "fn identity(value: vector<i64>) -> vector<i64>:\n    return value\n"
        "fn borrow(value: &mut bytes) -> tryte:\n    return 0\n"
        "fn main() -> i64:\n    return 0\n"
    )
    reference_ir = compile_source(source).ir
    assert reference_ir is not None
    events = _emit_ng_events(source)
    records = _event_records(events)
    assert records[0] == [0, 19, 8, 0, 0, 0, 0, 0]
    assert any(record[0] == 12 and record[2] == 8 for record in records)
    assert any(record[0] == 12 and record[2] == 9 for record in records)

    ng_ir = decode_ng_ir_events(source.encode("utf-8"), events)
    verify_ir(ng_ir)
    assert _canonical_structure(ng_ir) == _canonical_structure(reference_ir)


def test_ng_ir_v12_dereference_and_reborrow_match_reference_ir() -> None:
    source = (
        "fn read(value: &i64) -> i64:\n"
        "    return *value\n"
        "fn read_mutable(value: &mut i64) -> i64:\n"
        "    return *value\n"
        "fn read_through_reborrow(value: &mut i64) -> i64:\n"
        "    return read(&*value)\n"
        "fn main() -> i64:\n"
        "    mut value: i64 = 73\n"
        "    return read_mutable(&mut value) + read_through_reborrow(&mut value) - 73\n"
    )
    reference_ir = compile_source(source).ir
    assert reference_ir is not None

    events = _emit_ng_events(source)
    records = _event_records(events)
    assert records[0] == [0, 19, 8, 0, 0, 0, 0, 0]
    assert any(record[0] == 4 and record[2] == 18 for record in records)

    ng_ir = decode_ng_ir_events(source.encode("utf-8"), events)
    verify_ir(ng_ir)
    assert _canonical_structure(ng_ir) == _canonical_structure(reference_ir)
    assert execute_ir(ng_ir) == execute_ir(reference_ir) == 73

    mutable_reader = next(function for function in ng_ir.functions if function.name == "read_mutable")
    assert mutable_reader.parameters[0].reference_mutable is True
    mutable_load = next(
        instruction for instruction in mutable_reader.instructions
        if instruction.opcode.value == "reference_load"
    )
    assert mutable_load.reference_target is IRType.I64
    assert mutable_load.reference_mutable is False

    legacy = [record.copy() for record in records if record[0] != 22]
    legacy[0][1] = 11
    with pytest.raises(NGIRDecodeError, match="REFERENCE_LOAD opcode requires NG IR V12"):
        decode_ng_ir_events(source.encode("utf-8"), _flatten(legacy))

    malformed = [record.copy() for record in records]
    load = next(record for record in malformed if record[0] == 4 and record[2] == 18)
    loaded_register = next(
        record for record in malformed
        if record[0] == 3 and record[1] == load[1] and record[2] == load[3]
    )
    loaded_register[3] = 2
    with pytest.raises(NGIRDecodeError, match="REFERENCE_LOAD result type disagrees"):
        decode_ng_ir_events(source.encode("utf-8"), _flatten(malformed))


def test_ng_ir_v19_mutable_dereference_assignment_matches_reference_ir() -> None:
    source = (
        "fn bump(value: &mut i64) -> i64:\n"
        "    *value = *value + 1\n"
        "    return *value\n"
        "fn main() -> i64:\n"
        "    mut value: i64 = 41\n"
        "    return bump(&mut value)\n"
    )
    reference_ir = compile_source(source).ir
    assert reference_ir is not None

    records = _event_records(_emit_ng_events(source))
    assert records[0] == [0, 19, 8, 0, 0, 0, 0, 0]
    stores = [record for record in records if record[0] == 4 and record[2] == 21]
    assert len(stores) == 1

    ng_ir = decode_ng_ir_events(source.encode("utf-8"), _flatten(records))
    verify_ir(ng_ir)
    assert _canonical_structure(ng_ir) == _canonical_structure(reference_ir)
    assert execute_ir(ng_ir) == execute_ir(reference_ir) == 42

    store = next(
        instruction
        for function in ng_ir.functions
        for instruction in function.instructions
        if instruction.opcode is IROpcode.REFERENCE_STORE
    )
    assert store.reference_target is IRType.I64
    assert store.reference_mutable is True

    legacy = [record.copy() for record in records]
    legacy[0][1] = 18
    with pytest.raises(NGIRDecodeError, match="REFERENCE_STORE opcode requires NG IR format V19"):
        decode_ng_ir_events(source.encode("utf-8"), _flatten(legacy))

    immutable = [record.copy() for record in records]
    reference_type = next(record for record in immutable if record[0] == 12 and record[2] == 9)
    reference_metadata = next(
        record for record in immutable if record[0] == 13 and record[1] == reference_type[1]
    )
    reference_metadata[3] = 0
    with pytest.raises(NGIRDecodeError, match="REFERENCE_STORE operand must be a mutable reference"):
        decode_ng_ir_events(source.encode("utf-8"), _flatten(immutable))


def test_ng_ir_resolves_outer_local_reference_from_while_scope() -> None:
    source = (
        "fn read(value: &i64) -> i64:\n"
        "    return *value\n"
        "fn run(flag: trit) -> i64:\n"
        "    mut local: i64 = 73\n"
        "    while flag:\n"
        "        discard read(&local)\n"
        "        break\n"
        "    return local\n"
        "fn main() -> i64:\n"
        "    return run(0)\n"
    )
    reference_ir = compile_source(source).ir
    assert reference_ir is not None

    events = _emit_ng_events(source)
    ng_ir = decode_ng_ir_events(source.encode("utf-8"), events)
    verify_ir(ng_ir)

    assert _canonical_structure(ng_ir) == _canonical_structure(reference_ir)
    assert execute_ir(ng_ir) == execute_ir(reference_ir) == 73


def test_ng_ir_v13_static_strings_match_reference_ir_and_fail_closed() -> None:
    accented = chr(233)
    source = (
        "fn main() -> i64:\n"
        '    mut first: text = text_from_static("z")\n'
        f'    mut second: text = text_from_static("{accented}\\n")\n'
        '    mut repeated: text = text_from_static("z")\n'
        "    return 0\n"
    )
    reference = compile_source(source).ir
    assert reference is not None
    records = _event_records(_emit_ng_events(source))
    assert records[0] == [0, 19, 8, 0, 0, 0, 0, 0]
    string_instructions = [record for record in records if record[0] == 4 and record[2] == 19]
    assert len(string_instructions) == 3

    decoded = decode_ng_ir_events(source.encode("utf-8"), _flatten(records))
    verify_ir(decoded)
    assert _canonical_structure(decoded) == _canonical_structure(reference)
    assert [(item.id, item.value) for item in decoded.static_strings] == [
        ("s0", "z"),
        ("s1", accented + "\n"),
    ]
    const_strings = [
        instruction.static_string
        for block in decoded.functions[0].blocks
        for instruction in block.instructions
        if instruction.opcode.value == "const_str"
    ]
    assert const_strings == ["s0", "s1", "s0"]
    assert execute_ir(decoded) == execute_ir(reference)

    legacy = [record.copy() for record in records if record[0] != 22]
    legacy[0][1] = 12
    with pytest.raises(NGIRDecodeError, match="STRING type descriptor requires NG IR V13"):
        decode_ng_ir_events(source.encode("utf-8"), _flatten(legacy))

    malformed_span = [record.copy() for record in records]
    malformed_const = next(record for record in malformed_span if record[0] == 4 and record[2] == 19)
    malformed_const[6] = len(source.encode("utf-8")) + 1
    with pytest.raises(NGIRDecodeError, match="CONST_STR has an invalid source span"):
        decode_ng_ir_events(source.encode("utf-8"), _flatten(malformed_span))

    wrong_type = [record.copy() for record in records]
    wrong_const = next(record for record in wrong_type if record[0] == 4 and record[2] == 19)
    wrong_result = wrong_const[3]
    register = next(
        record for record in wrong_type
        if record[0] == 3 and record[1] == wrong_const[1] and record[2] == wrong_result
    )
    register[3] = 6
    with pytest.raises(NGIRDecodeError, match="CONST_STR result must use the STRING type descriptor"):
        decode_ng_ir_events(source.encode("utf-8"), _flatten(wrong_type))


def test_ng_ir_v7_relational_opcode_executes_and_is_not_valid_in_v6() -> None:
    cases = (
        ("i64", 2, "==", 2, -1),
        ("i64", 2, "!=", 3, -1),
        ("i64", 2, "<", 3, -1),
        ("i64", 2, "<=", 2, -1),
        ("i64", 3, ">", 2, -1),
        ("i64", 2, ">=", 3, 0),
        ("f64", 2.0, "==", 2.0, -1),
        ("f64", 2.0, "!=", 3.0, -1),
        ("f64", 2.0, "<", 3.0, -1),
        ("f64", 2.0, "<=", 2.0, -1),
        ("f64", 3.0, ">", 2.0, -1),
        ("f64", 2.0, ">=", 3.0, 0),
    )
    definitions = [
        f"fn relation_{index}(left: {type_name}, right: {type_name}) -> trit:\n"
        f"    return left {operator} right"
        for index, (type_name, _, operator, _, _) in enumerate(cases)
    ]
    source = "\n".join((*definitions, "fn main() -> i64:\n    return 0"))
    reference = compile_source(source).ir
    assert reference is not None
    records = _event_records(_emit_ng_events(source))
    assert records[0] == [0, 19, 8, 0, 0, 0, 0, 0]
    relation_records = [record for record in records if record[0] == 4 and record[2] == 15]
    assert len(relation_records) == len(cases)
    assert {record[7] for record in relation_records} == set(range(6))

    encoded = _flatten(records)
    decoded = decode_ng_ir_events(source.encode("utf-8"), encoded)
    verify_ir(decoded)
    functions = {function.name: function for function in decoded.functions}
    reference_functions = {function.name: function for function in reference.functions}
    for index, (_, left, _, right, expected) in enumerate(cases):
        function = functions[f"relation_{index}"]
        reference_function = reference_functions[f"relation_{index}"]
        actual = ir_emulator._execute_function(
            functions, function, (left, right), (), {}, HostExecutionContext()
        )
        expected_from_reference = ir_emulator._execute_function(
            reference_functions,
            reference_function,
            (left, right),
            (),
            {},
            HostExecutionContext(),
        )
        assert actual == expected_from_reference == expected
    assert execute_ir(decoded) == 0

    records = _legacy_event_records(records, 6)
    with pytest.raises(NGIRDecodeError, match="RELATE opcode requires NG IR format V7"):
        decode_ng_ir_events(source.encode("utf-8"), _flatten(records))


def test_ng_ir_v7_relational_match_selector_preserves_distinct_arms() -> None:
    source = (
        "fn classify(value: i64) -> i64:\n"
        "    match value == 95:\n"
        "        -1:\n"
        "            return 11\n"
        "        0:\n"
        "            return 22\n"
        "        1:\n"
        "            return 33\n"
        "fn main() -> i64:\n"
        "    return 0\n"
    )
    reference = compile_source(source).ir
    assert reference is not None
    ng_ir = decode_ng_ir_events(source.encode("utf-8"), _emit_ng_events(source))
    verify_ir(ng_ir)
    ng_functions = {function.name: function for function in ng_ir.functions}
    reference_functions = {function.name: function for function in reference.functions}
    ng_classify = ng_functions["classify"]
    reference_classify = reference_functions["classify"]
    assert _canonical_structure(ng_ir) == _canonical_structure(reference)
    for value, expected in ((94, 22), (95, 11), (96, 22)):
        assert ir_emulator._execute_function(
            ng_functions, ng_classify, (value,), (), {}, HostExecutionContext()
        ) == expected
        assert ir_emulator._execute_function(
            reference_functions,
            reference_classify,
            (value,),
            (),
            {},
            HostExecutionContext(),
        ) == expected


def test_ng_ir_v7_relational_match_contextualizes_trit_literal() -> None:
    source = (
        "fn classify(value: trit) -> i64:\n"
        "    match value < 0:\n"
        "        -1:\n"
        "            return 11\n"
        "        0:\n"
        "            return 22\n"
        "        1:\n"
        "            return 33\n"
        "fn main() -> i64:\n"
        "    return classify(-1)\n"
    )
    reference = compile_source(source).ir
    assert reference is not None
    ng_ir = decode_ng_ir_events(source.encode("utf-8"), _emit_ng_events(source))
    verify_ir(ng_ir)
    assert _canonical_structure(ng_ir) == _canonical_structure(reference)

    functions = {function.name: function for function in ng_ir.functions}
    classify = functions["classify"]
    assert tuple(
        ir_emulator._execute_function(
            functions, classify, (value,), (), {}, HostExecutionContext()
        )
        for value in (-1, 0, 1)
    ) == (11, 22, 22)


def test_ng_emits_and_executes_while_with_nested_match_and_backedge() -> None:
    source = (
        "fn increment(value: i64) -> i64:\n"
        "    return value + 1\n"
        "fn main() -> i64:\n"
        "    mut index: i64 = 0\n"
        "    while index < 3:\n"
        "        match index == 1:\n"
        "            -1:\n"
        "                index = increment(index)\n"
        "            0:\n"
        "                index = increment(index)\n"
        "            1:\n"
        "                index = increment(index)\n"
        "    return index\n"
    )
    reference = compile_source(source).ir
    assert reference is not None
    events = _emit_ng_events(source)
    ng_ir = decode_ng_ir_events(source.encode("utf-8"), events)

    verify_ir(ng_ir)
    assert execute_ir(ng_ir) == execute_ir(reference) == 3
    assert _canonical_structure(ng_ir) == _canonical_structure(reference)

    function = next(item for item in ng_ir.functions if item.name == "main")
    loop_header = next(
        block.name
        for block in function.blocks
        if any(instruction.opcode.value == "branch3" for instruction in block.instructions)
        and sum(
            instruction.opcode.value == "jump" and instruction.targets == (block.name,)
            for candidate in function.blocks
            for instruction in candidate.instructions
        ) >= 2
    )
    backedges = [
        instruction
        for block in function.blocks
        for instruction in block.instructions
        if instruction.opcode.value == "jump" and instruction.targets == (loop_header,)
    ]
    assert len(backedges) >= 2  # preheader entry and loop-body backedge


def test_ng_local_declarations_in_match_arms_are_scoped_per_arm() -> None:
    source = (
        "fn choose(flag: trit) -> i64:\n"
        "    mut result: i64 = 5\n"
        "    match flag:\n"
        "        -1:\n"
        "            mut result: i64 = 11\n"
        "            result = result + 1\n"
        "        0:\n"
        "            mut result: i64 = 22\n"
        "            result = result + 1\n"
        "        1:\n"
        "            mut result: i64 = 33\n"
        "            result = result + 1\n"
        "    return result\n"
        "fn main() -> i64:\n"
        "    return choose(-1) + choose(0) + choose(1)\n"
    )
    reference = compile_source(source).ir
    assert reference is not None
    ng_ir = decode_ng_ir_events(source.encode("utf-8"), _emit_ng_events(source))

    verify_ir(ng_ir)
    assert _canonical_structure(ng_ir) == _canonical_structure(reference)
    assert execute_ir(ng_ir) == execute_ir(reference) == 15


def test_ng_loop_local_declarations_do_not_leak_after_loop() -> None:
    source = (
        "fn main() -> i64:\n"
        "    mut result: i64 = 7\n"
        "    mut index: i64 = 0\n"
        "    while index < 3:\n"
        "        mut result: i64 = 20 + index\n"
        "        index = index + 1\n"
        "    return result * 10 + index\n"
    )
    reference = compile_source(source).ir
    assert reference is not None
    ng_ir = decode_ng_ir_events(source.encode("utf-8"), _emit_ng_events(source))

    verify_ir(ng_ir)
    assert _canonical_structure(ng_ir) == _canonical_structure(reference)
    assert execute_ir(ng_ir) == execute_ir(reference) == 73


def test_ng_break_in_nested_match_targets_the_nearest_loop_exit() -> None:
    source = (
        "fn classify(value: trit) -> i64:\n"
        "    mut count: i64 = 0\n"
        "    while count < 3:\n"
        "        match value:\n"
        "            -1:\n"
        "                break\n"
        "            0:\n"
        "                count = count + 1\n"
        "            1:\n"
        "                count = count + 1\n"
        "    return count\n"
        "fn main() -> i64:\n"
        "    return classify(-1)\n"
    )
    reference = compile_source(source).ir
    assert reference is not None
    events = _emit_ng_events(source)
    ng_ir = decode_ng_ir_events(source.encode("utf-8"), events)
    verify_ir(ng_ir)

    functions = {function.name: function for function in ng_ir.functions}
    classify = functions["classify"]
    post_loop_return_blocks = {
        block.name
        for block in classify.blocks
        if any(instruction.opcode.value == "return" for instruction in block.instructions)
    }
    break_targets = {
        instruction.targets[0]
        for block in classify.blocks
        for instruction in block.instructions
        if instruction.opcode.value == "jump"
        and instruction.targets
            and instruction.targets[0] in post_loop_return_blocks
    }
    assert len(post_loop_return_blocks) == 1
    assert break_targets == post_loop_return_blocks

    for value, expected in ((-1, 0), (0, 3), (1, 3)):
        actual = ir_emulator._execute_function(
            functions,
            classify,
            (value,),
            (),
            {},
            HostExecutionContext(),
        )
        assert actual == expected
    assert execute_ir(ng_ir) == execute_ir(reference) == 0


def test_ng_ir_v7_resolves_aggregate_calls_by_complete_ng_type_identity() -> None:
    sources = {
        "app.s3": (
            "module app\n"
            "record TokenLike:\n"
            "    id: i64\n"
            "fn keep_tokens(value: vector<TokenLike>) -> i64:\n"
            "    return 7\n"
            "fn relay_tokens(value: vector<TokenLike>) -> i64:\n"
            "    return keep_tokens(value)\n"
            "fn preserve_token_vector(value: vector<TokenLike>) -> vector<TokenLike>:\n"
            "    return value\n"
            "fn relay_token_vector(value: vector<TokenLike>) -> vector<TokenLike>:\n"
            "    return preserve_token_vector(value)\n"
            "fn keep_token(value: &TokenLike) -> i64:\n"
            "    return 11\n"
            "fn relay_token(value: &TokenLike) -> i64:\n"
            "    return keep_token(value)\n"
            "fn relay_read_id(value: &TokenLike) -> i64:\n"
            "    return read_id(value)\n"
            "fn read_id(value: &TokenLike) -> i64:\n"
            "    return value.id\n"
            "fn keep_mut_tokens(value: &mut vector<TokenLike>) -> i64:\n"
            "    return 13\n"
            "fn relay_mut_tokens(value: &mut vector<TokenLike>) -> i64:\n"
            "    return keep_mut_tokens(value)\n"
            "fn main() -> i64:\n"
            "    return 0\n"
        ),
    }
    reference_ir = compile_sources(sources, entry_module="app").ir
    assert reference_ir is not None
    source, events = _emit_ng_source_set_events(sources, entry_module="app")
    ng_ir = decode_ng_ir_events(source, events)

    verify_ir(ng_ir)
    assert _canonical_structure(ng_ir) == _canonical_structure(reference_ir)
    assert execute_ir(ng_ir) == execute_ir(reference_ir) == 0
    call_names = {
        instruction.callee
        for function in ng_ir.functions
        for instruction in function.instructions
        if instruction.opcode.value == "call"
    }
    assert any(name and name.endswith("keep_tokens") for name in call_names)
    assert any(name and name.endswith("keep_token") for name in call_names)
    assert any(name and name.endswith("keep_mut_tokens") for name in call_names)
    ref_parameters = [
        parameter
        for function in ng_ir.functions
        for parameter in function.parameters
        if parameter.type is IRType.REFERENCE
    ]
    assert any(parameter.reference_aggregate == "TokenLike" for parameter in ref_parameters)
    assert any(parameter.reference_mutable for parameter in ref_parameters)

    functions = {function.name: function for function in ng_ir.functions}
    vector = DynamicCompositeVector("TokenLike", ("i64",), 1)
    vector.push((73,))
    relay_scalar = next(
        function for function in ng_ir.functions if function.name.endswith("relay_tokens")
    )
    assert ir_emulator._execute_function(
        functions, relay_scalar, (vector,), (), {}, HostExecutionContext()
    ) == 7
    relay_vector = next(
        function for function in ng_ir.functions if function.name.endswith("relay_token_vector")
    )
    returned_vector = ir_emulator._execute_function(
        functions, relay_vector, (vector,), (), {}, HostExecutionContext()
    )
    assert returned_vector is vector

    field_cell = ir_emulator._Cell(value=73, initialized=True)
    aggregate = ir_emulator.AggregateReferenceValue("TokenLike", ((("id",), field_cell),), False)
    relay_field = next(
        function for function in ng_ir.functions if function.name.endswith("relay_read_id")
    )
    assert ir_emulator._execute_function(
        functions, relay_field, (aggregate,), (), {}, HostExecutionContext()
    ) == 73


@pytest.mark.parametrize(
    ("element_type", "builtin_name"),
    (("i64", "i64_vector_new"), ("tryte", "tryte_vector_new"), ("f64", "f64_vector_new")),
)
def test_ng_ir_v7_generic_vector_new_is_explicit_and_executable(element_type: str, builtin_name: str) -> None:
    source = (
        f"fn main() -> vector<{element_type}>:\n"
        f"    return vector_new<{element_type}>(3)\n"
    )
    reference_ir = compile_source(source).ir
    assert reference_ir is not None
    events = _emit_ng_events(source)
    records = _event_records(events)
    assert records[0] == [0, 19, 8, 0, 0, 0, 0, 0]
    builtin_record = next(record for record in records if record[0] == 16)
    call_instructions = [record for record in records if record[0] == 4]
    call_instruction_index = next(index for index, record in enumerate(call_instructions) if record[2] == 7)
    assert builtin_record[1:5] == [
        0,
        call_instruction_index,
        {"i64": 1, "tryte": 2, "f64": 3}[element_type],
        {"i64": 1, "tryte": 3, "f64": 4}[element_type],
    ]

    ng_ir = decode_ng_ir_events(source.encode("utf-8"), events)
    verify_ir(ng_ir)
    assert _canonical_structure(ng_ir) == _canonical_structure(reference_ir)
    result = execute_ir(ng_ir)
    assert isinstance(result, DynamicVector)
    assert result.element_type == element_type
    assert result.capacity == 3
    assert next(
        instruction.callee
        for function in ng_ir.functions
        for instruction in function.instructions
        if instruction.opcode.value == "call"
    ) == builtin_name


def test_ng_ir_v7_generic_vector_new_rejects_malformed_builtin_metadata() -> None:
    source = "fn main() -> vector<i64>:\n    return vector_new<i64>(3)\n"
    records = _event_records(_emit_ng_events(source))
    builtin_record = next(record for record in records if record[0] == 16)
    builtin_record[3] = 99
    with pytest.raises(NGIRDecodeError, match="unknown V5 generic CALL builtin ID"):
        decode_ng_ir_events(source.encode("utf-8"), _flatten(records))

    records = _event_records(_emit_ng_events(source))
    builtin_record = next(record for record in records if record[0] == 16)
    builtin_record[4] = 3
    with pytest.raises(NGIRDecodeError, match="type metadata disagrees"):
        decode_ng_ir_events(source.encode("utf-8"), _flatten(records))


def test_ng_ir_v7_decoder_keeps_v4_stream_compatibility() -> None:
    source = "fn main() -> i64:\n    return 0\n"
    records = _legacy_event_records(_event_records(_emit_ng_events(source)), 4)
    decoded = decode_ng_ir_events(source.encode("utf-8"), _flatten(records))
    verify_ir(decoded)
    assert execute_ir(decoded) == 0


@pytest.mark.parametrize(
    ("element_type", "builtin_name", "element_type_id", "vector_factory", "value"),
    (
        ("i64", "i64_vector_len", 1, i64_vector_new, 17),
        ("tryte", "tryte_vector_len", 3, tryte_vector_new, -17),
        ("f64", "f64_vector_len", 4, f64_vector_new, 1.25),
    ),
)
def test_ng_ir_v7_generic_vector_len_is_explicit_and_executable(
    element_type: str,
    builtin_name: str,
    element_type_id: int,
    vector_factory,
    value: int | float,
) -> None:
    source = (
        f"fn vector_size(values: &vector<{element_type}>) -> i64:\n"
        f"    return vector_len<{element_type}>(values)\n"
        "fn main() -> i64:\n"
        "    return 0\n"
    )
    reference_ir = compile_source(source).ir
    assert reference_ir is not None
    records = _event_records(_emit_ng_events(source))
    assert records[0] == [0, 19, 8, 0, 0, 0, 0, 0]
    builtin_record = next(record for record in records if record[0] == 17)
    assert builtin_record[1:5] == [0, 0, 1, element_type_id]

    ng_ir = decode_ng_ir_events(source.encode("utf-8"), _flatten(records))
    verify_ir(ng_ir)
    assert _canonical_structure(ng_ir) == _canonical_structure(reference_ir)
    function = ng_ir.functions[0]
    assert [
        instruction.callee
        for block in function.blocks
        for instruction in block.instructions
        if instruction.opcode.value == "call"
    ] == [builtin_name]

    vector = vector_factory(4)
    vector.push(value)
    vector.push(value)
    owner_cell = ir_emulator._Cell(value=vector, initialized=True)
    reference = ReferenceValue(owner_cell, 0, False)
    functions = {item.name: item for item in ng_ir.functions}
    assert ir_emulator._execute_function(
        functions,
        function,
        (reference,),
        (),
        {},
        HostExecutionContext(),
    ) == 2


def test_ng_source_set_generic_vector_calls_skip_global_function_lookup() -> None:
    sources = {
        "app.s3": (
            "module app\n"
            "fn main() -> i64:\n"
            "    mut values: vector<i64> = vector_new<i64>(1)\n"
            "    discard vector_push<i64>(&mut values, 7)\n"
            "    discard vector_set<i64>(&mut values, 0, 9)\n"
            "    return vector_get<i64>(&values, 0) + vector_len<i64>(&values)\n"
        )
    }
    reference = compile_sources(sources, entry_module="app").ir
    assert reference is not None
    metrics: dict[str, object] = {}

    status, source, cells = _run_ng_source_set_events(
        sources,
        entry_module="app",
        max_steps=50_000_000,
        metrics=metrics,
    )
    assert status == 0, cells[-40:]
    ng_ir = decode_ng_ir_events(source, cells)
    verify_ir(ng_ir)
    assert _canonical_structure(ng_ir) == _canonical_structure(reference)
    assert execute_ir(ng_ir) == execute_ir(reference) == 10

    calls = metrics["calls"]
    assert isinstance(calls, dict)
    assert calls.get("ng_find_function", 0) == 0


def test_ng_ir_v7_vector_len_rejects_malformed_reference_metadata() -> None:
    source = (
        "fn vector_size(values: &vector<i64>) -> i64:\n"
        "    return vector_len<i64>(values)\n"
        "fn main() -> i64:\n"
        "    return 0\n"
    )
    records = _event_records(_emit_ng_events(source))
    builtin_record = next(record for record in records if record[0] == 17)
    builtin_record[3] = 99
    with pytest.raises(NGIRDecodeError, match="unknown V6 generic CALL builtin ID"):
        decode_ng_ir_events(source.encode("utf-8"), _flatten(records))

    records = _event_records(_emit_ng_events(source))
    builtin_record = next(record for record in records if record[0] == 17)
    builtin_record[4] = 3
    with pytest.raises(NGIRDecodeError, match="type metadata disagrees"):
        decode_ng_ir_events(source.encode("utf-8"), _flatten(records))


def test_ng_ir_v16_generic_vector_get_is_explicit_and_executable() -> None:
    source = (
        "fn read(values: &vector<i64>, index: i64) -> i64:\n"
        "    return vector_get<i64>(values, index)\n"
        "fn main() -> i64:\n"
        "    return 0\n"
    )
    reference_ir = compile_source(source).ir
    assert reference_ir is not None
    events = _emit_ng_events(source)
    records = _event_records(events)
    assert records[0] == [0, 19, 8, 0, 0, 0, 0, 0]

    ng_ir = decode_ng_ir_events(source.encode("utf-8"), events)
    verify_ir(ng_ir)
    assert _canonical_structure(ng_ir) == _canonical_structure(reference_ir)
    read = next(function for function in ng_ir.functions if function.name == "read")
    call = next(
        instruction
        for block in read.blocks
        for instruction in block.instructions
        if instruction.opcode.value == "call"
    )
    assert call.callee == "i64_vector_get"

    vector = i64_vector_new(3)
    vector.push(37)
    vector.push(41)
    owner = ir_emulator._Cell(value=vector, initialized=True)
    reference = ReferenceValue(owner, 0, False)
    functions = {function.name: function for function in ng_ir.functions}
    assert ir_emulator._execute_function(
        functions,
        read,
        (reference, 1),
        (),
        {},
        HostExecutionContext(),
    ) == 41


def test_ng_ir_v16_generic_vector_set_is_explicit_and_executable() -> None:
    source = (
        "fn write(values: &mut vector<i64>, index: i64, value: i64) -> tryte:\n"
        "    return vector_set<i64>(values, index, value)\n"
        "fn main() -> i64:\n"
        "    return 0\n"
    )
    reference_ir = compile_source(source).ir
    assert reference_ir is not None
    events = _emit_ng_events(source)
    records = _event_records(events)
    assert records[0] == [0, 19, 8, 0, 0, 0, 0, 0]
    metadata = next(record for record in records if record[0] == 23)
    assert metadata[3:5] == [2, 1]

    ng_ir = decode_ng_ir_events(source.encode("utf-8"), events)
    verify_ir(ng_ir)
    assert _canonical_structure(ng_ir) == _canonical_structure(reference_ir)
    write = next(function for function in ng_ir.functions if function.name == "write")
    call = next(
        instruction
        for block in write.blocks
        for instruction in block.instructions
        if instruction.opcode.value == "call"
    )
    assert call.callee == "i64_vector_set"

    vector = i64_vector_new(2)
    vector.push(12)
    owner = ir_emulator._Cell(value=vector, initialized=True)
    reference = ReferenceValue(owner, 0, True)
    functions = {function.name: function for function in ng_ir.functions}
    assert ir_emulator._execute_function(
        functions,
        write,
        (reference, 0, 57),
        (),
        {},
        HostExecutionContext(),
    ) == 0
    assert vector.get(0) == 57


def test_ng_ir_v16_vector_record_get_set_and_local_assignment_preserve_cells() -> None:
    sources = {
        "app.s3": (
            "module app\n"
            "record Pair:\n"
            "    left: i64\n"
            "    right: i64\n"
            "fn fetch(values: &vector<Pair>, index: i64) -> Pair:\n"
            "    return vector_get<Pair>(values, index)\n"
            "fn weigh(value: Pair) -> i64:\n"
            "    return value.left + value.right\n"
            "fn replace(values: &mut vector<Pair>, index: i64, replacement: Pair) -> tryte:\n"
            "    return vector_set<Pair>(values, index, replacement)\n"
            "fn main() -> i64:\n"
            "    mut values: vector<Pair> = vector_new<Pair>(2)\n"
            "    discard vector_push<Pair>(&mut values, Pair(right=2, left=1))\n"
            "    discard replace(&mut values, 0, Pair(right=23, left=37))\n"
            "    mut fetched: Pair = vector_get<Pair>(&values, 0)\n"
            "    mut reassigned: Pair = Pair(right=0, left=0)\n"
            "    reassigned = vector_get<Pair>(&values, 0)\n"
            "    return weigh(fetched) + weigh(reassigned)\n"
        ),
    }
    reference_ir = compile_sources(sources, entry_module="app").ir
    assert reference_ir is not None
    source, events = _emit_ng_source_set_events(sources, entry_module="app")
    records = _event_records(events)
    assert records[0] == [0, 19, 8, 0, 0, 0, 0, 0]
    assert sum(record[0] == 19 and record[3] == 4 for record in records) == 3
    assert sum(record[0] == 19 and record[3] == 5 for record in records) == 1

    malformed_records = [record.copy() for record in records]
    set_target = next(record for record in malformed_records if record[0] == 19 and record[3] == 5)
    set_target[3] = 4
    with pytest.raises(NGIRDecodeError, match="malformed V9 composite vector operation metadata"):
        decode_ng_ir_events(source, _flatten(malformed_records))

    ng_ir = decode_ng_ir_events(source, events)
    verify_ir(ng_ir)
    assert _canonical_structure(ng_ir) == _canonical_structure(reference_ir)
    vector_get_calls = [
        instruction
        for function in ng_ir.functions
        for block in function.blocks
        for instruction in block.instructions
        if instruction.opcode.value == "call" and instruction.callee.endswith("__get")
    ]
    assert len(vector_get_calls) == 3
    assert all(len(instruction.results) == 2 for instruction in vector_get_calls)
    assert execute_ir(ng_ir) == execute_ir(reference_ir) == 120


def test_ng_ir_v16_record_local_vector_get_uses_exact_aggregate_capacity() -> None:
    sources = {
        "app.s3": (
            "module app\n"
            "record Quad:\n"
            "    first: i64\n"
            "    second: i64\n"
            "    third: i64\n"
            "    fourth: i64\n"
            "fn load(values: &vector<Quad>, index: i64) -> i64:\n"
            "    mut item: Quad = vector_get<Quad>(values, index)\n"
            "    return item.first + item.second + item.third + item.fourth\n"
            "fn main() -> i64:\n"
            "    mut values: vector<Quad> = vector_new<Quad>(1)\n"
            "    discard vector_push<Quad>(&mut values, Quad(first=10, second=20, third=30, fourth=40))\n"
            "    return load(&values, 0)\n"
        ),
    }
    reference_ir = compile_sources(sources, entry_module="app").ir
    assert reference_ir is not None
    source, events = _emit_ng_source_set_events(sources, entry_module="app")
    ng_ir = decode_ng_ir_events(source, events)
    verify_ir(ng_ir)
    assert _canonical_structure(ng_ir) == _canonical_structure(reference_ir)
    load = next(function for function in ng_ir.functions if function.name.endswith("__load"))
    get_call = next(
        instruction
        for block in load.blocks
        for instruction in block.instructions
        if instruction.opcode.value == "call" and instruction.callee.endswith("__get")
    )
    assert len(get_call.results) == 4
    assert execute_ir(ng_ir) == execute_ir(reference_ir) == 100


@pytest.mark.parametrize(
    ("element_type", "builtin_name", "element_type_id", "factory", "value"),
    (
        ("i64", "i64_vector_push", 1, i64_vector_new, 37),
        ("tryte", "tryte_vector_push", 3, tryte_vector_new, -17),
        ("f64", "f64_vector_push", 4, f64_vector_new, 1.25),
    ),
)
def test_ng_ir_v8_generic_vector_push_is_explicit_and_executable(
    element_type: str,
    builtin_name: str,
    element_type_id: int,
    factory,
    value: int | float,
) -> None:
    source = (
        f"fn append(values: &mut vector<{element_type}>, value: {element_type}) -> tryte:\n"
        f"    return vector_push<{element_type}>(values, value)\n"
        "fn main() -> i64:\n"
        "    return 0\n"
    )
    reference_ir = compile_source(source).ir
    assert reference_ir is not None
    records = _event_records(_emit_ng_events(source))
    assert records[0] == [0, 19, 8, 0, 0, 0, 0, 0]
    metadata = next(record for record in records if record[0] == 18)
    assert metadata[1] == 0
    assert metadata[3:5] == [1, element_type_id]

    ng_ir = decode_ng_ir_events(source.encode("utf-8"), _flatten(records))
    verify_ir(ng_ir)
    assert _canonical_structure(ng_ir) == _canonical_structure(reference_ir)
    assert [
        instruction.callee
        for function in ng_ir.functions
        for block in function.blocks
        for instruction in block.instructions
        if instruction.opcode.value == "call"
    ] == [builtin_name]

    vector = factory(2)
    owner = ir_emulator._Cell(value=vector, initialized=True)
    reference = ReferenceValue(owner, 0, True)
    functions = {item.name: item for item in ng_ir.functions}
    append = next(item for item in ng_ir.functions if item.name == "append")
    assert ir_emulator._execute_function(
        functions,
        append,
        (reference, value),
        (),
        {},
        HostExecutionContext(),
    ) == 0
    assert vector.length == 1
    assert execute_ir(ng_ir) == 0


def test_ng_ir_v8_vector_push_rejects_malformed_metadata() -> None:
    source = (
        "fn append(values: &mut vector<i64>, value: i64) -> tryte:\n"
        "    return vector_push<i64>(values, value)\n"
        "fn main() -> i64:\n"
        "    return 0\n"
    )
    records = _event_records(_emit_ng_events(source))
    metadata = next(record for record in records if record[0] == 18)
    metadata[3] = 99
    with pytest.raises(NGIRDecodeError, match="unknown V8 generic CALL builtin ID"):
        decode_ng_ir_events(source.encode("utf-8"), _flatten(records))

    records = _event_records(_emit_ng_events(source))
    metadata = next(record for record in records if record[0] == 18)
    metadata[4] = 3
    with pytest.raises(NGIRDecodeError, match="type metadata disagrees"):
        decode_ng_ir_events(source.encode("utf-8"), _flatten(records))


def test_ng_ir_v7_decoder_keeps_v5_vector_new_stream_compatibility() -> None:
    source = "fn main() -> vector<i64>:\n    return vector_new<i64>(3)\n"
    records = _legacy_event_records(_event_records(_emit_ng_events(source)), 5)
    decoded = decode_ng_ir_events(source.encode("utf-8"), _flatten(records))
    verify_ir(decoded)
    result = execute_ir(decoded)
    assert isinstance(result, DynamicVector)
    assert result.capacity == 3


def test_ng_source_set_rejects_aggregate_call_with_wrong_vector_element() -> None:
    sources = {
        "app.s3": (
            "module app\n"
            "record TokenLike:\n"
            "    id: i64\n"
            "fn keep_numbers(value: vector<i64>) -> vector<i64>:\n"
            "    return value\n"
            "fn wrong_element(value: vector<TokenLike>) -> vector<i64>:\n"
            "    return keep_numbers(value)\n"
            "fn main() -> i64:\n"
            "    return 0\n"
        ),
    }
    status, _, events = _run_ng_source_set_events(sources, entry_module="app")
    assert status < 0
    assert events == []


def test_ng_source_set_resolves_imported_nominal_type_inside_vector_reference() -> None:
    sources = {
        "app.s3": (
            "module app\n"
            "from model import Token\n"
            "from model import append_token\n"
            "fn read_kind() -> i64:\n"
            "    return Token(kind=7).kind\n"
            "fn main() -> i64:\n"
            "    mut tokens: vector<Token> = vector_new<Token>(2)\n"
            "    discard append_token(&mut tokens)\n"
            "    return vector_len<Token>(&tokens) + read_kind()\n"
        ),
        "model.s3": (
            "module model\n"
            "export record Token:\n"
            "    kind: i64\n"
            "export fn append_token(tokens: &mut vector<Token>) -> i64:\n"
            "    discard vector_push<Token>(tokens, Token(kind=7))\n"
            "    return 0\n"
        ),
    }

    reference_ir = compile_sources(sources, entry_module="app").ir
    assert reference_ir is not None
    source, events = _emit_ng_source_set_events(sources, entry_module="app")
    ng_ir = decode_ng_ir_events(source, events)
    verify_ir(ng_ir)

    assert _canonical_structure(ng_ir) == _canonical_structure(reference_ir)
    assert execute_ir(ng_ir) == execute_ir(reference_ir) == 8


def test_ng_ir_v4_transports_record_fields_without_semantic_resolution() -> None:
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


def test_ng_ir_v4_lowers_and_executes_aggregate_reference_field_load() -> None:
    sources = {
        "app.s3": (
            "module app\n"
            "record TokenLike:\n"
            "    id: i64\n"
            "fn read_id(value: &TokenLike) -> i64:\n"
            "    return value.id\n"
            "fn main() -> i64:\n"
            "    return 0\n"
        ),
    }
    reference_ir = compile_sources(sources, entry_module="app").ir
    assert reference_ir is not None
    source, events = _emit_ng_source_set_events(sources, entry_module="app")
    rows = _event_records(events)
    field_load = next(row for row in rows if row[0] == 4 and row[2] == 14)
    field_load_index = rows.index(field_load)
    field_span = rows[field_load_index + 1]
    assert field_span[0] == 15
    assert source[field_load[7]:field_span[3]].decode("utf-8") == "id"

    ng_ir = decode_ng_ir_events(source, events)
    verify_ir(ng_ir)
    assert _canonical_structure(ng_ir) == _canonical_structure(reference_ir)
    read_id = next(function for function in ng_ir.functions if function.name.endswith("read_id"))
    instruction = next(
        instruction
        for instruction in read_id.instructions
        if instruction.opcode.value == "aggregate_field_load"
    )
    assert instruction.reference_aggregate == "TokenLike"
    assert instruction.aggregate_field_path == ("id",)

    field_cell = ir_emulator._Cell(value=73, initialized=True)
    aggregate = ir_emulator.AggregateReferenceValue("TokenLike", ((("id",), field_cell),), False)
    functions = {function.name: function for function in ng_ir.functions}
    result = ir_emulator._execute_function(
        functions,
        read_id,
        (aggregate,),
        (),
        {},
        HostExecutionContext(),
    )
    assert result == 73


def test_ng_source_set_lowers_record_constructor_field_projection() -> None:
    sources = {
        "app.s3": (
            "module app\n"
            "record Pair:\n"
            "    left: i64\n"
            "    right: i64\n"
            "fn main() -> i64:\n"
            "    return Pair(right=23, left=19).right\n"
        ),
    }
    reference_ir = compile_sources(sources, entry_module="app").ir
    assert reference_ir is not None
    source, events = _emit_ng_source_set_events(sources, entry_module="app")
    ng_ir = decode_ng_ir_events(source, events)

    verify_ir(ng_ir)
    assert _canonical_structure(ng_ir) == _canonical_structure(reference_ir)
    assert execute_ir(ng_ir) == execute_ir(reference_ir) == 23


def test_ng_aggregate_returns_inside_match_and_while_match_reference() -> None:
    sources = {
        "app.s3": (
            "module app\n"
            "record Pair:\n"
            "    left: i64\n"
            "    right: i64\n"
            "fn from_match(flag: trit) -> Pair:\n"
            "    match flag:\n"
            "        -1:\n"
            "            return Pair(left=11, right=1)\n"
            "        0:\n"
            "            return Pair(left=22, right=2)\n"
            "        1:\n"
            "            return Pair(left=33, right=3)\n"
            "fn from_while(flag: trit) -> Pair:\n"
            "    while flag:\n"
            "        return Pair(left=40, right=2)\n"
            "    return Pair(left=1, right=1)\n"
            "fn main() -> i64:\n"
            "    matched: Pair = from_match(0)\n"
            "    looped: Pair = from_while(-1)\n"
            "    return matched.left + matched.right + looped.left + looped.right\n"
        ),
    }
    reference = compile_sources(sources, entry_module="app").ir
    assert reference is not None
    source, events = _emit_ng_source_set_events(sources, entry_module="app")
    ng_ir = decode_ng_ir_events(source, events)

    verify_ir(ng_ir)
    assert _canonical_structure(ng_ir) == _canonical_structure(reference)
    assert execute_ir(ng_ir) == execute_ir(reference) == 66


@pytest.mark.parametrize(
    ("corruption", "message"),
    (
        ("missing-cell", "expected record kind 24"),
        ("wrong-ordinal", "V17 RETURN result-cell identity"),
    ),
)
def test_ng_ir_v17_rejects_malformed_explicit_return_cells(
    corruption: str, message: str
) -> None:
    sources = {
        "app.s3": (
            "module app\n"
            "record Pair:\n"
            "    left: i64\n"
            "    right: i64\n"
            "fn make() -> Pair:\n"
            "    return Pair(left=5, right=8)\n"
            "fn main() -> i64:\n"
            "    return 0\n"
        )
    }
    source, events = _emit_ng_source_set_events(sources, entry_module="app")
    records = _event_records(events)
    return_index = next(
        index for index, record in enumerate(records) if record[0] == 4 and record[2] == 6
    )
    assert records[return_index][4] == 2
    assert records[return_index + 1][0] == 24

    if corruption == "missing-cell":
        del records[return_index + 1 : return_index + 3]
    else:
        records[return_index + 2][3] = 0

    with pytest.raises(NGIRDecodeError, match=message):
        decode_ng_ir_events(source, _flatten(records))


def test_ng_source_set_resolves_field_access_on_mutable_record_local() -> None:
    sources = {
        "app.s3": (
            "module app\n"
            "record Pair:\n"
            "    left: i64\n"
            "    right: i64\n"
            "fn main() -> i64:\n"
            "    mut pair: Pair = Pair(left=19, right=23)\n"
            "    return pair.right\n"
        ),
    }
    reference_ir = compile_sources(sources, entry_module="app").ir
    assert reference_ir is not None
    source, events = _emit_ng_source_set_events(sources, entry_module="app")
    ng_ir = decode_ng_ir_events(source, events)

    verify_ir(ng_ir)
    assert _canonical_structure(ng_ir) == _canonical_structure(reference_ir)
    assert execute_ir(ng_ir) == execute_ir(reference_ir) == 23


def test_ng_source_set_resolves_one_imported_record_identity_across_modules() -> None:
    sources = {
        "app.s3": (
            "module app\n"
            "from lexer import NgToken\n"
            "from types import read_start\n"
            "from parser import read_start as parser_read_start\n"
            "fn main() -> i64:\n"
            "    token: NgToken = NgToken(start=9)\n"
            "    return read_start(token) + parser_read_start(token)\n"
        ),
        "lexer.s3": (
            "module lexer\n"
            "export record NgToken:\n"
            "    start: i64\n"
            "export fn token_start(token: NgToken) -> i64:\n"
            "    return token.start\n"
        ),
        "types.s3": (
            "module types\n"
            "from lexer import NgToken\n"
            "export fn read_start(token: NgToken) -> i64:\n"
            "    return token.start\n"
        ),
        "parser.s3": (
            "module parser\n"
            "from lexer import NgToken\n"
            "export fn read_start(token: NgToken) -> i64:\n"
            "    return token.start\n"
        ),
    }
    reference_ir = compile_sources(sources, entry_module="app").ir
    assert reference_ir is not None
    source, events = _emit_ng_source_set_events(sources, entry_module="app")
    ng_ir = decode_ng_ir_events(source, events)

    verify_ir(ng_ir)
    assert _canonical_structure(ng_ir) == _canonical_structure(reference_ir)
    assert execute_ir(ng_ir) == execute_ir(reference_ir) == 18


def test_ng_source_set_keeps_same_named_records_from_different_modules_distinct() -> None:
    sources = {
        "app.s3": (
            "module app\n"
            "from model_b import Token, relay\n"
            "fn main() -> i64:\n"
            "    return relay(Token(value=9))\n"
        ),
        "model_a.s3": (
            "module model_a\n"
            "export record Token:\n"
            "    value: i64\n"
            "export fn accept(value: Token) -> i64:\n"
            "    return value.value\n"
        ),
        "model_b.s3": (
            "module model_b\n"
            "from model_a import accept\n"
            "export record Token:\n"
            "    value: i64\n"
            "export fn relay(value: Token) -> i64:\n"
            "    return accept(value)\n"
        ),
    }

    with pytest.raises(SemanticError):
        compile_sources(sources, entry_module="app")

    status, _, _ = _run_ng_source_set_events(sources, entry_module="app")
    assert status == -14


def test_ng_source_set_lowers_mutable_record_field_assignment() -> None:
    sources = {
        "app.s3": (
            "module app\n"
            "record Pair:\n"
            "    left: i64\n"
            "    right: i64\n"
            "fn main() -> i64:\n"
            "    mut pair: Pair = Pair(left=19, right=23)\n"
            "    pair.left = pair.right\n"
            "    return pair.left\n"
        ),
    }
    reference_ir = compile_sources(sources, entry_module="app").ir
    assert reference_ir is not None
    source, events = _emit_ng_source_set_events(sources, entry_module="app")
    ng_ir = decode_ng_ir_events(source, events)

    verify_ir(ng_ir)
    assert _canonical_structure(ng_ir) == _canonical_structure(reference_ir)
    assert execute_ir(ng_ir) == execute_ir(reference_ir) == 23


def test_ng_source_set_executes_composite_vector_new_push_and_len() -> None:
    sources = {
        "app.s3": (
            "module app\n"
            "record Token:\n"
            "    kind: i64\n"
            "    code: tryte\n"
            "fn main() -> i64:\n"
            "    mut tokens: vector<Token> = vector_new<Token>(2)\n"
            "    discard vector_push<Token>(&mut tokens, Token(code=4, kind=19))\n"
            "    return vector_len<Token>(&tokens)\n"
        ),
    }
    reference_ir = compile_sources(sources, entry_module="app").ir
    assert reference_ir is not None
    source, events = _emit_ng_source_set_events(sources, entry_module="app")
    records = _event_records(events)
    assert records[0] == [0, 19, 8, 0, 0, 0, 0, 0]
    assert sum(row[0] == 19 and row[3] == 1 for row in records) == 1
    assert sum(row[0] == 19 and row[3] == 2 for row in records) == 1
    assert sum(row[0] == 19 and row[3] == 3 for row in records) == 1

    ng_ir = decode_ng_ir_events(source, events)
    verify_ir(ng_ir)
    assert _canonical_structure(ng_ir) == _canonical_structure(reference_ir)
    assert execute_ir(ng_ir) == execute_ir(reference_ir) == 1


def test_ng_source_set_lowers_record_return_call_into_composite_vector_push() -> None:
    sources = {
        "app.s3": (
            "module app\n"
            "record Pair:\n"
            "    left: i64\n"
            "    right: i64\n"
            "fn make_pair(left: i64, right: i64) -> Pair:\n"
            "    return Pair(left=left, right=right)\n"
            "fn main() -> i64:\n"
            "    mut pairs: vector<Pair> = vector_new<Pair>(1)\n"
            "    discard vector_push<Pair>(&mut pairs, make_pair(19, 23))\n"
            "    return vector_len<Pair>(&pairs)\n"
        ),
    }
    reference_ir = compile_sources(sources, entry_module="app").ir
    assert reference_ir is not None

    source, events = _emit_ng_source_set_events(sources, entry_module="app")
    ng_ir = decode_ng_ir_events(source, events)

    verify_ir(ng_ir)
    assert _canonical_structure(ng_ir) == _canonical_structure(reference_ir)
    assert execute_ir(ng_ir) == execute_ir(reference_ir) == 1


def test_ng_source_set_flattens_record_argument_for_function_call() -> None:
    sources = {
        "app.s3": (
            "module app\n"
            "record Pair:\n"
            "    left: i64\n"
            "    right: i64\n"
            "fn sum_pair(pair: Pair) -> i64:\n"
            "    return pair.left + pair.right\n"
            "fn main() -> i64:\n"
            "    return sum_pair(Pair(left=19, right=23))\n"
        ),
    }
    reference_ir = compile_sources(sources, entry_module="app").ir
    assert reference_ir is not None

    source, events = _emit_ng_source_set_events(sources, entry_module="app")
    ng_ir = decode_ng_ir_events(source, events)

    verify_ir(ng_ir)
    assert _canonical_structure(ng_ir) == _canonical_structure(reference_ir)
    assert execute_ir(ng_ir) == execute_ir(reference_ir) == 42


def test_ng_source_set_forwards_nested_record_parameter_through_returning_call() -> None:
    sources = {
        "app.s3": (
            "module app\n"
            "record Inner:\n"
            "    value: i64\n"
            "record Pair:\n"
            "    left: i64\n"
            "    inner: Inner\n"
            "fn identity(pair: Pair) -> Pair:\n"
            "    return pair\n"
            "fn read(pair: Pair) -> i64:\n"
            "    return pair.inner.value\n"
            "fn main() -> i64:\n"
            "    return read(identity(Pair(left=19, inner=Inner(value=23))))\n"
        ),
    }
    reference_ir = compile_sources(sources, entry_module="app").ir
    assert reference_ir is not None

    source, events = _emit_ng_source_set_events(sources, entry_module="app")
    ng_ir = decode_ng_ir_events(source, events)

    verify_ir(ng_ir)
    assert _canonical_structure(ng_ir) == _canonical_structure(reference_ir)
    assert execute_ir(ng_ir) == execute_ir(reference_ir) == 23


def test_ng_source_set_flattens_nested_record_parameter_between_scalar_parameters() -> None:
    sources = {
        "app.s3": (
            "module app\n"
            "record Inner:\n"
            "    value: i64\n"
            "record Pair:\n"
            "    left: i64\n"
            "    inner: Inner\n"
            "fn combine(prefix: i64, pair: Pair, suffix: i64) -> i64:\n"
            "    return prefix + pair.left + pair.inner.value + suffix\n"
            "fn main() -> i64:\n"
            "    return combine(1, Pair(left=19, inner=Inner(value=20)), 2)\n"
        ),
    }
    reference_ir = compile_sources(sources, entry_module="app").ir
    assert reference_ir is not None

    source, events = _emit_ng_source_set_events(sources, entry_module="app")
    rows = _event_records(events)
    ng_ir = decode_ng_ir_events(source, events)

    verify_ir(ng_ir)
    assert _canonical_structure(ng_ir) == _canonical_structure(reference_ir)
    combine = next(function for function in ng_ir.functions if function.name.endswith("combine"))
    assert [parameter.name for parameter in combine.parameters] == [
        "prefix",
        "pair__left",
        "pair__inner__value",
        "suffix",
    ]
    assert any(row[0] == 23 for row in rows)
    assert execute_ir(ng_ir) == execute_ir(reference_ir) == 42


def test_ng_ir_v15_rejects_malformed_parameter_field_path_order() -> None:
    sources = {
        "app.s3": (
            "module app\n"
            "record Pair:\n"
            "    left: i64\n"
            "    right: i64\n"
            "fn sum_pair(pair: Pair) -> i64:\n"
            "    return pair.left + pair.right\n"
            "fn main() -> i64:\n"
            "    return sum_pair(Pair(left=19, right=23))\n"
        ),
    }
    source, events = _emit_ng_source_set_events(sources, entry_module="app")
    records = _event_records(events)
    path_event = next(row for row in records if row[0] == 23)
    path_event[3] = path_event[3] + 4

    with pytest.raises(NGIRDecodeError, match="V15 parameter field-path identity"):
        decode_ng_ir_events(source, _flatten(records))


def test_ng_source_set_rejects_unknown_aggregate_reference_field() -> None:
    sources = {
        "app.s3": (
            "module app\n"
            "record TokenLike:\n"
            "    id: i64\n"
            "fn read_missing(value: &TokenLike) -> i64:\n"
            "    return value.missing\n"
            "fn main() -> i64:\n"
            "    return 0\n"
        ),
    }
    status, _, events = _run_ng_source_set_events(sources, entry_module="app")
    assert status < 0
    assert events == []


def test_ng_ir_v15_lowers_record_parameter_value_cells() -> None:
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
    reference_ir = compile_sources(sources, entry_module="app").ir
    assert reference_ir is not None
    source, events = _emit_ng_source_set_events(sources, entry_module="app")
    ng_ir = decode_ng_ir_events(source, events)

    verify_ir(ng_ir)
    assert _canonical_structure(ng_ir) == _canonical_structure(reference_ir)
    assert execute_ir(ng_ir) == execute_ir(reference_ir) == 0


def test_ng_ir_v4_rejects_malformed_composite_descriptors() -> None:
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


def test_ng_internal_name_reserves_exact_buffer_capacity() -> None:
    source_text = "module library\nexport fn transform() -> i64:\n    return 1\n"
    function_name_start = source_text.index("transform")
    generated_name = b"__s3mod_library__transform"
    wrapper = f'''\
fn main() -> vector<i64>:
    mut source_text: text = text_from_static({json.dumps(source_text)})
    mut source: bytes = bytes_from_text(&source_text)
    mut original_length: i64 = bytes_len(&source)
    mut module_item: NgModule = NgModule(source_index=0, source_start=0, source_end=original_length, path_start=0, path_end=0, name_start=7, name_end=14, body_token_index=0, first_function=0, function_count=0, first_import=0, import_count=0)
    mut function: NgFunction = NgFunction(start=0, end=original_length, name_start={function_name_start}, name_end={function_name_start + len("transform")}, local_name_start={function_name_start}, local_name_end={function_name_start + len("transform")}, first_parameter=0, parameter_count=0, return_type=1, first_node=0, body_node=0, module_index=0, exported=1, name_fingerprint=0, local_name_fingerprint=0)
    mut entry_text: text = text_from_static("app")
    mut entry_module: bytes = bytes_from_text(&entry_text)
    mut main_text: text = text_from_static("main")
    mut main_name: bytes = bytes_from_text(&main_text)
    mut span: NgSpan = ng_append_internal_name(&mut source, module_item, function, &entry_module, &main_name)
    mut result: vector<i64> = vector_new<i64>({4 + len(generated_name)})
    mut index: i64 = 0
    discard vector_push<i64>(&mut result, span.start)
    discard vector_push<i64>(&mut result, span.end)
    discard vector_push<i64>(&mut result, bytes_len(&source))
    discard vector_push<i64>(&mut result, bytes_capacity(&source))
    while index < bytes_len(&source) - original_length:
        discard vector_push<i64>(&mut result, to_i64(bytes_get(&source, original_length + index)))
        index = index + 1
    return result
'''
    compilation = compile_source(_NG_SOURCE + "\n" + wrapper)
    assert compilation.ir is not None

    result = execute_ir(compilation.ir)
    assert hasattr(result, "element_type")
    values = [int(value) for value in result]
    expected_start = len(source_text.encode("utf-8"))
    expected_end = expected_start + len(generated_name)
    assert values[:3] == [expected_start, expected_end, expected_end]
    assert values[3] >= expected_end
    assert values[4:] == list(generated_name)


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


def test_ng_source_set_grows_type_table_for_generic_references() -> None:
    type_names = tuple(
        type_name
        for element in ("i64", "trit", "tryte", "f64", "bytes", "text")
        for type_name in (
            f"vector<{element}>",
            f"&vector<{element}>",
            f"&mut vector<{element}>",
        )
    )
    parameters = ", ".join(
        f"value_{index}: {type_name}"
        for index, type_name in enumerate(type_names)
    )
    sources = {
        "app.s3": (
            "module app\n"
            + f"fn consume({parameters}) -> i64:\n    return 0\n"
            + "fn main() -> i64:\n    return 0\n"
        ),
    }

    reference = compile_sources(sources, entry_module="app").ir
    assert reference is not None
    source, cells = _emit_ng_source_set_events(sources, entry_module="app")
    records = _event_records(cells)
    assert sum(record[0] == 12 for record in records) > 16

    ng_ir = decode_ng_ir_events(source, cells)
    verify_ir(ng_ir)
    assert _canonical_structure(ng_ir) == _canonical_structure(reference)
    assert execute_ir(ng_ir) == execute_ir(reference) == 0


def test_ng_record_parameter_preallocates_flattened_variable_and_register_capacity() -> None:
    fields = "\n".join(f"    field_{index:02d}: i64" for index in range(48))
    sources = {
        "app.s3": (
            "module app\n"
            "record Wide:\n"
            f"{fields}\n"
            "fn consume(value: Wide) -> i64:\n"
            "    return 0\n"
            "fn main() -> i64:\n"
            "    return 0\n"
        )
    }

    reference = compile_sources(sources, entry_module="app").ir
    assert reference is not None
    source, cells = _emit_ng_source_set_events(sources, entry_module="app")
    ng_ir = decode_ng_ir_events(source, cells)

    verify_ir(ng_ir)
    assert _canonical_structure(ng_ir) == _canonical_structure(reference)
    assert execute_ir(ng_ir) == execute_ir(reference) == 0


def test_ng_function_lookup_fingerprint_filter_reduces_name_comparisons() -> None:
    function_count = 64
    names = " ".join(f"f{index:04d}" for index in range(function_count))
    wrapper = f'''\
fn main() -> i64:
    mut source_text: text = text_from_static({json.dumps(names + " missing_long")})
    mut source: bytes = bytes_from_text(&source_text)
    mut functions: vector<NgFunction> = vector_new<NgFunction>({function_count})
    mut modules: vector<NgModule> = vector_new<NgModule>(1)
    mut index: i64 = 0
    mut name_start: i64 = 0
    mut name_end: i64 = 0
    mut fingerprint: i64 = 0
    mut total: i64 = 0
    mut module_total: i64 = 0
    mut missing_function_index: i64 = -1
    mut missing_module_index: i64 = -1
    while index < {function_count}:
        name_start = index * 6
        name_end = name_start + 5
        fingerprint = ng_span_fingerprint(&source, name_start, name_end)
        discard vector_push<NgFunction>(&mut functions, NgFunction(start=0, end=0, name_start=name_start, name_end=name_end, local_name_start=name_start, local_name_end=name_end, first_parameter=0, parameter_count=0, return_type=1, first_node=0, body_node=0, module_index=0, exported=0, name_fingerprint=fingerprint, local_name_fingerprint=fingerprint))
        index = index + 1
    discard vector_push<NgModule>(&mut modules, NgModule(source_index=0, source_start=0, source_end=bytes_len(&source), path_start=0, path_end=0, name_start=0, name_end=0, body_token_index=0, first_function=0, function_count={function_count}, first_import=0, import_count=0))
    index = 0
    while index < {function_count}:
        name_start = index * 6
        name_end = name_start + 5
        total = total + ng_find_function(&source, &functions, name_start, name_end)
        module_total = module_total + ng_find_function_in_module(&source, &modules, &functions, 0, name_start, name_end)
        index = index + 1
    name_start = {function_count * 6}
    name_end = name_start + 12
    missing_function_index = ng_find_function(&source, &functions, name_start, name_end)
    missing_module_index = ng_find_function_in_module(&source, &modules, &functions, 0, name_start, name_end)
    match missing_function_index <=> -13:
        0:
            match missing_module_index <=> -1:
                0:
                    return total + module_total
                -1:
                    return -1
                1:
                    return -1
        -1:
            return -1
        1:
            return -1
'''
    harness_source = _NG_SOURCE + "\n" + wrapper
    compilation = compile_source(harness_source)
    assert compilation.ir is not None
    metrics: dict[str, object] = {}
    result = _execute_ir_with_step_budget(
        compilation.ir,
        source_text=harness_source,
        max_steps=10_000_000,
        metrics=metrics,
    )

    assert result == 2 * function_count * (function_count - 1) // 2
    calls = metrics["calls"]
    assert isinstance(calls, dict)
    named_comparisons = int(calls.get("ng_named_spans_equal", 0))
    baseline_linear_name_comparisons = function_count * (function_count + 1) // 2
    fingerprint_calls = int(calls.get("ng_span_fingerprint", 0))
    assert named_comparisons <= 2 * function_count
    assert named_comparisons < 2 * baseline_linear_name_comparisons // 8
    assert fingerprint_calls == 3 * function_count


def test_ng_parameter_lookups_fingerprint_before_exact_span_comparison() -> None:
    parameter_count = 64
    names = " ".join(f"p{index:03d}" for index in range(parameter_count))
    wrapper = f'''\
fn main() -> i64:
    mut source_text: text = text_from_static({json.dumps(names)})
    mut source: bytes = bytes_from_text(&source_text)
    mut parameters: vector<NgParameter> = vector_new<NgParameter>({parameter_count})
    mut index: i64 = 0
    mut name_start: i64 = 0
    mut name_end: i64 = 0
    mut fingerprint: i64 = 0
    mut result: i64 = 0
    while index < {parameter_count}:
        name_start = index * 5
        name_end = name_start + 4
        fingerprint = ng_span_fingerprint(&source, name_start, name_end)
        discard vector_push<NgParameter>(&mut parameters, NgParameter(name_start=name_start, name_end=name_end, name_fingerprint=fingerprint, type_kind=index + 1))
        index = index + 1
    index = 0
    while index < {parameter_count}:
        name_start = index * 5
        name_end = name_start + 4
        result = result + ng_parameter_type(&source, &parameters, 0, {parameter_count}, name_start, name_end)
        result = result + ng_parameter_register(&source, &parameters, 0, {parameter_count}, name_start, name_end)
        index = index + 1
    return result
'''
    harness_source = _NG_SOURCE + "\n" + wrapper
    compilation = compile_source(harness_source)
    assert compilation.ir is not None
    metrics: dict[str, object] = {}
    result = _execute_ir_with_step_budget(
        compilation.ir,
        source_text=harness_source,
        max_steps=10_000_000,
        metrics=metrics,
    )

    assert result == parameter_count * parameter_count
    calls = metrics["calls"]
    assert isinstance(calls, dict)
    exact_span_comparisons = int(calls.get("ng_spans_equal", 0))
    fingerprint_calls = int(calls.get("ng_span_fingerprint", 0))
    linear_scan_reference_comparisons = 2 * parameter_count * (parameter_count + 1) // 2
    assert exact_span_comparisons == 0
    assert fingerprint_calls == 3 * parameter_count
    assert exact_span_comparisons * 16 < linear_scan_reference_comparisons


def test_ng_span_equality_cost_profile_baseline() -> None:
    comparison_count = 32
    wrapper = f'''\
fn main() -> i64:
    mut source_text: text = text_from_static("abcdefghij abcdefghij abcdefghik")
    mut source: bytes = bytes_from_text(&source_text)
    mut index: i64 = 0
    mut result: i64 = 0
    while index < {comparison_count}:
        result = result + to_i64(ng_spans_equal(&source, 0, 10, 11, 21))
        result = result + to_i64(ng_spans_equal(&source, 0, 10, 22, 32))
        index = index + 1
    return result
'''
    harness_source = _NG_SOURCE + "\n" + wrapper
    compilation = compile_source(harness_source)
    assert compilation.ir is not None
    metrics: dict[str, object] = {}
    result = _execute_ir_with_step_budget(
        compilation.ir,
        source_text=harness_source,
        max_steps=10_000_000,
        metrics=metrics,
    )
    assert result == -comparison_count
    line_counts = metrics["line_counts"]
    assert isinstance(line_counts, dict)
    equality_events = int(line_counts.get("ng_spans_equal", 0))
    calls = metrics["calls"]
    assert isinstance(calls, dict)
    equality_calls = int(calls.get("ng_spans_equal", 0))
    print(
        "SPAN_EQUALITY_PROFILE "
        f"calls={equality_calls} "
        f"ir_steps={equality_events} "
        f"steps_per_call={equality_events // equality_calls}"
    )


def test_ng_ir_variable_lookup_keeps_near_matching_local_names_distinct() -> None:
    sources = {
        "app.s3": (
            "module app\n"
            "fn main() -> i64:\n"
            "    parser: i64 = 1\n"
            "    pasper: i64 = 2\n"
            "    return parser * 10 + pasper\n"
        )
    }
    reference = compile_sources(sources, entry_module="app").ir
    assert reference is not None

    source, cells = _emit_ng_source_set_events(sources, entry_module="app")
    ng_ir = decode_ng_ir_events(source, cells)
    verify_ir(ng_ir)

    assert _canonical_structure(ng_ir) == _canonical_structure(reference)
    assert execute_ir(ng_ir) == execute_ir(reference) == 12


def test_ng_ir_variable_field_lookup_stays_with_parent_subtree() -> None:
    sibling_count = 256
    root_count = 128
    wrapper = f'''\
fn main() -> vector<i64>:
    mut source_text: text = text_from_static("root target left inner leaf right sibling other missing long_prefix_alpha long_prefix_omega")
    mut source: bytes = bytes_from_text(&source_text)
    mut variables: vector<NgIRVariable> = vector_new<NgIRVariable>(512)
    mut invalid_variables: vector<NgIRVariable> = vector_new<NgIRVariable>(2)
    mut result: vector<i64> = vector_new<i64>(5)
    mut index: i64 = 0
    mut fingerprint: i64 = ng_span_fingerprint(&source, 0, 4)
    mut sibling_index: i64 = -1
    discard vector_push<NgIRVariable>(&mut variables, NgIRVariable(name_start=0, name_end=4, name_fingerprint=fingerprint, type_kind=7, mutable=0, register=-1, memory=-1, parent_index=-1, field_name_start=-1, field_name_end=-1))
    fingerprint = ng_span_fingerprint(&source, 5, 11)
    discard vector_push<NgIRVariable>(&mut variables, NgIRVariable(name_start=5, name_end=11, name_fingerprint=fingerprint, type_kind=7, mutable=0, register=-1, memory=-1, parent_index=0, field_name_start=5, field_name_end=11))
    discard vector_push<NgIRVariable>(&mut variables, NgIRVariable(name_start=12, name_end=16, name_fingerprint=ng_span_fingerprint(&source, 12, 16), type_kind=1, mutable=0, register=0, memory=-1, parent_index=1, field_name_start=12, field_name_end=16))
    discard vector_push<NgIRVariable>(&mut variables, NgIRVariable(name_start=17, name_end=22, name_fingerprint=ng_span_fingerprint(&source, 17, 22), type_kind=7, mutable=0, register=-1, memory=-1, parent_index=1, field_name_start=17, field_name_end=22))
    discard vector_push<NgIRVariable>(&mut variables, NgIRVariable(name_start=23, name_end=27, name_fingerprint=ng_span_fingerprint(&source, 23, 27), type_kind=1, mutable=0, register=1, memory=-1, parent_index=3, field_name_start=23, field_name_end=27))
    discard vector_push<NgIRVariable>(&mut variables, NgIRVariable(name_start=28, name_end=33, name_fingerprint=ng_span_fingerprint(&source, 28, 33), type_kind=1, mutable=0, register=2, memory=-1, parent_index=1, field_name_start=28, field_name_end=33))
    discard vector_push<NgIRVariable>(&mut variables, NgIRVariable(name_start=56, name_end=73, name_fingerprint=ng_span_fingerprint(&source, 56, 73), type_kind=1, mutable=0, register=3, memory=-1, parent_index=1, field_name_start=56, field_name_end=73))
    discard vector_push<NgIRVariable>(&mut variables, NgIRVariable(name_start=74, name_end=91, name_fingerprint=ng_span_fingerprint(&source, 74, 91), type_kind=1, mutable=0, register=4, memory=-1, parent_index=1, field_name_start=74, field_name_end=91))
    sibling_index = vector_len<NgIRVariable>(&variables)
    discard vector_push<NgIRVariable>(&mut variables, NgIRVariable(name_start=34, name_end=41, name_fingerprint=ng_span_fingerprint(&source, 34, 41), type_kind=7, mutable=0, register=-1, memory=-1, parent_index=0, field_name_start=34, field_name_end=41))
    while index < {sibling_count}:
        discard vector_push<NgIRVariable>(&mut variables, NgIRVariable(name_start=12, name_end=16, name_fingerprint=ng_span_fingerprint(&source, 12, 16), type_kind=1, mutable=0, register=index, memory=-1, parent_index=sibling_index, field_name_start=12, field_name_end=16))
        index = index + 1
    index = 0
    while index < {root_count}:
        discard vector_push<NgIRVariable>(&mut variables, NgIRVariable(name_start=42, name_end=47, name_fingerprint=ng_span_fingerprint(&source, 42, 47), type_kind=1, mutable=0, register=index, memory=-1, parent_index=-1, field_name_start=-1, field_name_end=-1))
        index = index + 1
    discard vector_push<i64>(&mut result, ng_ir_variable_field_index(&source, &variables, 1, 28, 33))
    discard vector_push<i64>(&mut result, ng_ir_variable_field_index(&source, &variables, 3, 23, 27))
    discard vector_push<i64>(&mut result, ng_ir_variable_field_index(&source, &variables, 1, 48, 55))
    discard vector_push<i64>(&mut result, ng_ir_variable_field_index(&source, &variables, 1, 74, 91))
    discard vector_push<NgIRVariable>(&mut invalid_variables, NgIRVariable(name_start=0, name_end=4, name_fingerprint=fingerprint, type_kind=7, mutable=0, register=-1, memory=-1, parent_index=-1, field_name_start=-1, field_name_end=-1))
    discard vector_push<NgIRVariable>(&mut invalid_variables, NgIRVariable(name_start=12, name_end=16, name_fingerprint=ng_span_fingerprint(&source, 12, 16), type_kind=1, mutable=0, register=0, memory=-1, parent_index=2, field_name_start=12, field_name_end=16))
    discard vector_push<i64>(&mut result, ng_ir_variable_field_index(&source, &invalid_variables, 0, 12, 16))
    return result
'''
    harness_source = _NG_SOURCE + "\n" + wrapper
    compilation = compile_source(harness_source)
    assert compilation.ir is not None
    metrics: dict[str, object] = {}
    result = _execute_ir_with_step_budget(
        compilation.ir,
        source_text=harness_source,
        max_steps=10_000_000,
        metrics=metrics,
    )

    assert hasattr(result, "element_type")
    assert [int(result.get(index)) for index in range(result.length)] == [5, 4, -12, 7, -14]
    line_counts = metrics["line_counts"]
    assert isinstance(line_counts, dict)
    lookup_steps = int(line_counts.get("ng_ir_variable_field_index", 0))
    print(f"IR_FIELD_LOOKUP_PROFILE variables={9 + sibling_count + root_count} steps={lookup_steps}")
    assert lookup_steps < 25_000


def test_ng_ir_variable_lookup_skips_contiguous_record_cells() -> None:
    child_count = 256
    wrapper = f'''\
fn main() -> vector<i64>:
    mut source_text: text = text_from_static("item item other missing")
    mut source: bytes = bytes_from_text(&source_text)
    mut variables: vector<NgIRVariable> = vector_new<NgIRVariable>(1024)
    mut result: vector<i64> = vector_new<i64>(3)
    mut index: i64 = 0
    mut fingerprint: i64 = ng_span_fingerprint(&source, 0, 4)
    mut shadow_index: i64 = -1
    mut other_index: i64 = -1
    mut invalid_index: i64 = -1
    discard vector_push<NgIRVariable>(&mut variables, NgIRVariable(name_start=0, name_end=4, name_fingerprint=fingerprint, type_kind=7, mutable=0, register=-1, memory=-1, parent_index=-1, field_name_start=-1, field_name_end=-1))
    while index < {child_count}:
        discard vector_push<NgIRVariable>(&mut variables, NgIRVariable(name_start=0, name_end=4, name_fingerprint=fingerprint, type_kind=1, mutable=0, register=index, memory=-1, parent_index=0, field_name_start=-1, field_name_end=-1))
        index = index + 1
    shadow_index = vector_len<NgIRVariable>(&variables)
    fingerprint = ng_span_fingerprint(&source, 5, 9)
    discard vector_push<NgIRVariable>(&mut variables, NgIRVariable(name_start=5, name_end=9, name_fingerprint=fingerprint, type_kind=7, mutable=0, register=-1, memory=-1, parent_index=-1, field_name_start=-1, field_name_end=-1))
    index = 0
    while index < {child_count}:
        discard vector_push<NgIRVariable>(&mut variables, NgIRVariable(name_start=5, name_end=9, name_fingerprint=fingerprint, type_kind=1, mutable=0, register=index, memory=-1, parent_index=shadow_index, field_name_start=-1, field_name_end=-1))
        index = index + 1
    other_index = vector_len<NgIRVariable>(&variables)
    fingerprint = ng_span_fingerprint(&source, 10, 15)
    discard vector_push<NgIRVariable>(&mut variables, NgIRVariable(name_start=10, name_end=15, name_fingerprint=fingerprint, type_kind=7, mutable=0, register=-1, memory=-1, parent_index=-1, field_name_start=-1, field_name_end=-1))
    index = 0
    while index < {child_count}:
        discard vector_push<NgIRVariable>(&mut variables, NgIRVariable(name_start=10, name_end=15, name_fingerprint=fingerprint, type_kind=1, mutable=0, register=index, memory=-1, parent_index=other_index, field_name_start=-1, field_name_end=-1))
        index = index + 1
    discard vector_push<i64>(&mut result, ng_ir_variable_index(&source, &variables, 0, 4))
    discard vector_push<i64>(&mut result, ng_ir_variable_index(&source, &variables, 16, 23))
    invalid_index = vector_len<NgIRVariable>(&variables)
    discard vector_push<NgIRVariable>(&mut variables, NgIRVariable(name_start=0, name_end=4, name_fingerprint=fingerprint, type_kind=1, mutable=0, register=-1, memory=-1, parent_index=invalid_index, field_name_start=-1, field_name_end=-1))
    discard vector_push<i64>(&mut result, ng_ir_variable_index(&source, &variables, 16, 23))
    return result
'''
    harness_source = _NG_SOURCE + "\n" + wrapper
    compilation = compile_source(harness_source)
    assert compilation.ir is not None
    metrics: dict[str, object] = {}
    result = _execute_ir_with_step_budget(
        compilation.ir,
        source_text=harness_source,
        max_steps=10_000_000,
        metrics=metrics,
    )

    assert hasattr(result, "element_type")
    assert [int(result.get(index)) for index in range(result.length)] == [child_count + 1, -12, -14]
    line_counts = metrics["line_counts"]
    assert isinstance(line_counts, dict)
    calls = metrics["calls"]
    assert isinstance(calls, dict)
    lookup_steps = int(line_counts.get("ng_ir_variable_index", 0))
    fingerprint_calls = int(calls.get("ng_span_fingerprint", 0))
    total_steps = int(metrics["steps"])
    print(
        f"IR_VARIABLE_LOOKUP_PROFILE cells={3 * (child_count + 1) + 1} "
        f"steps={lookup_steps} total_steps={total_steps} fingerprints={fingerprint_calls}"
    )
    assert fingerprint_calls == 3
    assert total_steps < 419_174
    assert lookup_steps < 50_000


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


def test_ng_self_compiles_real_span_fingerprint_function() -> None:
    lexer_source = (_ROOT / "selfhost/compiler_ng/lexer.s3").read_text(encoding="utf-8")
    lexer_source = lexer_source.split("\nexport fn ng_spans_equal", maxsplit=1)[0] + "\n"
    app_source = (
        "module app\n"
        "from selfhost.compiler_ng.lexer import ng_span_fingerprint\n"
        "fn main() -> i64:\n"
        "    mut input: bytes = bytes_new(8)\n"
        "    discard bytes_push(&mut input, 97)\n"
        "    discard bytes_push(&mut input, 98)\n"
        "    discard bytes_push(&mut input, 99)\n"
        "    discard bytes_push(&mut input, 100)\n"
        "    discard bytes_push(&mut input, 101)\n"
        "    discard bytes_push(&mut input, 102)\n"
        "    discard bytes_push(&mut input, 103)\n"
        "    discard bytes_push(&mut input, 104)\n"
        "    return ng_span_fingerprint(&input, 0, 8)\n"
    )
    sources = {
        "app.s3": app_source,
        "character_classes.s3": (
            _ROOT / "selfhost/compiler_ng/character_classes.s3"
        ).read_text(encoding="utf-8"),
        "lexer.s3": lexer_source,
    }
    reference = compile_sources(sources, entry_module="app").ir
    assert reference is not None

    metrics: dict[str, object] = {}
    status, source, cells = _run_ng_source_set_events(
        sources,
        entry_module="app",
        max_steps=250_000_000,
        metrics=metrics,
    )
    assert status == 0, (
        f"NG status={status}; line_counts={metrics.get('line_counts')}; "
        f"event_tail={cells[-32:]}"
    )
    ng_ir = decode_ng_ir_events(source, cells)
    verify_ir(ng_ir)
    verify_ir(reference)

    actual = _canonical_structure(ng_ir)
    expected = _canonical_structure(reference)
    actual_function = next(
        item for item in actual[0]
        if item[0] == "__s3mod_selfhost_compiler_ng_lexer__ng_span_fingerprint"
    )
    expected_function = next(
        item for item in expected[0]
        if item[0] == "__s3mod_selfhost_compiler_ng_lexer__ng_span_fingerprint"
    )

    def register_context(module: IRModule, register: int) -> str:
        function = next(
            item
            for item in module.functions
            if item.name == "__s3mod_selfhost_compiler_ng_lexer__ng_span_fingerprint"
        )
        for block in function.blocks:
            for index, instruction in enumerate(block.instructions):
                if register in instruction.results:
                    lower = max(0, index - 3)
                    upper = min(len(block.instructions), index + 4)
                    return (
                        f"block={block.name} instruction={index} "
                        f"window={[item.to_dict() for item in block.instructions[lower:upper]]}"
                    )
        return "no producer"

    def block_summary(module: IRModule) -> tuple[tuple[str, tuple[str, ...]], ...]:
        function = next(
            item
            for item in module.functions
            if item.name == "__s3mod_selfhost_compiler_ng_lexer__ng_span_fingerprint"
        )
        return tuple(
            (
                block.name,
                tuple(instruction.opcode.value for instruction in block.instructions),
            )
            for block in function.blocks
        )

    actual_registers, expected_registers = actual_function[4], expected_function[4]
    first_register_difference = next(
        (
            (
                index,
                actual_registers[index] if index < len(actual_registers) else None,
                expected_registers[index] if index < len(expected_registers) else None,
            )
            for index in range(max(len(actual_registers), len(expected_registers)))
            if index >= len(actual_registers)
            or index >= len(expected_registers)
            or actual_registers[index] != expected_registers[index]
        ),
        None,
    )
    assert actual_function == expected_function, (
        f"fingerprint registers: counts {len(actual_registers)} != "
        f"{len(expected_registers)}; first difference at {first_register_difference}; "
        f"actual r25={register_context(ng_ir, 25)}; "
        f"reference r25={register_context(reference, 25)}; "
        f"blocks={_first_structure_difference(actual_function[6], expected_function[6], 'blocks')}; "
        f"actual_cfg={block_summary(ng_ir)}; reference_cfg={block_summary(reference)}; "
        + _first_structure_difference(
            actual_function, expected_function, "ng_span_fingerprint"
        )
    )
    assert execute_ir(ng_ir) == execute_ir(reference)


def test_ng_compiles_and_executes_real_lexer_source_set() -> None:
    app_source = (
        "module app\n"
        "from selfhost.compiler_ng.lexer import NgToken\n"
        "from selfhost.compiler_ng.lexer import ng_lex\n"
        "fn main() -> i64:\n"
        "    mut input: bytes = bytes_new(32)\n"
        "    discard bytes_push(&mut input, 95)\n"
        "    discard bytes_push(&mut input, 97)\n"
        "    discard bytes_push(&mut input, 108)\n"
        "    discard bytes_push(&mut input, 112)\n"
        "    discard bytes_push(&mut input, 104)\n"
        "    discard bytes_push(&mut input, 97)\n"
        "    discard bytes_push(&mut input, 32)\n"
        "    discard bytes_push(&mut input, 60)\n"
        "    discard bytes_push(&mut input, 61)\n"
        "    discard bytes_push(&mut input, 62)\n"
        "    discard bytes_push(&mut input, 32)\n"
        "    discard bytes_push(&mut input, 55)\n"
        "    mut tokens: vector<NgToken> = vector_new<NgToken>(16)\n"
        "    mut status: i64 = ng_lex(&input, &mut tokens)\n"
        "    match status <=> 0:\n"
        "        -1:\n"
        "            return -1\n"
        "        0:\n"
        "            return vector_len<NgToken>(&tokens)\n"
        "        1:\n"
        "            return -1\n"
    )
    sources = {
        "app.s3": app_source,
        "character_classes.s3": (
            _ROOT / "selfhost/compiler_ng/character_classes.s3"
        ).read_text(encoding="utf-8"),
        "lexer.s3": (_ROOT / "selfhost/compiler_ng/lexer.s3").read_text(
            encoding="utf-8"
        ),
    }

    reference = compile_sources(sources, entry_module="app").ir
    assert reference is not None
    source, cells = _emit_ng_source_set_events(
        sources, entry_module="app", max_steps=250_000_000
    )
    ng_ir = decode_ng_ir_events(source, cells)
    verify_ir(ng_ir)
    verify_ir(reference)
    ng_shapes = {item[0]: item for item in _canonical_structure(ng_ir)[0]}
    reference_shapes = {item[0]: item for item in _canonical_structure(reference)[0]}
    fingerprint_function = "__s3mod_selfhost_compiler_ng_lexer__ng_span_fingerprint"
    assert ng_shapes[fingerprint_function] == reference_shapes[fingerprint_function], (
        _first_structure_difference(
            ng_shapes[fingerprint_function],
            reference_shapes[fingerprint_function],
            fingerprint_function,
        )
    )
    ng_interfaces = tuple(
        (
            function.name,
            tuple((parameter.name, parameter.type) for parameter in function.parameters),
            function.return_type,
            function.result_types,
            function.external,
            function.exported,
        )
        for function in ng_ir.functions
    )
    reference_interfaces = tuple(
        (
            function.name,
            tuple((parameter.name, parameter.type) for parameter in function.parameters),
            function.return_type,
            function.result_types,
            function.external,
            function.exported,
        )
        for function in reference.functions
    )
    assert ng_interfaces == reference_interfaces

    lexer_predicate = "__s3mod_selfhost_compiler_ng_lexer__ng_is_identifier_start"
    ng_functions = {function.name: function for function in ng_ir.functions}
    reference_functions = {function.name: function for function in reference.functions}
    for unit, expected in ((65, -1), (95, -1), (48, 0), (96, 0)):
        actual = ir_emulator._execute_function(
            ng_functions,
            ng_functions[lexer_predicate],
            (unit,),
            (),
            {},
            HostExecutionContext(),
        )
        reference_result = ir_emulator._execute_function(
            reference_functions,
            reference_functions[lexer_predicate],
            (unit,),
            (),
            {},
            HostExecutionContext(),
        )
        assert actual == reference_result == expected

    assert execute_ir(ng_ir) == execute_ir(reference) == 4

    assembly = generate_assembly(ng_ir)
    emulator = Emulator()
    emulator.validate(assembly, entry="main")
    assert emulator.execute(assembly) == 4
    native = generate_native_assembly(assembly)
    assert ".globl s3_main" in native
    with pytest.raises(QBETranslationError, match="external or builtin call"):
        translate_verified_ir(ng_ir)


def test_ng_self_compiles_real_type_system_module_with_dereference() -> None:
    sources = {
        "app.s3": "module app\nfn main() -> i64:\n    return 0\n",
        "character_classes.s3": (_ROOT / "selfhost/compiler_ng/character_classes.s3").read_text(
            encoding="utf-8"
        ),
        "lexer.s3": (_ROOT / "selfhost/compiler_ng/lexer.s3").read_text(
            encoding="utf-8"
        ),
        "types.s3": (_ROOT / "selfhost/compiler_ng/types.s3").read_text(
            encoding="utf-8"
        ),
    }
    reference = compile_sources(sources, entry_module="app").ir
    assert reference is not None

    source, cells = _emit_ng_source_set_events(
        sources, entry_module="app", max_steps=1_000_000_000
    )
    ng_ir = decode_ng_ir_events(source, cells)
    verify_ir(ng_ir)
    actual_structure = _canonical_structure(ng_ir)
    expected_structure = _canonical_structure(reference)
    actual_functions, actual_strings = actual_structure
    expected_functions, expected_strings = expected_structure
    assert tuple(function[0] for function in actual_functions) == tuple(
        function[0] for function in expected_functions
    )
    relational_functions = {
        function.name
        for function in ng_ir.functions
        if any(
            instruction.opcode.value == "relate"
            for block in function.blocks
            for instruction in block.instructions
        )
    }
    for index, (actual_function, expected_function) in enumerate(zip(actual_functions, expected_functions)):
        if actual_function[0] in relational_functions:
            continue
        assert actual_function == expected_function, _first_structure_difference(
            actual_function,
            expected_function,
            f"function[{index}] {actual_function[0]}",
        )
    assert actual_strings == expected_strings, _first_structure_difference(
        actual_strings, expected_strings, "static_strings"
    )
    assert execute_ir(ng_ir) == execute_ir(reference) == 0
    assert any(
        instruction.opcode.value == "reference_load"
        for function in ng_ir.functions
        for instruction in function.instructions
    )


def test_ng_self_compiles_real_parser_module_with_field_assignment() -> None:
    sources = {
        "app.s3": "module app\nfn main() -> i64:\n    return 0\n",
        "character_classes.s3": (_ROOT / "selfhost/compiler_ng/character_classes.s3").read_text(
            encoding="utf-8"
        ),
        "lexer.s3": (_ROOT / "selfhost/compiler_ng/lexer.s3").read_text(
            encoding="utf-8"
        ),
        "types.s3": (_ROOT / "selfhost/compiler_ng/types.s3").read_text(
            encoding="utf-8"
        ),
        "parser.s3": (_ROOT / "selfhost/compiler_ng/parser.s3").read_text(
            encoding="utf-8"
        ),
    }
    reference = compile_sources(sources, entry_module="app").ir
    assert reference is not None

    source, cells = _emit_ng_source_set_events(
        sources, entry_module="app", max_steps=1_000_000_000
    )
    ng_ir = decode_ng_ir_events(source, cells)
    verify_ir(ng_ir)
    actual_structure = _canonical_structure(ng_ir)
    expected_structure = _canonical_structure(reference)
    assert actual_structure == expected_structure, _first_structure_difference(
        actual_structure, expected_structure, "parser_self_compile"
    )
    assert execute_ir(ng_ir) == execute_ir(reference) == 0


def test_ng_self_compiles_real_semantic_module() -> None:
    sources = {
        "app.s3": "module app\nfn main() -> i64:\n    return 0\n",
        "character_classes.s3": (_ROOT / "selfhost/compiler_ng/character_classes.s3").read_text(
            encoding="utf-8"
        ),
        "lexer.s3": (_ROOT / "selfhost/compiler_ng/lexer.s3").read_text(
            encoding="utf-8"
        ),
        "types.s3": (_ROOT / "selfhost/compiler_ng/types.s3").read_text(
            encoding="utf-8"
        ),
        "parser.s3": (_ROOT / "selfhost/compiler_ng/parser.s3").read_text(
            encoding="utf-8"
        ),
        "semantic.s3": (_ROOT / "selfhost/compiler_ng/semantic.s3").read_text(
            encoding="utf-8"
        ),
    }
    reference = compile_sources(sources, entry_module="app").ir
    assert reference is not None

    source, cells = _emit_ng_source_set_events(
        sources, entry_module="app", max_steps=1_000_000_000
    )
    ng_ir = decode_ng_ir_events(source, cells)
    verify_ir(ng_ir)
    actual_structure = _canonical_structure(ng_ir)
    expected_structure = _canonical_structure(reference)
    assert actual_structure == expected_structure, _first_structure_difference(
        actual_structure, expected_structure, "semantic_self_compile"
    )
    assert execute_ir(ng_ir) == execute_ir(reference) == 0


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


def test_ng_ir_v18_lowers_typed_unary_negation_to_canonical_invert() -> None:
    source = "\n".join(
        (
            "fn negate_i64(value: i64) -> i64:",
            "    return -value",
            "fn encode_negative_index(function_index: i64) -> i64:",
            "    return -function_index - 2",
            "fn negate_f64(value: f64) -> f64:",
            "    return -value",
            "fn negate_trit(value: trit) -> trit:",
            "    return -value",
            "fn negate_tryte(value: tryte) -> tryte:",
            "    return -value",
            "fn main() -> i64:",
            "    return negate_i64(17)",
        )
    )
    reference = compile_source(source).ir
    assert reference is not None
    events = _emit_ng_events(source)
    records = _event_records(events)
    assert records[0] == [0, 19, 8, 0, 0, 0, 0, 0]
    assert sum(record[0] == 4 and record[2] == 20 for record in records) == 5

    ng_ir = decode_ng_ir_events(source.encode("utf-8"), events)
    verify_ir(ng_ir)
    assert _canonical_structure(ng_ir) == _canonical_structure(reference)
    assert execute_ir(ng_ir) == execute_ir(reference) == -17


@pytest.mark.parametrize(
    ("type_name", "input_value", "expected"),
    (("i64", 17, -17), ("f64", 17.5, -17.5), ("trit", 1, -1), ("tryte", 17, -17)),
)
def test_ng_ir_v18_executes_typed_unary_negation(
    type_name: str, input_value: int | float, expected: int | float
) -> None:
    source = (
        f"fn negate(value: {type_name}) -> {type_name}:\n"
        "    return -value\n"
        "fn main() -> i64:\n"
        "    return 0\n"
    )
    reference = compile_source(source).ir
    assert reference is not None
    events = _emit_ng_events(source)
    ng_ir = decode_ng_ir_events(source.encode("utf-8"), events)
    verify_ir(ng_ir)

    assert _canonical_structure(ng_ir) == _canonical_structure(reference)

    def execute_with_argument(module: IRModule) -> object:
        functions = {function.name: function for function in module.functions}
        return ir_emulator._execute_function(
            functions,
            functions["negate"],
            (input_value,),
            (),
            {},
            HostExecutionContext(),
        )

    assert execute_with_argument(ng_ir) == execute_with_argument(reference) == expected


def test_ng_ir_v18_rejects_unary_negation_opcode_in_older_streams() -> None:
    source = "fn negate(value: i64) -> i64:\n    return -value\n"
    records = _event_records(_emit_ng_events(source))
    assert any(record[0] == 4 and record[2] == 20 for record in records)
    records[0][1] = 17
    with pytest.raises(NGIRDecodeError, match="INVERT opcode requires NG IR format V18"):
        decode_ng_ir_events(source.encode("utf-8"), _flatten(records))


def test_ng_ir_v11_lowers_numeric_conversions_and_dynamic_bytes_calls() -> None:
    source = "\n".join(
        (
            "fn main() -> i64:",
            "    mut data: bytes = bytes_new(2)",
            "    discard bytes_push(&mut data, 65)",
            "    discard bytes_push(&mut data, 66)",
            "    return to_i64(bytes_get(&data, 0)) + bytes_len(&data)",
        )
    )
    reference_ir = compile_source(source).ir
    assert reference_ir is not None
    cells = _emit_ng_events(source)
    records = _event_records(cells)
    assert records[0] == [0, 19, 8, 0, 0, 0, 0, 0]
    assert sum(record[0] == 21 for record in records) == 5
    assert any(record[0] == 4 and record[2] == 17 for record in records)

    ng_ir = decode_ng_ir_events(source.encode("utf-8"), cells)
    verify_ir(ng_ir)
    assert _canonical_structure(ng_ir) == _canonical_structure(reference_ir)
    assert execute_ir(ng_ir) == execute_ir(reference_ir) == 67


def test_ng_ir_v11_lowers_bytes_from_text_dynamic_builtin() -> None:
    source = "\n".join(
        (
            "fn materialize(input: &text) -> bytes:",
            "    return bytes_from_text(input)",
            "fn main() -> i64:",
            '    mut message: text = text_from_static("s3")',
            "    mut data: bytes = bytes_from_text(&message)",
            "    return bytes_len(&data)",
        )
    )
    reference_ir = compile_source(source).ir
    assert reference_ir is not None
    cells = _emit_ng_events(source)
    ng_ir = decode_ng_ir_events(source.encode("utf-8"), cells)
    verify_ir(ng_ir)

    assert _canonical_structure(ng_ir) == _canonical_structure(reference_ir)
    assert execute_ir(ng_ir) == execute_ir(reference_ir) == 2


def test_ng_ir_v11_lowers_text_len_dynamic_builtin() -> None:
    source = "\n".join(
        (
            "fn main() -> i64:",
            '    mut message: text = text_from_static("s3")',
            "    return text_len(&message)",
        )
    )
    reference_ir = compile_source(source).ir
    assert reference_ir is not None
    cells = _emit_ng_events(source)
    ng_ir = decode_ng_ir_events(source.encode("utf-8"), cells)
    verify_ir(ng_ir)

    assert _canonical_structure(ng_ir) == _canonical_structure(reference_ir)
    assert execute_ir(ng_ir) == execute_ir(reference_ir) == 2


def test_ng_ir_v11_lowers_bytes_concat_dynamic_builtin() -> None:
    source = "\n".join(
        (
            "fn main() -> i64:",
            "    mut left: bytes = bytes_new(2)",
            "    discard bytes_push(&mut left, 65)",
            "    discard bytes_push(&mut left, 66)",
            "    mut right: bytes = bytes_new(2)",
            "    discard bytes_push(&mut right, 67)",
            "    discard bytes_push(&mut right, 68)",
            "    mut joined: bytes = bytes_concat(&left, &right)",
            "    mut original_capacity: i64 = bytes_capacity(&joined)",
            "    discard bytes_reserve(&mut joined, original_capacity + 4)",
            "    return to_i64(bytes_get(&joined, 2)) + bytes_capacity(&joined)",
        )
    )
    reference_ir = compile_source(source).ir
    assert reference_ir is not None
    cells = _emit_ng_events(source)
    ng_ir = decode_ng_ir_events(source.encode("utf-8"), cells)
    verify_ir(ng_ir)

    assert _canonical_structure(ng_ir) == _canonical_structure(reference_ir)
    assert execute_ir(ng_ir) == execute_ir(reference_ir) == 75


def test_ng_source_set_rejects_bytes_builtin_argument_type_mismatch() -> None:
    sources = {
        "app.s3": (
            "module app\n"
            "fn invalid_index(data: &bytes) -> tryte:\n"
            "    return bytes_get(data, data)\n"
            "fn main() -> i64:\n"
            "    return 0\n"
        ),
    }
    status, _, events = _run_ng_source_set_events(sources, entry_module="app")
    assert status < 0
    assert events == []


def test_ng_source_set_rejects_text_len_non_text_reference() -> None:
    sources = {
        "app.s3": (
            "module app\n"
            "fn main() -> i64:\n"
            "    mut data: bytes = bytes_new(1)\n"
            "    return text_len(&data)\n"
        ),
    }
    status, _, events = _run_ng_source_set_events(sources, entry_module="app")
    assert status < 0
    assert events == []


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
        store_record = next(record for record in records if record[0] == 4 and record[2] == 10)
        store_record[5] = 999
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
        decode_ng_ir_events(source, [0, 99, 8, 0, 0, 0, 0, 0])
    with pytest.raises(NGIRDecodeError, match="type descriptor table"):
        decode_ng_ir_events(source, [0, 4, 8, 0, 0, 0, 0, 0])
    with pytest.raises(NGIRDecodeError, match="partial record"):
        decode_ng_ir_events(source, [0, 1])
