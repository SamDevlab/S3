"""Deterministic S3 Assembly -> AArch64 program lowering for M1.88/M1.89.

The lowerer covers the complete public S3 Assembly opcode enum. Primitive
integer/control-flow operations are emitted directly where the contract is
small; operations whose runtime representation is shared with existing native
backends are lowered to explicit target runtime helper calls. Native linker
and execution certification remain separate platform evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
import struct
from typing import Iterable

from .assembly import AssemblyFunction, AssemblyInstruction, AssemblyOpcode, AssemblyProgram, AssemblyType
from .backends.aarch64 import AARCH64_ELF_MACHINE, AArch64Backend
from .backends.macos_arm64 import MachOBackend


MAX_AARCH64_PROGRAM_INSTRUCTIONS = 100_000


class AArch64ProgramError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class AArch64ProgramArtifact:
    target: str
    text: str
    container_header: bytes
    instruction_count: int
    runtime_symbols: tuple[str, ...]


class AArch64ProgramLowerer:
    """Lower verified S3 Assembly programs to bounded AArch64 text."""

    def __init__(self, target: str, *, max_instructions: int = MAX_AARCH64_PROGRAM_INSTRUCTIONS) -> None:
        if target not in {"linux-aarch64", "macos-arm64"}:
            raise AArch64ProgramError("unsupported AArch64 program target")
        if isinstance(max_instructions, bool) or not isinstance(max_instructions, int) or not 1 <= max_instructions <= MAX_AARCH64_PROGRAM_INSTRUCTIONS:
            raise AArch64ProgramError("invalid AArch64 instruction limit")
        self.target = target
        self.max_instructions = max_instructions
        self._runtime_symbols: set[str] = set()
        self._instruction_count = 0

    def lower(self, program: AssemblyProgram) -> AArch64ProgramArtifact:
        if not isinstance(program, AssemblyProgram) or not program.functions:
            raise AArch64ProgramError("AArch64 lowering requires a non-empty AssemblyProgram")
        self._runtime_symbols = set()
        self._instruction_count = 0
        lines = [".text"]
        for function in program.functions:
            lines.extend(self._lower_function(function))
        if self._instruction_count > self.max_instructions:
            raise AArch64ProgramError("AArch64 program exceeds instruction limit")
        header = (
            AArch64Backend(max_instructions=self.max_instructions).elf_header().bytes
            if self.target == "linux-aarch64"
            else MachOBackend().header().bytes
        )
        artifact = AArch64ProgramArtifact(
            self.target,
            "\n".join(lines) + "\n",
            header,
            self._instruction_count,
            tuple(sorted(self._runtime_symbols)),
        )
        validate_aarch64_program_artifact(artifact)
        return artifact

    def _lower_function(self, function: AssemblyFunction) -> list[str]:
        max_register = max(function.all_register_types, default=-1)
        frame_bytes = _align16(max(16, (max_register + 1) * 8))
        symbol = self._symbol(function.name)
        lines = ["", f".globl {symbol}", f"{symbol}:"]
        lines.extend(self._emit("stp x29, x30, [sp, #-16]!", "mov x29, sp"))
        if frame_bytes:
            lines.extend(self._emit(f"sub sp, sp, #{frame_bytes}"))

        integer_index = 0
        floating_index = 0
        for parameter in function.parameters:
            if parameter.type is AssemblyType.F64:
                if floating_index >= 8:
                    raise AArch64ProgramError("AAPCS64 V1 supports at most eight floating register parameters")
                machine = f"d{floating_index}"
                floating_index += 1
            else:
                if integer_index >= 8:
                    raise AArch64ProgramError("AAPCS64 V1 supports at most eight integer register parameters")
                machine = f"x{integer_index}"
                integer_index += 1
            lines.extend(self._emit(self._store(parameter.register, machine)))

        for block in function.blocks:
            lines.append(f"{self._local_label(function.name, block.label)}:")
            for instruction in block.instructions:
                lines.extend(self._lower_instruction(function, instruction, frame_bytes))
        return lines

    def _lower_instruction(self, function: AssemblyFunction, instruction: AssemblyInstruction, frame_bytes: int) -> list[str]:
        op = instruction.opcode
        regs = instruction.registers
        if op is AssemblyOpcode.TCONST:
            if function.type_of(regs[0]) is AssemblyType.F64:
                value = float(instruction.immediate or 0.0)
                bits = struct.unpack("<Q", struct.pack("<d", value))[0]
                return self._emit(*self._mov_u64("x9", bits), "fmov d9, x9", self._store(regs[0], "d9"))
            return self._emit(*self._mov_u64("x9", int(instruction.immediate or 0)), self._store(regs[0], "x9"))
        if op is AssemblyOpcode.TMOV:
            machine = "d9" if function.type_of(regs[0]) is AssemblyType.F64 else "x9"
            return self._emit(self._load(regs[1], machine), self._store(regs[0], machine))
        if op is AssemblyOpcode.TCONST_STR:
            return self._helper(function, instruction, "__s3_const_str", extra_immediate=0)
        if op in {
            AssemblyOpcode.TINV,
            AssemblyOpcode.TADD,
            AssemblyOpcode.TNDIFF,
            AssemblyOpcode.TMUL,
            AssemblyOpcode.TDIV,
            AssemblyOpcode.TREL,
            AssemblyOpcode.TCVT,
            AssemblyOpcode.TMIN,
            AssemblyOpcode.TMAX,
            AssemblyOpcode.TCMP,
        }:
            return self._helper(function, instruction, f"__s3_{op.value.lower()}")
        if op is AssemblyOpcode.TCALL:
            arguments = instruction.argument_registers
            results = instruction.result_registers
            lines: list[str] = []
            for register, machine in self._abi_registers(function, arguments):
                lines.extend(self._emit(self._load(register, machine)))
            callee = self._symbol(instruction.callee or "")
            lines.extend(self._emit(f"bl {callee}"))
            for register, machine in self._abi_registers(function, results):
                lines.extend(self._emit(self._store(register, machine)))
            return lines
        if op is AssemblyOpcode.TLOAD:
            return self._helper(function, instruction, "__s3_tload", extra_immediate=instruction.memory)
        if op is AssemblyOpcode.TSTORE:
            return self._helper(function, instruction, "__s3_tstore", extra_immediate=instruction.memory, result_count=0)
        if op is AssemblyOpcode.TADDR:
            return self._helper(function, instruction, "__s3_taddr", extra_immediate=instruction.memory)
        if op is AssemblyOpcode.TREFLOAD:
            return self._helper(function, instruction, "__s3_trefload")
        if op is AssemblyOpcode.TREFSTORE:
            return self._helper(function, instruction, "__s3_trefstore", result_count=0)
        if op is AssemblyOpcode.TSLEN:
            return self._helper(function, instruction, "__s3_tslen")
        if op is AssemblyOpcode.TSLOAD:
            return self._helper(function, instruction, "__s3_tsload")
        if op is AssemblyOpcode.TSSTORE:
            return self._helper(function, instruction, "__s3_tsstore", result_count=0)
        if op is AssemblyOpcode.TJMP:
            return self._emit(f"b {self._local_label(function.name, instruction.labels[0])}")
        if op is AssemblyOpcode.TBR3:
            negative, zero, positive = instruction.labels
            if function.type_of(regs[0]) is AssemblyType.F64:
                return self._emit(
                    self._load(regs[0], "d9"),
                    "fcmp d9, #0.0",
                    f"b.mi {self._local_label(function.name, negative)}",
                    f"b.eq {self._local_label(function.name, zero)}",
                    f"b {self._local_label(function.name, positive)}",
                )
            return self._emit(
                self._load(regs[0], "x9"),
                "cmp x9, #0",
                f"b.lt {self._local_label(function.name, negative)}",
                f"b.eq {self._local_label(function.name, zero)}",
                f"b {self._local_label(function.name, positive)}",
            )
        if op is AssemblyOpcode.TRET:
            lines: list[str] = []
            for register, machine in self._abi_registers(function, regs):
                lines.extend(self._emit(self._load(register, machine)))
            if frame_bytes:
                lines.extend(self._emit(f"add sp, sp, #{frame_bytes}"))
            lines.extend(self._emit("ldp x29, x30, [sp], #16", "ret"))
            return lines
        raise AArch64ProgramError(f"unhandled S3 Assembly opcode: {op.value}")

    def _helper(
        self,
        function: AssemblyFunction,
        instruction: AssemblyInstruction,
        symbol: str,
        *,
        extra_immediate: int | None = None,
        result_count: int | None = None,
    ) -> list[str]:
        self._runtime_symbols.add(symbol)
        inputs = instruction.argument_registers if instruction.opcode is AssemblyOpcode.TCALL else instruction.registers[1:]
        if instruction.opcode in {AssemblyOpcode.TSTORE, AssemblyOpcode.TREFSTORE, AssemblyOpcode.TSSTORE}:
            inputs = instruction.registers
        lines: list[str] = []
        abi_inputs = self._abi_registers(function, inputs)
        for register, machine in abi_inputs:
            lines.extend(self._emit(self._load(register, machine)))

        integer_index = sum(machine.startswith("x") for _register, machine in abi_inputs)
        if instruction.immediate is not None:
            if integer_index >= 8:
                raise AArch64ProgramError("runtime helper integer argument width exceeds bounded ABI")
            lines.extend(self._emit(*self._mov_u64(f"x{integer_index}", int(instruction.immediate))))
            integer_index += 1
        if extra_immediate is not None:
            if integer_index >= 8:
                raise AArch64ProgramError("runtime helper integer argument width exceeds bounded ABI")
            lines.extend(self._emit(*self._mov_u64(f"x{integer_index}", int(extra_immediate))))

        lines.extend(self._emit(f"bl {self._symbol(symbol)}"))
        count = 1 if result_count is None else result_count
        if count:
            results = instruction.registers[:count]
            for register, machine in self._abi_registers(function, results):
                lines.extend(self._emit(self._store(register, machine)))
        return lines

    def _abi_registers(self, function: AssemblyFunction, registers: Iterable[int]) -> tuple[tuple[int, str], ...]:
        integer_index = 0
        floating_index = 0
        result: list[tuple[int, str]] = []
        for register in registers:
            type_name = function.type_of(register)
            if type_name is None:
                raise AArch64ProgramError(f"virtual register r{register} has no Assembly type")
            if type_name is AssemblyType.F64:
                if floating_index >= 8:
                    raise AArch64ProgramError("AAPCS64 V1 floating register width exceeds eight registers")
                result.append((register, f"d{floating_index}"))
                floating_index += 1
            else:
                if integer_index >= 8:
                    raise AArch64ProgramError("AAPCS64 V1 integer register width exceeds eight registers")
                result.append((register, f"x{integer_index}"))
                integer_index += 1
        return tuple(result)

    def _mov_u64(self, register: str, value: int) -> tuple[str, ...]:
        encoded = int(value) & 0xFFFFFFFFFFFFFFFF
        chunks = tuple((encoded >> shift) & 0xFFFF for shift in (0, 16, 32, 48))
        instructions = [f"movz {register}, #{chunks[0]}"]
        for index, chunk in enumerate(chunks[1:], start=1):
            if chunk:
                instructions.append(f"movk {register}, #{chunk}, lsl #{index * 16}")
        return tuple(instructions)

    def _emit(self, *instructions: str) -> list[str]:
        self._instruction_count += len(instructions)
        if self._instruction_count > self.max_instructions:
            raise AArch64ProgramError("AArch64 program exceeds instruction limit")
        return [f"    {instruction}" for instruction in instructions]

    def _load(self, register: int, target: str) -> str:
        return f"ldr {target}, [x29, #-{_slot_offset(register)}]"

    def _store(self, register: int, source: str) -> str:
        return f"str {source}, [x29, #-{_slot_offset(register)}]"

    def _symbol(self, name: str) -> str:
        if not name:
            raise AArch64ProgramError("empty function/runtime symbol")
        if self.target == "macos-arm64" and not name.startswith("_"):
            return "_" + name
        return name

    def _local_label(self, function: str, label: str) -> str:
        prefix = "L" if self.target == "macos-arm64" else ".L"
        safe = f"{function}_{label}".replace(".", "_")
        return prefix + safe


def validate_aarch64_program_artifact(artifact: AArch64ProgramArtifact) -> None:
    if artifact.instruction_count <= 0 or artifact.instruction_count > MAX_AARCH64_PROGRAM_INSTRUCTIONS:
        raise AArch64ProgramError("artifact instruction count is invalid")
    if not artifact.text.startswith(".text\n") or "ret" not in artifact.text:
        raise AArch64ProgramError("artifact does not contain bounded AArch64 text")
    if artifact.target == "linux-aarch64":
        if len(artifact.container_header) < 64 or artifact.container_header[:4] != b"\x7fELF":
            raise AArch64ProgramError("Linux AArch64 artifact lacks ELF64 header")
        machine = int.from_bytes(artifact.container_header[18:20], "little")
        if machine != AARCH64_ELF_MACHINE:
            raise AArch64ProgramError("Linux artifact machine is not AArch64")
    elif artifact.target == "macos-arm64":
        if len(artifact.container_header) < 32 or int.from_bytes(artifact.container_header[:4], "little") != 0xFEEDFACF:
            raise AArch64ProgramError("macOS ARM64 artifact lacks Mach-O 64 header")
    else:
        raise AArch64ProgramError("unknown AArch64 target")


def _slot_offset(register: int) -> int:
    if isinstance(register, bool) or not isinstance(register, int) or register < 0:
        raise AArch64ProgramError("virtual register index must be non-negative")
    return 8 * (register + 1)


def _align16(value: int) -> int:
    return (value + 15) & ~15
