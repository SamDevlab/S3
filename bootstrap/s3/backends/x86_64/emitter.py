"""Deterministic lowering from validated S3 Assembly to GNU x86-64."""

from __future__ import annotations

import re
from dataclasses import dataclass

from ...assembly import (
    AssemblyFunction,
    AssemblyInstruction,
    AssemblyOpcode,
    AssemblyProgram,
    AssemblyType,
)
from .diagnostics import NativeBackendError
from .layout import FrameLayout, MemorySlot, StackRegion, layout_frame
from .registers import SYSV_INTEGER_ARGUMENT_REGISTERS
from .runtime import render_runtime
from .allocation import AllocationPlan, analyze_allocation


_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_ARGUMENT_REGISTERS = SYSV_INTEGER_ARGUMENT_REGISTERS


@dataclass(frozen=True, slots=True)
class FailureSite:
    index: int
    prefix: str
    suffix: str | None = None
    value_register: str | None = None

    @property
    def label(self) -> str:
        return f".L__s3_failure_site_{self.index}"

    @property
    def prefix_label(self) -> str:
        return f".L__s3_failure_prefix_{self.index}"

    @property
    def suffix_label(self) -> str:
        return f".L__s3_failure_suffix_{self.index}"


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


def mangle_static_string(static_string: str) -> str:
    if re.fullmatch(r"s[0-9]+", static_string) is None:
        raise NativeBackendError(f"unsafe static string identifier {static_string!r}")
    return f".L{static_string}"


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
    def __init__(
        self,
        program: AssemblyProgram,
        *,
        max_frames: int,
        max_instructions: int,
        register_allocation: bool = False,
    ):
        self.program = program
        self.max_frames = max_frames
        self.max_instructions = max_instructions
        self.register_allocation = register_allocation
        self.failure_sites: list[FailureSite] = []
        self.current_function: AssemblyFunction | None = None
        self.current_block: str | None = None
        self.current_instruction: AssemblyInstruction | None = None
        self.functions = {function.name: function for function in program.functions}
        self.current_plan: AllocationPlan | None = None

    def emit(self) -> str:
        lines = [
            ".intel_syntax noprefix",
            "# Generated deterministically by the S3 Linux x86-64 backend.",
            ".section .text",
        ]
        for function in self.program.functions:
            lines.extend(self._emit_function(function))
            lines.append("")
        lines.extend(self._render_failure_handlers())
        lines.extend(self._render_static_string_data())
        lines.extend(self._render_failure_data())
        lines.append(render_runtime().rstrip())
        return "\n".join(lines) + "\n"

    def _emit_function(self, function: AssemblyFunction) -> list[str]:
        if self.register_allocation:
            plan = analyze_allocation(function)
            self.current_plan = plan
            layout = layout_frame(function, plan.used_physical_registers)
        else:
            self.current_plan = None
            layout = layout_frame(function)
        symbol = mangle_function(function.name)
        frame_failure = self._new_failure_site(
            category="frame limit",
            function=function.name,
            block="entry",
            opcode="ENTER",
            instruction=None,
            detail_prefix="depth ",
            detail_suffix=f" exceeds limit {self.max_frames}\n",
            value_register="qword ptr [rip + __s3_frame_count]",
        )
        lines = [
            f".globl {symbol}",
            f".type {symbol}, @function",
            f"{symbol}:",
            "    inc qword ptr [rip + __s3_frame_count]",
            (
                "    cmp qword ptr [rip + __s3_frame_count], "
                f"{self.max_frames}"
            ),
            f"    jg {frame_failure}",
            "    push rbp",
            "    mov rbp, rsp",
        ]
        if layout.frame_size:
            lines.append(f"    sub rsp, {layout.frame_size}")
        if self.register_allocation and self.current_plan:
            for phys in self.current_plan.used_physical_registers:
                slot = layout.callee_saved_slot(phys)
                lines.append(f"    mov qword ptr {_address(slot.region)}, {phys}")
        lines.extend(self._save_parameters(function, layout))
        lines.extend(self._initialize_metadata(function, layout))
        lines.append(f"    jmp {mangle_block(function.name, 'entry')}")
        for block in function.blocks:
            lines.append(f"{mangle_block(function.name, block.label)}:")
            for instruction in block.instructions:
                lines.extend(
                    self._emit_instruction(
                        function,
                        block.label,
                        layout,
                        instruction,
                    )
                )
        lines.append(f".size {symbol}, .-{symbol}")
        return lines

    def _save_parameters(
        self,
        function: AssemblyFunction,
        layout: FrameLayout,
    ) -> list[str]:
        lines: list[str] = []
        if function.result_width > 1:
            if layout.hidden_sret_pointer is None:
                raise NativeBackendError("missing hidden sret pointer slot")
            lines.append(
                f"    mov qword ptr {_address(layout.hidden_sret_pointer)}, rdi"
            )
        for position, parameter in enumerate(function.parameters):
            slot = layout.register(parameter.register)
            native_position = position + (1 if function.result_width > 1 else 0)

            phys = self.current_plan.physical_register(parameter.register) if (self.register_allocation and self.current_plan) else None

            if native_position < len(_ARGUMENT_REGISTERS):
                source = _ARGUMENT_REGISTERS[native_position]
                if phys is None:
                    lines.append(
                        f"    mov qword ptr {_address(slot.value)}, {source}"
                    )
                else:
                    lines.append(
                        f"    mov {phys}, {source}"
                    )
            else:
                caller_offset = (
                    16 + (native_position - len(_ARGUMENT_REGISTERS)) * 8
                )
                if phys is None:
                    lines.extend(
                        (
                            f"    mov rax, qword ptr [rbp + {caller_offset}]",
                            f"    mov qword ptr {_address(slot.value)}, rax",
                        )
                    )
                else:
                    lines.append(
                        f"    mov {phys}, qword ptr [rbp + {caller_offset}]"
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
        failure = self._instruction_failure(
            "uninitialized register",
            detail=f"register r{register} is uninitialized\n",
        )
        lines = [
            f"    cmp byte ptr {_address(slot.initialized)}, 0",
            f"    je {failure}",
        ]
        phys = self.current_plan.physical_register(register) if (self.register_allocation and self.current_plan) else None
        if phys is None:
            lines.append(f"    mov {target}, qword ptr {_address(slot.value)}")
        elif phys != target:
            lines.append(f"    mov {target}, {phys}")
        return lines

    def _write_register(
        self,
        layout: FrameLayout,
        register: int,
        source: str,
    ) -> list[str]:
        slot = layout.register(register)
        phys = self.current_plan.physical_register(register) if (self.register_allocation and self.current_plan) else None
        lines = []
        if phys is None:
            lines.append(f"    mov qword ptr {_address(slot.value)}, {source}")
        elif phys != source:
            lines.append(f"    mov {phys}, {source}")
        lines.append(f"    mov byte ptr {_address(slot.initialized)}, 1")
        return lines

    def _restore_callee_saved(self, layout: FrameLayout) -> list[str]:
        if not self.register_allocation or not self.current_plan:
            return []
        lines = []
        for phys in self.current_plan.used_physical_registers:
            slot = layout.callee_saved_slot(phys)
            lines.append(f"    mov {phys}, qword ptr {_address(slot.region)}")
        return lines

    @staticmethod
    def _range_check(
        type_name: AssemblyType,
        register: str,
        failure: str,
    ) -> list[str]:
        minimum, maximum = (
            (-1, 1)
            if type_name is AssemblyType.TRIT
            else (-364, 364)
        )
        return [
            f"    cmp {register}, {minimum}",
            f"    jl {failure}",
            f"    cmp {register}, {maximum}",
            f"    jg {failure}",
        ]

    def _emit_instruction(
        self,
        function: AssemblyFunction,
        block_name: str,
        layout: FrameLayout,
        instruction: AssemblyInstruction,
    ) -> list[str]:
        self.current_function = function
        self.current_block = block_name
        self.current_instruction = instruction
        opcode = instruction.opcode
        registers = instruction.registers

        limit_failure = self._instruction_failure(
            "instruction limit",
            detail=f"instruction limit {self.max_instructions} exceeded\n",
        )
        instrumentation = [
            f"    movabs r11, {self.max_instructions}",
            "    cmp qword ptr [rip + __s3_instruction_count], r11",
            f"    jae {limit_failure}",
            "    inc qword ptr [rip + __s3_instruction_count]",
        ]

        if opcode is AssemblyOpcode.TCONST:
            assert instruction.immediate is not None
            return instrumentation + [
                f"    mov rax, {instruction.immediate}",
                *self._write_register(layout, registers[0], "rax"),
            ]
        if opcode is AssemblyOpcode.TCONST_STR:
            assert instruction.static_string is not None
            return instrumentation + [
                f"    lea rax, [rip + {mangle_static_string(instruction.static_string)}]",
                *self._write_register(layout, registers[0], "rax"),
            ]
        if opcode is AssemblyOpcode.TMOV:
            return instrumentation + [
                *self._read_register(layout, registers[1], "rax"),
                *self._write_register(layout, registers[0], "rax"),
            ]
        if opcode is AssemblyOpcode.TINV:
            type_name = function.type_of(registers[0])
            assert type_name is not None
            overflow = self._overflow_failure(type_name, "rax")
            return instrumentation + [
                *self._read_register(layout, registers[1], "rax"),
                "    neg rax",
                f"    jo {overflow}",
                *self._range_check(type_name, "rax", overflow),
                *self._write_register(layout, registers[0], "rax"),
            ]
        if opcode is AssemblyOpcode.TADD:
            type_name = function.type_of(registers[0])
            assert type_name is not None
            overflow = self._overflow_failure(type_name, "rax")
            return instrumentation + [
                *self._read_register(layout, registers[1], "rax"),
                *self._read_register(layout, registers[2], "r10"),
                "    add rax, r10",
                f"    jo {overflow}",
                *self._range_check(type_name, "rax", overflow),
                *self._write_register(layout, registers[0], "rax"),
            ]
        if opcode in {AssemblyOpcode.TMIN, AssemblyOpcode.TMAX}:
            return instrumentation + self._emit_extreme(function, layout, instruction)
        if opcode is AssemblyOpcode.TCMP:
            return instrumentation + [
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
            return instrumentation + [
                f"    jmp {mangle_block(function.name, instruction.labels[0])}"
            ]
        if opcode is AssemblyOpcode.TBR3:
            negative, zero, positive = (
                mangle_block(function.name, label)
                for label in instruction.labels
            )
            invalid_trit = self._instruction_failure(
                "invalid trit state",
                detail_prefix="value ",
                detail_suffix=" outside [-1, 1]\n",
                value_register="rax",
            )
            return instrumentation + [
                *self._read_register(layout, registers[0], "rax"),
                "    cmp rax, -1",
                f"    je {negative}",
                "    cmp rax, 0",
                f"    je {zero}",
                "    cmp rax, 1",
                f"    je {positive}",
                f"    jmp {invalid_trit}",
            ]
        if opcode is AssemblyOpcode.TCALL:
            return instrumentation + self._emit_call(function, layout, instruction)
        if opcode is AssemblyOpcode.TRET:
            if function.result_width > 1:
                return instrumentation + self._emit_multi_return(
                    function,
                    layout,
                    instruction,
                )
            return instrumentation + [
                *self._read_register(layout, registers[0], "rax"),
                *self._restore_callee_saved(layout),
                "    dec qword ptr [rip + __s3_frame_count]",
                "    leave",
                "    ret",
            ]
        if opcode is AssemblyOpcode.TLOAD:
            return instrumentation + self._emit_load(layout, instruction)
        if opcode is AssemblyOpcode.TSTORE:
            return instrumentation + self._emit_store(layout, instruction)
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
        assert instruction.callee is not None
        callee = self.functions[instruction.callee]
        destinations = instruction.result_registers
        arguments = instruction.argument_registers
        if callee.result_width == 1:
            if len(destinations) != 1:
                raise NativeBackendError(
                    "scalar native call result requires one destination"
                )
            destination = destinations[0]
            return self._emit_scalar_call(layout, instruction, arguments, destination)
        if destinations and len(destinations) != callee.result_width:
            raise NativeBackendError("multi-cell native call result width mismatch")
        return self._emit_sret_call(layout, instruction, arguments, destinations, callee)

    def _emit_scalar_call(
        self,
        layout: FrameLayout,
        instruction: AssemblyInstruction,
        arguments: tuple[int, ...],
        destination: int,
    ) -> list[str]:
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

    def _emit_sret_call(
        self,
        layout: FrameLayout,
        instruction: AssemblyInstruction,
        arguments: tuple[int, ...],
        destinations: tuple[int, ...],
        callee: AssemblyFunction,
    ) -> list[str]:
        sret_size = callee.result_width * 8
        stack_argument_capacity = max(len(_ARGUMENT_REGISTERS) - 1, 0)
        stack_arguments = arguments[stack_argument_capacity:]
        pushed_words = len(stack_arguments)
        padding = 1 if (pushed_words + 1) % 2 else 0
        lines: list[str] = []
        if padding:
            lines.append("    sub rsp, 8")
        lines.append(f"    sub rsp, {sret_size}")
        lines.append("    mov rdi, rsp")
        for register in reversed(stack_arguments):
            lines.extend(self._read_register(layout, register, "rax"))
            lines.append("    push rax")
        for register, target in zip(
            arguments[:stack_argument_capacity],
            _ARGUMENT_REGISTERS[1:],
            strict=False,
        ):
            lines.extend(self._read_register(layout, register, target))
        assert instruction.callee is not None
        lines.append(f"    call {mangle_function(instruction.callee)}")
        if destinations:
            for index, destination in enumerate(destinations):
                lines.append(
                    f"    mov rax, qword ptr [rsp + {pushed_words * 8 + index * 8}]"
                )
                lines.extend(self._write_register(layout, destination, "rax"))
        cleanup = sret_size + (pushed_words + padding) * 8
        if cleanup:
            lines.append(f"    add rsp, {cleanup}")
        return lines

    def _emit_multi_return(
        self,
        function: AssemblyFunction,
        layout: FrameLayout,
        instruction: AssemblyInstruction,
    ) -> list[str]:
        if len(instruction.registers) != function.result_width:
            raise NativeBackendError("multi-cell native return width mismatch")
        if layout.hidden_sret_pointer is None:
            raise NativeBackendError("missing hidden sret pointer slot")
        lines = [
            f"    mov r11, qword ptr {_address(layout.hidden_sret_pointer)}"
        ]
        for index, register in enumerate(instruction.registers):
            lines.extend(self._read_register(layout, register, "rax"))
            lines.append(f"    mov qword ptr [r11 + {index * 8}], rax")
        lines.extend(self._restore_callee_saved(layout))
        lines.extend(
            (
                "    dec qword ptr [rip + __s3_frame_count]",
                "    leave",
                "    ret",
            )
        )
        return lines

    def _memory_bounds(self, memory: MemorySlot, index: str) -> list[str]:
        failure = self._instruction_failure(
            "bounds",
            detail_prefix="index ",
            detail_suffix=f" outside [0, {memory.length})\n",
            value_register=index,
        )
        return [
            f"    cmp {index}, 0",
            f"    jl {failure}",
            f"    cmp {index}, {memory.length}",
            f"    jge {failure}",
        ]

    def _emit_load(
        self,
        layout: FrameLayout,
        instruction: AssemblyInstruction,
    ) -> list[str]:
        destination, index_register = instruction.registers
        assert instruction.memory is not None
        memory = layout.memory(instruction.memory)
        uninitialized = self._instruction_failure(
            "uninitialized memory",
            detail_prefix="index ",
            detail_suffix=f" is uninitialized in m{memory.index}\n",
            value_register="r10",
        )
        if memory.element_type is AssemblyType.STRING:
            load = "mov rax, qword ptr"
        elif memory.element_size == 1:
            load = "movsx rax, byte ptr"
        else:
            load = "movsx rax, word ptr"
        return [
            *self._read_register(layout, index_register, "r10"),
            *self._memory_bounds(memory, "r10"),
            (
                f"    cmp byte ptr "
                f"{_address(memory.initialized, index='r10')}, 0"
            ),
            f"    je {uninitialized}",
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
        ]
        if memory.element_type is not AssemblyType.STRING:
            overflow = self._overflow_failure(memory.element_type, "r10")
            lines.extend(self._range_check(memory.element_type, "r10", overflow))
        init_address = _address(memory.initialized, index="rax")
        if not memory.mutable:
            immutable = self._instruction_failure(
                "immutable memory",
                detail_prefix="index ",
                detail_suffix=(
                    f" already initialized in immutable m{memory.index}\n"
                ),
                value_register="rax",
            )
            lines.extend(
                (
                    f"    cmp byte ptr {init_address}, 0",
                    f"    jne {immutable}",
                )
            )
        data_address = _address(
            memory.data,
            index="rax",
            scale=memory.element_size,
        )
        if memory.element_type is AssemblyType.STRING:
            source = "r10"
            size = "qword"
        elif memory.element_size == 1:
            source = "r10b"
            size = "byte"
        else:
            source = "r10w"
            size = "word"
        lines.extend(
            (
                f"    mov {size} ptr {data_address}, {source}",
                f"    mov byte ptr {init_address}, 1",
            )
        )
        return lines

    def _overflow_failure(
        self,
        type_name: AssemblyType,
        value_register: str,
    ) -> str:
        minimum, maximum = (
            (-1, 1)
            if type_name is AssemblyType.TRIT
            else (-364, 364)
        )
        return self._instruction_failure(
            "overflow",
            detail_prefix=f"{type_name.value} result ",
            detail_suffix=f" outside [{minimum}, {maximum}]\n",
            value_register=value_register,
        )

    def _instruction_failure(
        self,
        category: str,
        *,
        detail: str | None = None,
        detail_prefix: str | None = None,
        detail_suffix: str | None = None,
        value_register: str | None = None,
    ) -> str:
        assert self.current_function is not None
        assert self.current_block is not None
        assert self.current_instruction is not None
        return self._new_failure_site(
            category=category,
            function=self.current_function.name,
            block=self.current_block,
            opcode=self.current_instruction.opcode.value,
            instruction=self.current_instruction,
            detail=detail,
            detail_prefix=detail_prefix,
            detail_suffix=detail_suffix,
            value_register=value_register,
        )

    def _new_failure_site(
        self,
        *,
        category: str,
        function: str,
        block: str,
        opcode: str,
        instruction: AssemblyInstruction | None,
        detail: str | None = None,
        detail_prefix: str | None = None,
        detail_suffix: str | None = None,
        value_register: str | None = None,
    ) -> str:
        source = (
            "source unknown"
            if instruction is None or instruction.source is None
            else (
                f"source {instruction.source.line}:"
                f"{instruction.source.column}"
            )
        )
        assembly_line = (
            ""
            if instruction is None or instruction.line is None
            else f", assembly line {instruction.line}"
        )
        context = (
            f"runtime error [{category}] in function '{function}'\n"
            f"at {source} (block {block}, {opcode}{assembly_line}): "
        )
        if value_register is None:
            assert detail is not None
            site = FailureSite(len(self.failure_sites), context + detail)
        else:
            assert detail_prefix is not None
            assert detail_suffix is not None
            site = FailureSite(
                len(self.failure_sites),
                context + detail_prefix,
                detail_suffix,
                value_register,
            )
        self.failure_sites.append(site)
        return site.label

    def _render_failure_handlers(self) -> list[str]:
        lines = [".section .text"]
        for site in self.failure_sites:
            lines.append(f"{site.label}:")
            if site.value_register is None:
                lines.extend(
                    (
                        f"    lea rsi, [rip + {site.prefix_label}]",
                        f"    mov edx, {len(site.prefix.encode('ascii'))}",
                        "    jmp __s3_fail_message",
                    )
                )
            else:
                assert site.suffix is not None
                lines.extend(
                    (
                        f"    mov rdi, {site.value_register}",
                        f"    lea rsi, [rip + {site.prefix_label}]",
                        f"    mov edx, {len(site.prefix.encode('ascii'))}",
                        f"    lea rcx, [rip + {site.suffix_label}]",
                        f"    mov r8d, {len(site.suffix.encode('ascii'))}",
                        "    jmp __s3_fail_value",
                    )
                )
        lines.append("")
        return lines

    def _render_static_string_data(self) -> list[str]:
        if not self.program.static_strings:
            return []
        lines = [".section .rodata"]
        for entry in self.program.static_strings:
            lines.extend(
                (
                    f"{mangle_static_string(entry.id)}:",
                    f'    .asciz "{self._escape_ascii(entry.value)}"',
                )
            )
        lines.append("")
        return lines

    def _render_failure_data(self) -> list[str]:
        lines = [".section .rodata"]
        for site in self.failure_sites:
            lines.extend(
                (
                    f"{site.prefix_label}:",
                    f'    .ascii "{self._escape_ascii(site.prefix)}"',
                )
            )
            if site.suffix is not None:
                lines.extend(
                    (
                        f"{site.suffix_label}:",
                        f'    .ascii "{self._escape_ascii(site.suffix)}"',
                    )
                )
        lines.append("")
        return lines

    @staticmethod
    def _escape_ascii(value: str) -> str:
        return (
            value.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
        )
