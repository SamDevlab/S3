"""Deterministic lowering from validated S3 Assembly to GNU x86-64."""

from __future__ import annotations

import re

from ...assembly import (
    AssemblyFunction,
    AssemblyInstruction,
    AssemblyOpcode,
    AssemblyProgram,
    AssemblyType,
)
from .diagnostics import NativeBackendError
from .layout import FrameLayout, MemorySlot, StackRegion, layout_frame
from .runtime import render_runtime


_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_ARGUMENT_REGISTERS = ("rdi", "rsi", "rdx", "rcx", "r8", "r9")


def mangle_function(name: str) -> str:
    if _IDENTIFIER.fullmatch(name) is None:
        raise NativeBackendError(f"unsafe function identifier {name!r}")
    return f"s3_{name}"


def mangle_block(function_name: str, block_name: str) -> str:
    if (
        _IDENTIFIER.fullmatch(function_name) is None
        or _IDENTIFIER.fullmatch(block_name) is None
    ):
        raise NativeBackendError("unsafe function or block identifier")
    return (
        f".L_s3_f{len(function_name)}_{function_name}"
        f"_b{len(block_name)}_{block_name}"
    )


def _address(
    region: StackRegion,
    *,
    index: str | None = None,
    scale: int = 1,
) -> str:
    parts = ["rbp"]
    if index is not None:
        parts.append(f" + {index}" if scale == 1 else f" + {index}*{scale}")
    if region.offset < 0:
        parts.append(f" - {-region.offset}")
    elif region.offset > 0:
        parts.append(f" + {region.offset}")
    return f"[{''.join(parts)}]"


class X8664Emitter:
    def __init__(self, program: AssemblyProgram):
        self.program = program

    def emit(self) -> str:
        lines = [
            ".intel_syntax noprefix",
            "# Generated deterministically by the S3 Linux x86-64 backend.",
            ".section .text",
        ]
        for function in self.program.functions:
            lines.extend(self._emit_function(function))
            lines.append("")
        lines.append(render_runtime().rstrip())
        return "\n".join(lines) + "\n"

    def _emit_function(self, function: AssemblyFunction) -> list[str]:
        layout = layout_frame(function)
        symbol = mangle_function(function.name)
        lines = [
            f".globl {symbol}",
            f".type {symbol}, @function",
            f"{symbol}:",
            "    push rbp",
            "    mov rbp, rsp",
        ]
        if layout.frame_size:
            lines.append(f"    sub rsp, {layout.frame_size}")
        lines.extend(self._save_parameters(function, layout))
        lines.extend(self._initialize_metadata(function, layout))
        for block in function.blocks:
            lines.append(f"{mangle_block(function.name, block.label)}:")
            for instruction in block.instructions:
                lines.extend(
                    self._emit_instruction(function, layout, instruction)
                )
        lines.append(f".size {symbol}, .-{symbol}")
        return lines

    def _save_parameters(
        self,
        function: AssemblyFunction,
        layout: FrameLayout,
    ) -> list[str]:
        lines: list[str] = []
        for position, parameter in enumerate(function.parameters):
            slot = layout.register(parameter.register)
            if position < len(_ARGUMENT_REGISTERS):
                source = _ARGUMENT_REGISTERS[position]
                lines.append(
                    f"    mov qword ptr {_address(slot.value)}, {source}"
                )
            else:
                caller_offset = 16 + (position - len(_ARGUMENT_REGISTERS)) * 8
                lines.extend(
                    (
                        f"    mov rax, qword ptr [rbp + {caller_offset}]",
                        f"    mov qword ptr {_address(slot.value)}, rax",
                    )
                )
        return lines

    def _initialize_metadata(
        self,
        function: AssemblyFunction,
        layout: FrameLayout,
    ) -> list[str]:
        lines: list[str] = []
        for slot in layout.registers:
            lines.append(
                f"    mov byte ptr {_address(slot.initialized)}, 0"
            )
        for memory in layout.memories:
            lines.extend(
                (
                    f"    lea rdi, {_address(memory.initialized)}",
                    f"    mov ecx, {memory.length}",
                    "    xor eax, eax",
                    "    rep stosb",
                )
            )
        for parameter in function.parameters:
            slot = layout.register(parameter.register)
            lines.append(
                f"    mov byte ptr {_address(slot.initialized)}, 1"
            )
        return lines

    def _read_register(
        self,
        layout: FrameLayout,
        register: int,
        target: str,
    ) -> list[str]:
        slot = layout.register(register)
        return [
            f"    cmp byte ptr {_address(slot.initialized)}, 0",
            "    je __s3_fail_uninitialized_register",
            f"    mov {target}, qword ptr {_address(slot.value)}",
        ]

    def _write_register(
        self,
        layout: FrameLayout,
        register: int,
        source: str,
    ) -> list[str]:
        slot = layout.register(register)
        return [
            f"    mov qword ptr {_address(slot.value)}, {source}",
            f"    mov byte ptr {_address(slot.initialized)}, 1",
        ]

    @staticmethod
    def _range_check(type_name: AssemblyType, register: str) -> list[str]:
        minimum, maximum = (
            (-1, 1)
            if type_name is AssemblyType.TRIT
            else (-364, 364)
        )
        return [
            f"    cmp {register}, {minimum}",
            "    jl __s3_fail_overflow",
            f"    cmp {register}, {maximum}",
            "    jg __s3_fail_overflow",
        ]

    def _emit_instruction(
        self,
        function: AssemblyFunction,
        layout: FrameLayout,
        instruction: AssemblyInstruction,
    ) -> list[str]:
        opcode = instruction.opcode
        registers = instruction.registers
        if opcode is AssemblyOpcode.TCONST:
            assert instruction.immediate is not None
            return [
                f"    mov rax, {instruction.immediate}",
                *self._write_register(layout, registers[0], "rax"),
            ]
        if opcode is AssemblyOpcode.TMOV:
            return [
                *self._read_register(layout, registers[1], "rax"),
                *self._write_register(layout, registers[0], "rax"),
            ]
        if opcode is AssemblyOpcode.TINV:
            type_name = function.type_of(registers[0])
            assert type_name is not None
            return [
                *self._read_register(layout, registers[1], "rax"),
                "    neg rax",
                "    jo __s3_fail_overflow",
                *self._range_check(type_name, "rax"),
                *self._write_register(layout, registers[0], "rax"),
            ]
        if opcode is AssemblyOpcode.TADD:
            type_name = function.type_of(registers[0])
            assert type_name is not None
            return [
                *self._read_register(layout, registers[1], "rax"),
                *self._read_register(layout, registers[2], "r10"),
                "    add rax, r10",
                "    jo __s3_fail_overflow",
                *self._range_check(type_name, "rax"),
                *self._write_register(layout, registers[0], "rax"),
            ]
        if opcode in {AssemblyOpcode.TMIN, AssemblyOpcode.TMAX}:
            return self._emit_extreme(function, layout, instruction)
        if opcode is AssemblyOpcode.TCMP:
            return [
                *self._read_register(layout, registers[1], "rax"),
                *self._read_register(layout, registers[2], "r10"),
                "    xor r11d, r11d",
                "    cmp rax, r10",
                "    mov rax, -1",
                "    cmovl r11, rax",
                "    mov rax, 1",
                "    cmovg r11, rax",
                "    mov rax, r11",
                *self._write_register(layout, registers[0], "rax"),
            ]
        if opcode is AssemblyOpcode.TJMP:
            return [
                f"    jmp {mangle_block(function.name, instruction.labels[0])}"
            ]
        if opcode is AssemblyOpcode.TBR3:
            negative, zero, positive = (
                mangle_block(function.name, label)
                for label in instruction.labels
            )
            return [
                *self._read_register(layout, registers[0], "rax"),
                "    cmp rax, -1",
                f"    je {negative}",
                "    cmp rax, 0",
                f"    je {zero}",
                "    cmp rax, 1",
                f"    je {positive}",
                "    jmp __s3_fail_invalid_trit",
            ]
        if opcode is AssemblyOpcode.TCALL:
            return self._emit_call(function, layout, instruction)
        if opcode is AssemblyOpcode.TRET:
            return [
                *self._read_register(layout, registers[0], "rax"),
                "    leave",
                "    ret",
            ]
        if opcode is AssemblyOpcode.TLOAD:
            return self._emit_load(layout, instruction)
        if opcode is AssemblyOpcode.TSTORE:
            return self._emit_store(layout, instruction)
        raise NativeBackendError(f"unsupported opcode {opcode.value}")

    def _emit_extreme(
        self,
        function: AssemblyFunction,
        layout: FrameLayout,
        instruction: AssemblyInstruction,
    ) -> list[str]:
        destination, left, right = instruction.registers
        type_name = function.type_of(destination)
        assert type_name is not None
        lines = [
            *self._read_register(layout, left, "rax"),
            *self._read_register(layout, right, "r10"),
        ]
        if type_name is AssemblyType.TRIT:
            lines.extend(
                (
                    "    cmp rax, r10",
                    (
                        "    cmovg rax, r10"
                        if instruction.opcode is AssemblyOpcode.TMIN
                        else "    cmovl rax, r10"
                    ),
                )
            )
        else:
            helper = (
                "__s3_tryte_min"
                if instruction.opcode is AssemblyOpcode.TMIN
                else "__s3_tryte_max"
            )
            lines.extend(
                (
                    "    mov rdi, rax",
                    "    mov rsi, r10",
                    f"    call {helper}",
                )
            )
        lines.extend(self._write_register(layout, destination, "rax"))
        return lines

    def _emit_call(
        self,
        function: AssemblyFunction,
        layout: FrameLayout,
        instruction: AssemblyInstruction,
    ) -> list[str]:
        del function
        destination, *arguments = instruction.registers
        stack_arguments = arguments[len(_ARGUMENT_REGISTERS) :]
        padding = 1 if len(stack_arguments) % 2 else 0
        lines: list[str] = []
        if padding:
            lines.append("    sub rsp, 8")
        for register in reversed(stack_arguments):
            lines.extend(self._read_register(layout, register, "rax"))
            lines.append("    push rax")
        for register, target in zip(
            arguments[: len(_ARGUMENT_REGISTERS)],
            _ARGUMENT_REGISTERS,
            strict=False,
        ):
            lines.extend(self._read_register(layout, register, target))
        assert instruction.callee is not None
        lines.append(f"    call {mangle_function(instruction.callee)}")
        cleanup = (len(stack_arguments) + padding) * 8
        if cleanup:
            lines.append(f"    add rsp, {cleanup}")
        lines.extend(self._write_register(layout, destination, "rax"))
        return lines

    @staticmethod
    def _memory_bounds(memory: MemorySlot, index: str) -> list[str]:
        return [
            f"    cmp {index}, 0",
            "    jl __s3_fail_bounds",
            f"    cmp {index}, {memory.length}",
            "    jge __s3_fail_bounds",
        ]

    def _emit_load(
        self,
        layout: FrameLayout,
        instruction: AssemblyInstruction,
    ) -> list[str]:
        destination, index_register = instruction.registers
        assert instruction.memory is not None
        memory = layout.memory(instruction.memory)
        load = "movsx rax, byte ptr" if memory.element_size == 1 else (
            "movsx rax, word ptr"
        )
        return [
            *self._read_register(layout, index_register, "r10"),
            *self._memory_bounds(memory, "r10"),
            (
                f"    cmp byte ptr "
                f"{_address(memory.initialized, index='r10')}, 0"
            ),
            "    je __s3_fail_uninitialized_memory",
            (
                f"    {load} "
                f"{_address(memory.data, index='r10', scale=memory.element_size)}"
            ),
            *self._write_register(layout, destination, "rax"),
        ]

    def _emit_store(
        self,
        layout: FrameLayout,
        instruction: AssemblyInstruction,
    ) -> list[str]:
        index_register, source_register = instruction.registers
        assert instruction.memory is not None
        memory = layout.memory(instruction.memory)
        lines = [
            *self._read_register(layout, index_register, "rax"),
            *self._read_register(layout, source_register, "r10"),
            *self._memory_bounds(memory, "rax"),
            *self._range_check(memory.element_type, "r10"),
        ]
        init_address = _address(memory.initialized, index="rax")
        if not memory.mutable:
            lines.extend(
                (
                    f"    cmp byte ptr {init_address}, 0",
                    "    jne __s3_fail_immutable_memory",
                )
            )
        data_address = _address(
            memory.data,
            index="rax",
            scale=memory.element_size,
        )
        source = "r10b" if memory.element_size == 1 else "r10w"
        size = "byte" if memory.element_size == 1 else "word"
        lines.extend(
            (
                f"    mov {size} ptr {data_address}, {source}",
                f"    mov byte ptr {init_address}, 1",
            )
        )
        return lines
