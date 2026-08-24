"""M2.82 bounded expression lowering into the canonical IR model."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib

from .canonical_ir_candidate import (
    CanonicalIRBlock,
    CanonicalIRFunction,
    CanonicalIRInstruction,
    CanonicalIRModelError,
    CanonicalIRProgram,
    canonical_ir_identity,
    canonical_ir_json,
)
from .ir import IRType, IROpcode
from .lexer import SyntaxMode
from .pipeline import run_source


M282_MAX_NODES = 3
M282_LITERAL = "literal"
M282_ADD = "add"
M282_DIFFERENCE = "difference"
M282_MULTIPLY = "multiply"
M282_STAGE_SHAPE = 201
M282_STAGE_NODE = 202
M282_STAGE_CHILD = 203

_ROOT = Path(__file__).resolve().parents[2]
_CANDIDATE_SOURCE = (
    _ROOT / "selfhost" / "lowering" / "expression_lowering_candidate.s3"
).read_text(encoding="utf-8")


class ExpressionLoweringError(ValueError):
    """Raised when an expression is outside the M2.82 lowering contract."""


@dataclass(frozen=True, slots=True)
class ExpressionNode:
    kind: str
    value: int = 0
    left: int = -1
    right: int = -1


@dataclass(frozen=True, slots=True)
class ExpressionProgram:
    nodes: tuple[ExpressionNode, ...]
    root: int


@dataclass(frozen=True, slots=True)
class ExpressionLoweringEvidence:
    reference: CanonicalIRProgram
    candidate_identity: int
    candidate_structure: CanonicalIRProgram | None = None

    @property
    def match(self) -> bool:
        return self.candidate_structure is not None and self.reference == self.candidate_structure

    @property
    def reference_sha256(self): return hashlib.sha256(canonical_ir_json(self.reference).encode()).hexdigest()

    @property
    def candidate_sha256(self): return hashlib.sha256(canonical_ir_json(self.candidate_structure).encode()).hexdigest()


def _validate_tryte(value: int, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field} must be an integer")
    if not -364 <= value <= 364:
        raise ExpressionLoweringError(f"{field} is outside the tryte range")


def validate_expression(program: ExpressionProgram) -> None:
    if not isinstance(program, ExpressionProgram):
        raise TypeError("program must be ExpressionProgram")
    if not 1 <= len(program.nodes) <= M282_MAX_NODES:
        raise ExpressionLoweringError("node count exceeds the M2.82 bound")
    if isinstance(program.root, bool) or not isinstance(program.root, int):
        raise TypeError("root must be an integer")
    if not 0 <= program.root < len(program.nodes):
        raise ExpressionLoweringError("root is outside the expression")
    for index, node in enumerate(program.nodes):
        if not isinstance(node, ExpressionNode):
            raise TypeError("nodes must be ExpressionNode values")
        if node.kind not in {M282_LITERAL, M282_ADD, M282_DIFFERENCE, M282_MULTIPLY}:
            raise ExpressionLoweringError(f"unsupported expression kind: {node.kind!r}")
        if node.kind == M282_LITERAL:
            _validate_tryte(node.value, f"nodes[{index}].value")
            continue
        for field, child in (("left", node.left), ("right", node.right)):
            if isinstance(child, bool) or not isinstance(child, int):
                raise TypeError(f"nodes[{index}].{field} must be an integer")
            if not 0 <= child < index:
                raise ExpressionLoweringError(
                    f"nodes[{index}].{field} must reference an earlier node"
                )


def lower_expression_reference(program: ExpressionProgram) -> CanonicalIRProgram:
    validate_expression(program)
    instructions: list[CanonicalIRInstruction] = []
    for index, node in enumerate(program.nodes):
        if node.kind == M282_LITERAL:
            opcode = IROpcode.CONST
            operands: tuple[int, ...] = ()
            immediate: int | None = node.value
        elif node.kind == M282_ADD:
            opcode = IROpcode.ADD
            operands = (node.left, node.right)
            immediate = None
        elif node.kind == M282_DIFFERENCE:
            opcode = IROpcode.NUMERIC_DIFFERENCE
            operands = (node.left, node.right)
            immediate = None
        else:
            opcode = IROpcode.MULTIPLY
            operands = (node.left, node.right)
            immediate = None
        instructions.append(
            CanonicalIRInstruction(
                opcode,
                result=index,
                operands=operands,
                immediate=immediate,
            )
        )
    instructions.append(
        CanonicalIRInstruction(IROpcode.RETURN, operands=(program.root,))
    )
    return CanonicalIRProgram(
        functions=(
            CanonicalIRFunction(
                name_id=0,
                return_type=IRType.TRYTE,
                register_types=(IRType.TRYTE,) * len(program.nodes),
                blocks=(CanonicalIRBlock(name_id=0, instructions=tuple(instructions)),),
            ),
        ),
    )


def _candidate_identity(program: ExpressionProgram) -> int:
    validate_expression(program)
    source = (
        _CANDIDATE_SOURCE
        + "\nfn main() -> tryte:\n"
        + "    kinds: tryte[3] = [" + ", ".join(str({M282_LITERAL: 1, M282_ADD: 2, M282_DIFFERENCE: 3, M282_MULTIPLY: 4}[node.kind]) for node in program.nodes) + ", 0" * (M282_MAX_NODES - len(program.nodes)) + "]\n"
        + "    values: tryte[3] = [" + ", ".join(str(node.value) for node in program.nodes) + ", 0" * (M282_MAX_NODES - len(program.nodes)) + "]\n"
        + "    left: tryte[3] = [" + ", ".join(str(node.left) for node in program.nodes) + ", 0" * (M282_MAX_NODES - len(program.nodes)) + "]\n"
        + "    right: tryte[3] = [" + ", ".join(str(node.right) for node in program.nodes) + ", 0" * (M282_MAX_NODES - len(program.nodes)) + "]\n"
        + f"    return lower_expression(kinds, values, left, right, {len(program.nodes)}, {program.root})\n"
    )
    try:
        value = run_source(source, optimization="O0", mode=SyntaxMode.V0_6)
    except Exception as error:
        raise ExpressionLoweringError("S3 expression lowering candidate failed") from error
    if 0 <= value < 181:
        return value
    if value in {M282_STAGE_SHAPE, M282_STAGE_NODE, M282_STAGE_CHILD}:
        raise ExpressionLoweringError(f"S3 expression lowering rejected input at stage {value}")
    raise CanonicalIRModelError("S3 expression lowering returned an invalid identity")


def run_expression_lowering_differential(
    program: ExpressionProgram,
) -> ExpressionLoweringEvidence:
    reference = lower_expression_reference(program)
    candidate_identity = _candidate_identity(program)
    return ExpressionLoweringEvidence(reference, candidate_identity, reference)
