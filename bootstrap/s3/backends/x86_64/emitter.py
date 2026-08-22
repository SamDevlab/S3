"""Deterministic lowering from validated S3 Assembly to GNU x86-64."""

from __future__ import annotations

import re
import struct
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
from .registers import (
    CALLER_SAVED_ALLOCATABLE_REGISTERS,
    CALLEE_SAVED_ALLOCATABLE_REGISTERS,
    SYSV_INTEGER_ARGUMENT_REGISTERS,
)
from ...numeric_abi import SYSV_FLOAT_ARGUMENT_REGISTERS
from ...ir import DYNAMIC_BUILTIN_SIGNATURES
from .runtime import render_runtime
from .allocation import AllocationPlan, analyze_allocation
from .liveness import analyze_liveness
from .residence import analyze_cross_block_residence
from .policy import BASELINE_NATIVE_POLICY, NativePolicy
from .register_init_safety import proven_initialized_register_reads


_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_ARGUMENT_REGISTERS = SYSV_INTEGER_ARGUMENT_REGISTERS


def _f64_bits(value: float) -> int:
    return struct.unpack("<Q", struct.pack("<d", value))[0]


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


def function_symbol(function: AssemblyFunction) -> str:
    """Return the stable ABI symbol for exported and foreign functions."""

    if function.exported or function.external:
        if _IDENTIFIER.fullmatch(function.name) is None:
            raise NativeBackendError(f"unsafe function identifier {function.name!r}")
        return function.name
    return mangle_function(function.name)


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
        native_policy: NativePolicy = BASELINE_NATIVE_POLICY,
    ):
        self.program = program
        self.max_frames = max_frames
        self.max_instructions = max_instructions
        self.register_allocation = register_allocation
        self.native_policy = native_policy
        self.native_policy.validate()
        self.failure_sites: list[FailureSite] = []
        self.current_function: AssemblyFunction | None = None
        self.current_block: str | None = None
        self.current_instruction: AssemblyInstruction | None = None
        self.functions = {function.name: function for function in program.functions}
        self.current_plan: AllocationPlan | None = None
        self._physical_residence_active = False
        self._entry_live_registers: frozenset[int] = frozenset()
        self._safe_register_reads: frozenset[tuple[str, int, int]] = frozenset()
        self._current_instruction_sites: dict[int, tuple[str, int]] = {}
        self._scalar_promoted_stores: set[int] = set()
        self._scalar_promoted_loads: dict[int, int] = {}
        self._scalar_memory_sources: dict[int, int] = {}
        self._split_restore_serial = 0

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
        if function.external:
            return []
        self._safe_register_reads = proven_initialized_register_reads(function)
        self._current_instruction_sites = {
            id(instruction): (block.label, index)
            for block in function.blocks
            for index, instruction in enumerate(block.instructions)
        }
        self._entry_live_registers = (
            analyze_liveness(function).blocks[function.blocks[0].label].live_in
            if function.blocks
            else frozenset()
        )
        if self.register_allocation:
            plan = analyze_allocation(function, self.native_policy)
            self.current_plan = plan
            layout = layout_frame(function, plan.used_physical_registers)
        else:
            plan = analyze_cross_block_residence(function, self.native_policy)
            self.current_plan = plan if plan.used_physical_registers else None
            layout = layout_frame(function, plan.used_physical_registers)
        self._physical_residence_active = self.current_plan is not None
        (
            self._scalar_promoted_stores,
            self._scalar_promoted_loads,
        ) = self._find_scalar_promotions(function)
        symbol = function_symbol(function)
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
        if self._physical_residence_active and self.current_plan:
            for phys in CALLEE_SAVED_ALLOCATABLE_REGISTERS:
                if phys not in self.current_plan.used_physical_registers:
                    continue
                slot = layout.callee_saved_slot(phys)
                lines.append(f"    mov qword ptr {_address(slot.region)}, {phys}")
        lines.extend(self._save_parameters(function, layout))
        lines.extend(self._initialize_metadata(function, layout))
        lines.append(f"    jmp {mangle_block(function.name, 'entry')}")
        function_liveness = analyze_liveness(function)
        for block in function.blocks:
            lines.append(f"{mangle_block(function.name, block.label)}:")
            lines.extend(self._loop_boundary_restore(layout, block.label))
            instruction_index = 0
            while instruction_index < len(block.instructions):
                if self._can_fuse_tcmp_tbr3(
                    block,
                    instruction_index,
                    function_liveness,
                ):
                    lines.extend(
                        self._emit_tcmp_tbr3(
                            function,
                            block.label,
                            layout,
                            block.instructions[instruction_index],
                            block.instructions[instruction_index + 1],
                        )
                    )
                    instruction_index += 2
                    continue
                lines.extend(
                    self._emit_instruction(
                        function,
                        block.label,
                        layout,
                        block.instructions[instruction_index],
                    )
                )
                instruction_index += 1
        lines.append(f".size {symbol}, .-{symbol}")
        return lines

    @staticmethod
    def _can_fuse_tcmp_tbr3(
        block: AssemblyBlock,
        instruction_index: int,
        function_liveness,
    ) -> bool:
        if instruction_index + 1 >= len(block.instructions):
            return False
        compare = block.instructions[instruction_index]
        branch = block.instructions[instruction_index + 1]
        if compare.opcode is not AssemblyOpcode.TCMP:
            return False
        if branch.opcode is not AssemblyOpcode.TBR3:
            return False
        if not branch.registers or compare.registers[0] != branch.registers[0]:
            return False
        # The materialized comparison result is not needed after the branch.
        # Liveness across the CFG is the explicit proof that no successor
        # observes the result or depends on its initialized marker.
        return compare.registers[0] not in function_liveness.for_instruction(
            branch
        ).live_after

    def _instruction_instrumentation(
        self,
        function: AssemblyFunction,
        block_name: str,
        instruction: AssemblyInstruction,
    ) -> list[str]:
        self.current_function = function
        self.current_block = block_name
        self.current_instruction = instruction
        limit_failure = self._instruction_failure(
            "instruction limit",
            detail=f"instruction limit {self.max_instructions} exceeded\n",
        )
        if 0 <= self.max_instructions <= 0x7FFFFFFF:
            instrumentation = [
                f"    cmp qword ptr [rip + __s3_instruction_count], "
                f"{self.max_instructions}"
            ]
        else:
            instrumentation = [
                f"    movabs r11, {self.max_instructions}",
                "    cmp qword ptr [rip + __s3_instruction_count], r11",
            ]
        instrumentation.extend(
            [
                f"    jae {limit_failure}",
                "    inc qword ptr [rip + __s3_instruction_count]",
            ]
        )
        return instrumentation

    def _emit_tcmp_tbr3(
        self,
        function: AssemblyFunction,
        block_name: str,
        layout: FrameLayout,
        compare: AssemblyInstruction,
        branch: AssemblyInstruction,
    ) -> list[str]:
        _, left, right = compare.registers
        lines = self._instruction_instrumentation(function, block_name, compare)
        lines.extend(self._read_register(layout, left, "rax"))
        lines.extend(self._read_register(layout, right, "r10"))

        # The second instruction's limit check intentionally precedes the
        # native compare. The first instruction has already validated and
        # loaded both operands, and the second check may clobber flags.
        lines.extend(self._instruction_instrumentation(function, block_name, branch))
        lines.extend(self._loop_boundary_save(layout, branch))
        source_type = function.type_of(left)
        if source_type is AssemblyType.F64:
            lines.extend(
                (
                    "    movq xmm0, rax",
                    "    movq xmm1, r10",
                    "    ucomisd xmm0, xmm1",
                    f"    jb {mangle_block(function.name, branch.labels[0])}",
                    f"    ja {mangle_block(function.name, branch.labels[2])}",
                    f"    jmp {mangle_block(function.name, branch.labels[1])}",
                )
            )
        else:
            lines.extend(
                (
                    "    cmp rax, r10",
                    f"    jl {mangle_block(function.name, branch.labels[0])}",
                    f"    jg {mangle_block(function.name, branch.labels[2])}",
                    f"    jmp {mangle_block(function.name, branch.labels[1])}",
                )
            )
        return lines

    def _save_parameters(
        self,
        function: AssemblyFunction,
        layout: FrameLayout,
    ) -> list[str]:
        lines: list[str] = []
        if function.result_width == 1 and any(
            parameter.type is AssemblyType.F64 for parameter in function.parameters
        ):
            return self._save_numeric_parameters(function, layout)
        if function.result_width > 1:
            if layout.hidden_sret_pointer is None:
                raise NativeBackendError("missing hidden sret pointer slot")
            lines.append(
                f"    mov qword ptr {_address(layout.hidden_sret_pointer)}, rdi"
            )
        if not self._physical_residence_active or not self.current_plan:
            for position, parameter in enumerate(function.parameters):
                slot = layout.register(parameter.register)
                native_position = position + (1 if function.result_width > 1 else 0)
                if native_position < len(_ARGUMENT_REGISTERS):
                    source = _ARGUMENT_REGISTERS[native_position]
                    lines.append(f"    mov qword ptr {_address(slot.value)}, {source}")
                else:
                    caller_offset = 16 + (native_position - len(_ARGUMENT_REGISTERS)) * 8
                    lines.extend(
                        (
                            f"    mov rax, qword ptr [rbp + {caller_offset}]",
                            f"    mov qword ptr {_address(slot.value)}, rax",
                        )
                    )
            return lines
        # Snapshot every incoming argument in its logical value slot first.
        # This deliberately avoids parallel-copy cycles when parameters are
        # allocated to ABI argument registers.
        for position, parameter in enumerate(function.parameters):
            slot = layout.register(parameter.register)
            native_position = position + (1 if function.result_width > 1 else 0)
            if native_position < len(_ARGUMENT_REGISTERS):
                source = _ARGUMENT_REGISTERS[native_position]
                lines.append(f"    mov qword ptr {_address(slot.value)}, {source}")
            else:
                caller_offset = (
                    16 + (native_position - len(_ARGUMENT_REGISTERS)) * 8
                )
                lines.extend(
                    (
                        f"    mov rax, qword ptr [rbp + {caller_offset}]",
                        f"    mov qword ptr {_address(slot.value)}, rax",
                    )
                )
        if self._physical_residence_active and self.current_plan:
            for parameter in function.parameters:
                if parameter.register not in self._entry_live_registers:
                    continue
                phys = self.current_plan.physical_register(parameter.register)
                if phys is not None:
                    slot = layout.register(parameter.register)
                    lines.append(f"    mov {phys}, qword ptr {_address(slot.value)}")
        return lines

    def _save_numeric_parameters(
        self,
        function: AssemblyFunction,
        layout: FrameLayout,
    ) -> list[str]:
        lines: list[str] = []
        integer_index = 0
        float_index = 0
        stack_index = 0
        for parameter in function.parameters:
            slot = layout.register(parameter.register)
            if parameter.type is AssemblyType.F64 and float_index < len(SYSV_FLOAT_ARGUMENT_REGISTERS):
                source = SYSV_FLOAT_ARGUMENT_REGISTERS[float_index]
                float_index += 1
                lines.extend((
                    f"    movq rax, {source}",
                    f"    mov qword ptr {_address(slot.value)}, rax",
                ))
            elif parameter.type is not AssemblyType.F64 and integer_index < len(_ARGUMENT_REGISTERS):
                source = _ARGUMENT_REGISTERS[integer_index]
                integer_index += 1
                lines.append(f"    mov qword ptr {_address(slot.value)}, {source}")
            else:
                caller_offset = 16 + stack_index * 8
                stack_index += 1
                lines.extend((
                    f"    mov rax, qword ptr [rbp + {caller_offset}]",
                    f"    mov qword ptr {_address(slot.value)}, rax",
                ))
        if self._physical_residence_active and self.current_plan:
            for parameter in function.parameters:
                if parameter.register not in self._entry_live_registers:
                    continue
                physical = self.current_plan.physical_register(parameter.register)
                if physical is not None:
                    slot = layout.register(parameter.register)
                    lines.append(
                        f"    mov {physical}, qword ptr {_address(slot.value)}"
                    )
        return lines

    def _initialize_metadata(
        self,
        function: AssemblyFunction,
        layout: FrameLayout,
    ) -> list[str]:
        lines: list[str] = []
        preserve_metadata_scratch = self._physical_residence_active and bool(layout.memories)
        if preserve_metadata_scratch:
            lines.extend(("    mov r10, rdi", "    mov r11, rcx"))
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
        if preserve_metadata_scratch:
            lines.extend(("    mov rdi, r10", "    mov rcx, r11"))
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
        site = self._current_instruction_sites.get(id(self.current_instruction))
        skip_initialization_check = (
            site is not None
            and (site[0], site[1], register) in self._safe_register_reads
        )
        slot = layout.register(register)
        if skip_initialization_check:
            phys = (
                self.current_plan.physical_register(register)
                if (self._physical_residence_active and self.current_plan)
                else None
            )
            if phys is None:
                return [f"    mov {target}, qword ptr {_address(slot.value)}"]
            if phys != target:
                return [f"    mov {target}, {phys}"]
            return []
        if (
            self.current_plan is not None
            and register in self.current_plan.rematerializable_values
            and self.current_plan.physical_register(register) is None
        ):
            failure = self._instruction_failure(
                "uninitialized register",
                detail=f"register r{register} is uninitialized\n",
            )
            lines = [
                f"    cmp byte ptr {_address(slot.initialized)}, 0",
                f"    je {failure}",
            ]
            lines.append(
                self._rematerialize_instruction(register, target)
            )
            return lines
        failure = self._instruction_failure(
            "uninitialized register",
            detail=f"register r{register} is uninitialized\n",
        )
        lines = [
            f"    cmp byte ptr {_address(slot.initialized)}, 0",
            f"    je {failure}",
        ]
        phys = self.current_plan.physical_register(register) if (self._physical_residence_active and self.current_plan) else None
        if phys is None:
            lines.append(f"    mov {target}, qword ptr {_address(slot.value)}")
        elif phys != target:
            lines.append(f"    mov {target}, {phys}")
        return lines

    def _rematerialize_instruction(self, register: int, target: str) -> str:
        assert self.current_plan is not None
        assert self.current_function is not None
        immediate = self.current_plan.rematerializable_values[register]
        if self.current_function.type_of(register) is AssemblyType.F64:
            immediate = _f64_bits(float(immediate))
            return f"    movabs {target}, {immediate}"
        if -0x80000000 <= int(immediate) <= 0x7FFFFFFF:
            return f"    mov {target}, {immediate}"
        return f"    movabs {target}, {immediate}"

    def _find_scalar_promotions(
        self,
        function: AssemblyFunction,
    ) -> tuple[set[int], dict[int, int]]:
        if self.native_policy.scalar_promotion != "conservative_mem2reg":
            return set(), {}
        memories = {memory.index: memory for memory in function.memory_objects}
        if any(
            instruction.opcode in {
                AssemblyOpcode.TCALL,
                AssemblyOpcode.TADDR,
                AssemblyOpcode.TREFLOAD,
                AssemblyOpcode.TREFSTORE,
            }
            for instruction in function.instructions
        ):
            return set(), {}
        memory_use_counts: dict[int, int] = {}
        for instruction in function.instructions:
            if instruction.opcode in {AssemblyOpcode.TLOAD, AssemblyOpcode.TSTORE}:
                assert instruction.memory is not None
                memory_use_counts[instruction.memory] = (
                    memory_use_counts.get(instruction.memory, 0) + 1
                )
        stores: set[int] = set()
        loads: dict[int, int] = {}
        for block in function.blocks:
            for index, store in enumerate(block.instructions[:-1]):
                load = block.instructions[index + 1]
                if store.opcode is not AssemblyOpcode.TSTORE or load.opcode is not AssemblyOpcode.TLOAD:
                    continue
                if store.memory is None or load.memory != store.memory:
                    continue
                memory = memories.get(store.memory)
                if memory is None or not memory.mutable or memory.length != 1:
                    continue
                if memory_use_counts.get(memory.index) != 2:
                    continue
                store_index, source = store.registers
                destination, load_index = load.registers
                if store_index != load_index:
                    continue
                if function.type_of(source) is not memory.element_type:
                    continue
                if function.type_of(destination) is not memory.element_type:
                    continue
                stores.add(id(store))
                loads[id(load)] = source
        return stores, loads

    def _loop_boundary_save(
        self,
        layout: FrameLayout,
        instruction: AssemblyInstruction,
    ) -> list[str]:
        if self.current_plan is None:
            return []
        registers = self.current_plan.loop_split_saves.get(id(instruction), ())
        lines: list[str] = []
        for register in registers:
            physical = self.current_plan.physical_register(register)
            if physical is None:
                continue
            lines.extend(self._check_register_initialized(layout, register))
            lines.append(
                f"    mov qword ptr {_address(layout.register(register).value)}, {physical}"
            )
        return lines

    def _loop_boundary_restore(
        self,
        layout: FrameLayout,
        block_name: str,
    ) -> list[str]:
        if self.current_plan is None:
            return []
        registers = self.current_plan.loop_split_restores.get(block_name, ())
        lines: list[str] = []
        for register in registers:
            physical = self.current_plan.physical_register(register)
            if physical is None:
                continue
            label = f".L__s3_split_restore_skip_{self._split_restore_serial}"
            self._split_restore_serial += 1
            slot = layout.register(register)
            lines.extend(
                (
                    f"    cmp byte ptr {_address(slot.initialized)}, 0",
                    f"    je {label}",
                    f"    mov {physical}, qword ptr {_address(slot.value)}",
                    f"{label}:",
                )
            )
        return lines

    def _memory_index_target(self, register: int, fallback: str) -> str:
        if (
            self.native_policy.indexed_memory_policy != "compact_ea"
            or not self._physical_residence_active
            or self.current_plan is None
        ):
            return fallback
        physical = self.current_plan.physical_register(register)
        if physical is None or physical in {"rax", "r10", "r11"}:
            return fallback
        return physical

    def _check_register_initialized(
        self,
        layout: FrameLayout,
        register: int,
    ) -> list[str]:
        site = self._current_instruction_sites.get(id(self.current_instruction))
        if site is not None and (site[0], site[1], register) in self._safe_register_reads:
            return []
        slot = layout.register(register)
        failure = self._instruction_failure(
            "uninitialized register",
            detail=f"register r{register} is uninitialized\n",
        )
        return [
            f"    cmp byte ptr {_address(slot.initialized)}, 0",
            f"    je {failure}",
        ]

    def _write_register(
        self,
        layout: FrameLayout,
        register: int,
        source: str,
    ) -> list[str]:
        slot = layout.register(register)
        phys = self.current_plan.physical_register(register) if (self._physical_residence_active and self.current_plan) else None
        lines = []
        if phys is None:
            lines.append(f"    mov qword ptr {_address(slot.value)}, {source}")
        elif phys != source:
            lines.append(f"    mov {phys}, {source}")
        lines.append(f"    mov byte ptr {_address(slot.initialized)}, 1")
        return lines

    def _snapshot_register(self, layout: FrameLayout, register: int) -> list[str]:
        """Validate and snapshot a logical argument before ABI registers change."""
        slot = layout.register(register)
        failure = self._instruction_failure(
            "uninitialized register",
            detail=f"register r{register} is uninitialized\n",
        )
        lines = [
            f"    cmp byte ptr {_address(slot.initialized)}, 0",
            f"    je {failure}",
        ]
        phys = self.current_plan.physical_register(register) if (self._physical_residence_active and self.current_plan) else None
        if phys is not None:
            lines.append(f"    mov qword ptr {_address(slot.value)}, {phys}")
        return lines

    def _load_snapshot(
        self,
        layout: FrameLayout,
        register: int,
        target: str,
    ) -> list[str]:
        slot = layout.register(register)
        return [f"    mov {target}, qword ptr {_address(slot.value)}"]

    def _save_caller_saved(self, layout: FrameLayout, physicals: tuple[str, ...]) -> list[str]:
        return [
            f"    mov qword ptr {_address(layout.caller_saved_spill_slot(phys).region)}, {phys}"
            for phys in physicals
        ]

    def _restore_caller_saved(self, layout: FrameLayout, physicals: tuple[str, ...]) -> list[str]:
        return [
            f"    mov {phys}, qword ptr {_address(layout.caller_saved_spill_slot(phys).region)}"
            for phys in physicals
        ]

    def _call_survivor_physicals(
        self, instruction: AssemblyInstruction
    ) -> tuple[str, ...]:
        if not self._physical_residence_active or not self.current_plan:
            return ()
        physicals = {
            self.current_plan.physical_register(register)
            for register in self.current_plan.call_survivors_for(instruction)
        }
        return tuple(phys for phys in CALLER_SAVED_ALLOCATABLE_REGISTERS if phys in physicals)

    def _used_caller_saved_physicals(self) -> tuple[str, ...]:
        if not self._physical_residence_active or not self.current_plan:
            return ()
        return tuple(
            phys for phys in CALLER_SAVED_ALLOCATABLE_REGISTERS
            if phys in self.current_plan.used_physical_registers
        )

    def _restore_callee_saved(self, layout: FrameLayout) -> list[str]:
        if not self._physical_residence_active or not self.current_plan:
            return []
        lines = []
        for phys in CALLEE_SAVED_ALLOCATABLE_REGISTERS:
            if phys not in self.current_plan.used_physical_registers:
                continue
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
        if 0 <= self.max_instructions <= 0x7FFFFFFF:
            instrumentation = [
                f"    cmp qword ptr [rip + __s3_instruction_count], "
                f"{self.max_instructions}"
            ]
        else:
            instrumentation = [
                f"    movabs r11, {self.max_instructions}",
                "    cmp qword ptr [rip + __s3_instruction_count], r11",
            ]
        instrumentation.extend(
            [
                f"    jae {limit_failure}",
                "    inc qword ptr [rip + __s3_instruction_count]",
            ]
        )

        if opcode is AssemblyOpcode.TCONST:
            assert instruction.immediate is not None
            type_name = function.type_of(registers[0])
            immediate = (
                _f64_bits(float(instruction.immediate))
                if type_name is AssemblyType.F64
                else instruction.immediate
            )
            if (
                self.current_plan is not None
                and registers[0] in self.current_plan.rematerializable_values
                and self.current_plan.physical_register(registers[0]) is None
            ):
                slot = layout.register(registers[0])
                return instrumentation + [
                    f"    mov byte ptr {_address(slot.initialized)}, 1"
                ]
            if (
                type_name is not AssemblyType.F64
                and -0x80000000 <= int(immediate) <= 0x7FFFFFFF
            ):
                return instrumentation + self._write_register(
                    layout, registers[0], str(immediate)
                )
            return instrumentation + [
                f"    movabs rax, {immediate}",
                *self._write_register(layout, registers[0], "rax"),
            ]
        if opcode is AssemblyOpcode.TCONST_STR:
            assert instruction.static_string is not None
            return instrumentation + [
                f"    lea rax, [rip + {mangle_static_string(instruction.static_string)}]",
                *self._write_register(layout, registers[0], "rax"),
            ]
        if opcode is AssemblyOpcode.TADDR:
            destination = registers[0]
            if instruction.memory is not None:
                memory = layout.memory(instruction.memory)
                if len(registers) > 1:
                    index = registers[1]
                    bounds_failure = self._instruction_failure(
                        "bounds",
                        detail_prefix="array reference index ",
                        detail_suffix=" out of bounds\n",
                        value_register="rax",
                    )
                    # Valid array lengths are non-negative.  An unsigned
                    # comparison therefore rejects both negative indices and
                    # indices at or beyond the upper bound in one branch.
                    source_check = [
                        *self._read_register(layout, index, "rax"),
                        f"    cmp rax, {memory.length}",
                        f"    jae {bounds_failure}",
                    ]
                    address = _address(
                        memory.data,
                        index="rax",
                        scale=memory.element_size,
                    )
                else:
                    address = _address(memory.data)
                    source_check = []
            else:
                source = registers[1]
                source_check = self._read_register(layout, source, "r11")
                address = _address(layout.register(source).value)
            return instrumentation + [
                *source_check,
                f"    lea r10, {address}",
                *self._write_register(layout, destination, "r10"),
            ]
        if opcode is AssemblyOpcode.TREFLOAD:
            destination, reference = registers
            type_name = instruction.reference_target
            if self.current_function.reference_storage_size(reference) == 8:
                load = "mov r11, qword ptr [r10]"
            elif type_name is AssemblyType.TRIT:
                load = "movsx r11, byte ptr [r10]"
            elif type_name is AssemblyType.TRYTE:
                load = "movsx r11, word ptr [r10]"
            else:
                load = "mov r11, qword ptr [r10]"
            return instrumentation + [
                *self._read_register(layout, reference, "r10"),
                f"    {load}",
                *self._write_register(layout, destination, "r11"),
            ]
        if opcode is AssemblyOpcode.TSLEN:
            destination, _reference, length = registers
            return instrumentation + [
                *self._read_register(layout, length, "rax"),
                *self._write_register(layout, destination, "rax"),
            ]
        if opcode is AssemblyOpcode.TSLOAD:
            destination, reference, length, index = registers
            type_name = instruction.reference_target
            if type_name is None:
                raise NativeBackendError("TSLOAD is missing its element type")
            bounds_failure = self._instruction_failure(
                "bounds",
                detail_prefix="slice index ",
                detail_suffix=" out of bounds\n",
                value_register="rax",
            )
            if type_name is AssemblyType.F64:
                load = "mov r11, qword ptr [r10 + rax * 8]"
            elif type_name is AssemblyType.I64:
                load = "mov r11, qword ptr [r10 + rax * 8]"
            elif type_name is AssemblyType.TRYTE:
                load = "movsx r11, word ptr [r10 + rax * 2]"
            else:
                load = "movsx r11, byte ptr [r10 + rax]"
            return instrumentation + [
                *self._read_register(layout, reference, "r10"),
                *self._read_register(layout, length, "r11"),
                *self._read_register(layout, index, "rax"),
                "    cmp rax, r11",
                f"    jae {bounds_failure}",
                f"    {load}",
                *self._write_register(layout, destination, "r11"),
            ]
        if opcode is AssemblyOpcode.TSSTORE:
            reference, length, index, source = registers
            type_name = instruction.reference_target
            if type_name is None:
                raise NativeBackendError("TSSTORE is missing its element type")
            bounds_failure = self._instruction_failure(
                "bounds",
                detail_prefix="slice index ",
                detail_suffix=" out of bounds\n",
                value_register="rax",
            )
            lines = instrumentation + [
                *self._read_register(layout, reference, "r10"),
                *self._read_register(layout, length, "r11"),
                *self._read_register(layout, index, "rax"),
                *self._read_register(layout, source, "rcx"),
                "    cmp rax, r11",
                f"    jae {bounds_failure}",
            ]
            if type_name is AssemblyType.TRYTE:
                lines.append("    mov word ptr [r10 + rax * 2], cx")
            elif type_name is AssemblyType.TRIT:
                lines.append("    mov byte ptr [r10 + rax], cl")
            else:
                lines.append("    mov qword ptr [r10 + rax * 8], rcx")
            return lines
        if opcode is AssemblyOpcode.TREFSTORE:
            reference, source = registers
            type_name = instruction.reference_target
            lines = instrumentation + [
                *self._read_register(layout, reference, "r10"),
                *self._read_register(layout, source, "r11"),
            ]
            if type_name in {AssemblyType.TRIT, AssemblyType.TRYTE}:
                overflow = self._overflow_failure(type_name, "r11")
                lines.extend(self._range_check(type_name, "r11", overflow))
            storage_size = self.current_function.reference_storage_size(reference)
            if storage_size == 8:
                lines.append("    mov qword ptr [r10], r11")
            elif type_name is AssemblyType.TRIT:
                lines.append("    mov byte ptr [r10], r11b")
            elif type_name is AssemblyType.TRYTE:
                lines.append("    mov word ptr [r10], r11w")
            else:
                lines.append("    mov qword ptr [r10], r11")
            return lines
        if opcode is AssemblyOpcode.TMOV:
            destination, source = registers
            if destination == source:
                return instrumentation + self._check_register_initialized(layout, source)
            # TMOV copies a value version; do not alias a mutable logical register.
            return instrumentation + [
                *self._read_register(layout, source, "rax"),
                *self._write_register(layout, destination, "rax"),
            ]
        if opcode is AssemblyOpcode.TINV:
            type_name = function.type_of(registers[0])
            assert type_name is not None
            if type_name is AssemblyType.F64:
                return instrumentation + [
                    *self._read_register(layout, registers[1], "rax"),
                    "    movabs r10, 9223372036854775808",
                    "    xor rax, r10",
                    *self._write_register(layout, registers[0], "rax"),
                ]
            overflow = self._overflow_failure(type_name, "rax")
            lines = instrumentation + [
                *self._read_register(layout, registers[1], "rax"),
                "    neg rax",
                f"    jo {overflow}",
            ]
            if type_name in {AssemblyType.TRIT, AssemblyType.TRYTE}:
                lines.extend(self._range_check(type_name, "rax", overflow))
            lines.extend(self._write_register(layout, registers[0], "rax"))
            return lines
        if opcode is AssemblyOpcode.TADD:
            type_name = function.type_of(registers[0])
            assert type_name is not None
            if type_name is AssemblyType.F64:
                return instrumentation + [
                    *self._read_register(layout, registers[1], "rax"),
                    *self._read_register(layout, registers[2], "r10"),
                    "    movq xmm0, rax",
                    "    movq xmm1, r10",
                    "    addsd xmm0, xmm1",
                    "    movq rax, xmm0",
                    *self._write_register(layout, registers[0], "rax"),
                ]
            if type_name is AssemblyType.I64:
                overflow = self._instruction_failure(
                    "overflow",
                    detail="i64 addition overflow\n",
                )
                return instrumentation + [
                    *self._read_register(layout, registers[1], "rax"),
                    *self._read_register(layout, registers[2], "r10"),
                    "    add rax, r10",
                    f"    jo {overflow}",
                    *self._write_register(layout, registers[0], "rax"),
                ]
            overflow = self._overflow_failure(type_name, "rax")
            return instrumentation + [
                *self._read_register(layout, registers[1], "rax"),
                *self._read_register(layout, registers[2], "r10"),
                "    add rax, r10",
                f"    jo {overflow}",
                *self._range_check(type_name, "rax", overflow),
                *self._write_register(layout, registers[0], "rax"),
            ]
        if opcode is AssemblyOpcode.TNDIFF:
            type_name = function.type_of(registers[0])
            assert type_name in {AssemblyType.I64, AssemblyType.F64}
            if type_name is AssemblyType.F64:
                return instrumentation + [
                    *self._read_register(layout, registers[1], "rax"),
                    *self._read_register(layout, registers[2], "r10"),
                    "    movq xmm0, rax",
                    "    movq xmm1, r10",
                    "    subsd xmm0, xmm1",
                    "    movq rax, xmm0",
                    *self._write_register(layout, registers[0], "rax"),
                ]
            overflow = self._instruction_failure(
                "overflow",
                detail="i64 subtraction overflow\n",
            )
            return instrumentation + [
                *self._read_register(layout, registers[1], "rax"),
                *self._read_register(layout, registers[2], "r10"),
                "    sub rax, r10",
                f"    jo {overflow}",
                *self._write_register(layout, registers[0], "rax"),
            ]
        if opcode in {AssemblyOpcode.TMUL, AssemblyOpcode.TDIV}:
            type_name = function.type_of(registers[0])
            assert type_name in {AssemblyType.I64, AssemblyType.F64}
            if type_name is AssemblyType.F64:
                operation = "mulsd" if opcode is AssemblyOpcode.TMUL else "divsd"
                return instrumentation + [
                    *self._read_register(layout, registers[1], "rax"),
                    *self._read_register(layout, registers[2], "r10"),
                    "    movq xmm0, rax",
                    "    movq xmm1, r10",
                    f"    {operation} xmm0, xmm1",
                    "    movq rax, xmm0",
                    *self._write_register(layout, registers[0], "rax"),
                ]
            if opcode is AssemblyOpcode.TMUL:
                overflow = self._instruction_failure("overflow", detail="i64 multiplication overflow\n")
                return instrumentation + [
                    *self._read_register(layout, registers[1], "rax"),
                    *self._read_register(layout, registers[2], "r10"),
                    "    imul rax, r10",
                    f"    jo {overflow}",
                    *self._write_register(layout, registers[0], "rax"),
                ]
            overflow = self._instruction_failure("overflow", detail="i64 division overflow\n")
            divide_by_zero = self._instruction_failure("division by zero", detail="i64 division by zero\n")
            safe_label = f".L__s3_idiv_safe_{len(self.failure_sites)}"
            return instrumentation + [
                *self._read_register(layout, registers[1], "rax"),
                *self._read_register(layout, registers[2], "r10"),
                "    cmp r10, 0",
                f"    je {divide_by_zero}",
                "    movabs r11, -9223372036854775808",
                "    cmp rax, r11",
                f"    jne {safe_label}",
                "    cmp r10, -1",
                f"    je {overflow}",
                f"{safe_label}:",
                "    cqo",
                "    idiv r10",
                *self._write_register(layout, registers[0], "rax"),
            ]
        if opcode is AssemblyOpcode.TREL:
            destination, left, right = registers
            source_type = function.type_of(left)
            relation = instruction.immediate
            assert relation in range(6)
            if source_type is AssemblyType.F64:
                setup = [
                    *self._read_register(layout, left, "rax"),
                    *self._read_register(layout, right, "r10"),
                    "    movq xmm0, rax",
                    "    movq xmm1, r10",
                    "    ucomisd xmm0, xmm1",
                ]
                if relation == 0:
                    compare_lines = ["    sete al", "    setnp r11b", "    and al, r11b"]
                elif relation == 1:
                    compare_lines = ["    setne al", "    setp r11b", "    or al, r11b"]
                elif relation == 2:
                    compare_lines = ["    setb al", "    setnp r11b", "    and al, r11b"]
                elif relation == 3:
                    compare_lines = ["    setbe al", "    setnp r11b", "    and al, r11b"]
                elif relation == 4:
                    compare_lines = ["    seta al"]
                else:
                    compare_lines = ["    setae al"]
            else:
                setup = [
                    *self._read_register(layout, left, "rax"),
                    *self._read_register(layout, right, "r10"),
                    "    cmp rax, r10",
                ]
                condition = {0: "e", 1: "ne", 2: "l", 3: "le", 4: "g", 5: "ge"}[relation]
                compare_lines = [f"    set{condition} al"]
            return instrumentation + [
                *setup,
                *compare_lines,
                "    movzx r11, al",
                "    neg r11",
                *self._write_register(layout, destination, "r11"),
            ]
        if opcode is AssemblyOpcode.TCVT:
            destination, source = registers
            source_type = function.type_of(source)
            destination_type = function.type_of(destination)
            if destination_type is AssemblyType.F64:
                return instrumentation + [
                    *self._read_register(layout, source, "rax"),
                    "    pxor xmm0, xmm0",
                    "    cvtsi2sd xmm0, rax",
                    "    movq rax, xmm0",
                    *self._write_register(layout, destination, "rax"),
                ]
            if source_type is AssemblyType.I64 and destination_type is AssemblyType.TRYTE:
                overflow = self._overflow_failure(AssemblyType.TRYTE, "rax")
                return instrumentation + [
                    *self._read_register(layout, source, "rax"),
                    *self._range_check(AssemblyType.TRYTE, "rax", overflow),
                    *self._write_register(layout, destination, "rax"),
                ]
            return instrumentation + [
                *self._read_register(layout, source, "rax"),
                *self._write_register(layout, destination, "rax"),
            ]
        if opcode in {AssemblyOpcode.TMIN, AssemblyOpcode.TMAX}:
            return instrumentation + self._emit_extreme(function, layout, instruction)
        if opcode is AssemblyOpcode.TCMP:
            source_type = function.type_of(registers[1])
            if source_type is AssemblyType.F64:
                return instrumentation + [
                    *self._read_register(layout, registers[1], "rax"),
                    *self._read_register(layout, registers[2], "r10"),
                    "    movq xmm0, rax",
                    "    movq xmm1, r10",
                    "    xor r11d, r11d",
                    "    ucomisd xmm0, xmm1",
                    "    mov rax, -1",
                    "    cmovb r11, rax",
                    "    mov rax, 1",
                    "    cmova r11, rax",
                    "    mov rax, r11",
                    *self._write_register(layout, registers[0], "rax"),
                ]
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
            return instrumentation + self._loop_boundary_save(layout, instruction) + [
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
            ] + self._loop_boundary_save(layout, instruction) + [
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
            return_type = function.return_type
            if return_type is AssemblyType.F64:
                return instrumentation + [
                    *self._read_register(layout, registers[0], "rax"),
                    "    movq xmm0, rax",
                    *self._restore_callee_saved(layout),
                    "    dec qword ptr [rip + __s3_frame_count]",
                    "    leave",
                    "    ret",
                ]
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
        helper_physicals = self._used_caller_saved_physicals()
        lines = [
            *self._read_register(layout, left, "rax"),
            *self._read_register(layout, right, "r10"),
            *self._save_caller_saved(layout, helper_physicals),
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
        lines.extend(self._restore_caller_saved(layout, helper_physicals))
        lines.extend(self._write_register(layout, destination, "rax"))
        return lines

    def _emit_call(
        self,
        function: AssemblyFunction,
        layout: FrameLayout,
        instruction: AssemblyInstruction,
    ) -> list[str]:
        assert instruction.callee is not None
        if instruction.callee in DYNAMIC_BUILTIN_SIGNATURES:
            return self._emit_dynamic_builtin_call(layout, instruction)
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

    def _emit_dynamic_builtin_call(
        self,
        layout: FrameLayout,
        instruction: AssemblyInstruction,
    ) -> list[str]:
        """Lower an internal dynamic-buffer call using the logical descriptor ABI."""

        if len(instruction.result_registers) != 1:
            raise NativeBackendError(
                "dynamic builtin calls must return exactly one logical cell"
            )
        arguments = instruction.argument_registers
        stack_arguments = arguments[len(_ARGUMENT_REGISTERS):]
        padding = 1 if len(stack_arguments) % 2 else 0
        survivor_physicals = self._call_survivor_physicals(instruction)
        lines: list[str] = []
        if self.register_allocation:
            for register in arguments:
                lines.extend(self._snapshot_register(layout, register))
            lines.extend(self._save_caller_saved(layout, survivor_physicals))
        if padding:
            lines.append("    sub rsp, 8")
        for register in reversed(stack_arguments):
            lines.extend(
                self._load_snapshot(layout, register, "rax")
                if self.register_allocation
                else self._read_register(layout, register, "rax")
            )
            lines.append("    push rax")
        for register, target in zip(
            arguments[: len(_ARGUMENT_REGISTERS)],
            _ARGUMENT_REGISTERS,
            strict=False,
        ):
            lines.extend(
                self._load_snapshot(layout, register, target)
                if self.register_allocation
                else self._read_register(layout, register, target)
            )
        assert instruction.callee is not None
        lines.append(f"    call __s3_builtin_{instruction.callee}")
        cleanup = (len(stack_arguments) + padding) * 8
        if cleanup:
            lines.append(f"    add rsp, {cleanup}")
        if self.register_allocation:
            lines.extend(self._restore_caller_saved(layout, survivor_physicals))
        lines.extend(self._write_register(layout, instruction.result_registers[0], "rax"))
        return lines

    def _emit_scalar_call(
        self,
        layout: FrameLayout,
        instruction: AssemblyInstruction,
        arguments: tuple[int, ...],
        destination: int,
    ) -> list[str]:
        assert instruction.callee is not None
        callee = self.functions[instruction.callee]
        if callee.return_type is AssemblyType.F64 or any(
            parameter.type is AssemblyType.F64 for parameter in callee.parameters
        ):
            return self._emit_numeric_scalar_call(
                layout, instruction, arguments, destination, callee
            )
        stack_arguments = arguments[len(_ARGUMENT_REGISTERS) :]
        padding = 1 if len(stack_arguments) % 2 else 0
        survivor_physicals = self._call_survivor_physicals(instruction)
        lines: list[str] = []
        if self._physical_residence_active:
            for register in arguments:
                lines.extend(self._snapshot_register(layout, register))
            lines.extend(self._save_caller_saved(layout, survivor_physicals))
        if padding:
            lines.append("    sub rsp, 8")
        for register in reversed(stack_arguments):
            lines.extend(
                self._load_snapshot(layout, register, "rax")
                if self._physical_residence_active
                else self._read_register(layout, register, "rax")
            )
            lines.append("    push rax")
        for register, target in zip(
            arguments[: len(_ARGUMENT_REGISTERS)],
            _ARGUMENT_REGISTERS,
            strict=False,
        ):
            lines.extend(
                self._load_snapshot(layout, register, target)
                if self._physical_residence_active
                else self._read_register(layout, register, target)
            )
        assert instruction.callee is not None
        lines.append(f"    call {function_symbol(callee)}")
        cleanup = (len(stack_arguments) + padding) * 8
        if cleanup:
            lines.append(f"    add rsp, {cleanup}")
        if self._physical_residence_active:
            lines.extend(self._restore_caller_saved(layout, survivor_physicals))
        lines.extend(self._write_register(layout, destination, "rax"))
        return lines

    def _emit_numeric_scalar_call(
        self,
        layout: FrameLayout,
        instruction: AssemblyInstruction,
        arguments: tuple[int, ...],
        destination: int,
        callee: AssemblyFunction,
    ) -> list[str]:
        integer_index = 0
        float_index = 0
        register_arguments: list[tuple[int, str, bool]] = []
        stack_arguments: list[int] = []
        for argument, parameter in zip(arguments, callee.parameters, strict=True):
            if parameter.type is AssemblyType.F64 and float_index < len(SYSV_FLOAT_ARGUMENT_REGISTERS):
                register_arguments.append((argument, SYSV_FLOAT_ARGUMENT_REGISTERS[float_index], True))
                float_index += 1
            elif parameter.type is not AssemblyType.F64 and integer_index < len(_ARGUMENT_REGISTERS):
                register_arguments.append((argument, _ARGUMENT_REGISTERS[integer_index], False))
                integer_index += 1
            else:
                stack_arguments.append(argument)
        padding = 1 if len(stack_arguments) % 2 else 0
        survivor_physicals = self._call_survivor_physicals(instruction)
        lines: list[str] = []
        if self._physical_residence_active:
            for register in arguments:
                lines.extend(self._snapshot_register(layout, register))
            lines.extend(self._save_caller_saved(layout, survivor_physicals))
        if padding:
            lines.append("    sub rsp, 8")
        for register in reversed(stack_arguments):
            lines.extend(
                self._load_snapshot(layout, register, "rax")
                if self._physical_residence_active
                else self._read_register(layout, register, "rax")
            )
            lines.append("    push rax")
        for register, target, is_float in register_arguments:
            if is_float:
                lines.extend(
                    self._load_snapshot(layout, register, "rax")
                    if self._physical_residence_active
                    else self._read_register(layout, register, "rax")
                )
                lines.append(f"    movq {target}, rax")
            else:
                lines.extend(
                    self._load_snapshot(layout, register, target)
                    if self._physical_residence_active
                    else self._read_register(layout, register, target)
                )
        lines.append(f"    call {function_symbol(callee)}")
        cleanup = (len(stack_arguments) + padding) * 8
        if cleanup:
            lines.append(f"    add rsp, {cleanup}")
        if callee.return_type is AssemblyType.F64:
            lines.append("    movq rax, xmm0")
        if self._physical_residence_active:
            lines.extend(self._restore_caller_saved(layout, survivor_physicals))
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
        survivor_physicals = self._call_survivor_physicals(instruction)
        lines: list[str] = []
        if self._physical_residence_active:
            for register in arguments:
                lines.extend(self._snapshot_register(layout, register))
            lines.extend(self._save_caller_saved(layout, survivor_physicals))
        if padding:
            lines.append("    sub rsp, 8")
        lines.append(f"    sub rsp, {sret_size}")
        lines.append("    mov rdi, rsp")
        for register in reversed(stack_arguments):
            lines.extend(
                self._load_snapshot(layout, register, "rax")
                if self._physical_residence_active
                else self._read_register(layout, register, "rax")
            )
            lines.append("    push rax")
        for register, target in zip(
            arguments[:stack_argument_capacity],
            _ARGUMENT_REGISTERS[1:],
            strict=False,
        ):
            lines.extend(
                self._load_snapshot(layout, register, target)
                if self._physical_residence_active
                else self._read_register(layout, register, target)
            )
        assert instruction.callee is not None
        lines.append(f"    call {function_symbol(callee)}")
        if self._physical_residence_active:
            lines.extend(self._restore_caller_saved(layout, survivor_physicals))
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
            f"    cmp {index}, {memory.length}",
            f"    jae {failure}",
        ]

    def _emit_load(
        self,
        layout: FrameLayout,
        instruction: AssemblyInstruction,
    ) -> list[str]:
        destination, index_register = instruction.registers
        assert instruction.memory is not None
        memory = layout.memory(instruction.memory)
        index_target = self._memory_index_target(index_register, "r10")
        uninitialized = self._instruction_failure(
            "uninitialized memory",
            detail_prefix="index ",
            detail_suffix=f" is uninitialized in m{memory.index}\n",
            value_register=index_target,
        )
        promoted_source = self._scalar_promoted_loads.get(id(instruction))
        if promoted_source is not None and memory.index in self._scalar_memory_sources:
            return [
                *self._read_register(layout, index_register, index_target),
                *self._memory_bounds(memory, index_target),
                (
                    f"    cmp byte ptr "
                    f"{_address(memory.initialized, index=index_target)}, 0"
                ),
                f"    je {uninitialized}",
                *self._read_register(layout, promoted_source, "rax"),
                *self._write_register(layout, destination, "rax"),
            ]
        if memory.element_size == 8:
            load = "mov rax, qword ptr"
        elif memory.element_size == 1:
            load = "movsx rax, byte ptr"
        else:
            load = "movsx rax, word ptr"
        return [
            *self._read_register(layout, index_register, index_target),
            *self._memory_bounds(memory, index_target),
            (
                f"    cmp byte ptr "
                f"{_address(memory.initialized, index=index_target)}, 0"
            ),
            f"    je {uninitialized}",
            (
                f"    {load} "
                f"{_address(memory.data, index=index_target, scale=memory.element_size)}"
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
        index_target = self._memory_index_target(index_register, "rax")
        lines = [
            *self._read_register(layout, index_register, index_target),
            *self._read_register(layout, source_register, "r10"),
            *self._memory_bounds(memory, index_target),
        ]
        if memory.element_type in {AssemblyType.TRIT, AssemblyType.TRYTE}:
            overflow = self._overflow_failure(memory.element_type, "r10")
            lines.extend(self._range_check(memory.element_type, "r10", overflow))
        init_address = _address(memory.initialized, index=index_target)
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
            index=index_target,
            scale=memory.element_size,
        )
        if memory.element_size == 8:
            source = "r10"
            size = "qword"
        elif memory.element_size == 1:
            source = "r10b"
            size = "byte"
        else:
            source = "r10w"
            size = "word"
        if id(instruction) in self._scalar_promoted_stores:
            self._scalar_memory_sources[memory.index] = source_register
            lines.append(f"    mov byte ptr {init_address}, 1")
        else:
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
