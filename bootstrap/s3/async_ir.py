"""Native compiler IR for bounded resumable async frames (M1.81)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping

from .async_frontend import AsyncStateMachinePlan


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

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "frame": self.frame.to_dict(),
            "blocks": [block.to_dict() for block in self.blocks],
        }


@dataclass(frozen=True, slots=True)
class AsyncIRProgram:
    functions: tuple[AsyncIRFunction, ...]

    def to_dict(self) -> dict[str, object]:
        return {"functions": [function.to_dict() for function in self.functions]}


@dataclass(slots=True)
class _RuntimeSlot:
    value: object | None = None
    initialized: bool = False
    moved: bool = False
    dropped: bool = False


@dataclass(slots=True)
class AsyncIRFrameRuntime:
    function: AsyncIRFunction
    slots: list[_RuntimeSlot] = field(default_factory=list)
    state: str = "created"
    block: str = "entry"
    consumed: bool = False
    drop_log: list[int] = field(default_factory=list)

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
    """Lower M1.71 plans into deterministic frame/state/block IR."""

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
            blocks.append(
                AsyncIRBlock(
                    running,
                    running,
                    (AsyncIRInstruction(AsyncIROp.SUSPEND, target=suspended),),
                )
            )
            blocks.append(
                AsyncIRBlock(
                    suspended,
                    suspended,
                    (AsyncIRInstruction(AsyncIROp.RESUME, target=next_running),),
                )
            )
        final_running = f"running_{len(plan.suspension_points)}"
        if not plan.suspension_points:
            final_running = "running_0"
        blocks.append(AsyncIRBlock(final_running, final_running, (AsyncIRInstruction(AsyncIROp.COMPLETE, target="completed"),)))
        cleanup = tuple(AsyncIRInstruction(AsyncIROp.SLOT_DROP, slot=slot.index) for slot in slots)
        blocks.extend(
            (
                AsyncIRBlock("completed", "completed", cleanup + (AsyncIRInstruction(AsyncIROp.COMPLETE),)),
                AsyncIRBlock("failed", "failed", cleanup + (AsyncIRInstruction(AsyncIROp.FAIL, error="async failure"),)),
                AsyncIRBlock("cancelled", "cancelled", cleanup + (AsyncIRInstruction(AsyncIROp.CANCEL),)),
            )
        )
        blocks[0] = AsyncIRBlock(
            "entry",
            "created",
            (AsyncIRInstruction(AsyncIROp.FRAME_INIT), AsyncIRInstruction(AsyncIROp.RESUME, target="running_0")),
        )
        function = AsyncIRFunction(plan.function_name, AsyncIRFrame(slots, states), tuple(blocks))
        verify_async_ir(AsyncIRProgram((function,)))
        functions.append(function)
    program = AsyncIRProgram(tuple(functions))
    verify_async_ir(program)
    return program


def execute_async_ir(
    function: AsyncIRFunction,
    *,
    frame: AsyncIRFrameRuntime | None = None,
    initial_slots: Mapping[int, object] | None = None,
) -> tuple[AsyncIRFrameRuntime, AsyncIRPoll]:
    """Execute until suspension or terminal state using the native async IR."""

    verify_async_ir(AsyncIRProgram((function,)))
    runtime = frame or AsyncIRFrameRuntime(function)
    if initial_slots and runtime.state == "created":
        for index, value in sorted(initial_slots.items()):
            runtime.initialize(index, value)
    if runtime.consumed:
        return runtime, AsyncIRPoll(AsyncIRPollKind.FAILED, runtime.state, error="terminal future consumed")
    blocks = {block.name: block for block in function.blocks}
    while True:
        block = blocks[runtime.block]
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
                break
            elif instruction.opcode is AsyncIROp.COMPLETE:
                if instruction.target is not None:
                    runtime.state = blocks[instruction.target].state
                    runtime.block = instruction.target
                    break
                runtime.drop_all()
                runtime.state = "completed"
                runtime.consumed = True
                runtime.block = "completed"
                return runtime, AsyncIRPoll(AsyncIRPollKind.READY, runtime.state)
            elif instruction.opcode is AsyncIROp.FAIL:
                if instruction.target is not None:
                    runtime.state = blocks[instruction.target].state
                    runtime.block = instruction.target
                    break
                runtime.drop_all()
                runtime.state = "failed"
                runtime.consumed = True
                runtime.block = "failed"
                return runtime, AsyncIRPoll(AsyncIRPollKind.FAILED, runtime.state, error=instruction.error)
            elif instruction.opcode is AsyncIROp.CANCEL:
                if instruction.target is not None:
                    runtime.state = blocks[instruction.target].state
                    runtime.block = instruction.target
                    break
                runtime.drop_all()
                runtime.state = "cancelled"
                runtime.consumed = True
                runtime.block = "cancelled"
                return runtime, AsyncIRPoll(AsyncIRPollKind.CANCELLED, runtime.state)
        else:
            raise AsyncIRVerificationError(f"block {block.name!r} did not transition")


def cancel_async_ir(function: AsyncIRFunction, frame: AsyncIRFrameRuntime) -> AsyncIRPoll:
    """Run the explicit cancellation cleanup path exactly once."""

    if frame.consumed:
        return AsyncIRPoll(AsyncIRPollKind.FAILED, frame.state, error="terminal future consumed")
    frame.block = function.frame.cancelled_block
    _, result = execute_async_ir(function, frame=frame)
    return result
