"""Generate typed, labelled S3 Assembly from verified block-based S3 IR."""

from __future__ import annotations

from .diagnostics import (
    DiagnosticCategory,
    DiagnosticCode,
    DiagnosticPhase,
)
from .assembly import (
    AssemblyBlock,
    AssemblyFunction,
    AssemblyInstruction,
    AssemblyMemoryObject,
    AssemblyOpcode,
    AssemblyParameter,
    AssemblyProgram,
    AssemblyStaticString,
    AssemblyType,
)
from .ir import IRInstruction, IROpcode, IRProgram, IRType
from .initialization import analyze_initialization
from .verifier import verify_ir


class CodegenError(Exception):
    """Raised when a verified IR construct has no assembly encoding."""

    diagnostic_category = DiagnosticCategory.INTERNAL
    diagnostic_code = DiagnosticCode.CODEGEN_UNSUPPORTED_IR
    diagnostic_phase = DiagnosticPhase.ASSEMBLY


TYPE_MAP = {
    IRType.TRIT: AssemblyType.TRIT,
    IRType.TRYTE: AssemblyType.TRYTE,
    IRType.STRING: AssemblyType.STRING,
}

OPCODE_MAP = {
    IROpcode.CONST: AssemblyOpcode.TCONST,
    IROpcode.CONST_STR: AssemblyOpcode.TCONST_STR,
    IROpcode.MOVE: AssemblyOpcode.TMOV,
    IROpcode.INVERT: AssemblyOpcode.TINV,
    IROpcode.ADD: AssemblyOpcode.TADD,
    IROpcode.MINIMUM: AssemblyOpcode.TMIN,
    IROpcode.MAXIMUM: AssemblyOpcode.TMAX,
    IROpcode.COMPARE: AssemblyOpcode.TCMP,
    IROpcode.CALL: AssemblyOpcode.TCALL,
    IROpcode.LOAD: AssemblyOpcode.TLOAD,
    IROpcode.STORE: AssemblyOpcode.TSTORE,
    IROpcode.RETURN: AssemblyOpcode.TRET,
    IROpcode.JUMP: AssemblyOpcode.TJMP,
    IROpcode.BRANCH3: AssemblyOpcode.TBR3,
}


def _generate_instruction(instruction: IRInstruction) -> AssemblyInstruction:
    try:
        opcode = OPCODE_MAP[instruction.opcode]
    except KeyError as error:
        raise CodegenError(
            f"IR opcode '{instruction.opcode}' has no assembly encoding"
        ) from error
    if opcode is AssemblyOpcode.TCONST:
        assert instruction.result is not None
        return AssemblyInstruction(
            opcode,
            (instruction.result,),
            immediate=instruction.immediate,
            source=instruction.location,
        )
    if opcode is AssemblyOpcode.TCONST_STR:
        assert instruction.result is not None
        return AssemblyInstruction(
            opcode,
            (instruction.result,),
            static_string=instruction.static_string,
            source=instruction.location,
        )
    if opcode is AssemblyOpcode.TCALL:
        return AssemblyInstruction(
            opcode,
            (*instruction.results, *instruction.operands),
            callee=instruction.callee,
            source=instruction.location,
            result_width=len(instruction.results),
        )
    if opcode in {AssemblyOpcode.TJMP, AssemblyOpcode.TBR3}:
        return AssemblyInstruction(
            opcode,
            instruction.operands,
            labels=instruction.targets,
            source=instruction.location,
        )
    if opcode is AssemblyOpcode.TLOAD:
        assert instruction.result is not None
        return AssemblyInstruction(
            opcode,
            (instruction.result, instruction.operands[0]),
            memory=instruction.memory,
            source=instruction.location,
        )
    if opcode is AssemblyOpcode.TSTORE:
        return AssemblyInstruction(
            opcode,
            instruction.operands,
            memory=instruction.memory,
            source=instruction.location,
        )
    registers = (
        instruction.operands
        if not instruction.results
        else (*instruction.results, *instruction.operands)
    )
    return AssemblyInstruction(
        opcode,
        registers,
        source=instruction.location,
    )


def generate_assembly(ir_program: IRProgram) -> AssemblyProgram:
    verify_ir(ir_program)
    analyze_initialization(ir_program)
    functions: list[AssemblyFunction] = []
    for function in ir_program.functions:
        parameter_registers = {
            parameter.register for parameter in function.parameters
        }
        functions.append(
            AssemblyFunction(
                function.name,
                TYPE_MAP[function.return_type],
                tuple(
                    AssemblyParameter(
                        parameter.register,
                        TYPE_MAP[parameter.type],
                    )
                    for parameter in function.parameters
                ),
                tuple(
                    (register.index, TYPE_MAP[register.type])
                    for register in function.registers
                    if register.index not in parameter_registers
                ),
                tuple(
                    AssemblyBlock(
                        block.name,
                        tuple(
                            _generate_instruction(instruction)
                            for instruction in block.instructions
                        ),
                    )
                    for block in function.blocks
                ),
                tuple(
                    AssemblyMemoryObject(
                        memory.index,
                        TYPE_MAP[memory.element_type],
                        memory.length,
                        memory.mutable,
                    )
                    for memory in function.memory_objects
                ),
                tuple(TYPE_MAP[type_name] for type_name in function.result_types),
            )
        )
    return AssemblyProgram(
        tuple(functions),
        static_strings=tuple(
            AssemblyStaticString(entry.id, entry.value)
            for entry in ir_program.static_strings
        ),
    )


def generate_assembly_text(ir_program: IRProgram) -> str:
    return generate_assembly(ir_program).render()
