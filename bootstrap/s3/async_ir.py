"""Native compiler IR for bounded resumable async frames (M1.81/M1.82)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping

from .async_frontend import AsyncStateMachinePlan
from .async_language import (
    AsyncAction,
    AsyncActionKind,
    AsyncExecutableFunction,
    AsyncExecutableProgram,
    AsyncExpression,
    AsyncExpressionKind,
)


class AsyncIRVerificationError(ValueError):
    """Raised when a resumable async IR graph is not fail-closed."""


class AsyncIROp(Enum):
    FRAME_INIT = "frame_init"
    SLOT_INIT = "slot_init"
    SLOT_MOVE = "slot_move"
    SLOT_DROP = "slot_drop"
    SUSPEND = "suspend"
    RESUME = "resume"
    COMPLETE = "complete"
    FAIL = "fail"
    CANCEL = "cancel"


class AsyncIRPollKind(Enum):
    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class AsyncIRPoll:
    kind: AsyncIRPollKind
    state: str
    value: object | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class AsyncIRSlot:
    index: int
    name: str
    type_name: str = "owned"


@dataclass(frozen=True, slots=True)
class AsyncIRInstruction:
    opcode: AsyncIROp
    slot: int | None = None
    target: str | None = None
    value: object | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {"opcode": self.opcode.value}
        if self.slot is not None:
            result["slot"] = self.slot
        if self.target is not None:
            result["target"] = self.target
        if self.value is not None:
            result["value"] = self.value
        if self.error is not None:
            result["error"] = self.error
        return result


@dataclass(frozen=True, slots=True)
class AsyncIRBlock:
    name: str
    state: str
    instructions: tuple[AsyncIRInstruction, ...]

    @property
    def terminator(self) -> AsyncIRInstruction:
        if not self.instructions:
            raise AsyncIRVerificationError(f"block {self.name!r} is empty")
        return self.instructions[-1]

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "state": self.state,
            "instructions": [item.to_dict() for item in self.instructions],
        }


@dataclass(frozen=True, slots=True)
class AsyncIRFrame:
    slots: tuple[AsyncIRSlot, ...]
    states: tuple[str, ...]
    entry_block: str = "entry"
    completed_block: str = "completed"
    failed_block: str = "failed"
    cancelled_block: str = "cancelled"

    def to_dict(self) -> dict[str, object]:
        return {
            "slots": [
                {"index": slot.index, "name": slot.name, "type": slot.type_name}
                for slot in self.slots
            ],
            "states": list(self.states),
            "entry": self.entry_block,
            "completed": self.completed_block,
            "failed": self.failed_block,
            "cancelled": self.cancelled_block,
        }


@dataclass(frozen=True, slots=True)
class AsyncIRFunction:
    name: str
    frame: AsyncIRFrame
    blocks: tuple[AsyncIRBlock, ...]
    executable: AsyncExecutableFunction | None = None

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "name": self.name,
            "frame": self.frame.to_dict(),
            "blocks": [block.to_dict() for block in self.blocks],
        }
        if self.executable is not None:
            result["executable"] = {
                "parameters": list(self.executable.parameters),
                "future_parameters": list(self.executable.future_parameters),
                "actions": [_action_to_dict(action) for action in self.executable.actions],
                "generic_parameters": [list(item) for item in self.executable.generic_parameters],
            }
        return result


@dataclass(frozen=True, slots=True)
class AsyncIRProgram:
    functions: tuple[AsyncIRFunction, ...]
    support_functions: tuple[AsyncExecutableFunction, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "functions": [function.to_dict() for function in self.functions],
            "support_functions": [
                {
                    "name": function.name,
                    "parameters": list(function.parameters),
                    "future_parameters": list(function.future_parameters),
                    "actions": [_action_to_dict(action) for action in function.actions],
                }
                for function in self.support_functions
            ],
        }

    def executable(self, name: str) -> AsyncExecutableFunction | None:
        for function in self.functions:
            if function.name == name and function.executable is not None:
                return function.executable
        for function in self.support_functions:
            if function.name == name:
                return function
        return None

    def ir_function(self, name: str) -> AsyncIRFunction | None:
        for function in self.functions:
            if function.name == name:
                return function
        return None


@dataclass(slots=True)
class _RuntimeSlot:
    value: object | None = None
    initialized: bool = False
    moved: bool = False
    dropped: bool = False


@dataclass(slots=True)
class _OwnedIRFuture:
    callee: str
    arguments: tuple[object, ...]
    type_arguments: tuple[str, ...] = ()
    consumed: bool = False
    dropped: bool = False
    frame: AsyncIRFrameRuntime | None = None

    def resolve(self, program: AsyncIRProgram) -> AsyncIRPoll:
        result = self.poll(program)
        if result.kind is not AsyncIRPollKind.PENDING:
            self.consume()
        return result

    def poll(self, program: AsyncIRProgram) -> AsyncIRPoll:
        if self.consumed or self.dropped:
            return AsyncIRPoll(AsyncIRPollKind.FAILED, "failed", error="Future was already moved, consumed, or dropped")
        function = program.ir_function(self.callee)
        if function is None:
            # Non-async support functions have no resumable suspension point.
            # Their bounded evaluator remains the only valid execution path.
            return execute_async_program(program, self.callee, arguments=self.arguments, max_polls=1)
        self.frame, result = execute_async_ir(
            function,
            frame=self.frame,
            program=program,
            arguments=self.arguments if self.frame is None else (),
        )
        return result

    def consume(self) -> None:
        if self.consumed or self.dropped:
            raise AsyncIRVerificationError("Future was already moved, consumed, or dropped")
        self.consumed = True

    def drop(self) -> None:
        if self.consumed or self.dropped:
            return
        if self.frame is not None and not self.frame.consumed:
            self.frame.drop_all()
            self.frame.consumed = True
            self.frame.state = "cancelled"
            self.frame.block = self.frame.function.frame.cancelled_block
        self.dropped = True


@dataclass(slots=True)
class _SelectCandidate:
    arm: object
    future: _OwnedIRFuture
    source_name: str | None


@dataclass(slots=True)
class AsyncIRFrameRuntime:
    function: AsyncIRFunction
    slots: list[_RuntimeSlot] = field(default_factory=list)
    state: str = "created"
    block: str = "entry"
    consumed: bool = False
    drop_log: list[int] = field(default_factory=list)
    bindings: dict[str, object] = field(default_factory=dict)
    futures: dict[str, _OwnedIRFuture] = field(default_factory=dict)
    action_queue: list[AsyncAction] = field(default_factory=list)
    action_index: int = 0
    pending_action_index: int | None = None
    pending_future: _OwnedIRFuture | None = None
    select_candidates: list[_SelectCandidate] | None = None
    parameters_bound: bool = False
    suspension_index: int = 0

    def __post_init__(self) -> None:
        self.slots = [_RuntimeSlot() for _ in self.function.frame.slots]

    def initialize(self, index: int, value: object) -> None:
        slot = self._slot(index)
        if slot.initialized or slot.moved or slot.dropped:
            raise AsyncIRVerificationError(f"slot {index} initialized twice")
        slot.value = value
        slot.initialized = True

    def move(self, index: int) -> object:
        slot = self._slot(index)
        if not slot.initialized or slot.moved or slot.dropped:
            raise AsyncIRVerificationError(f"slot {index} move is invalid")
        slot.moved = True
        value = slot.value
        slot.value = None
        return value

    def drop(self, index: int) -> None:
        slot = self._slot(index)
        if slot.dropped:
            return
        slot.dropped = True
        if slot.initialized and not slot.moved:
            self.drop_log.append(index)
        slot.value = None

    def drop_all(self) -> None:
        for slot in range(len(self.slots)):
            self.drop(slot)
        for future in tuple(self.futures.values()):
            future.drop()
        self.futures.clear()
        if self.pending_future is not None:
            self.pending_future.drop()
            self.pending_future = None
        if self.select_candidates is not None:
            for candidate in self.select_candidates:
                candidate.future.drop()
            self.select_candidates = None

    def _slot(self, index: int) -> _RuntimeSlot:
        if index < 0 or index >= len(self.slots):
            raise AsyncIRVerificationError(f"unknown frame slot {index}")
        return self.slots[index]


def verify_async_ir(program: AsyncIRProgram) -> None:
    """Verify graph shape, state table, ownership operations, and terminal paths."""

    names: set[str] = set()
    for function in program.functions:
        if function.name in names:
            raise AsyncIRVerificationError(f"duplicate async function {function.name!r}")
        names.add(function.name)
        _verify_function(function)
    support_names = [item.name for item in program.support_functions]
    if len(set(support_names)) != len(support_names) or names.intersection(support_names):
        raise AsyncIRVerificationError("async executable function identities are duplicated")


def _verify_function(function: AsyncIRFunction) -> None:
    frame = function.frame
    if not frame.states or frame.states[0] != "created":
        raise AsyncIRVerificationError("async frame must start in created state")
    if len(set(frame.states)) != len(frame.states):
        raise AsyncIRVerificationError("async frame state table contains duplicates")
    slots = {slot.index for slot in frame.slots}
    if slots != set(range(len(frame.slots))):
        raise AsyncIRVerificationError("async frame slots must be contiguous")
    if len({slot.name for slot in frame.slots}) != len(frame.slots):
        raise AsyncIRVerificationError("async frame slot names must be unique")
    blocks = {block.name: block for block in function.blocks}
    if len(blocks) != len(function.blocks):
        raise AsyncIRVerificationError("async IR block names must be unique")
    if frame.entry_block not in blocks:
        raise AsyncIRVerificationError("async frame entry block is missing")
    if frame.completed_block not in blocks or frame.failed_block not in blocks or frame.cancelled_block not in blocks:
        raise AsyncIRVerificationError("async frame terminal cleanup block is missing")
    terminal_ops = {AsyncIROp.COMPLETE, AsyncIROp.FAIL, AsyncIROp.CANCEL}
    for block in function.blocks:
        if block.state not in frame.states:
            raise AsyncIRVerificationError(f"block {block.name!r} uses undeclared state")
        if not block.instructions or block.terminator.opcode not in terminal_ops | {AsyncIROp.SUSPEND, AsyncIROp.RESUME}:
            raise AsyncIRVerificationError(f"block {block.name!r} has invalid terminator")
        for instruction in block.instructions:
            if instruction.slot is not None and instruction.slot not in slots:
                raise AsyncIRVerificationError(f"block {block.name!r} uses unknown slot")
            if instruction.opcode in {AsyncIROp.SUSPEND, AsyncIROp.RESUME}:
                if instruction.target not in blocks:
                    raise AsyncIRVerificationError(f"block {block.name!r} targets an unknown block")
                target = blocks[instruction.target]
                if instruction.opcode is AsyncIROp.SUSPEND and not target.state.startswith("suspended_"):
                    raise AsyncIRVerificationError("suspend target must be a suspended state")
                if instruction.opcode is AsyncIROp.RESUME and not target.state.startswith("running_"):
                    raise AsyncIRVerificationError("resume target must be a running state")
    for terminal_name, opcode in (
        (frame.completed_block, AsyncIROp.COMPLETE),
        (frame.failed_block, AsyncIROp.FAIL),
        (frame.cancelled_block, AsyncIROp.CANCEL),
    ):
        block = blocks[terminal_name]
        if block.terminator.opcode is not opcode:
            raise AsyncIRVerificationError(f"terminal block {terminal_name!r} has the wrong opcode")
        dropped = {item.slot for item in block.instructions if item.opcode is AsyncIROp.SLOT_DROP}
        if dropped != slots:
            raise AsyncIRVerificationError(f"terminal block {terminal_name!r} does not drop every slot")


def lower_async_ir(plans: tuple[AsyncStateMachinePlan, ...]) -> AsyncIRProgram:
    """Lower M1.71 plans into deterministic structural frame/state/block IR."""

    functions: list[AsyncIRFunction] = []
    for plan in plans:
        slots = tuple(AsyncIRSlot(index, name) for index, name in enumerate(plan.frame_slots))
        states = tuple(plan.states)
        blocks: list[AsyncIRBlock] = [
            AsyncIRBlock(
                "entry",
                "created",
                (AsyncIRInstruction(AsyncIROp.FRAME_INIT), AsyncIRInstruction(AsyncIROp.RESUME, target="running_0")),
            )
        ]
        for index, point in enumerate(plan.suspension_points):
            running = f"running_{index}"
            suspended = point.suspended_state
            next_running = point.resume_state
            blocks.append(AsyncIRBlock(running, running, (AsyncIRInstruction(AsyncIROp.SUSPEND, target=suspended),)))
            blocks.append(AsyncIRBlock(suspended, suspended, (AsyncIRInstruction(AsyncIROp.RESUME, target=next_running),)))
        final_running = f"running_{len(plan.suspension_points)}"
        blocks.append(AsyncIRBlock(final_running, final_running, (AsyncIRInstruction(AsyncIROp.COMPLETE, target="completed"),)))
        cleanup = tuple(AsyncIRInstruction(AsyncIROp.SLOT_DROP, slot=slot.index) for slot in slots)
        blocks.extend(
            (
                AsyncIRBlock("completed", "completed", cleanup + (AsyncIRInstruction(AsyncIROp.COMPLETE),)),
                AsyncIRBlock("failed", "failed", cleanup + (AsyncIRInstruction(AsyncIROp.FAIL, error="async failure"),)),
                AsyncIRBlock("cancelled", "cancelled", cleanup + (AsyncIRInstruction(AsyncIROp.CANCEL),)),
            )
        )
        function = AsyncIRFunction(plan.function_name, AsyncIRFrame(slots, states), tuple(blocks))
        _verify_function(function)
        functions.append(function)
    program = AsyncIRProgram(tuple(functions))
    verify_async_ir(program)
    return program


def lower_executable_async_ir(executable: AsyncExecutableProgram) -> AsyncIRProgram:
    """Materialize executable async actions into explicit resumable IR frames."""

    functions: list[AsyncIRFunction] = []
    support: list[AsyncExecutableFunction] = []
    for model in executable.functions:
        if not model.async_function:
            support.append(model)
            continue
        slots = tuple(AsyncIRSlot(index, name) for index, name in enumerate(model.frame_slots))
        await_actions = list(_iter_await_actions(model.actions))
        states: list[str] = ["created", "running_0"]
        for index in range(len(await_actions)):
            states.extend((f"suspended_{index}", f"running_{index + 1}"))
        states.extend(("completed", "failed", "cancelled"))
        blocks: list[AsyncIRBlock] = [
            AsyncIRBlock("entry", "created", (AsyncIRInstruction(AsyncIROp.FRAME_INIT), AsyncIRInstruction(AsyncIROp.RESUME, target="running_0")))
        ]
        for index in range(len(await_actions)):
            blocks.append(AsyncIRBlock(f"running_{index}", f"running_{index}", (AsyncIRInstruction(AsyncIROp.SUSPEND, target=f"suspended_{index}"),)))
            blocks.append(AsyncIRBlock(f"suspended_{index}", f"suspended_{index}", (AsyncIRInstruction(AsyncIROp.RESUME, target=f"running_{index + 1}"),)))
        final_running = f"running_{len(await_actions)}"
        blocks.append(AsyncIRBlock(final_running, final_running, (AsyncIRInstruction(AsyncIROp.COMPLETE, target="completed"),)))
        cleanup = tuple(AsyncIRInstruction(AsyncIROp.SLOT_DROP, slot=slot.index) for slot in slots)
        blocks.extend(
            (
                AsyncIRBlock("completed", "completed", cleanup + (AsyncIRInstruction(AsyncIROp.COMPLETE),)),
                AsyncIRBlock("failed", "failed", cleanup + (AsyncIRInstruction(AsyncIROp.FAIL, error="async failure"),)),
                AsyncIRBlock("cancelled", "cancelled", cleanup + (AsyncIRInstruction(AsyncIROp.CANCEL),)),
            )
        )
        functions.append(AsyncIRFunction(model.name, AsyncIRFrame(slots, tuple(states)), tuple(blocks), model))
    program = AsyncIRProgram(tuple(functions), tuple(support))
    verify_async_ir(program)
    return program


def execute_async_ir(
    function: AsyncIRFunction,
    *,
    frame: AsyncIRFrameRuntime | None = None,
    initial_slots: Mapping[int, object] | None = None,
    program: AsyncIRProgram | None = None,
    arguments: tuple[object, ...] = (),
) -> tuple[AsyncIRFrameRuntime, AsyncIRPoll]:
    """Execute one async IR step until suspension or terminal state."""

    verify_async_ir(AsyncIRProgram((function,)))
    runtime = frame or AsyncIRFrameRuntime(function)
    if function.executable is not None:
        if program is None:
            return runtime, AsyncIRPoll(AsyncIRPollKind.FAILED, runtime.state, error="executable async IR requires its program catalog")
        return _execute_executable(function, runtime, program, arguments)

    if initial_slots and runtime.state == "created":
        for index, value in sorted(initial_slots.items()):
            runtime.initialize(index, value)
    if runtime.consumed:
        return runtime, AsyncIRPoll(AsyncIRPollKind.FAILED, runtime.state, error="terminal future consumed")
    blocks = {block.name: block for block in function.blocks}
    while True:
        block = blocks[runtime.block]
        transitioned = False
        for instruction in block.instructions:
            if instruction.opcode is AsyncIROp.FRAME_INIT:
                runtime.state = "created"
            elif instruction.opcode is AsyncIROp.SLOT_INIT:
                if instruction.slot is None:
                    raise AsyncIRVerificationError("slot_init requires a slot")
                runtime.initialize(instruction.slot, instruction.value)
            elif instruction.opcode is AsyncIROp.SLOT_MOVE:
                if instruction.slot is None:
                    raise AsyncIRVerificationError("slot_move requires a slot")
                runtime.move(instruction.slot)
            elif instruction.opcode is AsyncIROp.SLOT_DROP:
                if instruction.slot is None:
                    raise AsyncIRVerificationError("slot_drop requires a slot")
                runtime.drop(instruction.slot)
            elif instruction.opcode is AsyncIROp.SUSPEND:
                runtime.block = instruction.target or ""
                runtime.state = blocks[runtime.block].state
                return runtime, AsyncIRPoll(AsyncIRPollKind.PENDING, runtime.state)
            elif instruction.opcode is AsyncIROp.RESUME:
                runtime.state = blocks[instruction.target or ""].state
                runtime.block = instruction.target or ""
                transitioned = True
                break
            elif instruction.opcode is AsyncIROp.COMPLETE:
                if instruction.target is not None:
                    runtime.state = blocks[instruction.target].state
                    runtime.block = instruction.target
                    transitioned = True
                    break
                return _finish(runtime, AsyncIRPollKind.READY, "completed")
            elif instruction.opcode is AsyncIROp.FAIL:
                if instruction.target is not None:
                    runtime.state = blocks[instruction.target].state
                    runtime.block = instruction.target
                    transitioned = True
                    break
                return _finish(runtime, AsyncIRPollKind.FAILED, "failed", error=instruction.error)
            elif instruction.opcode is AsyncIROp.CANCEL:
                if instruction.target is not None:
                    runtime.state = blocks[instruction.target].state
                    runtime.block = instruction.target
                    transitioned = True
                    break
                return _finish(runtime, AsyncIRPollKind.CANCELLED, "cancelled")
        if not transitioned:
            raise AsyncIRVerificationError(f"block {block.name!r} did not transition")


def execute_async_program(
    program: AsyncIRProgram,
    entry: str = "main",
    *,
    arguments: tuple[object, ...] = (),
    max_polls: int = 100_000,
) -> AsyncIRPoll:
    """Drive one compiler-owned async function to a terminal result."""

    if isinstance(max_polls, bool) or not isinstance(max_polls, int) or not 1 <= max_polls <= 100_000:
        return AsyncIRPoll(AsyncIRPollKind.FAILED, "failed", error="async poll limit must be within 1..100000")
    function = program.ir_function(entry)
    if function is None:
        support = program.executable(entry)
        if support is None:
            return AsyncIRPoll(AsyncIRPollKind.FAILED, "failed", error=f"unknown async executable function {entry!r}")
        return _execute_support_function(program, support, arguments)
    frame: AsyncIRFrameRuntime | None = None
    for _ in range(max_polls):
        frame, result = execute_async_ir(function, frame=frame, program=program, arguments=arguments)
        if result.kind is not AsyncIRPollKind.PENDING:
            return result
    if frame is not None:
        frame.drop_all()
        frame.state = "failed"
        frame.consumed = True
    return AsyncIRPoll(AsyncIRPollKind.FAILED, "failed", error="async program exceeded poll limit")


def cancel_async_ir(function: AsyncIRFunction, frame: AsyncIRFrameRuntime) -> AsyncIRPoll:
    """Run explicit cancellation cleanup exactly once."""

    if frame.consumed:
        return AsyncIRPoll(AsyncIRPollKind.FAILED, frame.state, error="terminal future consumed")
    frame.drop_all()
    frame.state = "cancelled"
    frame.consumed = True
    frame.block = function.frame.cancelled_block
    return AsyncIRPoll(AsyncIRPollKind.CANCELLED, frame.state)


def _execute_executable(
    function: AsyncIRFunction,
    runtime: AsyncIRFrameRuntime,
    program: AsyncIRProgram,
    arguments: tuple[object, ...],
) -> tuple[AsyncIRFrameRuntime, AsyncIRPoll]:
    model = function.executable
    assert model is not None
    if runtime.consumed:
        return runtime, AsyncIRPoll(AsyncIRPollKind.FAILED, runtime.state, error="terminal future consumed")
    if not runtime.parameters_bound:
        if len(arguments) != len(model.parameters):
            return _finish(runtime, AsyncIRPollKind.FAILED, "failed", error="async argument arity mismatch")
        for name, value in zip(model.parameters, arguments):
            if name in model.future_parameters:
                if not isinstance(value, _OwnedIRFuture) or value.consumed or value.dropped:
                    return _finish(runtime, AsyncIRPollKind.FAILED, "failed", error=f"future parameter {name!r} requires live ownership")
                runtime.futures[name] = value
            else:
                runtime.bindings[name] = value
        runtime.parameters_bound = True
        runtime.action_queue = list(model.actions)
        runtime.state = "running_0"
        runtime.block = "running_0"

    if runtime.pending_action_index is not None:
        action = runtime.action_queue[runtime.pending_action_index]
        resolved = _resolve_await(action, runtime, program)
        if resolved.kind in {AsyncIRPollKind.FAILED, AsyncIRPollKind.CANCELLED}:
            return _finish(runtime, resolved.kind, resolved.state, error=resolved.error)
        if resolved.kind is AsyncIRPollKind.PENDING:
            return runtime, resolved
        value = resolved.value
        action_index = runtime.pending_action_index
        runtime.pending_action_index = None
        runtime.suspension_index += 1
        runtime.state = f"running_{runtime.suspension_index}"
        runtime.block = runtime.state
        if action.kind is AsyncActionKind.SELECT:
            selected = value
            if selected is None or not hasattr(selected, "actions"):
                return _finish(runtime, AsyncIRPollKind.FAILED, "failed", error="select resolved without a selected arm")
            runtime.action_queue[action_index:action_index + 1] = list(selected.actions)
            if not selected.actions:
                runtime.action_index += 1
        else:
            runtime.action_index += 1
        if action.kind is not AsyncActionKind.SELECT and action.target is not None:
            runtime.bindings[action.target] = value
        if action.kind is not AsyncActionKind.SELECT and action.return_after:
            return _finish(runtime, AsyncIRPollKind.READY, "completed", value=value)

    while runtime.action_index < len(runtime.action_queue):
        action = runtime.action_queue[runtime.action_index]
        try:
            if action.kind is AsyncActionKind.ASSIGN:
                runtime.bindings[_required(action.target, "assignment target")] = _eval_expression(action.expression, runtime, program)
                runtime.action_index += 1
                continue
            if action.kind is AsyncActionKind.FUTURE_CREATE:
                target = _required(action.target, "future target")
                if target in runtime.futures:
                    return _finish(runtime, AsyncIRPollKind.FAILED, "failed", error=f"live Future {target!r} would be overwritten")
                args = tuple(_eval_expression(item, runtime, program) for item in action.arguments)
                runtime.futures[target] = _OwnedIRFuture(_required(action.callee, "async callee"), args, action.type_arguments)
                runtime.action_index += 1
                continue
            if action.kind is AsyncActionKind.FUTURE_MOVE:
                source = _required(action.source_future, "future source")
                target = _required(action.target, "future target")
                future = runtime.futures.pop(source, None)
                if future is None or future.consumed or future.dropped:
                    return _finish(runtime, AsyncIRPollKind.FAILED, "failed", error=f"Future {source!r} is not live")
                if target in runtime.futures:
                    future.drop()
                    return _finish(runtime, AsyncIRPollKind.FAILED, "failed", error=f"Future {target!r} already owns a value")
                runtime.futures[target] = future
                runtime.action_index += 1
                continue
            if _is_await_action(action):
                runtime.pending_action_index = runtime.action_index
                runtime.state = f"suspended_{runtime.suspension_index}"
                runtime.block = runtime.state
                return runtime, AsyncIRPoll(AsyncIRPollKind.PENDING, runtime.state)
            if action.kind is AsyncActionKind.RETURN:
                value = _eval_expression(action.expression, runtime, program)
                runtime.action_index += 1
                return _finish(runtime, AsyncIRPollKind.READY, "completed", value=value)
            if action.kind is AsyncActionKind.DISCARD:
                if action.expression is not None:
                    _eval_expression(action.expression, runtime, program)
                runtime.action_index += 1
                continue
            return _finish(runtime, AsyncIRPollKind.FAILED, "failed", error=f"unsupported async action {action.kind.value}")
        except (AsyncIRVerificationError, ArithmeticError, TypeError, ValueError) as error:
            return _finish(runtime, AsyncIRPollKind.FAILED, "failed", error=str(error))
    return _finish(runtime, AsyncIRPollKind.FAILED, "failed", error="async function reached end without return")


def _resolve_await(action: AsyncAction, runtime: AsyncIRFrameRuntime, program: AsyncIRProgram) -> AsyncIRPoll:
    if action.kind is AsyncActionKind.SELECT:
        return _resolve_select(action, runtime, program)
    if action.callee is not None:
        if runtime.pending_future is None:
            args = tuple(_eval_expression(item, runtime, program) for item in action.arguments)
            runtime.pending_future = _OwnedIRFuture(action.callee, args)
        result = runtime.pending_future.poll(program)
        if result.kind is not AsyncIRPollKind.PENDING:
            runtime.pending_future.consume()
            runtime.pending_future = None
        return result
    if action.source_future is not None:
        future = runtime.futures.get(action.source_future)
        if future is None:
            return AsyncIRPoll(AsyncIRPollKind.FAILED, "failed", error=f"Future {action.source_future!r} is not live")
        result = future.poll(program)
        if result.kind is not AsyncIRPollKind.PENDING:
            runtime.futures.pop(action.source_future, None)
            future.consume()
        return result
    return AsyncIRPoll(AsyncIRPollKind.FAILED, "failed", error="await action has no owned source")


def _resolve_select(action: AsyncAction, runtime: AsyncIRFrameRuntime, program: AsyncIRProgram) -> AsyncIRPoll:
    if runtime.select_candidates is None:
        candidates: list[_SelectCandidate] = []
        for arm in action.select_arms:
            if arm.source_future is not None:
                future = runtime.futures.get(arm.source_future)
                if future is None:
                    return AsyncIRPoll(AsyncIRPollKind.FAILED, "failed", error=f"Future {arm.source_future!r} is not live")
                candidates.append(_SelectCandidate(arm, future, arm.source_future))
                continue
            if arm.callee is None:
                return AsyncIRPoll(AsyncIRPollKind.FAILED, "failed", error="select arm has no async operation")
            args = tuple(_eval_expression(item, runtime, program) for item in arm.arguments)
            candidates.append(_SelectCandidate(arm, _OwnedIRFuture(arm.callee, args), None))
        runtime.select_candidates = candidates

    candidates = runtime.select_candidates
    assert candidates is not None
    for candidate in candidates:
        result = candidate.future.poll(program)
        if result.kind is AsyncIRPollKind.READY:
            candidate.future.consume()
            for other in candidates:
                if other is not candidate:
                    other.future.drop()
                if other.source_name is not None:
                    runtime.futures.pop(other.source_name, None)
            runtime.select_candidates = None
            return AsyncIRPoll(AsyncIRPollKind.READY, "ready", value=candidate.arm)
        if result.kind is AsyncIRPollKind.FAILED:
            candidate.future.consume()
            for other in candidates:
                if other is not candidate:
                    other.future.drop()
                if other.source_name is not None:
                    runtime.futures.pop(other.source_name, None)
            runtime.select_candidates = None
            return AsyncIRPoll(AsyncIRPollKind.FAILED, "failed", error=result.error or "select operation failed")

    # A pending round keeps every child frame alive. The next parent poll
    # resumes each candidate once, preserving bounded work and ownership.
    return AsyncIRPoll(AsyncIRPollKind.PENDING, f"suspended_{runtime.suspension_index}")


def _execute_support_function(program: AsyncIRProgram, model: AsyncExecutableFunction, arguments: tuple[object, ...]) -> AsyncIRPoll:
    if model.async_function:
        return AsyncIRPoll(AsyncIRPollKind.FAILED, "failed", error="async function is missing structural IR")
    if len(arguments) != len(model.parameters):
        return AsyncIRPoll(AsyncIRPollKind.FAILED, "failed", error="function argument arity mismatch")
    # A minimal synthetic frame is enough for non-suspending support functions.
    slots = tuple(AsyncIRSlot(index, name) for index, name in enumerate(model.frame_slots))
    dummy = AsyncIRFunction(
        model.name,
        AsyncIRFrame(slots, ("created", "running_0", "completed", "failed", "cancelled")),
        (
            AsyncIRBlock("entry", "created", (AsyncIRInstruction(AsyncIROp.RESUME, target="running_0"),)),
            AsyncIRBlock("running_0", "running_0", (AsyncIRInstruction(AsyncIROp.COMPLETE, target="completed"),)),
            AsyncIRBlock("completed", "completed", tuple(AsyncIRInstruction(AsyncIROp.SLOT_DROP, slot=slot.index) for slot in slots) + (AsyncIRInstruction(AsyncIROp.COMPLETE),)),
            AsyncIRBlock("failed", "failed", tuple(AsyncIRInstruction(AsyncIROp.SLOT_DROP, slot=slot.index) for slot in slots) + (AsyncIRInstruction(AsyncIROp.FAIL),)),
            AsyncIRBlock("cancelled", "cancelled", tuple(AsyncIRInstruction(AsyncIROp.SLOT_DROP, slot=slot.index) for slot in slots) + (AsyncIRInstruction(AsyncIROp.CANCEL),)),
        ),
        model,
    )
    runtime = AsyncIRFrameRuntime(dummy)
    runtime.parameters_bound = True
    for name, value in zip(model.parameters, arguments):
        if name in model.future_parameters:
            if not isinstance(value, _OwnedIRFuture):
                return AsyncIRPoll(AsyncIRPollKind.FAILED, "failed", error="future argument ownership mismatch")
            runtime.futures[name] = value
        else:
            runtime.bindings[name] = value
    runtime.state = "running_0"
    while runtime.action_index < len(model.actions):
        action = model.actions[runtime.action_index]
        if _is_await_action(action):
            return AsyncIRPoll(AsyncIRPollKind.FAILED, "failed", error="synchronous support function cannot await")
        if action.kind is AsyncActionKind.ASSIGN:
            runtime.bindings[_required(action.target, "assignment target")] = _eval_expression(action.expression, runtime, program)
        elif action.kind is AsyncActionKind.FUTURE_CREATE:
            args = tuple(_eval_expression(item, runtime, program) for item in action.arguments)
            runtime.futures[_required(action.target, "future target")] = _OwnedIRFuture(_required(action.callee, "async callee"), args, action.type_arguments)
        elif action.kind is AsyncActionKind.FUTURE_MOVE:
            source = _required(action.source_future, "future source")
            future = runtime.futures.pop(source, None)
            if future is None:
                return AsyncIRPoll(AsyncIRPollKind.FAILED, "failed", error=f"Future {source!r} is not live")
            runtime.futures[_required(action.target, "future target")] = future
        elif action.kind is AsyncActionKind.RETURN:
            value = _eval_expression(action.expression, runtime, program)
            runtime.drop_all()
            return AsyncIRPoll(AsyncIRPollKind.READY, "completed", value=value)
        elif action.kind is AsyncActionKind.DISCARD and action.expression is not None:
            _eval_expression(action.expression, runtime, program)
        else:
            return AsyncIRPoll(AsyncIRPollKind.FAILED, "failed", error=f"unsupported support action {action.kind.value}")
        runtime.action_index += 1
    runtime.drop_all()
    return AsyncIRPoll(AsyncIRPollKind.FAILED, "failed", error="function reached end without return")


def _eval_expression(expression: AsyncExpression | None, runtime: AsyncIRFrameRuntime, program: AsyncIRProgram) -> object:
    if expression is None:
        raise AsyncIRVerificationError("missing executable expression")
    if expression.kind is AsyncExpressionKind.LITERAL:
        return expression.value
    if expression.kind is AsyncExpressionKind.SLOT:
        name = _required(expression.name, "slot name")
        if name not in runtime.bindings:
            raise AsyncIRVerificationError(f"uninitialized async frame slot {name!r}")
        return runtime.bindings[name]
    if expression.kind is AsyncExpressionKind.FUTURE_MOVE:
        name = _required(expression.name, "future move source")
        future = runtime.futures.pop(name, None)
        if future is None or future.consumed or future.dropped:
            raise AsyncIRVerificationError(f"Future {name!r} is not live")
        return future
    if expression.kind is AsyncExpressionKind.UNARY:
        value = _eval_expression(expression.arguments[0], runtime, program)
        if expression.operator == "-":
            return -value  # type: ignore[operator]
        if expression.operator == "~":
            return -value  # balanced-ternary inversion for scalar values
        raise AsyncIRVerificationError(f"unsupported async unary operator {expression.operator!r}")
    if expression.kind is AsyncExpressionKind.BINARY:
        left = _eval_expression(expression.arguments[0], runtime, program)
        right = _eval_expression(expression.arguments[1], runtime, program)
        return _binary(expression.operator, left, right)
    if expression.kind is AsyncExpressionKind.SYNC_CALL:
        args = tuple(_eval_expression(item, runtime, program) for item in expression.arguments)
        result = execute_async_program(program, _required(expression.name, "sync callee"), arguments=args)
        if result.kind is not AsyncIRPollKind.READY:
            raise AsyncIRVerificationError(result.error or "synchronous helper failed")
        return result.value
    raise AsyncIRVerificationError(f"unsupported executable expression {expression.kind.value}")


def _binary(operator: str | None, left: object, right: object) -> object:
    if operator == "+":
        return left + right  # type: ignore[operator]
    if operator == "-":
        return left - right  # type: ignore[operator]
    if operator == "*":
        return left * right  # type: ignore[operator]
    if operator == "/":
        if right == 0:
            raise ZeroDivisionError("division by zero")
        if isinstance(left, int) and isinstance(right, int):
            return int(left / right)
        return left / right  # type: ignore[operator]
    if operator == "&":
        return min(left, right)  # type: ignore[type-var]
    if operator == "|":
        return max(left, right)  # type: ignore[type-var]
    if operator == "<=>":
        return -1 if left < right else 1 if left > right else 0  # type: ignore[operator]
    if operator == "==":
        return 1 if left == right else 0
    if operator == "!=":
        return 1 if left != right else 0
    if operator == "<":
        return 1 if left < right else 0  # type: ignore[operator]
    if operator == "<=":
        return 1 if left <= right else 0  # type: ignore[operator]
    if operator == ">":
        return 1 if left > right else 0  # type: ignore[operator]
    if operator == ">=":
        return 1 if left >= right else 0  # type: ignore[operator]
    raise AsyncIRVerificationError(f"unsupported async binary operator {operator!r}")


def _is_await_action(action: AsyncAction) -> bool:
    return action.kind in {AsyncActionKind.AWAIT_CALL, AsyncActionKind.AWAIT_FUTURE, AsyncActionKind.SELECT} or (
        action.kind is AsyncActionKind.DISCARD and (action.callee is not None or action.source_future is not None)
    )


def _iter_await_actions(actions: tuple[AsyncAction, ...] | list[AsyncAction]):
    for action in actions:
        if _is_await_action(action):
            yield action
        if action.select_arms:
            for arm in action.select_arms:
                yield from _iter_await_actions(arm.actions)


def _finish(
    runtime: AsyncIRFrameRuntime,
    kind: AsyncIRPollKind,
    state: str,
    *,
    value: object | None = None,
    error: str | None = None,
) -> tuple[AsyncIRFrameRuntime, AsyncIRPoll]:
    runtime.drop_all()
    runtime.state = state
    runtime.block = state
    runtime.consumed = True
    return runtime, AsyncIRPoll(kind, state, value=value, error=error)


def _required(value: str | None, label: str) -> str:
    if not value:
        raise AsyncIRVerificationError(f"missing {label}")
    return value


def _action_to_dict(action: AsyncAction) -> dict[str, object]:
    result: dict[str, object] = {"kind": action.kind.value, "source_offset": action.source_offset}
    if action.target is not None:
        result["target"] = action.target
    if action.callee is not None:
        result["callee"] = action.callee
    if action.source_future is not None:
        result["source_future"] = action.source_future
    if action.return_after:
        result["return_after"] = True
    if action.type_arguments:
        result["type_arguments"] = list(action.type_arguments)
    if action.expression is not None:
        result["expression"] = _expression_to_dict(action.expression)
    if action.arguments:
        result["arguments"] = [_expression_to_dict(item) for item in action.arguments]
    if action.select_arms:
        result["select_arms"] = [
            {
                **({"callee": arm.callee} if arm.callee is not None else {}),
                **({"source_future": arm.source_future} if arm.source_future is not None else {}),
                "source_offset": arm.source_offset,
                **({"arguments": [_expression_to_dict(item) for item in arm.arguments]} if arm.arguments else {}),
                "actions": [_action_to_dict(item) for item in arm.actions],
            }
            for arm in action.select_arms
        ]
    return result


def _expression_to_dict(expression: AsyncExpression) -> dict[str, object]:
    result: dict[str, object] = {"kind": expression.kind.value}
    if expression.value is not None:
        result["value"] = expression.value
    if expression.name is not None:
        result["name"] = expression.name
    if expression.operator is not None:
        result["operator"] = expression.operator
    if expression.arguments:
        result["arguments"] = [_expression_to_dict(item) for item in expression.arguments]
    if expression.type_arguments:
        result["type_arguments"] = list(expression.type_arguments)
    return result
