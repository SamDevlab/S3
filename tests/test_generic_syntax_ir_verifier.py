from __future__ import annotations

from dataclasses import replace
import platform
from pathlib import Path

import pytest

from bootstrap.s3 import compile_source, run_source
from bootstrap.s3.backends.x86_64 import NativeBackendError, NativeToolchain, generate_native_assembly
from bootstrap.s3.compiler_substrate import InvalidIdError
from bootstrap.s3.generic_ir import IRBuilder, IRProgram, IRRange, IROpcode, IRType
from bootstrap.s3.generic_syntax import (
    DeclarationPayload,
    FloatPayload,
    FunctionPayload,
    IntegerPayload,
    NodeKind,
    OperatorPayload,
    SymbolPayload,
    SyntaxArena,
    SyntaxSpan,
    SyntaxValidationError,
    TextPayload,
    TypePayload,
)
from bootstrap.s3.generic_verifier import verify_ir_program
from bootstrap.s3.diagnostics import DiagnosticCode, SemanticError


SPAN = SyntaxSpan(0, 0, 1)


def _syntax_fixture() -> SyntaxArena:
    arena = SyntaxArena(symbol_count=4, type_count=2)
    integer = arena.append_node(
        NodeKind.INTEGER_LITERAL,
        SPAN,
        payload=IntegerPayload(7),
    )
    identifier = arena.append_node(
        NodeKind.IDENTIFIER,
        SPAN,
        payload=SymbolPayload(1),
    )
    block = arena.append_node(NodeKind.BLOCK, SPAN, children=(integer, identifier))
    root = arena.append_node(NodeKind.PROGRAM, SPAN, children=(block,))
    arena.set_root(root)
    return arena


def _scalar_program(value: int = 7) -> tuple[IRProgram, int, int]:
    builder = IRBuilder()
    function_id = builder.begin_function(1, "main", (IRType.I64,))
    value_id = builder.allocate_value(IRType.I64)
    builder.begin_block(2)
    builder.append_instruction(IROpcode.CONST, result_ids=(value_id,), immediate=value)
    builder.append_instruction(IROpcode.RETURN, operand_ids=(value_id,))
    builder.finish_block()
    builder.finish_function()
    return builder.program, function_id, value_id


def test_syntax_arena_is_flat_deterministic_and_validated() -> None:
    first = _syntax_fixture()
    second = _syntax_fixture()
    first.validate()
    second.validate()
    assert first.structural_digest() == second.structural_digest()
    assert first.child_ids(first.root_id or -1) == (2,)
    assert first.child_ids(2) == (0, 1)


def test_syntax_node_ids_are_direct_and_rollback_does_not_renumber() -> None:
    arena = _syntax_fixture()
    checkpoint = arena.checkpoint()
    temporary = arena.append_node(
        NodeKind.STRING_LITERAL,
        SPAN,
        payload=TextPayload("temporary"),
    )
    arena.rollback(checkpoint)
    replacement = arena.append_node(
        NodeKind.FLOAT_LITERAL,
        SPAN,
        payload=FloatPayload(1.5),
    )
    assert temporary not in arena.nodes
    assert replacement > temporary
    arena.validate()
    assert arena.node(replacement).kind is NodeKind.FLOAT_LITERAL


def test_syntax_payload_authority_covers_expression_and_declaration_families() -> None:
    arena = SyntaxArena(symbol_count=4, type_count=3)
    values = (
        arena.append_node(NodeKind.INTEGER_LITERAL, SPAN, payload=IntegerPayload(1)),
        arena.append_node(NodeKind.STRING_LITERAL, SPAN, payload=TextPayload("x")),
        arena.append_node(NodeKind.IDENTIFIER, SPAN, payload=SymbolPayload(0)),
        arena.append_node(NodeKind.BINARY, SPAN, payload=OperatorPayload(1)),
        arena.append_node(NodeKind.VARIABLE_DECLARATION, SPAN, payload=DeclarationPayload(2, 1)),
        arena.append_node(NodeKind.GENERIC_TYPE, SPAN, payload=TypePayload(2)),
    )
    root = arena.append_node(NodeKind.PROGRAM, SPAN, children=values)
    arena.set_root(root)
    arena.validate()


def test_syntax_function_payload_rejects_dangling_return_type() -> None:
    arena = SyntaxArena(symbol_count=1, type_count=1)
    function = arena.append_node(
        NodeKind.FUNCTION,
        SPAN,
        payload=FunctionPayload(
            symbol_id=0,
            return_type_id=1,
            parameter_first=0,
            parameter_count=0,
            body_id=-1,
        ),
    )
    arena.set_root(function)
    with pytest.raises(SyntaxValidationError, match="invalid function payload"):
        arena.validate()


def test_composite_vector_aggregate_field_boundary_is_explicitly_blocked() -> None:
    source = """\
record Item:
    value: i64
record Arena:
    values: vector<Item>
fn main() -> i64:
    return 0
"""
    with pytest.raises(SemanticError) as error:
        compile_source(source)
    assert error.value.diagnostic_code is DiagnosticCode.SEMANTIC_INVALID_ARGUMENT_TYPE
    assert "composite vectors cannot be stored inside aggregate fields" in str(error.value)


@pytest.mark.parametrize("case", range(8))
def test_syntax_negative_corpus_fails_closed(case: int) -> None:
    arena = _syntax_fixture()
    root = arena.root_id
    assert root is not None
    if case == 0:
        arena.children._items[0] = 999  # intentional malformed fixture
    elif case == 1:
        arena.nodes._items[root] = replace(arena.node(root), child_count=99)
    elif case == 2:
        arena.nodes._items[0] = replace(arena.node(0), payload_kind=arena.node(root).payload_kind, payload_id=-1)
    elif case == 3:
        arena.nodes._items[0] = replace(arena.node(0), span=SyntaxSpan(0, 4, 1))
    elif case == 4:
        arena.root_id = 999
    elif case == 5:
        arena.payloads[arena.node(1).payload_kind]._items[0] = SymbolPayload(999)
    elif case == 6:
        arena.nodes._items[2] = replace(arena.node(2), first_child=99)
    else:
        arena.nodes._items[0] = replace(arena.node(0), kind="not-a-node-kind")
    with pytest.raises(SyntaxValidationError):
        arena.validate()


def test_syntax_checkpoint_restores_payload_and_child_cursors() -> None:
    arena = _syntax_fixture()
    checkpoint = arena.checkpoint()
    temporary = arena.append_node(
        NodeKind.BINARY,
        SPAN,
        payload=OperatorPayload(3),
        children=(0, 1),
    )
    assert temporary in arena.nodes
    arena.rollback(checkpoint)
    arena.validate()
    with pytest.raises(InvalidIdError):
        arena.node(temporary)


@pytest.mark.parametrize("node_count", (32, 128, 512, 2048))
def test_syntax_scaling_probes_are_deterministic(node_count: int) -> None:
    def build() -> SyntaxArena:
        arena = SyntaxArena(symbol_count=1, type_count=1)
        literals = tuple(
            arena.append_node(
                NodeKind.INTEGER_LITERAL,
                SyntaxSpan(0, offset, offset + 1),
                payload=IntegerPayload(offset),
            )
            for offset in range(node_count)
        )
        root = arena.append_node(
            NodeKind.PROGRAM,
            SyntaxSpan(0, 0, node_count),
            children=literals,
        )
        arena.set_root(root)
        arena.validate()
        return arena

    first = build()
    second = build()
    assert len(tuple(first.nodes.items())) == node_count + 1
    assert first.structural_digest() == second.structural_digest()


def _linear_ir(instruction_count: int) -> IRProgram:
    builder = IRBuilder()
    builder.begin_function(1, "linear", (IRType.I64,))
    values = tuple(builder.allocate_value(IRType.I64) for _ in range(instruction_count - 1))
    builder.begin_block(2)
    for value_id, immediate in zip(values, range(instruction_count - 1)):
        builder.append_instruction(
            IROpcode.CONST,
            result_ids=(value_id,),
            immediate=immediate,
        )
    builder.append_instruction(IROpcode.RETURN, operand_ids=(values[-1],))
    builder.finish_block()
    builder.finish_function()
    return builder.program


@pytest.mark.parametrize("instruction_count", (32, 128, 512, 2048))
def test_ir_instruction_scaling_probes_are_deterministic(instruction_count: int) -> None:
    first = _linear_ir(instruction_count)
    second = _linear_ir(instruction_count)
    assert len(tuple(first.instructions.items())) == instruction_count
    assert first.structural_digest() == second.structural_digest()
    assert verify_ir_program(first).success is True


def _block_chain(block_count: int) -> IRProgram:
    builder = IRBuilder()
    builder.begin_function(1, "chain", (IRType.I64,))
    entry = builder.begin_block(10)
    blocks = (entry,) + tuple(builder.reserve_block(10 + index) for index in range(1, block_count))
    for index, block_id in enumerate(blocks[:-1]):
        if index:
            builder.open_block(block_id)
        builder.append_instruction(IROpcode.JUMP, target_block_ids=(blocks[index + 1],))
        builder.finish_block()
    builder.open_block(blocks[-1])
    value_id = builder.allocate_value(IRType.I64)
    builder.append_instruction(IROpcode.CONST, result_ids=(value_id,), immediate=0)
    builder.append_instruction(IROpcode.RETURN, operand_ids=(value_id,))
    builder.finish_block()
    builder.finish_function()
    return builder.program


@pytest.mark.parametrize("block_count", (4, 16, 64, 128))
def test_ir_block_scaling_probes_are_deterministic(block_count: int) -> None:
    first = _block_chain(block_count)
    second = _block_chain(block_count)
    assert len(tuple(first.blocks.items())) == block_count
    assert first.structural_digest() == second.structural_digest()
    result = verify_ir_program(first)
    assert result.success is True
    assert len(result.reachable_blocks) == block_count


def test_generic_ir_program_has_one_authoritative_arena_per_entity() -> None:
    program, function_id, value_id = _scalar_program()
    function = program.functions.get(function_id)
    assert program.values.get(value_id).function_id == function_id
    assert function.entry_block_id is not None
    assert program.blocks.get(function.entry_block_id).function_id == function_id
    assert len(tuple(program.instructions.items())) == 2
    result = verify_ir_program(program)
    assert result.success is True
    assert result.reachable_blocks == (0,)
    assert result.dominators == ((0, (0,)),)


def test_generic_ir_verifier_is_immutable_and_repeatable() -> None:
    program, _, _ = _scalar_program(11)
    before = program.structural_digest()
    first = verify_ir_program(program)
    middle = program.structural_digest()
    second = verify_ir_program(program)
    after = program.structural_digest()
    assert first == second
    assert before == middle == after


def test_ir_builder_transaction_rolls_back_all_ranges_and_can_continue() -> None:
    builder = IRBuilder()
    builder.begin_function(1, "main", (IRType.I64,))
    checkpoint = builder.checkpoint()
    builder.begin_block(2)
    temporary = builder.allocate_value(IRType.I64)
    builder.append_instruction(IROpcode.CONST, result_ids=(temporary,), immediate=9)
    builder.append_instruction(IROpcode.RETURN, operand_ids=(temporary,))
    builder.finish_block()
    builder.rollback(checkpoint)
    function = builder.program.functions.get(0)
    assert function.block_range.count == 0
    assert function.value_range.count == 0
    builder.begin_block(3)
    value_id = builder.allocate_value(IRType.I64)
    builder.append_instruction(IROpcode.CONST, result_ids=(value_id,), immediate=13)
    builder.append_instruction(IROpcode.RETURN, operand_ids=(value_id,))
    builder.finish_block()
    builder.finish_function()
    assert value_id > temporary
    assert verify_ir_program(builder.program).success is True


def test_ir_multi_result_call_and_cfg_are_generic() -> None:
    builder = IRBuilder()
    pair_id = builder.begin_function(1, "pair", (IRType.I64, IRType.TRIT))
    first = builder.allocate_value(IRType.I64)
    second = builder.allocate_value(IRType.TRIT)
    builder.begin_block(2)
    builder.append_instruction(IROpcode.CONST, result_ids=(first,), immediate=4)
    builder.append_instruction(IROpcode.CONST, result_ids=(second,), immediate=1)
    builder.append_instruction(IROpcode.RETURN, operand_ids=(first, second))
    builder.finish_block()
    builder.finish_function()

    builder.begin_function(3, "caller", (IRType.I64,))
    result = builder.allocate_value(IRType.I64)
    result_flag = builder.allocate_value(IRType.TRIT)
    builder.begin_block(4)
    builder.append_instruction(
        IROpcode.CALL,
        result_ids=(result, result_flag),
        callee_function_id=pair_id,
    )
    builder.append_instruction(IROpcode.RETURN, operand_ids=(result,))
    builder.finish_block()
    builder.finish_function()
    verification = verify_ir_program(builder.program)
    assert verification.success is True


def test_ir_cfg_and_dominance_use_block_ids_not_labels() -> None:
    builder = IRBuilder()
    builder.begin_function(1, "branching", (IRType.I64,))
    condition = builder.allocate_value(IRType.TRIT)
    result = builder.allocate_value(IRType.I64)
    entry = builder.begin_block(10)
    left = builder.reserve_block(11)
    right = builder.reserve_block(12)
    join = builder.reserve_block(13)
    builder.append_instruction(IROpcode.CONST, result_ids=(condition,), immediate=0)
    builder.append_instruction(IROpcode.BRANCH3, operand_ids=(condition,), target_block_ids=(left, join, right))
    builder.finish_block()
    builder.open_block(left)
    builder.append_instruction(IROpcode.JUMP, target_block_ids=(join,))
    builder.finish_block()
    builder.open_block(right)
    builder.append_instruction(IROpcode.JUMP, target_block_ids=(join,))
    builder.finish_block()
    builder.open_block(join)
    builder.append_instruction(IROpcode.CONST, result_ids=(result,), immediate=1)
    builder.append_instruction(IROpcode.RETURN, operand_ids=(result,))
    builder.finish_block()
    builder.finish_function()
    verification = verify_ir_program(builder.program)
    assert verification.success is True
    assert set(verification.reachable_blocks) == {entry, left, right, join}
    dominators = dict(verification.dominators)
    assert dominators[join] == (entry, join)


@pytest.mark.parametrize("case", range(8))
def test_ir_negative_verification_corpus_fails_closed(case: int) -> None:
    program, _, value_id = _scalar_program()
    block = program.blocks.get(0)
    instruction = program.instructions.get(1)
    if case == 0:
        program.operands.append(999)
        program.instructions._items[1] = replace(instruction, operand_range=IRRange(1, 1))
    elif case == 1:
        program.instructions._items[0] = replace(program.instructions.get(0), opcode="unknown")
    elif case == 2:
        block.terminator_id = 999
    elif case == 3:
        block.instruction_range = IRRange(0, 1)
    elif case == 4:
        program.instructions._items[1] = replace(instruction, opcode=IROpcode.JUMP, target_range=IRRange(0, 0))
    elif case == 5:
        program.values._items[value_id] = replace(program.values.get(value_id), type="bad")
    elif case == 6:
        program.functions._items[0] = replace(program.functions.get(0), entry_block_id=99)
    else:
        program.instructions._items[1] = replace(instruction, operand_range=IRRange(0, 0))
    result = verify_ir_program(program)
    assert result.success is False
    assert result.diagnostic_code


@pytest.mark.parametrize("case", range(256))
def test_deterministic_generic_differential_corpus(case: int) -> None:
    if case < 96:
        program, _, _ = _scalar_program(case - 48)
        result = verify_ir_program(program)
        assert result.success is True
    elif case < 224:
        program, _, _ = _scalar_program(case)
        program.operands.append(10_000 + case)
        instruction = program.instructions.get(1)
        program.instructions._items[1] = replace(instruction, operand_range=IRRange(1, 1))
        result = verify_ir_program(program)
        assert result.success is False
        assert result.diagnostic_code == "unknown_operand"
    else:
        arena = SyntaxArena(symbol_count=2, type_count=1)
        literal = arena.append_node(
            NodeKind.INTEGER_LITERAL,
            SyntaxSpan(0, case, case + 1),
            payload=IntegerPayload(case),
        )
        root = arena.append_node(NodeKind.PROGRAM, SyntaxSpan(0, 0, case + 1), children=(literal,))
        arena.set_root(root)
        arena.validate()
        assert arena.structural_digest() == _syntax_digest_for_case(case)


def _syntax_digest_for_case(case: int) -> str:
    arena = SyntaxArena(symbol_count=2, type_count=1)
    literal = arena.append_node(
        NodeKind.INTEGER_LITERAL,
        SyntaxSpan(0, case, case + 1),
        payload=IntegerPayload(case),
    )
    root = arena.append_node(NodeKind.PROGRAM, SyntaxSpan(0, 0, case + 1), children=(literal,))
    arena.set_root(root)
    return arena.structural_digest()


def test_selfhost_shapes_compile_without_composite_aggregate_fields() -> None:
    repository = Path(__file__).parents[1]
    for relative in (
        "selfhost/substrate/syntax_arena.s3",
        "selfhost/substrate/generic_ir_program.s3",
        "selfhost/substrate/verifier_kernel.s3",
    ):
        source = (repository / relative).read_text(encoding="utf-8")
        compilation = compile_source(source + "\nfn main() -> i64:\n    return 0\n")
        assert compilation.assembly.functions


def test_native_ir_type_registry_and_call_signatures_are_checked() -> None:
    repository = Path(__file__).parents[1]
    verifier = (repository / "selfhost/substrate/verifier_kernel.s3").read_text(encoding="utf-8")
    probe = """
fn type_foundation_probe() -> i64:
    mut program: NativeIR = native_ir_empty()
    mut vector_type: NativeIRAppendResult = native_ir_intern_composite_type(
        program, 2, native_ir_type_i64(), 0, -1
    )
    mut vector_accepted: i64 = vector_type.accepted
    mut vector_id: i64 = vector_type.value_id
    program = vector_type.program
    mut repeated_vector: NativeIRAppendResult = native_ir_intern_composite_type(
        program, 2, native_ir_type_i64(), 0, -1
    )
    mut repeated_accepted: i64 = repeated_vector.accepted
    mut repeated_id: i64 = repeated_vector.value_id
    program = repeated_vector.program
    mut reference_type: NativeIRAppendResult = native_ir_intern_composite_type(
        program, 3, vector_id, 1, -1
    )
    mut reference_accepted: i64 = reference_type.accepted
    mut reference_id: i64 = reference_type.value_id
    program = reference_type.program
    mut invalid_type: NativeIRAppendResult = native_ir_intern_composite_type(
        program, 2, 99, 0, -1
    )
    mut invalid_type_accepted: i64 = invalid_type.accepted
    program = invalid_type.program
    mut tryte_type: NativeIRAppendResult = native_ir_intern_tryte_type(program)
    mut tryte_accepted: i64 = tryte_type.accepted
    mut tryte_id: i64 = tryte_type.value_id
    program = tryte_type.program
    mut repeated_tryte: NativeIRAppendResult = native_ir_intern_tryte_type(program)
    mut repeated_tryte_accepted: i64 = repeated_tryte.accepted
    mut repeated_tryte_id: i64 = repeated_tryte.value_id
    program = repeated_tryte.program
    mut type_verification_result: NativeIRVerifiedResult = verify_program(program)
    mut type_verification: NativeVerification = type_verification_result.verification
    program = type_verification_result.program
    mut function: NativeIRAppendResult = native_ir_append_function(program, 7, 1)
    program = function.program
    mut parameter: NativeIRAppendResult = native_ir_append_typed_parameter(
        program, 7, 0, reference_id
    )
    mut parameter_accepted: i64 = parameter.accepted
    mut parameter_id: i64 = parameter.value_id
    program = parameter.program
    mut parameter_type: i64 = native_ir_value_type_id(
        &program.value_ids, &program.value_type_ids, parameter_id
    )
    mut score: i64 = native_ir_trit_to_i64(vector_accepted == 1)
    score = score + native_ir_trit_to_i64(repeated_accepted == 1) * 2
    score = score + native_ir_trit_to_i64(repeated_id == vector_id) * 4
    score = score + native_ir_trit_to_i64(reference_accepted == 1) * 8
    score = score + native_ir_trit_to_i64(parameter_accepted == 1) * 16
    score = score + native_ir_trit_to_i64(parameter_type == reference_id) * 32
    score = score + native_ir_trit_to_i64(i64_vector_len(&program.type_kinds) == 5) * 64
    score = score + native_ir_trit_to_i64(invalid_type_accepted == 0) * 128
    score = score + native_ir_trit_to_i64(tryte_accepted == 1) * 256
    score = score + native_ir_trit_to_i64(repeated_tryte_accepted == 1) * 512
    score = score + native_ir_trit_to_i64(repeated_tryte_id == tryte_id) * 1024
    score = score + native_ir_trit_to_i64(i64_vector_len(&program.type_kinds) == 5) * 2048
    score = score + native_ir_trit_to_i64(
        i64_vector_get(&program.type_kinds, tryte_id) == 4
    ) * 4096
    score = score + native_ir_trit_to_i64(
        i64_vector_get(&program.type_element_ids, tryte_id) == -1
    ) * 8192
    score = score + native_ir_trit_to_i64(
        i64_vector_get(&program.type_mutability_flags, tryte_id) == 0
    ) * 16384
    score = score + native_ir_trit_to_i64(
        i64_vector_get(&program.type_lengths, tryte_id) == -1
    ) * 32768
    score = score + native_ir_trit_to_i64(type_verification.accepted == 1) * 65536
    score = score + native_ir_trit_to_i64(
        type_verification.digest_before == type_verification.digest_after
    ) * 131072
    return score

fn typed_argument_program(source_type: i64, expected_type: i64) -> NativeIR:
    mut program: NativeIR = call_program(1)
    mut vector_type: NativeIRAppendResult = native_ir_intern_composite_type(
        program, 2, native_ir_type_i64(), 0, -1
    )
    mut vector_type_id: i64 = vector_type.value_id
    program = vector_type.program
    mut reference_type: NativeIRAppendResult = native_ir_intern_composite_type(
        program, 3, vector_type_id, 0, -1
    )
    mut reference_type_id: i64 = reference_type.value_id
    program = reference_type.program
    discard i64_vector_set(&mut program.instruction_callee_function_ids, 0, 1)
    discard i64_vector_set(&mut program.instruction_operand_count, 0, 1)
    discard i64_vector_set(&mut program.instruction_operand_first, 0, 1)
    discard i64_vector_push(&mut program.operand_value_ids, 1)
    mut caller_parameter: NativeIRAppendResult = native_ir_append_typed_parameter(
        program, 0, 0, source_type
    )
    program = caller_parameter.program
    mut callee_parameter_first: i64 = i64_vector_len(&program.parameter_value_ids)
    discard i64_vector_set(
        &mut program.function_parameter_first,
        1,
        callee_parameter_first
    )
    mut callee_parameter: NativeIRAppendResult = native_ir_append_typed_parameter(
        program, 1, 0, expected_type
    )
    program = callee_parameter.program
    discard i64_vector_set(&mut program.type_lengths, reference_type_id, -1)
    return program

fn typed_call_valid_probe() -> i64:
    mut program: NativeIR = call_program(1)
    mut verified: NativeIRVerifiedResult = verify_program(program)
    mut verification: NativeVerification = verified.verification
    mut score: i64 = verification.accepted * 100
    score = score + native_ir_trit_to_i64(
        verification.digest_before == verification.digest_after
    ) * 10
    score = score + verification.diagnostic_code
    return score

fn typed_call_result_mismatch_probe() -> i64:
    mut program: NativeIR = call_program(1)
    discard i64_vector_set(
        &mut program.function_result_type_ids, 0, native_ir_type_bool()
    )
    mut verified: NativeIRVerifiedResult = verify_program(program)
    mut verification: NativeVerification = verified.verification
    mut score: i64 = verification.accepted * 100
    score = score + native_ir_trit_to_i64(
        verification.digest_before == verification.digest_after
    ) * 10
    score = score + verification.diagnostic_code
    return score

fn typed_argument_probe(source_type: i64, expected_type: i64) -> i64:
    mut verification: NativeIRVerifiedResult = verify_program(
        typed_argument_program(source_type, expected_type)
    )
    mut score: i64 = verification.verification.accepted * 100
    score = score + native_ir_trit_to_i64(
        verification.verification.digest_before == verification.verification.digest_after
    ) * 10
    score = score + verification.verification.diagnostic_code
    return score

fn builder_call_arity_probe() -> i64:
    mut program: NativeIR = call_program(1)
    mut arguments: i64_vector = i64_vector_new<i64>(1)
    discard i64_vector_push(&mut arguments, 0)
    mut appended: NativeIRAppendResult = native_ir_append_call_arguments(
        program, 0, 0, 0, &arguments
    )
    return appended.accepted

fn verifier_invalid_primitive_probe() -> i64:
    mut program: NativeIR = native_ir_empty()
    discard i64_vector_set(&mut program.type_element_ids, 0, 0)
    mut verified: NativeIRVerifiedResult = verify_program(program)
    mut verification: NativeVerification = verified.verification
    mut score: i64 = verification.accepted * 100
    score = score + native_ir_trit_to_i64(
        verification.digest_before == verification.digest_after
    ) * 10
    score = score + verification.diagnostic_code
    return score

fn verifier_invalid_tryte_primitive_probe() -> i64:
    mut program: NativeIR = native_ir_empty()
    discard i64_vector_push(&mut program.type_kinds, 4)
    discard i64_vector_push(&mut program.type_element_ids, 0)
    discard i64_vector_push(&mut program.type_mutability_flags, 0)
    discard i64_vector_push(&mut program.type_lengths, -1)
    mut verified: NativeIRVerifiedResult = verify_program(program)
    mut verification: NativeVerification = verified.verification
    mut score: i64 = verification.accepted * 100
    score = score + native_ir_trit_to_i64(
        verification.digest_before == verification.digest_after
    ) * 10
    score = score + verification.diagnostic_code
    return score

fn verifier_duplicate_type_probe() -> i64:
    mut program: NativeIR = native_ir_empty()
    discard i64_vector_push(&mut program.type_kinds, 2)
    discard i64_vector_push(&mut program.type_element_ids, 0)
    discard i64_vector_push(&mut program.type_mutability_flags, 0)
    discard i64_vector_push(&mut program.type_lengths, -1)
    discard i64_vector_push(&mut program.type_kinds, 2)
    discard i64_vector_push(&mut program.type_element_ids, 0)
    discard i64_vector_push(&mut program.type_mutability_flags, 0)
    discard i64_vector_push(&mut program.type_lengths, -1)
    mut verified: NativeIRVerifiedResult = verify_program(program)
    mut verification: NativeVerification = verified.verification
    mut score: i64 = verification.accepted * 100
    score = score + native_ir_trit_to_i64(
        verification.digest_before == verification.digest_after
    ) * 10
    score = score + verification.diagnostic_code
    return score

fn verifier_return_type_mismatch_probe() -> i64:
    mut program: NativeIR = scalar_program()
    discard i64_vector_set(
        &mut program.function_result_type_ids, 0, native_ir_type_bool()
    )
    mut verified: NativeIRVerifiedResult = verify_program(program)
    mut verification: NativeVerification = verified.verification
    mut score: i64 = verification.accepted * 100
    score = score + native_ir_trit_to_i64(
        verification.digest_before == verification.digest_after
    ) * 10
    score = score + verification.diagnostic_code
    return score

fn main() -> i64:
    mut result: i64 = native_ir_trit_to_i64(type_foundation_probe() == 262143)
    result = result * 2 + native_ir_trit_to_i64(typed_call_valid_probe() == 110)
    result = result * 2 + native_ir_trit_to_i64(typed_call_result_mismatch_probe() == 25)
    result = result * 2 + native_ir_trit_to_i64(
        typed_argument_probe(native_ir_type_i64(), native_ir_type_i64()) == 110
    )
    result = result * 2 + native_ir_trit_to_i64(
        typed_argument_probe(native_ir_type_i64(), native_ir_type_bool()) == 25
    )
    result = result * 2 + native_ir_trit_to_i64(
        typed_argument_probe(3, 3) == 110
    )
    result = result * 2 + native_ir_trit_to_i64(
        typed_argument_probe(3, 2) == 25
    )
    result = result * 2 + native_ir_trit_to_i64(builder_call_arity_probe() == 0)
    result = result * 2 + native_ir_trit_to_i64(verifier_invalid_primitive_probe() == 25)
    result = result * 2 + native_ir_trit_to_i64(
        verifier_invalid_tryte_primitive_probe() == 25
    )
    result = result * 2 + native_ir_trit_to_i64(verifier_duplicate_type_probe() == 25)
    result = result * 2 + native_ir_trit_to_i64(verifier_return_type_mismatch_probe() == 25)
    return result
"""
    assert run_source(verifier + probe) == 4095


def test_native_ir_external_vector_builtin_has_a_verified_typed_signature() -> None:
    repository = Path(__file__).parents[1]
    verifier = (repository / "selfhost/substrate/verifier_kernel.s3").read_text(encoding="utf-8")
    probe = """
record ExternalCallProbe:
    program: NativeIR
    external_accepted: i64
    external_reference_parameter_accepted: i64
    caller_accepted: i64
    caller_reference_parameter_accepted: i64
    block_accepted: i64
    call_accepted: i64
    call_value_id: i64

fn external_vector_len_probe() -> ExternalCallProbe:
    mut program: NativeIR = native_ir_empty()
    mut vector_type: NativeIRAppendResult = native_ir_intern_composite_type(
        program, 2, native_ir_type_i64(), 0, -1
    )
    mut vector_type_id: i64 = vector_type.value_id
    program = vector_type.program
    mut reference_type: NativeIRAppendResult = native_ir_intern_composite_type(
        program, 3, vector_type_id, 1, -1
    )
    mut reference_type_id: i64 = reference_type.value_id
    program = reference_type.program
    mut source: vector<i64> = vector_new<i64>(20)
    discard vector_push<i64>(&mut source, 118)
    discard vector_push<i64>(&mut source, 101)
    discard vector_push<i64>(&mut source, 99)
    discard vector_push<i64>(&mut source, 116)
    discard vector_push<i64>(&mut source, 111)
    discard vector_push<i64>(&mut source, 114)
    discard vector_push<i64>(&mut source, 95)
    discard vector_push<i64>(&mut source, 108)
    discard vector_push<i64>(&mut source, 101)
    discard vector_push<i64>(&mut source, 110)
    discard vector_push<i64>(&mut source, 32)
    discard vector_push<i64>(&mut source, 99)
    discard vector_push<i64>(&mut source, 97)
    discard vector_push<i64>(&mut source, 108)
    discard vector_push<i64>(&mut source, 108)
    discard vector_push<i64>(&mut source, 101)
    discard vector_push<i64>(&mut source, 114)
    mut external: NativeIRAppendResult = native_ir_append_external_function_source(
        program, 7, 1, native_ir_type_i64(), &source, 0, 10
    )
    mut external_accepted: i64 = external.accepted
    program = external.program
    mut external_reference: NativeIRAppendResult = native_ir_append_typed_parameter(
        program, 7, 0, reference_type_id
    )
    mut external_reference_accepted: i64 = external_reference.accepted
    program = external_reference.program
    mut caller: NativeIRAppendResult = native_ir_append_function_source(
        program, 8, 1, &source, 11, 17
    )
    mut caller_accepted: i64 = caller.accepted
    program = caller.program
    mut caller_reference: NativeIRAppendResult = native_ir_append_typed_parameter(
        program, 8, 0, reference_type_id
    )
    mut caller_reference_accepted: i64 = caller_reference.accepted
    mut caller_reference_id: i64 = caller_reference.value_id
    program = caller_reference.program
    mut block: NativeIRAppendResult = native_ir_append_block_for_function(
        program, 8, 0, 1
    )
    mut block_accepted: i64 = block.accepted
    program = block.program
    mut arguments: i64_vector = i64_vector_new<i64>(1)
    discard i64_vector_push(&mut arguments, caller_reference_id)
    mut call: NativeIRAppendResult = native_ir_append_call_arguments(
        program, 8, 0, 7, &arguments
    )
    mut call_accepted: i64 = call.accepted
    mut call_value_id: i64 = call.value_id
    program = call.program
    mut returned: NativeIRAppendResult = native_ir_append_instruction_for_function(
        program, 8, 0, 1, 0, call_value_id, -1, -1
    )
    program = returned.program
    return ExternalCallProbe(
        program=program,
        external_accepted=external_accepted,
        external_reference_parameter_accepted=external_reference_accepted,
        caller_accepted=caller_accepted,
        caller_reference_parameter_accepted=caller_reference_accepted,
        block_accepted=block_accepted,
        call_accepted=call_accepted,
        call_value_id=call_value_id
    )

fn valid_external_call_probe() -> i64:
    mut state: ExternalCallProbe = external_vector_len_probe()
    mut score: i64 = native_ir_trit_to_i64(state.external_accepted == 1)
    score = score * 2 + native_ir_trit_to_i64(state.external_reference_parameter_accepted == 1)
    score = score * 2 + native_ir_trit_to_i64(state.caller_accepted == 1)
    score = score * 2 + native_ir_trit_to_i64(state.caller_reference_parameter_accepted == 1)
    score = score * 2 + native_ir_trit_to_i64(state.block_accepted == 1)
    score = score * 2 + native_ir_trit_to_i64(state.call_accepted == 1)
    score = score * 2 + native_ir_trit_to_i64(state.call_value_id >= 0)
    mut function_id: i64 = 7
    mut function_external: i64 = native_ir_function_is_external(
        &state.program.function_ids,
        &state.program.function_external_flags,
        function_id
    )
    mut verified: NativeIRVerifiedResult = verify_program(state.program)
    score = score * 2 + verified.verification.accepted
    score = score * 2 + native_ir_trit_to_i64(
        verified.verification.digest_before == verified.verification.digest_after
    )
    score = score * 2 + native_ir_trit_to_i64(function_external == 1)
    return score

fn wrong_external_call_argument_probe() -> i64:
    mut state: ExternalCallProbe = external_vector_len_probe()
    discard i64_vector_set(&mut state.program.parameter_type_ids, 1, native_ir_type_i64())
    discard i64_vector_set(&mut state.program.value_type_ids, 1, native_ir_type_i64())
    mut verified: NativeIRVerifiedResult = verify_program(state.program)
    return native_ir_trit_to_i64(verified.verification.accepted == 0)

fn external_block_builder_probe() -> i64:
    mut state: ExternalCallProbe = external_vector_len_probe()
    mut attempted: NativeIRAppendResult = native_ir_append_block_for_function(
        state.program, 7, 1, 1
    )
    return native_ir_trit_to_i64(attempted.accepted == 0) * native_ir_trit_to_i64(
        i64_vector_len(&attempted.program.block_ids) == 1
    )

fn external_body_verifier_probe() -> i64:
    mut state: ExternalCallProbe = external_vector_len_probe()
    mut forged: NativeIR = state.program
    discard i64_vector_reserve(&mut forged.block_ids, 2)
    discard i64_vector_reserve(&mut forged.block_function_ids, 2)
    discard i64_vector_reserve(&mut forged.block_instruction_first, 2)
    discard i64_vector_reserve(&mut forged.block_instruction_count, 2)
    discard i64_vector_reserve(&mut forged.block_terminator_kinds, 2)
    discard i64_vector_push(&mut forged.block_ids, 1)
    discard i64_vector_push(&mut forged.block_function_ids, 7)
    discard i64_vector_push(&mut forged.block_instruction_first, 2)
    discard i64_vector_push(&mut forged.block_instruction_count, 0)
    discard i64_vector_push(&mut forged.block_terminator_kinds, 1)
    discard i64_vector_set(&mut forged.function_block_count, 0, 1)
    mut verified: NativeIRVerifiedResult = verify_program(forged)
    return native_ir_trit_to_i64(verified.verification.accepted == 0) * native_ir_trit_to_i64(
        verified.verification.digest_before == verified.verification.digest_after
    )

fn external_invalid_linkage_probe() -> i64:
    mut state: ExternalCallProbe = external_vector_len_probe()
    discard i64_vector_set(&mut state.program.function_external_flags, 0, 2)
    mut verified: NativeIRVerifiedResult = verify_program(state.program)
    return native_ir_trit_to_i64(verified.verification.accepted == 0) * native_ir_trit_to_i64(
        verified.verification.digest_before == verified.verification.digest_after
    )

fn main() -> i64:
    mut result: i64 = native_ir_trit_to_i64(valid_external_call_probe() == 1023)
    result = result * 2 + wrong_external_call_argument_probe()
    result = result * 2 + external_block_builder_probe()
    result = result * 2 + external_body_verifier_probe()
    result = result * 2 + external_invalid_linkage_probe()
    return result
"""
    assert run_source(verifier + probe) == 31


@pytest.mark.s3_native
def test_selfhost_shapes_have_linux_native_qualification(tmp_path: Path) -> None:
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        pytest.skip("generic substrate native qualification requires Linux x86-64")
    try:
        toolchain = NativeToolchain.detect()
    except NativeBackendError as error:
        pytest.skip(str(error))
    repository = Path(__file__).parents[1]
    for relative in (
        "selfhost/substrate/syntax_arena.s3",
        "selfhost/substrate/generic_ir_program.s3",
        "selfhost/substrate/verifier_kernel.s3",
    ):
        source = (repository / relative).read_text(encoding="utf-8")
        assembly = compile_source(
            source + "\nfn main() -> i64:\n    return 0\n"
        ).assembly
        executable = toolchain.build(
            generate_native_assembly(assembly),
            tmp_path / Path(relative).stem,
        )
        completed = toolchain.run(executable)
        assert completed.returncode == 0
        assert completed.stdout == "program returned: 0\n"
        assert completed.stderr == ""


def test_native_verifier_branch_fixture_returns_a_typed_value_in_each_arm() -> None:
    repository = Path(__file__).parents[1]
    verifier = (repository / "selfhost/substrate/verifier_kernel.s3").read_text(encoding="utf-8")
    source = verifier + "\nfn main() -> i64:\n    return verifier_case(1)\n"

    hosted = run_source(source)

    assert hosted // 1_000_000_000 == 1
    assert (hosted % 1_000_000_000) // 100_000_000 == 1


def test_native_ir_typed_relations_verify_operand_and_code_contracts() -> None:
    repository = Path(__file__).parents[1]
    verifier = (repository / "selfhost/substrate/verifier_kernel.s3").read_text(
        encoding="utf-8"
    )
    probe = """
fn typed_relation_verifier_probe(
    relation_code: i64, left_type_id: i64, right_type_id: i64
) -> i64:
    mut program: NativeIR = native_ir_empty()
    mut function: NativeIRAppendResult = native_ir_append_function(program, 0, 1)
    program = function.program
    mut result_type: NativeIRAppendResult = native_ir_set_function_result_type(
        program, 0, 1
    )
    program = result_type.program
    mut block: NativeIRAppendResult = native_ir_append_block_for_function(
        program, 0, 0, 1
    )
    program = block.program
    mut left: NativeIRAppendResult = native_ir_append_typed_instruction_for_function(
        program, 0, 0, 0, 1, -1, -1, left_type_id
    )
    mut left_id: i64 = left.value_id
    program = left.program
    mut right: NativeIRAppendResult = native_ir_append_typed_instruction_for_function(
        program, 0, 0, 0, 0, -1, -1, right_type_id
    )
    mut right_id: i64 = right.value_id
    program = right.program
    mut relation: NativeIRAppendResult = native_ir_append_typed_instruction_for_function(
        program, 0, 0, 11, relation_code, left_id, right_id, 1
    )
    mut relation_id: i64 = relation.value_id
    match relation.accepted == 1:
        -1:
            program = relation.program
        0:
            return relation.accepted
        1:
            return relation.accepted
    mut returned: NativeIRAppendResult = native_ir_append_instruction_for_function(
        program, 0, 0, 1, 0, relation_id, -1, -1
    )
    program = returned.program
    mut verified: NativeIRVerifiedResult = verify_program(program)
    return verified.verification.accepted * 100 + verified.verification.diagnostic_code

fn typed_compare_verifier_probe(
    immediate: i64, left_type_id: i64, right_type_id: i64, result_type_id: i64
) -> i64:
    mut program: NativeIR = native_ir_empty()
    mut function: NativeIRAppendResult = native_ir_append_function(program, 0, 1)
    program = function.program
    mut result_type: NativeIRAppendResult = native_ir_set_function_result_type(
        program, 0, 1
    )
    program = result_type.program
    mut block: NativeIRAppendResult = native_ir_append_block_for_function(
        program, 0, 0, 1
    )
    program = block.program
    mut left: NativeIRAppendResult = native_ir_append_typed_instruction_for_function(
        program, 0, 0, 0, 1, -1, -1, left_type_id
    )
    mut left_id: i64 = left.value_id
    program = left.program
    mut right: NativeIRAppendResult = native_ir_append_typed_instruction_for_function(
        program, 0, 0, 0, 0, -1, -1, right_type_id
    )
    mut right_id: i64 = right.value_id
    program = right.program
    mut compared: NativeIRAppendResult = native_ir_append_typed_instruction_for_function(
        program, 0, 0, 12, immediate, left_id, right_id, result_type_id
    )
    mut compared_id: i64 = compared.value_id
    match compared.accepted == 1:
        -1:
            program = compared.program
        0:
            return compared.accepted
        1:
            return compared.accepted
    mut returned: NativeIRAppendResult = native_ir_append_instruction_for_function(
        program, 0, 0, 1, 0, compared_id, -1, -1
    )
    program = returned.program
    mut verified: NativeIRVerifiedResult = verify_program(program)
    return verified.verification.accepted * 100 + verified.verification.diagnostic_code

fn main() -> i64:
    mut score: i64 = native_ir_trit_to_i64(
        typed_relation_verifier_probe(0, 0, 0) == 100
    )
    score = score * 2 + native_ir_trit_to_i64(
        typed_relation_verifier_probe(2, 0, 0) == 100
    )
    score = score * 2 + native_ir_trit_to_i64(
        typed_relation_verifier_probe(5, 0, 0) == 100
    )
    score = score * 2 + native_ir_trit_to_i64(
        typed_relation_verifier_probe(0, 0, 1) == 15
    )
    score = score * 2 + native_ir_trit_to_i64(
        typed_relation_verifier_probe(6, 0, 0) == 0
    )
    score = score * 2 + native_ir_trit_to_i64(
        typed_compare_verifier_probe(0, 0, 0, 1) == 100
    )
    score = score * 2 + native_ir_trit_to_i64(
        typed_compare_verifier_probe(0, 0, 0, 0) == 15
    )
    score = score * 2 + native_ir_trit_to_i64(
        typed_compare_verifier_probe(0, 0, 1, 1) == 15
    )
    score = score * 2 + native_ir_trit_to_i64(
        typed_compare_verifier_probe(1, 0, 0, 1) == 0
    )
    return score
"""

    assert run_source(verifier + "\n" + probe) == 511


def test_native_ir_i64_difference_verifier_contracts() -> None:
    repository = Path(__file__).parents[1]
    verifier = (repository / "selfhost/substrate/verifier_kernel.s3").read_text(
        encoding="utf-8"
    )
    probe = """
fn typed_difference_verifier_probe(
    immediate: i64, result_type_id: i64, left_type_id: i64, right_type_id: i64
) -> i64:
    mut function: NativeIRAppendResult = native_ir_append_function(
        native_ir_empty(), 0, 1
    )
    mut result_type: NativeIRAppendResult = native_ir_set_function_result_type(
        function.program, 0, result_type_id
    )
    mut block: NativeIRAppendResult = native_ir_append_block_for_function(
        result_type.program, 0, 0, 1
    )
    mut left: NativeIRAppendResult = native_ir_append_typed_instruction_for_function(
        block.program, 0, 0, 0, 1, -1, -1, left_type_id
    )
    mut left_id: i64 = left.value_id
    mut right: NativeIRAppendResult = native_ir_append_typed_instruction_for_function(
        left.program, 0, 0, 0, 0, -1, -1, right_type_id
    )
    mut right_id: i64 = right.value_id
    mut difference: NativeIRAppendResult = native_ir_append_typed_instruction_for_function(
        right.program, 0, 0, 13, immediate, left_id, right_id, result_type_id
    )
    mut difference_accepted: i64 = difference.accepted
    mut difference_id: i64 = difference.value_id
    match difference_accepted == 1:
        -1:
            mut returned: NativeIRAppendResult = native_ir_append_instruction_for_function(
                difference.program, 0, 0, 1, 0, difference_id, -1, -1
            )
            mut verified: NativeIRVerifiedResult = verify_program(returned.program)
            return verified.verification.accepted * 100 + verified.verification.diagnostic_code
        0:
            return difference_accepted
        1:
            return difference_accepted

fn main() -> i64:
    mut score: i64 = native_ir_trit_to_i64(
        typed_difference_verifier_probe(0, 0, 0, 0) == 100
    )
    score = score * 2 + native_ir_trit_to_i64(
        typed_difference_verifier_probe(1, 0, 0, 0) == 8
    )
    score = score * 2 + native_ir_trit_to_i64(
        typed_difference_verifier_probe(0, 1, 0, 0) == 15
    )
    score = score * 2 + native_ir_trit_to_i64(
        typed_difference_verifier_probe(0, 0, 1, 0) == 15
    )
    score = score * 2 + native_ir_trit_to_i64(
        typed_difference_verifier_probe(0, 0, 0, 1) == 15
    )
    return score
"""

    assert run_source(verifier + "\n" + probe) == 31


def test_native_ir_verifier_checksum_handles_large_i64_immediates() -> None:
    repository = Path(__file__).parents[1]
    verifier = (repository / "selfhost/substrate/verifier_kernel.s3").read_text(
        encoding="utf-8"
    )
    probe = """
fn large_immediate_checksum_probe() -> i64:
    mut program: NativeIR = native_ir_empty()
    mut function: NativeIRAppendResult = native_ir_append_function(program, 0, 1)
    program = function.program
    mut result_type: NativeIRAppendResult = native_ir_set_function_result_type(
        program, 0, native_ir_type_i64()
    )
    program = result_type.program
    mut block: NativeIRAppendResult = native_ir_append_block_for_function(
        program, 0, 0, 1
    )
    program = block.program
    mut constant: NativeIRAppendResult = native_ir_append_typed_instruction_for_function(
        program, 0, 0, 0, 1000000000000000000, -1, -1, native_ir_type_i64()
    )
    mut value_id: i64 = constant.value_id
    program = constant.program
    mut returned: NativeIRAppendResult = native_ir_append_instruction_for_function(
        program, 0, 0, 1, 0, value_id, -1, -1
    )
    program = returned.program
    mut verified: NativeIRVerifiedResult = verify_program(program)
    return verified.verification.accepted * 10 + native_ir_trit_to_i64(
        verified.verification.digest_before == verified.verification.digest_after
    )

fn main() -> i64:
    return large_immediate_checksum_probe()
"""

    assert run_source(verifier + "\n" + probe) == 11


def test_native_ir_typed_branch_and_jump_cfg_contracts() -> None:
    repository = Path(__file__).parents[1]
    verifier = (repository / "selfhost/substrate/verifier_kernel.s3").read_text(
        encoding="utf-8"
    )
    probe = """
fn append_i64_constant(
    program: NativeIR, function_id: i64, block_id: i64, value: i64
) -> NativeIRAppendResult:
    return native_ir_append_typed_instruction_for_function(
        program, function_id, block_id, 0, value, -1, -1, 0
    )

fn append_return(
    program: NativeIR, function_id: i64, block_id: i64, value_id: i64
) -> NativeIR:
    mut returned: NativeIRAppendResult = native_ir_append_instruction_for_function(
        program, function_id, block_id, 1, 0, value_id, -1, -1
    )
    return returned.program

fn valid_branch_program() -> NativeIR:
    mut program: NativeIR = native_ir_empty()
    mut main_function: NativeIRAppendResult = native_ir_append_function(program, 0, 1)
    program = main_function.program
    mut main_result_type: NativeIRAppendResult = native_ir_set_function_result_type(
        program, 0, 0
    )
    program = main_result_type.program
    mut entry: NativeIRAppendResult = native_ir_append_block_for_function(
        program, 0, 0, 2
    )
    program = entry.program
    mut negative: NativeIRAppendResult = native_ir_append_block_for_function(
        program, 0, 1, 1
    )
    program = negative.program
    mut neutral: NativeIRAppendResult = native_ir_append_block_for_function(
        program, 0, 2, 1
    )
    program = neutral.program
    mut positive: NativeIRAppendResult = native_ir_append_block_for_function(
        program, 0, 3, 1
    )
    program = positive.program

    mut left: NativeIRAppendResult = append_i64_constant(program, 0, 0, 1)
    mut left_id: i64 = left.value_id
    program = left.program
    mut right: NativeIRAppendResult = append_i64_constant(program, 0, 0, 2)
    mut right_id: i64 = right.value_id
    program = right.program
    mut relation: NativeIRAppendResult = native_ir_append_typed_instruction_for_function(
        program, 0, 0, 11, 0, left_id, right_id, 1
    )
    mut condition_id: i64 = relation.value_id
    program = relation.program
    mut branch: NativeIRAppendResult = native_ir_append_branch_for_function(
        program, 0, 0, condition_id, 1, 2, 3
    )
    program = branch.program

    mut negative_value: NativeIRAppendResult = append_i64_constant(program, 0, 1, 11)
    mut negative_value_id: i64 = negative_value.value_id
    program = append_return(negative_value.program, 0, 1, negative_value_id)
    mut neutral_value: NativeIRAppendResult = append_i64_constant(program, 0, 2, 22)
    mut neutral_value_id: i64 = neutral_value.value_id
    program = append_return(neutral_value.program, 0, 2, neutral_value_id)
    mut positive_value: NativeIRAppendResult = append_i64_constant(program, 0, 3, 33)
    mut positive_value_id: i64 = positive_value.value_id
    program = append_return(positive_value.program, 0, 3, positive_value_id)

    mut other_function: NativeIRAppendResult = native_ir_append_function(program, 1, 1)
    program = other_function.program
    mut other_result_type: NativeIRAppendResult = native_ir_set_function_result_type(
        program, 1, 0
    )
    program = other_result_type.program
    mut other_block: NativeIRAppendResult = native_ir_append_block_for_function(
        program, 1, 10, 1
    )
    program = other_block.program
    mut other_value: NativeIRAppendResult = append_i64_constant(program, 1, 10, 44)
    mut other_value_id: i64 = other_value.value_id
    program = append_return(other_value.program, 1, 10, other_value_id)
    return program

fn branch_cfg_contract_probe() -> i64:
    mut verified: NativeIRVerifiedResult = verify_program(valid_branch_program())
    mut score: i64 = native_ir_trit_to_i64(verified.verification.accepted == 1)
    score = score * 2 + native_ir_trit_to_i64(
        verified.verification.digest_before == verified.verification.digest_after
    )

    mut wrong_count: NativeIR = valid_branch_program()
    discard i64_vector_set(&mut wrong_count.instruction_target_count, 3, 2)
    mut wrong_count_result: NativeIRVerifiedResult = verify_program(wrong_count)
    score = score * 2 + native_ir_trit_to_i64(
        wrong_count_result.verification.accepted == 0
    )

    mut foreign_target: NativeIR = valid_branch_program()
    discard i64_vector_set(&mut foreign_target.target_block_ids, 0, 10)
    mut foreign_result: NativeIRVerifiedResult = verify_program(foreign_target)
    score = score * 2 + native_ir_trit_to_i64(foreign_result.verification.accepted == 0)

    score = score * 2 + invalid_branch_builder_probe()
    score = score * 2 + invalid_jump_builder_probe()
    return score

fn invalid_branch_builder_probe() -> i64:
    mut program: NativeIR = native_ir_empty()
    mut function: NativeIRAppendResult = native_ir_append_function(program, 0, 1)
    program = function.program
    mut entry: NativeIRAppendResult = native_ir_append_block_for_function(
        program, 0, 0, 2
    )
    program = entry.program
    mut negative: NativeIRAppendResult = native_ir_append_block_for_function(
        program, 0, 1, 1
    )
    program = negative.program
    mut neutral: NativeIRAppendResult = native_ir_append_block_for_function(
        program, 0, 2, 1
    )
    program = neutral.program
    mut positive: NativeIRAppendResult = native_ir_append_block_for_function(
        program, 0, 3, 1
    )
    program = positive.program
    mut condition: NativeIRAppendResult = append_i64_constant(program, 0, 0, 1)
    mut condition_id: i64 = condition.value_id
    mut targets: i64_vector = i64_vector_new<i64>(3)
    discard i64_vector_push(&mut targets, 1)
    discard i64_vector_push(&mut targets, 2)
    discard i64_vector_push(&mut targets, 3)
    mut attempted: NativeIRAppendResult = native_ir_append_control_instruction_for_function(
        condition.program, 0, 0, 2, condition_id, &targets
    )
    return native_ir_trit_to_i64(attempted.accepted == 0)

fn invalid_jump_builder_probe() -> i64:
    mut program: NativeIR = native_ir_empty()
    mut function: NativeIRAppendResult = native_ir_append_function(program, 0, 1)
    program = function.program
    mut entry: NativeIRAppendResult = native_ir_append_block_for_function(
        program, 0, 0, 3
    )
    program = entry.program
    mut attempted: NativeIRAppendResult = native_ir_append_jump_for_function(
        program, 0, 0, 99
    )
    return native_ir_trit_to_i64(attempted.accepted == 0)

fn jump_cfg_contract_probe() -> i64:
    mut program: NativeIR = native_ir_empty()
    mut function: NativeIRAppendResult = native_ir_append_function(program, 0, 1)
    program = function.program
    mut result_type: NativeIRAppendResult = native_ir_set_function_result_type(
        program, 0, 0
    )
    program = result_type.program
    mut entry: NativeIRAppendResult = native_ir_append_block_for_function(
        program, 0, 0, 3
    )
    program = entry.program
    mut exit_block: NativeIRAppendResult = native_ir_append_block_for_function(
        program, 0, 1, 1
    )
    program = exit_block.program
    mut jump: NativeIRAppendResult = native_ir_append_jump_for_function(
        program, 0, 0, 1
    )
    program = jump.program
    mut value: NativeIRAppendResult = append_i64_constant(program, 0, 1, 55)
    mut value_id: i64 = value.value_id
    program = append_return(value.program, 0, 1, value_id)
    mut verified: NativeIRVerifiedResult = verify_program(program)
    mut score: i64 = native_ir_trit_to_i64(verified.verification.accepted == 1)
    score = score * 2 + native_ir_trit_to_i64(
        verified.verification.digest_before == verified.verification.digest_after
    )

    mut bad_count: NativeIR = valid_jump_program()
    discard i64_vector_set(&mut bad_count.instruction_target_count, 0, 0)
    mut bad_count_result: NativeIRVerifiedResult = verify_program(bad_count)
    score = score * 2 + native_ir_trit_to_i64(bad_count_result.verification.accepted == 0)
    return score

fn valid_jump_program() -> NativeIR:
    mut program: NativeIR = native_ir_empty()
    mut function: NativeIRAppendResult = native_ir_append_function(program, 0, 1)
    program = function.program
    mut result_type: NativeIRAppendResult = native_ir_set_function_result_type(
        program, 0, 0
    )
    program = result_type.program
    mut entry: NativeIRAppendResult = native_ir_append_block_for_function(
        program, 0, 0, 3
    )
    program = entry.program
    mut exit_block: NativeIRAppendResult = native_ir_append_block_for_function(
        program, 0, 1, 1
    )
    program = exit_block.program
    mut jump: NativeIRAppendResult = native_ir_append_jump_for_function(
        program, 0, 0, 1
    )
    program = jump.program
    mut value: NativeIRAppendResult = append_i64_constant(program, 0, 1, 55)
    mut value_id: i64 = value.value_id
    program = append_return(value.program, 0, 1, value_id)
    return program

fn cfg_graph_query_probe() -> i64:
    mut program: NativeIR = valid_branch_program()
    mut score: i64 = native_ir_trit_to_i64(
        native_ir_block_is_reachable(
            &program.function_ids, &program.function_block_first,
            &program.function_block_count, &program.block_ids,
            &program.block_function_ids, &program.block_instruction_first,
            &program.block_instruction_count, &program.instruction_ids,
            &program.instruction_opcodes, &program.instruction_target_first,
            &program.instruction_target_count, &program.target_block_ids, 0, 0
        ) == 1
    )
    score = score * 2 + native_ir_trit_to_i64(
        native_ir_block_is_reachable(
            &program.function_ids, &program.function_block_first,
            &program.function_block_count, &program.block_ids,
            &program.block_function_ids, &program.block_instruction_first,
            &program.block_instruction_count, &program.instruction_ids,
            &program.instruction_opcodes, &program.instruction_target_first,
            &program.instruction_target_count, &program.target_block_ids, 0, 3
        ) == 1
    )
    score = score * 2 + native_ir_trit_to_i64(
        native_ir_block_predecessor_count(
            &program.block_ids, &program.block_function_ids,
            &program.block_instruction_first, &program.block_instruction_count,
            &program.instruction_ids, &program.instruction_opcodes,
            &program.instruction_target_first, &program.instruction_target_count,
            &program.target_block_ids, 0, 0
        ) == 0
    )
    score = score * 2 + native_ir_trit_to_i64(
        native_ir_block_predecessor_count(
            &program.block_ids, &program.block_function_ids,
            &program.block_instruction_first, &program.block_instruction_count,
            &program.instruction_ids, &program.instruction_opcodes,
            &program.instruction_target_first, &program.instruction_target_count,
            &program.target_block_ids, 0, 2
        ) == 1
    )
    return score

fn cfg_backedge_and_unreachable_probe() -> i64:
    mut program: NativeIR = native_ir_empty()
    mut function: NativeIRAppendResult = native_ir_append_function(program, 0, 1)
    program = function.program
    mut result_type: NativeIRAppendResult = native_ir_set_function_result_type(
        program, 0, 0
    )
    program = result_type.program
    mut entry: NativeIRAppendResult = native_ir_append_block_for_function(
        program, 0, 0, 2
    )
    program = entry.program
    mut loop: NativeIRAppendResult = native_ir_append_block_for_function(
        program, 0, 1, 3
    )
    program = loop.program
    mut exit_block: NativeIRAppendResult = native_ir_append_block_for_function(
        program, 0, 2, 1
    )
    program = exit_block.program
    mut orphan: NativeIRAppendResult = native_ir_append_block_for_function(
        program, 0, 3, 1
    )
    program = orphan.program
    mut left: NativeIRAppendResult = append_i64_constant(program, 0, 0, 1)
    mut left_id: i64 = left.value_id
    program = left.program
    mut right: NativeIRAppendResult = append_i64_constant(program, 0, 0, 2)
    mut right_id: i64 = right.value_id
    program = right.program
    mut relation: NativeIRAppendResult = native_ir_append_typed_instruction_for_function(
        program, 0, 0, 11, 0, left_id, right_id, 1
    )
    mut condition_id: i64 = relation.value_id
    program = relation.program
    mut branch: NativeIRAppendResult = native_ir_append_branch_for_function(
        program, 0, 0, condition_id, 1, 2, 2
    )
    program = branch.program
    mut backedge: NativeIRAppendResult = native_ir_append_jump_for_function(
        program, 0, 1, 0
    )
    program = backedge.program
    mut exit_value: NativeIRAppendResult = append_i64_constant(program, 0, 2, 7)
    mut exit_value_id: i64 = exit_value.value_id
    program = append_return(exit_value.program, 0, 2, exit_value_id)
    mut orphan_value: NativeIRAppendResult = append_i64_constant(program, 0, 3, 9)
    mut orphan_value_id: i64 = orphan_value.value_id
    program = append_return(orphan_value.program, 0, 3, orphan_value_id)
    mut score: i64 = native_ir_trit_to_i64(
        native_ir_block_is_reachable(
            &program.function_ids, &program.function_block_first,
            &program.function_block_count, &program.block_ids,
            &program.block_function_ids, &program.block_instruction_first,
            &program.block_instruction_count, &program.instruction_ids,
            &program.instruction_opcodes, &program.instruction_target_first,
            &program.instruction_target_count, &program.target_block_ids, 0, 1
        ) == 1
    )
    score = score * 2 + native_ir_trit_to_i64(
        native_ir_block_is_reachable(
            &program.function_ids, &program.function_block_first,
            &program.function_block_count, &program.block_ids,
            &program.block_function_ids, &program.block_instruction_first,
            &program.block_instruction_count, &program.instruction_ids,
            &program.instruction_opcodes, &program.instruction_target_first,
            &program.instruction_target_count, &program.target_block_ids, 0, 3
        ) == 0
    )
    score = score * 2 + native_ir_trit_to_i64(
        native_ir_block_predecessor_count(
            &program.block_ids, &program.block_function_ids,
            &program.block_instruction_first, &program.block_instruction_count,
            &program.instruction_ids, &program.instruction_opcodes,
            &program.instruction_target_first, &program.instruction_target_count,
            &program.target_block_ids, 0, 0
        ) == 1
    )
    score = score * 2 + native_ir_trit_to_i64(
        native_ir_block_predecessor_count(
            &program.block_ids, &program.block_function_ids,
            &program.block_instruction_first, &program.block_instruction_count,
            &program.instruction_ids, &program.instruction_opcodes,
            &program.instruction_target_first, &program.instruction_target_count,
            &program.target_block_ids, 0, 2
        ) == 1
    )
    score = score * 2 + native_ir_trit_to_i64(
        native_ir_block_predecessor_count(
            &program.block_ids, &program.block_function_ids,
            &program.block_instruction_first, &program.block_instruction_count,
            &program.instruction_ids, &program.instruction_opcodes,
            &program.instruction_target_first, &program.instruction_target_count,
            &program.target_block_ids, 0, 3
        ) == 0
    )
    mut verified: NativeIRVerifiedResult = verify_program(program)
    score = score * 2 + native_ir_trit_to_i64(verified.verification.accepted == 1)
    score = score * 2 + native_ir_trit_to_i64(
        verified.verification.digest_before == verified.verification.digest_after
    )
    return score

fn dominated_cross_block_value_probe() -> i64:
    mut program: NativeIR = native_ir_empty()
    mut function: NativeIRAppendResult = native_ir_append_function(program, 0, 1)
    program = function.program
    mut result_type: NativeIRAppendResult = native_ir_set_function_result_type(
        program, 0, 0
    )
    program = result_type.program
    mut entry: NativeIRAppendResult = native_ir_append_block_for_function(
        program, 0, 0, 3
    )
    program = entry.program
    mut exit_block: NativeIRAppendResult = native_ir_append_block_for_function(
        program, 0, 1, 1
    )
    program = exit_block.program
    mut value: NativeIRAppendResult = append_i64_constant(program, 0, 0, 55)
    mut value_id: i64 = value.value_id
    program = value.program
    mut jump: NativeIRAppendResult = native_ir_append_jump_for_function(
        program, 0, 0, 1
    )
    program = jump.program
    program = append_return(program, 0, 1, value_id)
    mut verified: NativeIRVerifiedResult = verify_program(program)
    mut score: i64 = native_ir_trit_to_i64(verified.verification.accepted == 1)
    score = score * 2 + native_ir_trit_to_i64(
        verified.verification.digest_before == verified.verification.digest_after
    )
    return score

fn main() -> i64:
    mut result: i64 = branch_cfg_contract_probe() * 2048
    result = result + jump_cfg_contract_probe() * 256
    result = result + cfg_graph_query_probe() * 16
    result = result + cfg_backedge_and_unreachable_probe() * 2
    result = result + dominated_cross_block_value_probe()
    return result
"""

    assert run_source(verifier + "\n" + probe) == 131313


def test_native_ir_verifier_rejects_cross_block_value_without_dominance() -> None:
    repository = Path(__file__).parents[1]
    verifier = (repository / "selfhost/substrate/verifier_kernel.s3").read_text(
        encoding="utf-8"
    )
    probe = """
fn main() -> i64:
    mut program: NativeIR = branch_program()
    mut first_result: i64 = i64_vector_get(&program.instruction_result_first, 4)
    mut first_value_id: i64 = i64_vector_get(&program.result_value_ids, first_result)
    mut second_return_operands: i64 = i64_vector_get(&program.instruction_operand_first, 7)
    discard i64_vector_set(&mut program.operand_value_ids, second_return_operands, first_value_id)
    mut verified: NativeIRVerifiedResult = verify_program(program)
    return native_ir_trit_to_i64(verified.verification.accepted == 0) * 10 + native_ir_trit_to_i64(
        verified.verification.diagnostic_code == 11
    )
"""

    assert run_source(verifier + "\n" + probe) == 11


def test_native_verifier_multi_result_call_fixture_returns_each_declared_result() -> None:
    repository = Path(__file__).parents[1]
    verifier = (repository / "selfhost/substrate/verifier_kernel.s3").read_text(encoding="utf-8")
    source = verifier + "\nfn main() -> i64:\n    return verifier_case(3)\n"

    hosted = run_source(source)

    assert hosted // 1_000_000_000 == 1
    assert (hosted % 1_000_000_000) // 100_000_000 == 1

    wrong_signature = run_source(
        verifier + "\nfn main() -> i64:\n    return verifier_case(17)\n"
    )
    assert wrong_signature // 1_000_000_000 == 0
    assert (wrong_signature % 1_000_000_000) // 100_000_000 == 1


def test_native_ir_heterogeneous_multi_result_call_and_return_are_typed() -> None:
    repository = Path(__file__).parents[1]
    verifier = (repository / "selfhost/substrate/verifier_kernel.s3").read_text(
        encoding="utf-8"
    )
    probe = """
fn heterogeneous_result_program(malformed_case: i64) -> NativeIR:
    mut program: NativeIR = native_ir_empty()
    mut caller: NativeIRAppendResult = native_ir_append_function(program, 0, 2)
    program = caller.program
    mut caller_type: NativeIRAppendResult = native_ir_set_function_result_type(
        program, 0, 0
    )
    program = caller_type.program
    mut caller_second_type: NativeIRAppendResult = native_ir_set_function_result_type_at(
        program, 0, 1, 1
    )
    program = caller_second_type.program
    mut callee: NativeIRAppendResult = native_ir_append_external_function(
        program, 1, 2, 0
    )
    program = callee.program
    mut callee_second_type: NativeIRAppendResult = native_ir_set_function_result_type_at(
        program, 1, 1, 1
    )
    program = callee_second_type.program
    mut block: NativeIRAppendResult = native_ir_append_block_for_function(
        program, 0, 0, 1
    )
    program = block.program
    mut empty_arguments: i64_vector = i64_vector_new<i64>(0)
    mut call: NativeIRAppendResult = native_ir_append_call_arguments(
        program, 0, 0, 1, &empty_arguments
    )
    mut first_call_result_value_id: i64 = call.value_id
    mut second_call_result_value_id: i64 = call.value_id + 1
    program = call.program
    mut return_values: i64_vector = i64_vector_new<i64>(2)
    discard i64_vector_push(&mut return_values, first_call_result_value_id)
    discard i64_vector_push(&mut return_values, second_call_result_value_id)
    mut returned: NativeIRAppendResult = native_ir_append_return_values_for_function(
        program, 0, 0, &return_values
    )
    program = returned.program
    match malformed_case == 1:
        -1:
            mut last_type_index: i64 = i64_vector_len(&program.value_type_ids) - 1
            discard i64_vector_set(
                &mut program.value_type_ids, last_type_index, 0
            )
        0:
            discard 0
        1:
            discard 0
    match malformed_case == 2:
        -1:
            discard i64_vector_set(
                &mut program.operand_value_ids, 1, first_call_result_value_id
            )
        0:
            discard 0
        1:
            discard 0
    return program

fn main() -> i64:
    mut good: NativeIRVerifiedResult = verify_program(
        heterogeneous_result_program(0)
    )
    mut bad_call_result: NativeIRVerifiedResult = verify_program(
        heterogeneous_result_program(1)
    )
    mut bad_return_operand: NativeIRVerifiedResult = verify_program(
        heterogeneous_result_program(2)
    )
    mut second_type: i64 = native_ir_function_result_type_id(
        &good.program.function_ids,
        &good.program.function_result_widths,
        &good.program.function_result_type_first,
        &good.program.function_result_type_ids,
        1,
        1
    )
    mut score: i64 = good.verification.accepted * 1000000
    score = score + native_ir_trit_to_i64(
        good.verification.diagnostic_code == 0
    ) * 10000
    score = score + native_ir_trit_to_i64(
        good.verification.digest_before == good.verification.digest_after
    ) * 1000
    score = score + native_ir_trit_to_i64(second_type == 1) * 100
    score = score + native_ir_trit_to_i64(
        bad_call_result.verification.accepted == 0
    ) * 10
    score = score + native_ir_trit_to_i64(
        bad_call_result.verification.diagnostic_code == 15
    ) * 4
    score = score + native_ir_trit_to_i64(
        bad_return_operand.verification.accepted == 0
    ) * 2
    score = score + native_ir_trit_to_i64(
        bad_return_operand.verification.diagnostic_code == 15
    )
    return score
"""

    observed = run_source(verifier + probe)
    assert observed == 1_011_117, observed


def test_native_verifier_reference_matrix_fixtures_are_well_typed() -> None:
    repository = Path(__file__).parents[1]
    verifier = (repository / "selfhost/substrate/verifier_kernel.s3").read_text(
        encoding="utf-8"
    )
    probe = """
fn reference_case_score(case_id: i64) -> i64:
    mut result: NativeIRVerifiedResult = verify_program(case_program(case_id))
    mut accepted: i64 = native_ir_trit_to_i64(result.verification.accepted == 1)
    mut digest_equal: i64 = native_ir_trit_to_i64(
        result.verification.digest_before == result.verification.digest_after
    )
    return accepted * 10 + digest_equal

fn main() -> i64:
    return reference_case_score(6) * 100 + reference_case_score(27)
"""

    assert run_source(verifier + probe) == 1111


def test_native_verifier_preserves_valid_dominance_case_fixtures() -> None:
    repository = Path(__file__).parents[1]
    verifier = (repository / "selfhost/substrate/verifier_kernel.s3").read_text(
        encoding="utf-8"
    )
    probe = """
fn main() -> i64:
    mut result: NativeIRVerifiedResult = verify_program(case_program(9))
    mut score: i64 = native_ir_trit_to_i64(result.verification.accepted == 1)
    score = score * 2 + native_ir_trit_to_i64(
        result.verification.digest_before == result.verification.digest_after
    )
    result = verify_program(case_program(29))
    score = score * 2 + native_ir_trit_to_i64(result.verification.accepted == 1)
    score = score * 2 + native_ir_trit_to_i64(
        result.verification.digest_before == result.verification.digest_after
    )
    return score
"""

    assert run_source(verifier + "\n" + probe) == 15


@pytest.mark.s3_native
def test_native_verifier_differential_matrix_is_immutable_and_repeatable(tmp_path: Path) -> None:
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        pytest.skip("native verifier qualification requires Linux x86-64")
    try:
        toolchain = NativeToolchain.detect()
    except NativeBackendError as error:
        pytest.skip(str(error))

    repository = Path(__file__).parents[1]
    verifier = (repository / "selfhost/substrate/verifier_kernel.s3").read_text(encoding="utf-8")
    valid_cases = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 23, 24, 25, 26, 27, 28, 29}
    observed: dict[int, int] = {}

    for case in range(32):
        source = verifier + f"\nfn main() -> i64:\n    return verifier_case({case})\n"
        hosted = run_source(source)
        if case in valid_cases:
            assert hosted // 1_000_000_000 == 1, (case, hosted)
        else:
            assert hosted // 1_000_000_000 == 0, (case, hosted)
        assert (hosted % 1_000_000_000) // 100_000_000 == 1, (case, hosted)

        assembly = compile_source(source).assembly
        executable = toolchain.build(
            generate_native_assembly(assembly),
            tmp_path / f"verifier-case-{case}",
        )
        completed = toolchain.run(executable)
        assert completed.returncode == 0
        assert completed.stderr == ""
        prefix = "program returned: "
        assert completed.stdout.startswith(prefix)
        native = int(completed.stdout[len(prefix):].strip())
        observed[case] = native
        assert native == hosted, (case, hosted, native)

    for case in (0, 3, 10, 17, 21, 30):
        for _ in range(3):
            source = verifier + f"\nfn main() -> i64:\n    return verifier_case({case})\n"
            executable = toolchain.build(
                generate_native_assembly(compile_source(source).assembly),
                tmp_path / f"verifier-repeat-{case}",
            )
            completed = toolchain.run(executable)
            assert completed.returncode == 0
            assert int(completed.stdout.removeprefix("program returned: ").strip()) == observed[case]


def test_native_ir_typed_memory_builder_and_verifier_contracts() -> None:
    repository = Path(__file__).parents[1]
    verifier = (repository / "selfhost/substrate/verifier_kernel.s3").read_text(
        encoding="utf-8"
    )
    probe = r"""
fn append_i64_value(program: NativeIR, block_id: i64, value: i64) -> NativeIRAppendResult:
    return native_ir_append_typed_instruction_for_function(
        program, 0, block_id, 0, value, -1, -1, 0
    )

fn memory_prefix() -> NativeIR:
    mut function: NativeIRAppendResult = native_ir_append_function(
        native_ir_empty(), 0, 1
    )
    mut result_type: NativeIRAppendResult = native_ir_set_function_result_type(
        function.program, 0, 0
    )
    mut block: NativeIRAppendResult = native_ir_append_block_for_function(
        result_type.program, 0, 0, 1
    )
    mut memory: NativeIRAppendResult = native_ir_append_memory(
        block.program, 0, 0, 2
    )
    mut index: NativeIRAppendResult = append_i64_value(memory.program, 0, 0)
    mut wrong_value: NativeIRAppendResult = native_ir_append_typed_instruction_for_function(
        index.program, 0, 0, 0, -1, -1, -1, 1
    )
    return wrong_value.program

fn valid_memory_program() -> NativeIR:
    mut function: NativeIRAppendResult = native_ir_append_function(
        native_ir_empty(), 0, 1
    )
    mut result_type: NativeIRAppendResult = native_ir_set_function_result_type(
        function.program, 0, 0
    )
    mut block: NativeIRAppendResult = native_ir_append_block_for_function(
        result_type.program, 0, 0, 1
    )
    mut memory: NativeIRAppendResult = native_ir_append_memory(
        block.program, 0, 0, 2
    )
    mut index: NativeIRAppendResult = append_i64_value(memory.program, 0, 1)
    mut index_id: i64 = index.value_id
    mut value: NativeIRAppendResult = append_i64_value(index.program, 0, 77)
    mut value_id: i64 = value.value_id
    mut stored: NativeIRAppendResult = native_ir_append_store_for_function(
        value.program, 0, 0, 0, index_id, value_id
    )
    mut loaded: NativeIRAppendResult = native_ir_append_load_for_function(
        stored.program, 0, 0, 0, index_id
    )
    mut loaded_id: i64 = loaded.value_id
    mut returned: NativeIRAppendResult = native_ir_append_instruction_for_function(
        loaded.program, 0, 0, 1, 0, loaded_id, -1, -1
    )
    return returned.program

fn memory_builder_status() -> i64:
    mut function: NativeIRAppendResult = native_ir_append_function(
        native_ir_empty(), 0, 1
    )
    mut result_type: NativeIRAppendResult = native_ir_set_function_result_type(
        function.program, 0, 0
    )
    mut block: NativeIRAppendResult = native_ir_append_block_for_function(
        result_type.program, 0, 0, 1
    )
    mut memory: NativeIRAppendResult = native_ir_append_memory(
        block.program, 0, 0, 2
    )
    mut memory_count: i64 = i64_vector_len(&memory.program.memory_ids)
    mut status: i64 = native_ir_trit_to_i64(memory.accepted == 1)
    status = status * 2 + native_ir_trit_to_i64(memory_count == 1)
    mut index: NativeIRAppendResult = append_i64_value(memory.program, 0, 1)
    mut index_id: i64 = index.value_id
    mut index_type_id: i64 = native_ir_value_type_id(
        &index.program.value_ids, &index.program.value_type_ids, index_id
    )
    status = status * 2 + native_ir_trit_to_i64(index.accepted == 1)
    status = status * 2 + native_ir_trit_to_i64(index_id == 0)
    status = status * 2 + native_ir_trit_to_i64(index_type_id == 0)
    mut value: NativeIRAppendResult = append_i64_value(index.program, 0, 77)
    mut value_id: i64 = value.value_id
    mut value_type_id: i64 = native_ir_value_type_id(
        &value.program.value_ids, &value.program.value_type_ids, value_id
    )
    status = status * 2 + native_ir_trit_to_i64(value.accepted == 1)
    status = status * 2 + native_ir_trit_to_i64(value_id == 1)
    status = status * 2 + native_ir_trit_to_i64(value_type_id == 0)
    mut memory_index: i64 = native_ir_memory_index(&value.program.memory_ids, 0)
    status = status * 2 + native_ir_trit_to_i64(memory_index == 0)
    mut core_store: NativeIRAppendResult = native_ir_append_instruction_core_for_function(
        value.program, 0, 0, 5, 0, index_id, value_id, -1, 0
    )
    mut core_value_count: i64 = i64_vector_len(&core_store.program.value_ids)
    status = status * 2 + native_ir_trit_to_i64(core_store.accepted == 1)
    status = status * 2 + native_ir_trit_to_i64(core_value_count == 2)
    return status

fn memory_contract_probe() -> i64:
    mut valid: NativeIR = valid_memory_program()
    mut valid_value_count: i64 = i64_vector_len(&valid.value_ids)
    mut verified: NativeIRVerifiedResult = verify_program(valid)
    mut score: i64 = native_ir_trit_to_i64(
        verified.verification.accepted == 1
    )
    score = score * 2 + native_ir_trit_to_i64(
        verified.verification.digest_before == verified.verification.digest_after
    )
    score = score * 2 + native_ir_trit_to_i64(
        valid_value_count == 3
    )

    mut invalid_id: NativeIRAppendResult = native_ir_append_load_for_function(
        memory_prefix(), 0, 0, 99, 0
    )
    score = score * 2 + native_ir_trit_to_i64(invalid_id.accepted == 0)

    mut invalid_store: NativeIRAppendResult = native_ir_append_store_for_function(
        memory_prefix(), 0, 0, 0, 0, 1
    )
    score = score * 2 + native_ir_trit_to_i64(invalid_store.accepted == 0)

    mut bad_metadata: NativeIR = valid_memory_program()
    discard i64_vector_set(&mut bad_metadata.memory_lengths, 0, 0)
    mut metadata_result: NativeIRVerifiedResult = verify_program(bad_metadata)
    score = score * 2 + native_ir_trit_to_i64(
        metadata_result.verification.accepted == 0
    )

    mut bad_store_type: NativeIR = valid_memory_program()
    discard i64_vector_set(&mut bad_store_type.value_type_ids, 1, 1)
    mut store_result: NativeIRVerifiedResult = verify_program(bad_store_type)
    score = score * 2 + native_ir_trit_to_i64(
        store_result.verification.accepted == 0
    )

    mut bad_load_type: NativeIR = valid_memory_program()
    mut last_value_type_index: i64 = i64_vector_len(&bad_load_type.value_type_ids) - 1
    discard i64_vector_set(&mut bad_load_type.value_type_ids, last_value_type_index, 1)
    mut load_result: NativeIRVerifiedResult = verify_program(bad_load_type)
    score = score * 2 + native_ir_trit_to_i64(
        load_result.verification.accepted == 0
    )
    return score * 10000 + memory_builder_status()

fn main() -> i64:
    return memory_contract_probe()
"""

    observed = run_source(verifier + "\n" + probe)
    assert observed == 2552047, f"memory verifier/builder score={observed}"

    for case in (4, 5):
        source = verifier + f"\nfn main() -> i64:\n    return verifier_case({case})\n"
        hosted = run_source(source)
        assert hosted // 1_000_000_000 == 1, (case, hosted)
        assert (hosted % 1_000_000_000) // 100_000_000 == 1, (case, hosted)


def test_native_ir_typed_vector_reference_builder_and_verifier_contracts() -> None:
    repository = Path(__file__).parents[1]
    verifier = (repository / "selfhost/substrate/verifier_kernel.s3").read_text(
        encoding="utf-8"
    )
    probe = r"""
fn append_i64(program: NativeIR, function_id: i64, block_id: i64, value: i64) -> NativeIRAppendResult:
    return native_ir_append_typed_instruction_for_function(
        program, function_id, block_id, 0, value, -1, -1, native_ir_type_i64()
    )

fn valid_vector_reference_program() -> NativeIR:
    mut vector_type: NativeIRAppendResult = native_ir_intern_composite_type(
        native_ir_empty(), 2, native_ir_type_i64(), 0, -1
    )
    mut vector_type_id: i64 = vector_type.value_id
    mut function: NativeIRAppendResult = native_ir_append_function(
        vector_type.program, 0, 1
    )
    mut result_type: NativeIRAppendResult = native_ir_set_function_result_type(
        function.program, 0, native_ir_type_i64()
    )
    mut block: NativeIRAppendResult = native_ir_append_block_for_function(
        result_type.program, 0, 0, 1
    )
    mut parameter: NativeIRAppendResult = native_ir_append_typed_parameter(
        block.program, 0, 0, vector_type_id
    )
    mut parameter_value_id: i64 = parameter.value_id
    mut reference: NativeIRAppendResult = native_ir_append_reference_for_function(
        parameter.program, 0, 0, parameter_value_id, vector_type_id, 1
    )
    mut scalar: NativeIRAppendResult = append_i64(
        reference.program, 0, 0, 0
    )
    mut scalar_value_id: i64 = scalar.value_id
    mut returned: NativeIRAppendResult = native_ir_append_instruction_for_function(
        scalar.program, 0, 0, 1, 0, scalar_value_id, -1, -1
    )
    return returned.program

fn vector_reference_contract_probe() -> i64:
    mut valid: NativeIR = valid_vector_reference_program()
    mut reference_result_id: i64 = i64_vector_get(&valid.result_value_ids, 0)
    mut reference_type_id: i64 = native_ir_value_type_id(
        &valid.value_ids, &valid.value_type_ids, reference_result_id
    )
    mut reference_type_kind: i64 = i64_vector_get(&valid.type_kinds, reference_type_id)
    mut verified: NativeIRVerifiedResult = verify_program(valid)
    mut score: i64 = native_ir_trit_to_i64(verified.verification.accepted == 1)
    score = score * 2 + native_ir_trit_to_i64(
        verified.verification.digest_before == verified.verification.digest_after
    )
    score = score * 2 + native_ir_trit_to_i64(reference_type_kind == 3)
    mut invalid_flags: NativeIR = valid_vector_reference_program()
    discard i64_vector_set(&mut invalid_flags.instruction_reference_flags, 0, 2)
    mut invalid_verified: NativeIRVerifiedResult = verify_program(invalid_flags)
    score = score * 2 + native_ir_trit_to_i64(
        invalid_verified.verification.accepted == 0
    )
    return score

fn main() -> i64:
    return vector_reference_contract_probe()
"""

    assert run_source(verifier + "\n" + probe) == 15
