"""Deterministic S3 Assembly -> AArch64 program lowering for M1.88/M1.89.

The lowerer covers the complete public S3 Assembly opcode enum.  Primitive
integer/control-flow operations are emitted directly where the contract is
small; operations whose runtime representation is shared with existing native
backends are lowered to explicit target runtime helper calls.  Native linker
and execution certification remain separate platform evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .assembly import AssemblyFunction, AssemblyInstruction, AssemblyOpcode, AssemblyProgram
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
        for parameter_index, parameter in enumerate(function.parameters):
            if parameter_index >= 8:
                raise AArch64ProgramError("AAPCS64 V1 supports at most eight register parameters")
            lines.extend(self._emit(f"str x{parameter_index}, [x29, #-{_slot_offset(parameter.register)}]"))
        for block in function.blocks:
            lines.append(f"{self._local_label(function.name, block.label)}:")
            for instruction in block.instructions:
                lines.extend(self._lower_instruction(function, instruction, frame_bytes))
        return lines

    def _lower_instruction(self, function: AssemblyFunction, instruction: AssemblyInstruction, frame_bytes: int) -> list[str]:
        op = instruction.opcode
        regs = instruction.registers
        if op is AssemblyOpcode.TCONST:
            return self._emit(f"mov x9, #{int(instruction.immediate or 0)}", self._store(regs[0], "x9"))
        if op is AssemblyOpcode.TMOV:
            return self._emit(self._load(regs[1], "x9"), self._store(regs[0], "x9"))
        if op is AssemblyOpcode.TCONST_STR:
            return self._helper(instruction, "__s3_const_str", extra_immediate=0)
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
            return self._helper(instruction, f"__s3_{op.value.lower()}")
        if op is AssemblyOpcode.TCALL:
            arguments = instruction.argument_registers
            results = instruction.result_registers
            if len(arguments) > 8 or len(results) > 8:
                raise AArch64ProgramError("AAPCS64 V1 call/result width exceeds eight registers")
            lines: list[str] = []
            for index, register in enumerate(arguments):
                lines.extend(self._emit(self._load(register, f"x{index}")))
            callee = self._symbol(instruction.callee or "")
            lines.extend(self._emit(f"bl {callee}"))
            for index, register in enumerate(results):
                lines.extend(self._emit(self._store(register, f"x{index}")))
            return lines
        if op is AssemblyOpcode.TLOAD:
            return self._helper(instruction, "__s3_tload", extra_immediate=instruction.memory)
        if op is AssemblyOpcode.TSTORE:
            return self._helper(instruction, "__s3_tstore", extra_immediate=instruction.memory, result_count=0)
        if op is AssemblyOpcode.TADDR:
            return self._helper(instruction, "__s3_taddr", extra_immediate=instruction.memory)
        if op is AssemblyOpcode.TREFLOAD:
            return self._helper(instruction, "__s3_trefload")
        if op is AssemblyOpcode.TREFSTORE:
            return self._helper(instruction, "__s3_trefstore", result_count=0)
        if op is AssemblyOpcode.TSLEN:
            return self._helper(instruction, "__s3_tslen")
        if op is AssemblyOpcode.TSLOAD:
            return self._helper(instruction, "__s3_tsload")
        if op is AssemblyOpcode.TSSTORE:
            return self._helper(instruction, "__s3_tsstore", result_count=0)
        if op is AssemblyOpcode.TJMP:
            return self._emit(f"b {self._local_label(function.name, instruction.labels[0])}")
        if op is AssemblyOpcode.TBR3:
            negative, zero, positive = instruction.labels
            return self._emit(
                self._load(regs[0], "x9"),
                "cmp x9, #0",
                f"b.lt {self._local_label(function.name, negative)}",
                f"b.eq {self._local_label(function.name, zero)}",
                f"b {self._local_label(function.name, positive)}",
            )
        if op is AssemblyOpcode.TRET:
            if len(regs) > 8:
                raise AArch64ProgramError("AAPCS64 V1 return width exceeds eight registers")
            lines: list[str] = []
            for index, register in enumerate(regs):
                lines.extend(self._emit(self._load(register, f"x{index}")))
            if frame_bytes:
                lines.extend(self._emit(f"add sp, sp, #{frame_bytes}"))
            lines.extend(self._emit("ldp x29, x30, [sp], #16", "ret"))
            return lines
        raise AArch64ProgramError(f"unhandled S3 Assembly opcode: {op.value}")

    def _helper(
        self,
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
        if len(inputs) > 7:
            raise AArch64ProgramError("runtime helper input width exceeds bounded ABI")
        lines: list[str] = []
        for index, register in enumerate(inputs):
            lines.extend(self._emit(self._load(register, f"x{index}")))
        next_arg = len(inputs)
        if instruction.immediate is not None and next_arg < 8:
            lines.extend(self._emit(f"mov x{next_arg}, #{int(instruction.immediate)}"))
            next_arg += 1
        if extra_immediate is not None and next_arg < 8:
            lines.extend(self._emit(f"mov x{next_arg}, #{int(extra_immediate)}"))
        lines.extend(self._emit(f"bl {self._symbol(symbol)}"))
        count = 1 if result_count is None else result_count
        if count and instruction.registers:
            lines.extend(self._emit(self._store(instruction.registers[0], "x0")))
        return lines

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
