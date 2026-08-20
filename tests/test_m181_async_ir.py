from __future__ import annotations

import json

import pytest

from bootstrap.s3.async_frontend import lower_async_program, parse_async_source
from bootstrap.s3.async_ir import (
    AsyncIRFrameRuntime,
    AsyncIRPollKind,
    AsyncIRProgram,
    AsyncIRVerificationError,
    AsyncIROp,
    cancel_async_ir,
    execute_async_ir,
    execute_async_program,
    lower_async_ir,
    verify_async_ir,
)
from bootstrap.s3.pipeline import compile_source, run_source


pytestmark = pytest.mark.s3_fast


def _program():
    source = (
        "async fn child() -> i64:\n"
        "    return 7\n"
        "async fn main() -> i64:\n"
        "    return await child()\n"
    )
    parsed = parse_async_source(source)
    plans = lower_async_program(parsed.program, parsed.syntax)
    return lower_async_ir(plans)


def test_async_ir_is_materialized_in_compilation_result() -> None:
    result = compile_source(
        "async fn child() -> i64:\n"
        "    return 7\n"
        "async fn main() -> i64:\n"
        "    return await child()\n"
    )
    assert result.async_ir is not None
    assert [function.name for function in result.async_ir.functions] == ["child", "main"]
    assert result.async_ir.functions[1].blocks[1].terminator.opcode is AsyncIROp.SUSPEND
    assert result.async_ir.functions[1].executable is not None


def test_pipeline_executes_source_await_through_resumable_ir_and_preserves_value() -> None:
    source = (
        "async fn child() -> i64:\n"
        "    return 7\n"
        "async fn main() -> i64:\n"
        "    return await child()\n"
    )
    compilation = compile_source(source)
    program = compilation.async_ir
    assert program is not None
    main = program.ir_function("main")
    assert main is not None
    frame, first = execute_async_ir(main, program=program)
    assert first.kind is AsyncIRPollKind.PENDING
    assert first.state == "suspended_0"
    _, second = execute_async_ir(main, frame=frame, program=program)
    assert second.kind is AsyncIRPollKind.READY
    assert second.value == 7
    assert execute_async_program(program).value == 7
    assert run_source(source) == 7


def test_zero_await_and_one_await_execute_structural_compatibility_ir() -> None:
    program = _program()
    child = program.functions[0]
    main = program.functions[1]
    _, child_result = execute_async_ir(child)
    assert child_result.kind is AsyncIRPollKind.READY
    frame, pending = execute_async_ir(main)
    assert pending.kind is AsyncIRPollKind.PENDING
    assert pending.state == "suspended_0"
    _, ready = execute_async_ir(main, frame=frame)
    assert ready.kind is AsyncIRPollKind.READY
    assert ready.state == "completed"


def test_multiple_suspensions_have_resume_edges_and_deterministic_layout() -> None:
    source = (
        "async fn child() -> i64:\n"
        "    return 7\n"
        "async fn main() -> i64:\n"
        "    first: i64 = await child()\n"
        "    return await child()\n"
    )
    parsed = parse_async_source(source)
    plan = lower_async_program(parsed.program, parsed.syntax)[1]
    first = lower_async_ir((plan,))
    second = lower_async_ir((plan,))
    assert first.to_dict() == second.to_dict()
    function = first.functions[0]
    assert [block.state for block in function.blocks if block.state.startswith("suspended_")] == ["suspended_0", "suspended_1"]
    assert run_source(source) == 7


def test_owned_frame_slots_drop_once_and_moved_slots_do_not_drop() -> None:
    function = _program().functions[1]
    frame = AsyncIRFrameRuntime(function)
    frame.initialize(0, "owned") if function.frame.slots else None
    if function.frame.slots:
        frame.move(0)
    _, pending = execute_async_ir(function, frame=frame)
    assert pending.kind is AsyncIRPollKind.PENDING
    result = cancel_async_ir(function, frame)
    assert result.kind is AsyncIRPollKind.CANCELLED
    assert frame.drop_log == []
    assert cancel_async_ir(function, frame).kind is AsyncIRPollKind.FAILED


def test_unmoved_slot_is_dropped_on_completion_and_cancel() -> None:
    function = _program().functions[1]
    frame = AsyncIRFrameRuntime(function)
    if function.frame.slots:
        frame.initialize(0, "owned")
    _, pending = execute_async_ir(function, frame=frame)
    assert pending.kind is AsyncIRPollKind.PENDING
    assert cancel_async_ir(function, frame).kind is AsyncIRPollKind.CANCELLED
    assert frame.drop_log == ([0] if function.frame.slots else [])


def test_invalid_resume_target_is_rejected() -> None:
    program = _program()
    function = program.functions[1]
    block = function.blocks[2]
    bad = type(block)(block.name, block.state, (type(block.instructions[0])(AsyncIROp.RESUME, target="entry"),))
    broken = type(function)(function.name, function.frame, tuple(bad if item is block else item for item in function.blocks))
    with pytest.raises(AsyncIRVerificationError, match="resume target"):
        verify_async_ir(AsyncIRProgram((broken,)))


def test_terminal_blocks_have_explicit_drop_paths() -> None:
    function = _program().functions[1]
    for name in ("completed", "failed", "cancelled"):
        block = next(item for item in function.blocks if item.name == name)
        assert block.instructions[-1].opcode in {AsyncIROp.COMPLETE, AsyncIROp.FAIL, AsyncIROp.CANCEL}
        assert all(item.opcode is AsyncIROp.SLOT_DROP for item in block.instructions[:-1])


def test_serialized_ir_is_json_stable() -> None:
    encoded = json.dumps(_program().to_dict(), sort_keys=True, separators=(",", ":"))
    assert encoded == json.dumps(_program().to_dict(), sort_keys=True, separators=(",", ":"))


def test_executable_async_ir_serialization_is_deterministic() -> None:
    source = (
        "async fn child() -> i64:\n"
        "    return 5\n"
        "async fn main() -> i64:\n"
        "    value: i64 = await child()\n"
        "    return value + 2\n"
    )
    first = compile_source(source).async_ir
    second = compile_source(source).async_ir
    assert first is not None and second is not None
    assert first.to_dict() == second.to_dict()
    assert run_source(source) == 7
